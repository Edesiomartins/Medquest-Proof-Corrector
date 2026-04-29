"""Remove notas e resultados de aluno de um lote (reprocessamento / invalidação)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.grading import QuestionScore, StudentResult

logger = logging.getLogger(__name__)


def clear_batch_grading_results(db: Session, batch_id: UUID) -> int:
    """
    Apaga QuestionScore e StudentResult do batch. Idempotente.

    Retorna quantos StudentResult foram removidos.
    """
    result_ids = [
        rid
        for (rid,) in db.query(StudentResult.id)
        .filter(StudentResult.batch_id == batch_id)
        .all()
    ]
    n = len(result_ids)
    if n == 0:
        return 0

    db.query(QuestionScore).filter(
        QuestionScore.student_result_id.in_(result_ids)
    ).delete(synchronize_session=False)
    db.query(StudentResult).filter(StudentResult.id.in_(result_ids)).delete(
        synchronize_session=False
    )
    db.flush()
    return n
