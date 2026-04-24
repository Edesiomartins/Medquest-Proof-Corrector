import json
import logging

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
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


class PageGradingResult(BaseModel):
    grades: list[QuestionGrade]
    total_score: float
    ocr_text: str


class TextGradingService:
    @staticmethod
    async def grade_text(
        ocr_text: str,
        questions: list[QuestionSpec],
        model: str = VISION_MODEL,
        timeout: float = 60.0,
    ) -> PageGradingResult:
        if not settings.OPENROUTER_API_KEY:
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
        parsed = await _call_openrouter(payload, timeout=timeout)
        return _parse_grading_response(parsed, questions, fallback_ocr_text=ocr_text)


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


async def _call_openrouter(payload: dict, timeout: float) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://medquest-proof-corrector.app",
        "X-Title": "Medquest Proof Corrector",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    content: str = data["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(content)


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
    async def grade_page(
        image_bytes: bytes,
        questions: list[QuestionSpec],
        model: str = VISION_MODEL,
        timeout: float = 90.0,
    ) -> PageGradingResult:
        if not settings.OPENROUTER_API_KEY:
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
            parsed = await _call_openrouter(payload, timeout=timeout)
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
