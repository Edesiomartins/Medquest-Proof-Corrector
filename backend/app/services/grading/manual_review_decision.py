"""Regras determinísticas para marcar correções que exigem revisão humana."""

from __future__ import annotations

import math
import re
from app.services.llm.grading import SingleQuestionGrade
from app.services.vision.ocr import OCRResult


def _word_count(text: str) -> int:
    return len([p for p in re.split(r"\s+", text.strip()) if p])


def decide_manual_review(
    ocr_result: OCRResult,
    grade: SingleQuestionGrade,
    answer_text: str,
    max_score: float,
    *,
    json_parse_failed: bool = False,
    fallback_visual_ok: bool = False,
    alignment_failed: bool = False,
    score_parse_invalid: bool = False,
) -> tuple[bool, str | None]:
    """
    Retorna (requires_manual_review, manual_review_reason).

    Quando requires_manual_review é False, o caller deve definir final_score = ai_score.
    Quando True, final_score deve ser None até o professor revisar.
    """
    if alignment_failed:
        return True, "Falha no alinhamento/crop da página."

    if json_parse_failed or score_parse_invalid:
        return True, "Resposta da IA em formato inválido ou nota fora do intervalo."

    if grade.score < 0 or grade.score > max_score + 1e-6:
        return True, f"Nota fora do intervalo permitido (0–{max_score})."

    if not math.isfinite(grade.grading_confidence) or grade.grading_confidence < 0.70:
        return True, "Confiança da correção automática abaixo do limiar (0,70)."

    ocr_conf = ocr_result.confidence_avg
    if ocr_conf is not None and ocr_conf < 0.70:
        return True, "Confiança do OCR abaixo do limiar (0,70)."

    words = _word_count(answer_text)
    if not answer_text.strip() or words < 3:
        return True, "Texto extraído vazio ou muito curto (menos de 3 palavras)."

    if ocr_result.needs_fallback and not fallback_visual_ok:
        return True, "OCR instável (fallback necessário) e sem transcrição visual alternativa."

    if grade.score <= 0 and len(answer_text.strip()) > 200:
        return True, "Nota zero com resposta longa — possível erro de leitura ou interpretação."

    partial_or_zero = grade.score < max_score or grade.score <= 0
    if partial_or_zero:
        just = (grade.justification or "").strip()
        if not just:
            return True, "Justificativa obrigatória ausente para nota parcial ou zero."

    if grade.manual_review_required:
        return True, grade.manual_review_reason or "IA sinalizou revisão manual."

    return False, None
