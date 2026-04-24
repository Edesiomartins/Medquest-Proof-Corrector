from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class ClassCreate(BaseModel):
    name: str


class ClassSummary(BaseModel):
    id: UUID
    name: str
    student_count: int


class StudentResponse(BaseModel):
    id: UUID
    class_id: UUID
    name: str
    registration_number: str
    curso: Optional[str] = None

    class Config:
        from_attributes = True
