from pydantic import BaseModel
from uuid import UUID
from typing import Optional

class BatchResponse(BaseModel):
    batch_id: UUID
    status: str
    
class BatchStatusResponse(BaseModel):
    batch_id: UUID
    status: str
    total_pages_detected: int
    
class ReviewDecision(BaseModel):
    approved_score: float
    comments: Optional[str] = None
    force_regrade: bool = False
