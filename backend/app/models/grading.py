from sqlalchemy import Column, String, Float, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, timezone
import uuid
from .base import Base

class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_region_id = Column(UUID(as_uuid=True), ForeignKey("answer_regions.id"), nullable=False)
    provider_used = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=True)
    confidence_avg = Column(Float, nullable=True)
    needs_fallback_flag = Column(Boolean, default=False)

class GradingResult(Base):
    __tablename__ = "grading_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ocr_result_id = Column(UUID(as_uuid=True), ForeignKey("ocr_results.id"), nullable=False)
    model_used = Column(String, nullable=False)
    suggested_score = Column(Float, nullable=False)
    criteria_met_json = Column(JSONB, nullable=True)
    justification = Column(Text, nullable=True)
    requires_manual_review = Column(Boolean, default=False)

class ManualReview(Base):
    __tablename__ = "manual_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grading_result_id = Column(UUID(as_uuid=True), ForeignKey("grading_results.id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    final_score = Column(Float, nullable=False)
    reviewer_comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
