"""Testes das regras determinísticas de revisão manual."""

from app.services.grading.manual_review_decision import decide_manual_review
from app.services.llm.grading import SingleQuestionGrade
from app.services.vision.ocr import OCRResult


def _ocr(**kwargs) -> OCRResult:
    base = dict(text="", confidence_avg=None, needs_fallback=False, provider="test")
    base.update(kwargs)
    return OCRResult(**base)


def _grade(**kwargs) -> SingleQuestionGrade:
    base = dict(
        question_number=1,
        score=1.0,
        justification="ok",
        criteria_met=[],
        criteria_missing=[],
        grading_confidence=0.95,
        manual_review_required=False,
        manual_review_reason=None,
    )
    base.update(kwargs)
    return SingleQuestionGrade(**base)


def test_auto_high_confidence():
    ocr = _ocr(text="resposta com mais de tres palavras aqui", confidence_avg=0.95, needs_fallback=False)
    g = _grade(score=1.0)
    need, reason = decide_manual_review(ocr, g, ocr.text, 1.0)
    assert need is False
    assert reason is None


def test_empty_ocr():
    ocr = _ocr(text="  ", confidence_avg=0.99)
    g = _grade(score=0.0, justification="vazio")
    need, reason = decide_manual_review(ocr, g, ocr.text, 1.0)
    assert need is True
    assert reason is not None


def test_low_ocr_confidence():
    ocr = _ocr(text="uma duas tres quatro", confidence_avg=0.5)
    g = _grade(score=0.75)
    need, _ = decide_manual_review(ocr, g, ocr.text, 1.0)
    assert need is True


def test_zero_long_answer():
    text = "x" * 201
    ocr = _ocr(text=text, confidence_avg=0.95, needs_fallback=False)
    g = _grade(score=0.0, justification="errado")
    need, _ = decide_manual_review(ocr, g, text, 1.0)
    assert need is True


def test_invalid_json_flag():
    ocr = _ocr(text="uma duas tres", confidence_avg=0.95)
    g = _grade(score=0.5, justification="parcial")
    need, _ = decide_manual_review(
        ocr, g, ocr.text, 1.0, json_parse_failed=True, score_parse_invalid=True
    )
    assert need is True
