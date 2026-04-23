from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .base import Base

class ExamTemplate(Base):
    __tablename__ = "exam_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    pdf_blueprint_url = Column(String, nullable=True)
    page_width = Column(Float, nullable=False)
    page_height = Column(Float, nullable=False)

class Exam(Base):
    __tablename__ = "exams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("exam_templates.id"), nullable=False)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=True)
    name = Column(String, nullable=False)
    max_score = Column(Float, nullable=False)

class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    max_score = Column(Float, nullable=False)
    expected_answer = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    box_x = Column(Float, nullable=False)
    box_y = Column(Float, nullable=False)
    box_w = Column(Float, nullable=False)
    box_h = Column(Float, nullable=False)

class QuestionRubric(Base):
    __tablename__ = "question_rubrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("exam_questions.id"), nullable=False)
    criteria = Column(Text, nullable=False)
    score_impact = Column(Float, nullable=False)
    is_mandatory = Column(Boolean, default=False)
