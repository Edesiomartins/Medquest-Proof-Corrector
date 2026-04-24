from pydantic import BaseModel
from uuid import UUID


class BatchResponse(BaseModel):
    batch_id: UUID
    status: str


class BatchStatusResponse(BaseModel):
    batch_id: UUID
    status: str
    total_pages: int
