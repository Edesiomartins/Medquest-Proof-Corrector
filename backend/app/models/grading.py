from sqlalchemy import Column, String, Float, Integer, ForeignKey, Text, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum
from .base import Base


class ResultStatus(str, enum.Enum):
    PENDING = "PENDING"
    GRADED = "GRADED"
    REVIEWED = "REVIEWED"


class StudentResult(Base):
    """Uma prova corrigida de um aluno (1 página do PDF)."""
    __tablename__ = "student_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("upload_batches.id"), nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=True)
    page_number = Column(Integer, nullable=False)
    total_score = Column(Float, default=0.0)
    status = Column(SQLEnum(ResultStatus), default=ResultStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class QuestionScore(Base):
    """Nota de uma questão específica para um aluno."""
    __tablename__ = "question_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_result_id = Column(UUID(as_uuid=True), ForeignKey("student_results.id"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("exam_questions.id"), nullable=False)
    ai_score = Column(Float, default=0.0)
    ai_justification = Column(Text, nullable=True)
    final_score = Column(Float, nullable=True)
    professor_comment = Column(Text, nullable=True)
