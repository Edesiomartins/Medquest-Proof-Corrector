from __future__ import annotations

import base64
import json
import logging
import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.services.json_utils import parse_json_safely

logger = logging.getLogger(__name__)

VISION_EXTRACTION_PROMPT = """
Você é um especialista em leitura visual de provas manuscritas de estudantes de Medicina.

Sua tarefa é analisar a imagem da folha de respostas e extrair fielmente as respostas manuscritas do aluno.

Regras obrigatórias:
1. Extraia apenas o texto manuscrito pelo aluno nas áreas de resposta.
2. Não traduza o texto.
3. Não corrija português.
4. Não melhore a resposta.
5. Não complete lacunas.
6. Não invente termos técnicos.
7. Preserve frases informais, rasuras e anotações relevantes.
8. Se uma palavra estiver duvidosa, use [?].
9. Se um trecho estiver ilegível, use [ilegível].
10. Identifique nome, matrícula, turma e número das questões quando estiverem visíveis.
11. Se houver anotação fora da área principal da resposta, registre em reading_notes.
12. Se o aluno escreveu "não sei", "não faço ideia" ou equivalente, preserve exatamente.
13. Retorne somente JSON válido.
14. Não use markdown.
15. Não inclua explicações fora do JSON.

Classifique reading_confidence assim:
- alta: texto claramente legível;
- media: pequenos trechos duvidosos;
- baixa: muitos trechos ilegíveis.

Formato JSON obrigatório:
{
  "student": {
    "name": "",
    "registration": "",
    "class": ""
  },
  "page_number": 1,
  "questions": [
    {
      "number": 1,
      "prompt_detected": "",
      "answer_transcription": "",
      "reading_confidence": "alta|media|baixa",
      "reading_notes": "",
      "has_answer": true
    }
  ]
}
"""


class OpenRouterVisionError(RuntimeError):
    pass


def extract_answers_from_page_image(
    image_path: str,
    page_number: int | None = None,
    context: dict | None = None,
) -> dict:
    """
    Envia a página ou recorte para um modelo com visão via OpenRouter e retorna JSON normalizado.
    """
    if not settings.OPENROUTER_API_KEY:
        raise OpenRouterVisionError("OPENROUTER_API_KEY não configurada.")

    context = dict(context or {})
    if page_number is not None:
        context["page_number"] = page_number
    requested_model = str(context.get("vision_model") or settings.OPENROUTER_VISION_MODEL).strip()
    models = _vision_model_candidates(requested_model)
    data_url = encode_image_to_data_url(image_path)
    prompt = _build_prompt(context)
    errors: list[str] = []

    for index, model in enumerate(models):
        started = time.perf_counter()
        fallback_used = index > 0
        try:
            raw = _call_openrouter_vision(model=model, prompt=prompt, data_url=data_url)
            parsed = _load_json_object(raw)
            if parsed.get("status") == "error":
                raise OpenRouterVisionError(str(parsed.get("error") or "invalid_json"))
            normalized = _normalize_vision_response(parsed, context, raw)
            normalized["model_used"] = model
            normalized["fallback_used"] = fallback_used
            logger.info(
                "OpenRouter vision extraction succeeded",
                extra={
                    "model": model,
                    "page": normalized.get("page_number"),
                    "fallback_used": fallback_used,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                },
            )
            return normalized
        except Exception as exc:
            elapsed = time.perf_counter() - started
            message = f"{model}: {exc}"
            errors.append(message)
            logger.warning(
                "OpenRouter vision extraction failed",
                extra={
                    "model": model,
                    "page": context.get("page_number"),
                    "fallback_used": fallback_used,
                    "elapsed_seconds": round(elapsed, 3),
                    "error": str(exc),
                },
            )

    raise OpenRouterVisionError("Falha em todos os modelos de visão: " + " | ".join(errors))


extract_handwritten_answers_from_image = extract_answers_from_page_image


def _call_openrouter_vision(model: str, prompt: str, data_url: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT_SECONDS) as client:
        response = client.post(url, json=payload, headers=_headers())
    logger.info("OpenRouter vision HTTP status", extra={"model": model, "status_code": response.status_code})
    if response.status_code >= 400:
        raise OpenRouterVisionError(f"HTTP {response.status_code}: {response.text[:500]}")
    return _extract_message_content(response.json())


def _build_prompt(context: dict) -> str:
    parts = [VISION_EXTRACTION_PROMPT.strip()]
    if context:
        safe_context = {
            key: value
            for key, value in context.items()
            if key not in {"vision_model", "image_path"} and value is not None
        }
        if safe_context:
            parts.append(
                "Contexto adicional fornecido pelo sistema:\n"
                + json.dumps(safe_context, ensure_ascii=False, indent=2)
            )
    parts.append(
        "Instrução final: retorne exclusivamente um objeto JSON válido. "
        "Não use markdown, comentários ou texto fora do JSON."
    )
    return "\n\n".join(parts)


def _vision_model_candidates(primary: str) -> list[str]:
    text_model = settings.OPENROUTER_TEXT_MODEL.strip()
    fallbacks = _split_csv(settings.OPENROUTER_VISION_FALLBACKS)
    candidates = [primary or settings.OPENROUTER_VISION_MODEL, *fallbacks]
    clean: list[str] = []
    for model in candidates:
        model = model.strip()
        if not model or model in clean:
            continue
        if model == text_model or model == "openai/gpt-oss-120b":
            logger.warning("Modelo textual ignorado na etapa de visão: %s", model)
            continue
        clean.append(model)
    if not clean:
        clean.append("google/gemini-2.5-flash")
    return clean


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


def encode_image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        mime = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise OpenRouterVisionError("Resposta sem choices.")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str):
        return _strip_markdown_json(content)
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return _strip_markdown_json("\n".join(text_parts))
    raise OpenRouterVisionError("Resposta sem conteúdo textual.")


def _load_json_object(raw: str) -> dict:
    return parse_json_safely(raw)


def _normalize_vision_response(parsed: dict, context: dict, raw: str) -> dict:
    student = parsed.get("student") if isinstance(parsed.get("student"), dict) else {}
    questions = parsed.get("questions") if isinstance(parsed.get("questions"), list) else []
    normalized_questions = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        normalized_questions.append(
            {
                "number": _to_int(item.get("number"), default=len(normalized_questions) + 1),
                "prompt_detected": str(item.get("prompt_detected") or ""),
                "answer_transcription": str(item.get("answer_transcription") or ""),
                "reading_confidence": _normalize_confidence(item.get("reading_confidence")),
                "reading_notes": str(item.get("reading_notes") or ""),
                "has_answer": bool(item.get("has_answer", bool(item.get("answer_transcription")))),
            }
        )

    return {
        "student": {
            "name": str(student.get("name") or ""),
            "registration": str(student.get("registration") or ""),
            "class": str(student.get("class") or ""),
        },
        "page_number": _to_int(
            parsed.get("page_number") or parsed.get("page_index"),
            default=_to_int(context.get("page_number") or context.get("page_index"), 1),
        ),
        "questions": normalized_questions,
        "raw_model_output": raw,
    }


def _normalize_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"alta", "media", "baixa"}:
        return text
    if text in {"média", "medio", "médio"}:
        return "media"
    return "baixa"


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _strip_markdown_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]
