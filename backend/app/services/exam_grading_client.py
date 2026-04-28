from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.services.json_utils import parse_json_safely

logger = logging.getLogger(__name__)

GRADING_PROMPT = """
Você é um professor de Medicina avaliando uma questão discursiva.

Você receberá:
1. Enunciado da questão.
2. Padrão de resposta ou rubrica.
3. Resposta transcrita do aluno.
4. Confiança da leitura visual.

Regras obrigatórias:
1. Corrija apenas com base no texto transcrito.
2. Não presuma que o aluno escreveu algo que não aparece na transcrição.
3. Não invente conteúdo.
4. Não penalize ortografia se o conceito estiver correto.
5. Atribua nota proporcional aos conceitos essenciais presentes.
6. Se a resposta não responder ao conteúdo, atribua 0.
7. Se a resposta estiver em branco, classifique como sem_resposta.
8. Se a transcrição estiver ilegível, classifique como ilegivel.
9. Se reading_confidence for baixa, marque needs_human_review como true.
10. A justificativa deve ser objetiva, técnica e curta.
11. Retorne somente JSON válido.
12. Não use markdown.

Formato JSON obrigatório:
{
  "score": 0.0,
  "max_score": 1.0,
  "verdict": "correta|parcial|incorreta|sem_resposta|ilegivel",
  "justification": "",
  "missing_concepts": [],
  "detected_concepts": [],
  "needs_human_review": false,
  "review_reason": ""
}
"""


class OpenRouterGradingError(RuntimeError):
    pass


def grade_discursive_answer(
    question: dict,
    rubric: dict,
    student_answer: str,
    reading_confidence: str = "media",
) -> dict:
    if not settings.OPENROUTER_API_KEY:
        raise OpenRouterGradingError("OPENROUTER_API_KEY não configurada.")

    primary = str(question.get("text_model") or rubric.get("text_model") or settings.OPENROUTER_TEXT_MODEL).strip()
    models = _model_candidates(primary)
    prompt = _build_prompt(question, rubric, student_answer, reading_confidence)
    errors: list[str] = []

    for index, model in enumerate(models):
        started = time.perf_counter()
        fallback_used = index > 0
        try:
            raw = _call_openrouter_text(model=model, prompt=prompt)
            parsed = _load_json_object(raw)
            if parsed.get("status") == "error":
                raise OpenRouterGradingError(str(parsed.get("error") or "invalid_json"))
            normalized = _normalize_grading_response(parsed, question, rubric, raw)
            normalized["model_used"] = model
            normalized["fallback_used"] = fallback_used
            logger.info(
                "OpenRouter grading succeeded",
                extra={
                    "model": model,
                    "question_number": normalized.get("question_number"),
                    "fallback_used": fallback_used,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                },
            )
            return normalized
        except Exception as exc:
            errors.append(f"{model}: {exc}")
            logger.warning(
                "OpenRouter grading failed",
                extra={
                    "model": model,
                    "question_number": question.get("number"),
                    "fallback_used": fallback_used,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "error": str(exc),
                },
            )

    raise OpenRouterGradingError("Falha em todos os modelos textuais: " + " | ".join(errors))


def grade_page_answers(extracted_page: dict, rubric: dict) -> dict:
    graded_questions = []
    for question in extracted_page.get("questions") or []:
        qnum = int(question.get("number") or 0)
        question_rubric = _rubric_for_question(rubric, qnum)
        if not question_rubric:
            graded_questions.append({**question, "grade": _missing_rubric_grade(question)})
            continue
        grade = grade_discursive_answer(
            question,
            question_rubric,
            question.get("answer_transcription") or "",
            reading_confidence=question.get("reading_confidence") or "media",
        )
        graded_questions.append({**question, "grade": grade})
    return {**extracted_page, "questions": graded_questions}


def _call_openrouter_text(model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": GRADING_PROMPT.strip()},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=_headers())
    logger.info("OpenRouter grading HTTP status", extra={"model": model, "status_code": response.status_code})
    if response.status_code >= 400:
        raise OpenRouterGradingError(f"HTTP {response.status_code}: {response.text[:500]}")
    return _extract_message_content(response.json())


def _build_prompt(question: dict, rubric: dict, student_answer: str, reading_confidence: str) -> str:
    payload = {
        "question_number": question.get("number") or question.get("question_number"),
        "question_prompt": question.get("prompt") or question.get("prompt_detected") or "",
        "reading_confidence": reading_confidence or question.get("reading_confidence") or "media",
        "student_answer": student_answer or "",
        "rubric": rubric or {},
    }
    return (
        "Corrija a resposta abaixo e retorne apenas o JSON solicitado.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _normalize_grading_response(parsed: dict, question: dict, rubric: dict, raw: str) -> dict:
    qnum = _to_int(question.get("number") or question.get("question_number"), 0)
    max_score = _to_float(
        parsed.get("max_score")
        or question.get("max_score")
        or rubric.get("max_score")
        or rubric.get("valor")
        or 1.0,
        1.0,
    )
    score = _to_float(parsed.get("score"), 0.0)
    score = max(0.0, min(score, max_score))
    confidence = str(question.get("reading_confidence") or "").lower()
    answer = str(question.get("answer_transcription") or "").strip()
    needs_review = (
        bool(parsed.get("needs_human_review", False))
        or confidence == "baixa"
        or answer.count("[ilegível]") + answer.count("[ilegivel]") >= 2
    )
    verdict = _normalize_verdict(parsed.get("verdict"), answer, confidence)

    return {
        "question_number": qnum,
        "score": score,
        "max_score": max_score,
        "verdict": verdict,
        "justification": str(parsed.get("justification") or ""),
        "missing_concepts": _list_of_strings(parsed.get("missing_concepts")),
        "detected_concepts": _list_of_strings(parsed.get("detected_concepts")),
        "needs_human_review": needs_review,
        "review_reason": str(
            parsed.get("review_reason")
            or ("Leitura visual com baixa confiança." if confidence == "baixa" else "")
        ),
        "raw_model_output": raw,
    }


def _normalize_verdict(value: Any, answer: str, confidence: str) -> str:
    text = str(value or "").strip().lower()
    allowed = {"correta", "parcial", "incorreta", "sem_resposta", "ilegivel"}
    if text in allowed:
        return text
    if not answer:
        return "sem_resposta"
    if confidence == "baixa" and ("[ilegível]" in answer or "[ilegivel]" in answer):
        return "ilegivel"
    return "incorreta"


def _model_candidates(primary: str) -> list[str]:
    candidates = [primary or settings.OPENROUTER_TEXT_MODEL, *_split_csv(settings.OPENROUTER_TEXT_FALLBACKS)]
    clean: list[str] = []
    for model in candidates:
        model = model.strip()
        if model and model not in clean:
            clean.append(model)
    return clean or ["openai/gpt-oss-120b"]


def _headers() -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if settings.OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = settings.OPENROUTER_HTTP_REFERER
    if settings.OPENROUTER_APP_TITLE:
        headers["X-OpenRouter-Title"] = settings.OPENROUTER_APP_TITLE
        headers["X-Title"] = settings.OPENROUTER_APP_TITLE
    return headers


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise OpenRouterGradingError("Resposta sem choices.")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str):
        return _strip_markdown_json(content)
    if isinstance(content, list):
        return _strip_markdown_json("\n".join(item.get("text", "") for item in content if isinstance(item, dict)))
    raise OpenRouterGradingError("Resposta sem conteúdo textual.")


def _load_json_object(raw: str) -> dict:
    return parse_json_safely(raw)


def _rubric_for_question(rubric: dict, number: int) -> dict | None:
    if not rubric:
        return None
    if "free_text_rubric" in rubric:
        return rubric
    if isinstance(rubric.get("questions"), list):
        for item in rubric["questions"]:
            if isinstance(item, dict) and int(item.get("number") or item.get("question_number") or 0) == number:
                return item
    value = rubric.get(str(number)) or rubric.get(number)
    return value if isinstance(value, dict) else None


def _missing_rubric_grade(question: dict) -> dict:
    confidence = str(question.get("reading_confidence") or "media")
    return {
        "question_number": int(question.get("number") or 0),
        "score": None,
        "max_score": None,
        "verdict": "sem_rubrica",
        "justification": "Rubrica não fornecida para esta questão.",
        "detected_concepts": [],
        "missing_concepts": [],
        "needs_human_review": confidence == "baixa",
        "review_reason": "Leitura visual com baixa confiança." if confidence == "baixa" else "",
    }


def _strip_markdown_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]
