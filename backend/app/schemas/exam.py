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
    template_id: UUID

class ExamResponse(ExamBase):
    id: UUID
    template_id: UUID
    class_id: Optional[UUID] = None

    class Config:
        from_attributes = True
