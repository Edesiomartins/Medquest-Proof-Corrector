import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from uuid import UUID

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.storage import write_batch_pdf
from app.models.exam import Exam
from app.models.pipeline import UploadBatch, BatchStatus
from app.schemas.upload import BatchResponse, BatchStatusResponse

router = APIRouter(dependencies=[Depends(get_current_user)])

_MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


@router.post("/upload", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    exam_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF file.")
    if len(raw) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds maximum size of {settings.MAX_UPLOAD_MB} MB.",
        )

    batch_id = uuid.uuid4()
    try:
        file_url = write_batch_pdf(batch_id, raw)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not store upload: {e}") from e

    new_batch = UploadBatch(
        id=batch_id,
        exam_id=exam_id,
        file_url=file_url,
        status=BatchStatus.PENDING,
    )
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    
    # Dispatch Celery Task here
    from app.workers.pipeline import process_upload_batch
    process_upload_batch.delay(str(new_batch.id))
    
    return BatchResponse(
        batch_id=new_batch.id,
        status=new_batch.status.value
    )

@router.get("/{batch_id}/status", response_model=BatchStatusResponse)
def get_batch_status(batch_id: UUID, db: Session = Depends(get_db)):
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
        
    return BatchStatusResponse(
        batch_id=batch.id,
        status=batch.status.value,
        total_pages_detected=batch.total_pages_detected
    )
