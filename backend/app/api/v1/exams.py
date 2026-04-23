from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.models.exam import Exam, ExamQuestion
from app.schemas.exam import ExamCreate, ExamResponse, ExamQuestionCreate, ExamQuestionResponse

router = APIRouter()

@router.get("/", response_model=List[ExamResponse])
def list_exams(db: Session = Depends(get_db)):
    exams = db.query(Exam).all()
    return exams

@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(exam_in: ExamCreate, db: Session = Depends(get_db)):
    new_exam = Exam(
        name=exam_in.name,
        max_score=exam_in.max_score,
        template_id=exam_in.template_id
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)
    return new_exam

@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(exam_id: UUID, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam

@router.post("/{exam_id}/questions", response_model=ExamQuestionResponse)
def add_question(exam_id: UUID, question_in: ExamQuestionCreate, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
        
    new_question = ExamQuestion(
        exam_id=exam_id,
        **question_in.model_dump()
    )
    db.add(new_question)
    db.commit()
    db.refresh(new_question)
    return new_question
