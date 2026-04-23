from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClassCreate(BaseModel):
    name: str = Field(default="Nova turma", min_length=1, max_length=200)


class ClassSummary(BaseModel):
    id: UUID
    name: str
    student_count: int

    model_config = ConfigDict(from_attributes=True)
