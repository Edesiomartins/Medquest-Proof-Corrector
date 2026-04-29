from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class ExamCreate(BaseModel):
    name: str
    class_id: Optional[UUID] = None


class ExamResponse(BaseModel):
    id: UUID
    name: str
    class_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class ExamSummary(BaseModel):
    id: UUID
    name: str
    class_id: Optional[UUID] = None
    question_count: int


class ExamQuestionCreate(BaseModel):
    question_number: int
    question_text: str
    expected_answer: str
    correction_criteria: Optional[str] = None
    max_score: float = 1.0


class ExamQuestionResponse(BaseModel):
    id: UUID
    exam_id: UUID
    question_number: int
    question_text: str
    expected_answer: str
    correction_criteria: Optional[str] = None
    max_score: float

    class Config:
        from_attributes = True
