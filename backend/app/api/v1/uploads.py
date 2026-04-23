from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.models.pipeline import UploadBatch, BatchStatus
from app.schemas.upload import BatchResponse, BatchStatusResponse

router = APIRouter()

@router.post("/upload", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch(
    exam_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    # TODO: Upload file to Object Storage (S3/R2)
    fake_s3_url = f"s3://medquest-bucket/batches/{exam_id}/{file.filename}"
    
    # Save to database
    new_batch = UploadBatch(
        exam_id=exam_id,
        file_url=fake_s3_url,
        status=BatchStatus.PENDING
    )
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    
    # TODO: Dispatch Celery Task here
    # ingest_pdf_task.delay(batch_id=str(new_batch.id))
    
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
