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


class OCRResult(BaseModel):
    text: str
    confidence_avg: float | None = None
    needs_fallback: bool = False
    provider: str


class OCRProvider(ABC):
    @abstractmethod
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        """Extrai texto manuscrito/digitalizado de uma imagem."""


class DisabledOCRProvider(OCRProvider):
    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(text="", confidence_avg=None, needs_fallback=True, provider="disabled")


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
            response = await client.post(
                GOOGLE_VISION_ANNOTATE_URL,
                params={"key": settings.GOOGLE_VISION_API_KEY},
                json=payload,
            )
            response.raise_for_status()

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


def get_ocr_provider() -> OCRProvider:
    if settings.OCR_PROVIDER.lower() == "google_vision":
        return GoogleVisionOCRProvider()
    return DisabledOCRProvider()


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


def _needs_fallback(text: str, confidence: float | None) -> bool:
    words = [part for part in text.split() if part.strip()]
    if len(words) < 3:
        return True
    if confidence is not None and confidence < 0.70:
        return True
    return False
