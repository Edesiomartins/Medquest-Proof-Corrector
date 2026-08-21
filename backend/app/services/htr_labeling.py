"""Colhe pares rotulados de leitura manuscrita a partir da revisão humana.

Item 13 do docs/HTR_PLANO_EXECUCAO.md. Ver `app/models/htr_label.py` para o
porquê.

Duas regras de qualidade valem mais que o resto deste módulo:

1. **Confirmação conta tanto quanto correção.** Se só as correções forem
   gravadas, o conjunto fica enviesado: todo exemplo será um erro do modelo, e
   qualquer métrica ou ajuste fino derivado dele enxergará um sistema muito pior
   do que ele é. Por isso `record_review` grava também quando o professor aprova
   a leitura sem mudar nada.
2. **Sem recorte, sem rótulo.** O par só vale se a imagem existir para ser
   olhada de novo. Um rótulo sem recorte é uma linha de texto sem contexto.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.htr_label import HtrLabel
from app.services.vision.htr_metrics import character_error_rate, normalize_text

logger = logging.getLogger(__name__)


def record_review(
    db: Session,
    *,
    question_score,
    human_transcription: str,
    reviewer_id: UUID | None = None,
    exam_id: UUID | None = None,
    student_id: UUID | None = None,
    vision_model: str | None = None,
) -> HtrLabel | None:
    """Grava o par (recorte, leitura do modelo, leitura humana).

    Devolve None — sem gravar — quando não há recorte associado: sem a imagem o
    par não é auditável nem treinável.

    Não faz commit: quem chama decide o limite da transação, que costuma incluir
    a atualização da própria nota.
    """
    crop_path = getattr(question_score, "answer_crop_path", None)
    if not crop_path:
        logger.debug(
            "QuestionScore %s sem recorte; par de rotulagem não gravado.",
            getattr(question_score, "id", None),
        )
        return None

    model_text = str(getattr(question_score, "extracted_answer_text", "") or "")
    human_text = str(human_transcription or "")

    # Caixa vazia confirmada como vazia também é rótulo válido — é justamente o
    # caso que mede alucinação.
    if not normalize_text(human_text) and not normalize_text(model_text):
        was_correct = True
        cer = 0.0
    else:
        was_correct = normalize_text(model_text) == normalize_text(human_text)
        cer = character_error_rate(human_text, model_text)

    label = HtrLabel(
        question_score_id=getattr(question_score, "id", None),
        exam_id=exam_id,
        student_id=student_id,
        question_number=getattr(question_score, "source_question_number", None),
        page_number=getattr(question_score, "source_page_number", None),
        answer_crop_path=str(crop_path),
        model_transcription=model_text,
        human_transcription=human_text,
        character_error_rate=cer,
        was_correct=was_correct,
        reading_confidence=_confidence_label(getattr(question_score, "transcription_confidence", None)),
        ocr_provider=getattr(question_score, "ocr_provider", None),
        vision_model=vision_model,
        reviewer_id=reviewer_id,
    )
    db.add(label)
    logger.info(
        "Par de rotulagem gravado: questão %s, CER %.3f, %s.",
        label.question_number,
        cer,
        "leitura confirmada" if was_correct else "leitura corrigida",
    )
    return label


def _confidence_label(value) -> str | None:
    """Converte a confiança numérica gravada na nota para o rótulo textual."""
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)[:16]
    if numeric >= 0.85:
        return "alta"
    if numeric >= 0.60:
        return "media"
    return "baixa"


def export_dataset(db: Session, *, exam_id: UUID | None = None, limit: int | None = None) -> list[dict]:
    """Exporta os pares no formato que `scripts/eval_htr.py` consome.

    Devolve dicionários prontos para virar `labels.jsonl`, com os estratos que
    dão para inferir automaticamente. Os eixos que dependem de olhar a folha —
    cursiva ligada, lápis, foto de celular — continuam sendo marcação manual;
    ver docs/HTR_EVAL_SET.md.
    """
    query = db.query(HtrLabel)
    if exam_id is not None:
        query = query.filter(HtrLabel.exam_id == exam_id)
    query = query.order_by(HtrLabel.created_at.desc())
    if limit:
        query = query.limit(limit)

    rows = []
    for label in query.all():
        strata = ["confirmada" if label.was_correct else "corrigida"]
        if not normalize_text(label.human_transcription or ""):
            strata.append("vazia")
        elif len(normalize_text(label.human_transcription).split()) <= 3:
            strata.append("curta")

        rows.append(
            {
                "crop": label.answer_crop_path,
                "reference": label.human_transcription or "",
                "strata": strata,
                "question": label.question_number,
                "model_transcription": label.model_transcription or "",
                "cer_at_review": label.character_error_rate,
            }
        )
    return rows
