from pydantic import BaseModel
from uuid import UUID


class ClassCreate(BaseModel):
    name: str


class ClassSummary(BaseModel):
    id: UUID
    name: str
    student_count: int
