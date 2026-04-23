from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional

class ExamQuestionBase(BaseModel):
    question_text: str
    max_score: float
    expected_answer: str
    page_number: int
    box_x: float
    box_y: float
    box_w: float
    box_h: float

class ExamQuestionCreate(ExamQuestionBase):
    pass

class ExamQuestionResponse(ExamQuestionBase):
    id: UUID
    exam_id: UUID

    class Config:
        from_attributes = True

class ExamBase(BaseModel):
    name: str
    max_score: float

class ExamCreate(ExamBase):
    """Se template_id for omitido, cria um ExamTemplate mínimo (A4 em pontos)."""

    template_id: Optional[UUID] = None
    class_id: Optional[UUID] = None


class ExamResponse(ExamBase):
    id: UUID
    template_id: UUID
    class_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class ExamSummary(ExamBase):
    id: UUID
    template_id: UUID
    class_id: Optional[UUID] = None
    question_count: int = 0

    class Config:
        from_attributes = True
