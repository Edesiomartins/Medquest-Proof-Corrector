from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.visual_exam import VisualExamAnswer, VisualExamRun, VisualExamRunStatus
from app.services.visual_exam_pipeline import analyze_discursive_exam_pdf

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])

_MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


@router.post("/analyze-discursive-pdf", status_code=status.HTTP_200_OK)
async def analyze_discursive_pdf(
    file: UploadFile = File(...),
    rubric: str | None = Form(default=None),
    vision_model: str | None = Form(default=None),
    text_model: str | None = Form(default=None),
    process_pages: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")
    if file.content_type and file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=400, detail="O arquivo enviado não parece ser um PDF.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Arquivo PDF vazio.")
    if len(raw) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"PDF excede {settings.MAX_UPLOAD_MB} MB.")

    rubric_payload = _parse_optional_json_or_text(rubric)

    run_id = uuid.uuid4()
    run_dir = settings.UPLOAD_DIR.resolve() / "visual_exam_runs" / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = run_dir / _safe_pdf_name(file.filename)
    pdf_path.write_bytes(raw)

    run = VisualExamRun(
        id=run_id,
        user_id=current_user.id,
        filename=file.filename,
        status=VisualExamRunStatus.PROCESSING,
        vision_model_used=vision_model or settings.OPENROUTER_VISION_MODEL,
        text_model_used=text_model or settings.OPENROUTER_TEXT_MODEL,
    )
    db.add(run)
    db.commit()

    try:
        result = await run_in_threadpool(
            analyze_discursive_exam_pdf,
            str(pdf_path),
            rubric_payload,
            {
                "vision_model": vision_model,
                "text_model": text_model,
                "process_pages": process_pages,
            },
        )
        raw_students = result.pop("_raw_students", [])

        run.status = (
            VisualExamRunStatus.SUCCESS if result.get("status") == "success" else VisualExamRunStatus.FAILED
        )
        run.pages_processed = int(result.get("pages_processed") or 0)
        run.vision_model_used = result.get("vision_model_used") or run.vision_model_used
        run.text_model_used = result.get("text_model_used") or run.text_model_used
        if result.get("errors"):
            run.error = " | ".join(str(error) for error in result["errors"])

        _persist_visual_answers(db, run.id, raw_students or result.get("students") or [])
        db.commit()

        if result.get("status") != "success":
            raise HTTPException(status_code=500, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        run.status = VisualExamRunStatus.FAILED
        run.error = str(exc)
        db.add(run)
        db.commit()
        logger.exception("Falha ao analisar PDF discursivo por leitura visual.")
        raise HTTPException(status_code=500, detail=f"Falha ao analisar PDF discursivo: {exc}") from exc


def _persist_visual_answers(db: Session, run_id: uuid.UUID, students: list[dict]) -> None:
    for page in students:
        student = page.get("student") or {}
        raw_vision = page.get("raw_vision_json") or page
        for question in page.get("questions") or []:
            grade = question.get("grade") or {}
            raw_grade = question.get("raw_grading_json") or grade
            db.add(
                VisualExamAnswer(
                    run_id=run_id,
                    student_name=student.get("name") or None,
                    registration=student.get("registration") or None,
                    class_name=student.get("class") or None,
                    page_number=int(page.get("page") or raw_vision.get("page_number") or 0),
                    question_number=int(question.get("number") or 0),
                    prompt_detected=question.get("prompt_detected") or None,
                    answer_transcription=question.get("answer_transcription") or None,
                    reading_confidence=question.get("reading_confidence") or None,
                    reading_notes=question.get("reading_notes") or None,
                    score=grade.get("score") if isinstance(grade.get("score"), (int, float)) else None,
                    max_score=grade.get("max_score") if isinstance(grade.get("max_score"), (int, float)) else None,
                    verdict=grade.get("verdict") or None,
                    justification=grade.get("justification") or None,
                    detected_concepts_json=json.dumps(grade.get("detected_concepts") or [], ensure_ascii=False),
                    missing_concepts_json=json.dumps(grade.get("missing_concepts") or [], ensure_ascii=False),
                    needs_human_review=bool(
                        grade.get("needs_human_review")
                        or question.get("reading_confidence") == "baixa"
                    ),
                    review_reason=grade.get("review_reason") or None,
                    raw_vision_json=json.dumps(raw_vision, ensure_ascii=False),
                    raw_grading_json=json.dumps(raw_grade, ensure_ascii=False),
                )
            )


def _parse_optional_json_or_text(raw: str | None):
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"free_text_rubric": raw.strip()}


def _safe_pdf_name(filename: str) -> str:
    name = Path(filename).name.replace("\\", "_").replace("/", "_")
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"
