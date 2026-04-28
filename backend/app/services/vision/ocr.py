import base64
import io
import logging
from abc import ABC, abstractmethod

import httpx
from PIL import Image
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_VISION_ANNOTATE_URL = "https://vision.googleapis.com/v1/images:annotate"
MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"


class OCRResult(BaseModel):
    text: str
    confidence_avg: float | None = None
    needs_fallback: bool = False
    provider: str
    error_message: str | None = None


class OCRProvider(ABC):
    @abstractmethod
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        """Extrai texto manuscrito/digitalizado de uma imagem."""


class DisabledOCRProvider(OCRProvider):
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(
            text="",
            confidence_avg=None,
            needs_fallback=True,
            provider="disabled",
            error_message="OCR desativado.",
        )


class GoogleVisionOCRProvider(OCRProvider):
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        if not settings.GOOGLE_VISION_API_KEY:
            logger.warning("GOOGLE_VISION_API_KEY não configurada; OCR ficará vazio.")
            return OCRResult(text="", confidence_avg=None, needs_fallback=True, provider="google_vision")

        payload = {
            "requests": [
                {
                    "image": {"content": base64.b64encode(image_bytes).decode("utf-8")},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                    "imageContext": {"languageHints": ["pt", "pt-BR"]},
                }
            ]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    GOOGLE_VISION_ANNOTATE_URL,
                    params={"key": settings.GOOGLE_VISION_API_KEY},
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                logger.warning("Google Vision OCR falhou com HTTP %s.", status_code)
                return OCRResult(
                    text="",
                    confidence_avg=None,
                    needs_fallback=True,
                    provider="google_vision",
                    error_message=f"Google Vision retornou HTTP {status_code}.",
                )
            except httpx.HTTPError as exc:
                logger.warning("Google Vision OCR indisponível: %s", exc.__class__.__name__)
                return OCRResult(
                    text="",
                    confidence_avg=None,
                    needs_fallback=True,
                    provider="google_vision",
                    error_message="Google Vision indisponível ou sem resposta.",
                )

        data = response.json()
        annotation = data.get("responses", [{}])[0].get("fullTextAnnotation") or {}
        text = str(annotation.get("text") or "").strip()
        confidence = _average_google_confidence(annotation)
        return OCRResult(
            text=text,
            confidence_avg=confidence,
            needs_fallback=_needs_fallback(text, confidence),
            provider="google_vision",
        )


class MistralOCRProvider(OCRProvider):
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        if not settings.MISTRAL_API_KEY:
            logger.warning("MISTRAL_API_KEY não configurada; OCR Mistral ficará indisponível.")
            return OCRResult(
                text="",
                confidence_avg=None,
                needs_fallback=True,
                provider="mistral_ocr",
                error_message="MISTRAL_API_KEY não configurada.",
            )

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": settings.MISTRAL_OCR_MODEL,
            "document": {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{b64}",
            },
            "confidence_scores_granularity": "page",
        }
        headers = {
            "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(MISTRAL_OCR_URL, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                logger.warning("Mistral OCR falhou com HTTP %s.", status_code)
                return OCRResult(
                    text="",
                    confidence_avg=None,
                    needs_fallback=True,
                    provider="mistral_ocr",
                    error_message=f"Mistral OCR retornou HTTP {status_code}.",
                )
            except httpx.HTTPError as exc:
                logger.warning("Mistral OCR indisponível: %s", exc.__class__.__name__)
                return OCRResult(
                    text="",
                    confidence_avg=None,
                    needs_fallback=True,
                    provider="mistral_ocr",
                    error_message="Mistral OCR indisponível ou sem resposta.",
                )

        try:
            data = response.json()
        except ValueError:
            return OCRResult(
                text="",
                confidence_avg=None,
                needs_fallback=True,
                provider="mistral_ocr",
                error_message="Mistral OCR retornou JSON inválido.",
            )

        pages = data.get("pages") or []
        text = _mistral_pages_text(pages)
        confidence = _average_mistral_confidence(pages)
        return OCRResult(
            text=text,
            confidence_avg=confidence,
            needs_fallback=_needs_fallback(text, confidence),
            provider="mistral_ocr",
        )


class FallbackOCRProvider(OCRProvider):
    def __init__(self, primary: OCRProvider, fallback: OCRProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        primary_result = await self.primary.extract_handwriting(image_bytes)
        if not primary_result.error_message and not primary_result.needs_fallback:
            return primary_result

        fallback_result = await self.fallback.extract_handwriting(image_bytes)
        if not fallback_result.error_message and not fallback_result.needs_fallback:
            fallback_result.provider = f"{primary_result.provider}->fallback:{fallback_result.provider}"
            return fallback_result

        if fallback_result.text.strip():
            fallback_result.provider = f"{primary_result.provider}->fallback:{fallback_result.provider}"
            return fallback_result

        messages = [
            msg
            for msg in (primary_result.error_message, fallback_result.error_message)
            if msg
        ]
        return OCRResult(
            text=primary_result.text or fallback_result.text,
            confidence_avg=primary_result.confidence_avg or fallback_result.confidence_avg,
            needs_fallback=True,
            provider=f"{primary_result.provider}->fallback:{fallback_result.provider}",
            error_message="; ".join(messages) if messages else "OCR principal e fallback sem texto confiável.",
        )


def get_ocr_provider() -> OCRProvider:
    provider_names = _parse_provider_names(settings.OCR_PROVIDER)
    providers = [_provider_for_name(name) for name in provider_names]
    providers = [provider for provider in providers if provider is not None]

    if not providers:
        return DisabledOCRProvider()

    provider = providers[0]
    for fallback in providers[1:]:
        provider = FallbackOCRProvider(provider, fallback)
    return provider


def _parse_provider_names(raw: str) -> list[str]:
    value = raw.strip().lower()
    if value in {"mistral_google", "mistral_google_vision"}:
        return ["mistral", "google_vision"]
    return [part.strip() for part in value.split(",") if part.strip()]


def _provider_for_name(name: str) -> OCRProvider | None:
    if name in {"mistral", "mistral_ocr"}:
        return MistralOCRProvider()
    if name == "google_vision":
        return GoogleVisionOCRProvider()
    if name == "disabled":
        return DisabledOCRProvider()
    logger.warning("OCR provider desconhecido: %s", name)
    return None


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _average_google_confidence(annotation: dict) -> float | None:
    confidences: list[float] = []
    for page in annotation.get("pages", []):
        for block in page.get("blocks", []):
            for paragraph in block.get("paragraphs", []):
                for word in paragraph.get("words", []):
                    confidence = word.get("confidence")
                    if isinstance(confidence, (int, float)):
                        confidences.append(float(confidence))
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _mistral_pages_text(pages: list[dict]) -> str:
    chunks = []
    for page in pages:
        markdown = str(page.get("markdown") or "").strip()
        if markdown:
            chunks.append(markdown)
    return "\n\n".join(chunks).strip()


def _average_mistral_confidence(pages: list[dict]) -> float | None:
    confidences: list[float] = []
    for page in pages:
        scores = page.get("confidence_scores") or {}
        confidence = scores.get("average_page_confidence_score")
        if isinstance(confidence, (int, float)):
            confidences.append(float(confidence))
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _needs_fallback(text: str, confidence: float | None) -> bool:
    words = [part for part in text.split() if part.strip()]
    if len(words) < 3:
        return True
    if confidence is not None and confidence < 0.70:
        return True
    return False
