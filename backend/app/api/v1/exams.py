from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.exam import Exam, ExamQuestion
from app.models.student import Student
from app.models.user import Class
from app.schemas.exam import (
    ExamCreate,
    ExamQuestionCreate,
    ExamQuestionResponse,
    ExamResponse,
    ExamSummary,
)
from app.services.generator.answer_sheet import (
    QuestionSlot,
    StudentInfo,
    generate_answer_sheets,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("", response_model=List[ExamSummary])
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
            class_id=e.class_id,
            question_count=count_map.get(e.id, 0),
        )
        for e in exams
    ]


@router.post("", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
def create_exam(exam_in: ExamCreate, db: Session = Depends(get_db)):
    new_exam = Exam(name=exam_in.name, class_id=exam_in.class_id)
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)
    return new_exam


@router.get("/{exam_id}", response_model=ExamResponse)
def get_exam(exam_id: UUID, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return exam


@router.put("/{exam_id}", response_model=ExamResponse)
def update_exam(exam_id: UUID, exam_in: ExamCreate, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    exam.name = exam_in.name
    exam.class_id = exam_in.class_id
    db.commit()
    db.refresh(exam)
    return exam


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(exam_id: UUID, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete()
    db.delete(exam)
    db.commit()


@router.delete("/{exam_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(exam_id: UUID, question_id: UUID, db: Session = Depends(get_db)):
    q = db.query(ExamQuestion).filter(
        ExamQuestion.id == question_id, ExamQuestion.exam_id == exam_id
    ).first()
    if not q:
        raise HTTPException(status_code=404, detail="Questão não encontrada.")
    db.delete(q)
    db.commit()


@router.get("/{exam_id}/questions", response_model=List[ExamQuestionResponse])
def list_questions(exam_id: UUID, db: Session = Depends(get_db)):
    return (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam_id)
        .order_by(ExamQuestion.question_number)
        .all()
    )


@router.post("/{exam_id}/questions", response_model=ExamQuestionResponse)
def add_question(exam_id: UUID, q_in: ExamQuestionCreate, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    q = ExamQuestion(exam_id=exam_id, **q_in.model_dump())
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.get("/{exam_id}/answer-sheets")
def download_answer_sheets(exam_id: UUID, db: Session = Depends(get_db)):
    """Gera e baixa folhas-resposta PDF para todos os alunos da turma vinculada."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")

    if not exam.class_id:
        raise HTTPException(status_code=400, detail="Prova não vinculada a uma turma.")

    turma = db.query(Class).filter(Class.id == exam.class_id).first()
    turma_name = turma.name if turma else "—"

    students = (
        db.query(Student)
        .filter(Student.class_id == exam.class_id)
        .order_by(Student.registration_number)
        .all()
    )
    if not students:
        raise HTTPException(status_code=404, detail="Nenhum aluno na turma.")

    questions = (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam_id)
        .order_by(ExamQuestion.question_number)
        .all()
    )
    if not questions:
        raise HTTPException(status_code=400, detail="Prova sem questões cadastradas.")

    pdf_bytes = generate_answer_sheets(
        exam_name=exam.name,
        questions=[
            QuestionSlot(number=q.question_number, text=q.question_text, max_score=q.max_score)
            for q in questions
        ],
        students=[
            StudentInfo(
                name=s.name,
                registration_number=s.registration_number,
                curso=s.curso or "—",
                turma=turma_name,
            )
            for s in students
        ],
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="folhas_{exam.name}.pdf"'},
    )
