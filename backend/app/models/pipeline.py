from sqlalchemy import Column, String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from .base import Base

class BatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    CROPPING = "CROPPING"
    OCR = "OCR"
    GRADING = "GRADING"
    REVIEW_PENDING = "REVIEW_PENDING"
    DONE = "DONE"
    FAILED = "FAILED"

class ReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"

class OCRStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEEDS_FALLBACK = "NEEDS_FALLBACK"

class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    file_url = Column(String, nullable=False)
    status = Column(SQLEnum(BatchStatus), default=BatchStatus.PENDING, nullable=False)
    total_pages_detected = Column(Integer, default=0)

class DetectedExamInstance(Base):
    __tablename__ = "detected_exam_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("upload_batches.id"), nullable=False)
    student_identifier_text = Column(String, nullable=True)
    review_status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING)

class AnswerRegion(Base):
    __tablename__ = "answer_regions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id = Column(UUID(as_uuid=True), ForeignKey("detected_exam_instances.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("exam_questions.id"), nullable=False)
    cropped_image_url = Column(String, nullable=True)
    ocr_status = Column(SQLEnum(OCRStatus), default=OCRStatus.PENDING)
