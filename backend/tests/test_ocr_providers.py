import asyncio

import pytest

from app.core.config import settings
from app.services.vision.ocr import (
    FallbackOCRProvider,
    GoogleVisionOCRProvider,
    MistralOCRProvider,
    OCRProvider,
    OCRResult,
    _average_mistral_confidence,
    _mistral_pages_text,
    get_ocr_provider,
)


class _FakeProvider(OCRProvider):
    def __init__(self, result: OCRResult) -> None:
        self.result = result
        self.calls = 0

    async def extract_handwriting(self, image_bytes: bytes) -> OCRResult:
        self.calls += 1
        return self.result


def test_get_ocr_provider_uses_mistral_google_chain(monkeypatch):
    monkeypatch.setattr(settings, "OCR_PROVIDER", "mistral,google_vision")

    provider = get_ocr_provider()

    assert isinstance(provider, FallbackOCRProvider)
    assert isinstance(provider.primary, MistralOCRProvider)
    assert isinstance(provider.fallback, GoogleVisionOCRProvider)


def test_get_ocr_provider_keeps_legacy_mistral_google_alias(monkeypatch):
    monkeypatch.setattr(settings, "OCR_PROVIDER", "mistral_google")

    provider = get_ocr_provider()

    assert isinstance(provider, FallbackOCRProvider)
    assert isinstance(provider.primary, MistralOCRProvider)
    assert isinstance(provider.fallback, GoogleVisionOCRProvider)


def test_mistral_pages_text_and_confidence_parsing():
    pages = [
        {
            "markdown": "Resposta manuscrita 1",
            "confidence_scores": {"average_page_confidence_score": 0.9},
        },
        {
            "markdown": "Resposta manuscrita 2",
            "confidence_scores": {"average_page_confidence_score": 0.8},
        },
    ]

    assert _mistral_pages_text(pages) == "Resposta manuscrita 1\n\nResposta manuscrita 2"
    assert _average_mistral_confidence(pages) == pytest.approx(0.85)


def test_fallback_provider_uses_google_when_mistral_fails():
    primary = _FakeProvider(
        OCRResult(
            text="",
            needs_fallback=True,
            provider="mistral_ocr",
            error_message="Mistral OCR retornou HTTP 401.",
        )
    )
    fallback = _FakeProvider(
        OCRResult(
            text="resposta lida pelo google vision",
            confidence_avg=0.95,
            needs_fallback=False,
            provider="google_vision",
        )
    )

    result = asyncio.run(FallbackOCRProvider(primary, fallback).extract_handwriting(b"img"))

    assert primary.calls == 1
    assert fallback.calls == 1
    assert result.text == "resposta lida pelo google vision"
    assert result.provider == "mistral_ocr->fallback:google_vision"
    assert result.error_message is None
