from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.exam import Exam, ExamQuestion, ExamTemplate
from app.schemas.exam import (
    ExamCreate,
    ExamQuestionCreate,
    ExamQuestionResponse,
    ExamResponse,
    ExamSummary,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/", response_model=List[ExamSummary])
def list_exams(db: Session = Depends(get_db)):
    counts = (
        db.query(ExamQuestion.exam_id, func.count(ExamQuestion.id))
        .group_by(ExamQuestion.exam_id)
        .all()
    )
    count_map = {eid: c for eid, c in counts}
    exams = db.query(Exam).order_by(Exam.name).all()
    return [
        ExamSummary(
            id=e.id,
            name=e.name,
            max_score=e.max_score,
            template_id=e.template_id,
            class_id=e.class_id,
            question_count=count_map.get(e.id, 0),
        )
        for e in exams
    ]


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(exam_in: ExamCreate, db: Session = Depends(get_db)):
    template_id = exam_in.template_id
    if template_id is None:
        tmpl = ExamTemplate(
            name=f"Template — {exam_in.name}",
            pdf_blueprint_url=None,
            page_width=595.0,
            page_height=842.0,
        )
        db.add(tmpl)
        db.flush()
        template_id = tmpl.id

    new_exam = Exam(
        name=exam_in.name,
        max_score=exam_in.max_score,
        template_id=template_id,
        class_id=exam_in.class_id,
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
