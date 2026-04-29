import json
import logging
import math

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
VISION_MODEL = "anthropic/claude-sonnet-4"


class QuestionSpec(BaseModel):
    question_number: int
    question_text: str
    expected_answer: str
    max_score: float


class QuestionGrade(BaseModel):
    question_number: int
    score: float
    justification: str


class SingleQuestionGrade(BaseModel):
    question_number: int
    score: float = 0.0
    justification: str = ""
    criteria_met: list[str] = Field(default_factory=list)
    criteria_missing: list[str] = Field(default_factory=list)
    grading_confidence: float = 0.0
    manual_review_required: bool = False
    manual_review_reason: str | None = None


class PageGradingResult(BaseModel):
    grades: list[QuestionGrade]
    total_score: float
    ocr_text: str


class OpenRouterAuthError(RuntimeError):
    pass


class TextGradingService:
    @staticmethod
    async def grade_single_question(
        ocr_text: str,
        question: QuestionSpec,
        model: str = VISION_MODEL,
        timeout: float = 60.0,
    ) -> tuple[SingleQuestionGrade, bool]:
        """
        Corrige uma única questão a partir da transcrição daquele box.

        Retorna (nota, parse_ok). Se parse_ok for False, tratar como revisão manual obrigatória.
        """
        if not _has_openrouter_api_key():
            return SingleQuestionGrade(question_number=question.question_number), False

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SINGLE_QUESTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _SINGLE_QUESTION_USER_PROMPT.format(
                        question_number=question.question_number,
                        question_text=question.question_text,
                        expected_answer=question.expected_answer,
                        max_score=question.max_score,
                        ocr_text=ocr_text or "(vazio)",
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1536,
        }

        try:
            raw = await _call_openrouter_raw(payload, timeout=timeout)
            return _parse_single_question_json(raw, question)
        except json.JSONDecodeError as exc:
            logger.error("JSON inválido da LLM (questão %s): %s", question.question_number, exc)
            return _fallback_grade(question), False
        except Exception as exc:
            logger.exception("Falha na correção LLM: %s", exc)
            return _fallback_grade(question), False

    @staticmethod
    async def grade_text(
        ocr_text: str,
        questions: list[QuestionSpec],
        model: str = VISION_MODEL,
        timeout: float = 60.0,
    ) -> PageGradingResult:
        """Legado: múltiplas questões em um único texto (evitar em novos fluxos)."""
        if not _has_openrouter_api_key():
            return _zero_result(questions, ocr_text)

        if not ocr_text.strip():
            return _zero_result(questions, "")

        questions_text = _format_questions(questions)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _TEXT_GRADING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _TEXT_GRADING_USER_PROMPT.format(
                        questions_text=questions_text,
                        ocr_text=ocr_text,
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        try:
            parsed = await _call_openrouter_json(payload, timeout=timeout)
            return _parse_grading_response(parsed, questions, fallback_ocr_text=ocr_text)
        except json.JSONDecodeError:
            return _zero_result(questions, ocr_text)


_SINGLE_QUESTION_SYSTEM_PROMPT = """\
Você é uma professora universitária de medicina corrigindo UMA questão discursiva curta.

Sua função é CORRIGIR a resposta do aluno com base exclusivamente na transcrição OCR daquele box \
(não invente texto que não apareça na transcrição).

Regras:
- Corrija de acordo com o enunciado, o gabarito e a pontuação máxima informados.
- Aceite sinônimos e respostas semanticamente equivalentes ao gabarito.
- Não exija redação idêntica ao gabarito.
- Atribua nota parcial em incrementos de 0,25 entre 0 e a pontuação máxima.
- Se a transcrição estiver confusa ou ilegível, atribua baixa confiança (grading_confidence) \
e explique em manual_review_reason — mas NÃO peça revisão humana se a correção for evidente \
após interpretação razoável do texto.
- Se a correção estiver clara e o texto for interpretável, use manual_review_required=false.

Responda EXCLUSIVAMENTE com um único objeto JSON válido (sem markdown):
{
  "question_number": <int>,
  "score": <float>,
  "justification": "<string>",
  "criteria_met": ["<string>", ...],
  "criteria_missing": ["<string>", ...],
  "grading_confidence": <float entre 0 e 1>,
  "manual_review_required": <boolean>,
  "manual_review_reason": <string ou null>
}
"""


_SINGLE_QUESTION_USER_PROMPT = """\
## Questão {question_number} (máximo {max_score} pontos)

### Enunciado
{question_text}

### Gabarito / resposta esperada
{expected_answer}

### Transcrição OCR desta resposta (um único box)
{ocr_text}

Corrija apenas esta questão e produza o JSON solicitado.
"""


_SINGLE_QUESTION_VISUAL_SYSTEM_PROMPT = """\
Você é uma professora universitária de medicina corrigindo UMA questão discursiva curta.

Sua função é LER a resposta manuscrita diretamente na imagem enviada e CORRIGIR essa resposta \
de acordo com o enunciado, o gabarito e a pontuação máxima.

Regras:
- A imagem contém apenas o box de resposta do aluno para uma única questão.
- Use a imagem como fonte principal. A transcrição preliminar, quando fornecida, é apenas auxiliar e pode conter erros.
- Aceite sinônimos e respostas semanticamente equivalentes ao gabarito.
- Atribua nota parcial em incrementos de 0,25 entre 0 e a pontuação máxima.
- Se a escrita estiver ilegível ou não for possível inferir a resposta, use baixa confiança e explique.
- Não invente conteúdo que não consiga ler na imagem.

Responda EXCLUSIVAMENTE com um único objeto JSON válido (sem markdown):
{
  "question_number": <int>,
  "score": <float>,
  "justification": "<string>",
  "criteria_met": ["<string>", ...],
  "criteria_missing": ["<string>", ...],
  "grading_confidence": <float entre 0 e 1>,
  "manual_review_required": <boolean>,
  "manual_review_reason": <string ou null>
}
"""


_SINGLE_QUESTION_VISUAL_USER_PROMPT = """\
## Questão {question_number} (máximo {max_score} pontos)

### Enunciado
{question_text}

### Gabarito / resposta esperada
{expected_answer}

### Transcrição preliminar (pode estar errada)
{ocr_text}

Leia a resposta manuscrita na imagem anexada, corrija apenas esta questão e produza o JSON solicitado.
"""


_TEXT_GRADING_SYSTEM_PROMPT = """\
Você é um professor universitário de medicina rigoroso e justo.
Receba a transcrição OCR da resposta manuscrita do aluno e corrija cada questão.

Instruções:
1. Use apenas o texto OCR informado como resposta do aluno.
2. Compare com a resposta esperada (gabarito) fornecida.
3. Atribua uma nota de 0 até o valor máximo da questão, em incrementos de 0.25.
4. Se o texto OCR estiver vazio, ilegível ou não responder à questão, atribua 0.
5. Seja objetivo e não invente conteúdo que não esteja na transcrição.

Responda EXCLUSIVAMENTE com o JSON abaixo, sem markdown nem texto adicional:
{{
  "grades": [
    {{"question_number": 1, "score": 0.75, "justification": "..."}},
    ...
  ],
  "total_score": <soma das notas>,
  "ocr_text": "<texto OCR recebido>"
}}
"""


_TEXT_GRADING_USER_PROMPT = """\
## Questões e Gabarito

{questions_text}

## Transcrição OCR da prova do aluno

{ocr_text}

Corrija cada questão conforme o gabarito acima.
"""


def _encode_image(image_bytes: bytes) -> str:
    import base64

    return base64.b64encode(image_bytes).decode("utf-8")


def _format_questions(questions: list[QuestionSpec]) -> str:
    return "\n".join(
        f"**Questão {q.question_number}** (vale {q.max_score} pts)\n"
        f"Enunciado: {q.question_text}\n"
        f"Gabarito: {q.expected_answer}\n"
        for q in questions
    )


async def _call_openrouter_raw(payload: dict, timeout: float) -> str:
    api_key = _openrouter_api_key()
    if not api_key:
        raise OpenRouterAuthError("OPENROUTER_API_KEY não configurada.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if settings.OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = settings.OPENROUTER_HTTP_REFERER
    if settings.OPENROUTER_APP_TITLE:
        headers["X-OpenRouter-Title"] = settings.OPENROUTER_APP_TITLE
        headers["X-Title"] = settings.OPENROUTER_APP_TITLE

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        if resp.status_code == 401:
            message = _extract_openrouter_error(resp)
            raise OpenRouterAuthError(
                "OpenRouter retornou 401 Unauthorized. Verifique OPENROUTER_API_KEY "
                "(chave inválida, expirada, com aspas extras ou pertencente a outro ambiente). "
                f"Detalhe: {message}"
            )
        resp.raise_for_status()

    data = resp.json()
    content: str = data["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return content


async def _call_openrouter_json(payload: dict, timeout: float) -> dict:
    raw = await _call_openrouter_raw(payload, timeout=timeout)
    return json.loads(raw)


def _parse_single_question_json(
    raw: str,
    question: QuestionSpec,
) -> tuple[SingleQuestionGrade, bool]:
    try:
        data = _load_json_object(raw)
    except (json.JSONDecodeError, TypeError):
        return _fallback_grade(question), False
    if not isinstance(data, dict):
        return _fallback_grade(question), False
    qn = int(data.get("question_number", data.get("questao", question.question_number)))
    raw_score = data.get("score", data.get("nota", 0))
    score = float(raw_score)
    raw_max_score = data.get("max_score", data.get("nota_maxima", question.max_score))
    max_s = min(1.0, max(0.0, float(raw_max_score)))
    invalid = False
    if math.isnan(score) or score < -1e-6 or score > max_s + 1e-6:
        invalid = True
        score = max(0.0, min(score, max_s)) if math.isfinite(score) else 0.0

    score = max(0.0, min(float(score), max_s))
    score = round(score * 4) / 4

    gc = float(data.get("grading_confidence", 0))
    if math.isnan(gc):
        gc = 0.0
        invalid = True
    gc = max(0.0, min(gc, 1.0))

    raw_confidence = data.get("grading_confidence", data.get("confianca", gc))
    try:
        parsed_confidence = float(raw_confidence)
    except (TypeError, ValueError):
        parsed_confidence = gc
        invalid = True
    if math.isnan(parsed_confidence):
        parsed_confidence = 0.0
        invalid = True
    parsed_confidence = max(0.0, min(parsed_confidence, 1.0))

    grade = SingleQuestionGrade(
        question_number=qn,
        score=score,
        justification=str(data.get("justification", data.get("comentario", "")) or ""),
        criteria_met=list(data.get("criteria_met", data.get("criterios_atendidos")) or []),
        criteria_missing=list(data.get("criteria_missing", data.get("criterios_ausentes")) or []),
        grading_confidence=parsed_confidence,
        manual_review_required=bool(data.get("manual_review_required", data.get("revisao_necessaria", False))),
        manual_review_reason=data.get("manual_review_reason", data.get("motivo_revisao")),
    )
    return grade, not invalid


def _load_json_object(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(raw[start : end + 1])


def _fallback_grade(question: QuestionSpec) -> SingleQuestionGrade:
    return SingleQuestionGrade(
        question_number=question.question_number,
        score=0.0,
        justification="",
        grading_confidence=0.0,
        manual_review_required=True,
        manual_review_reason="Falha técnica ou JSON inválido na correção automática.",
    )


def _parse_grading_response(
    parsed: dict,
    questions: list[QuestionSpec],
    fallback_ocr_text: str = "",
) -> PageGradingResult:
    grades = []
    for g in parsed.get("grades", []):
        qnum = g.get("question_number", 0)
        spec = next((q for q in questions if q.question_number == qnum), None)
        max_s = spec.max_score if spec else 1.0
        score = min(float(g.get("score", 0)), max_s)
        score = max(0, round(score * 4) / 4)
        grades.append(QuestionGrade(
            question_number=qnum,
            score=score,
            justification=g.get("justification", ""),
        ))

    existing_question_numbers = {grade.question_number for grade in grades}
    for question in questions:
        if question.question_number not in existing_question_numbers:
            grades.append(QuestionGrade(
                question_number=question.question_number,
                score=0,
                justification="",
            ))

    grades.sort(key=lambda grade: grade.question_number)
    total = sum(g.score for g in grades)
    ocr_text = parsed.get("ocr_text", fallback_ocr_text)
    return PageGradingResult(grades=grades, total_score=total, ocr_text=ocr_text)


def _zero_result(questions: list[QuestionSpec], ocr_text: str = "") -> PageGradingResult:
    return PageGradingResult(
        grades=[
            QuestionGrade(question_number=q.question_number, score=0, justification="")
            for q in questions
        ],
        total_score=0,
        ocr_text=ocr_text,
    )


class VisionGradingService:
    @staticmethod
    async def grade_single_question_image(
        image_bytes: bytes,
        question: QuestionSpec,
        *,
        ocr_text: str = "",
        model: str = VISION_MODEL,
        timeout: float = 90.0,
    ) -> tuple[SingleQuestionGrade, bool]:
        """
        Corrige uma única questão lendo diretamente a imagem do box de resposta.

        Usado como fallback quando a leitura textual preliminar ou a correção baseada em texto falha.
        """
        if not _has_openrouter_api_key():
            return _fallback_grade(question), False

        b64 = _encode_image(image_bytes)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SINGLE_QUESTION_VISUAL_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": _SINGLE_QUESTION_VISUAL_USER_PROMPT.format(
                                question_number=question.question_number,
                                question_text=question.question_text,
                                expected_answer=question.expected_answer,
                                max_score=question.max_score,
                                ocr_text=ocr_text or "(sem transcrição confiável)",
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 1536,
        }

        try:
            raw = await _call_openrouter_raw(payload, timeout=timeout)
            return _parse_single_question_json(raw, question)
        except Exception as exc:
            logger.exception("Falha na correção visual LLM: %s", exc)
            return _fallback_grade(question), False

    @staticmethod
    async def grade_page(
        image_bytes: bytes,
        questions: list[QuestionSpec],
        model: str = VISION_MODEL,
        timeout: float = 90.0,
    ) -> PageGradingResult:
        if not _has_openrouter_api_key():
            raise RuntimeError("OPENROUTER_API_KEY não configurada.")

        questions_text = _format_questions(questions)

        b64 = _encode_image(image_bytes)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _USER_PROMPT.format(questions_text=questions_text)},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        try:
            parsed = await _call_openrouter_json(payload, timeout=timeout)
        except json.JSONDecodeError as exc:
            logger.error("LLM retornou JSON inválido: %s", exc)
            return PageGradingResult(
                grades=[
                    QuestionGrade(
                        question_number=q.question_number,
                        score=0,
                        justification="IA não retornou resposta válida. Revisão manual necessária.",
                    )
                    for q in questions
                ],
                total_score=0,
                ocr_text="",
            )

        return _parse_grading_response(parsed, questions)


_SYSTEM_PROMPT = """\
Você é um professor universitário de medicina rigoroso e justo.
Receba a imagem escaneada da prova manuscrita de um aluno e corrija cada questão.

Instruções:
1. Leia a resposta manuscrita do aluno na imagem para CADA questão.
2. Compare com a resposta esperada (gabarito) fornecida.
3. Atribua uma nota de 0 até o valor máximo da questão, em incrementos de 0.25.
   (Ex: se max_score=1.0, notas possíveis: 0, 0.25, 0.5, 0.75, 1.0)
4. Se a resposta estiver ilegível ou em branco, atribua 0.
5. Seja objetivo: a nota reflete o quanto a resposta atende ao gabarito.

Responda EXCLUSIVAMENTE com o JSON abaixo, sem markdown nem texto adicional:
{{
  "grades": [
    {{"question_number": 1, "score": 0.75, "justification": "..."}},
    ...
  ],
  "total_score": <soma das notas>,
  "ocr_text": "<transcrição completa do que o aluno escreveu, separando questões com Q1:, Q2:, etc.>"
}}
"""

_USER_PROMPT = """\
## Questões e Gabarito

{questions_text}

Analise a imagem da prova e corrija cada questão conforme o gabarito acima.
"""


def _openrouter_api_key() -> str:
    # Evita erro comum de chave com aspas/copiar-colar com espaços.
    return str(settings.OPENROUTER_API_KEY or "").strip().strip('"').strip("'")


def _has_openrouter_api_key() -> bool:
    return bool(_openrouter_api_key())


def _extract_openrouter_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return (response.text or "sem detalhe").strip()[:300]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("code") or "sem detalhe")
        if err is not None:
            return str(err)
        detail = data.get("message") or data.get("detail")
        if detail is not None:
            return str(detail)
    return str(data)[:300]
