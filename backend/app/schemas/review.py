from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class QuestionScoreDetail(BaseModel):
    id: UUID
    question_number: int
    question_text: str
    max_score: float
    ai_score: float
    ai_justification: Optional[str] = None
    final_score: Optional[float] = None
    professor_comment: Optional[str] = None


class StudentResultDetail(BaseModel):
    id: UUID
    student_name: Optional[str] = None
    registration_number: Optional[str] = None
    page_number: int
    total_score: float
    status: str
    scores: list[QuestionScoreDetail]


class UpdateScore(BaseModel):
    final_score: float
    professor_comment: Optional[str] = None
