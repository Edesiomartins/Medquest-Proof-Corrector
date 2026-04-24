from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.exam import Exam, ExamQuestion
from app.models.grading import QuestionScore, ResultStatus, StudentResult
from app.models.pipeline import UploadBatch
from app.models.student import Student
from app.models.user import Class
from app.schemas.review import QuestionScoreDetail, StudentResultDetail, UpdateScore
from app.services.export.spreadsheet import export_results_xlsx

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/batch/{batch_id}", response_model=List[StudentResultDetail])
def list_batch_results(batch_id: UUID, db: Session = Depends(get_db)):
    """Lista todos os resultados de um lote para revisão."""
    results = (
        db.query(StudentResult)
        .filter(StudentResult.batch_id == batch_id)
        .order_by(StudentResult.page_number)
        .all()
    )
    return [_build_detail(db, r) for r in results]


@router.get("/next", response_model=StudentResultDetail)
def get_next_pending(db: Session = Depends(get_db)):
    """Retorna o próximo resultado pendente de revisão."""
    result = (
        db.query(StudentResult)
        .filter(StudentResult.status.in_([ResultStatus.GRADED, ResultStatus.PENDING]))
        .order_by(StudentResult.page_number)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Nenhuma prova pendente de revisão.")
    return _build_detail(db, result)


@router.post("/scores/{score_id}", status_code=status.HTTP_200_OK)
def update_score(
    score_id: UUID,
    payload: UpdateScore,
    db: Session = Depends(get_db),
):
    """Professor ajusta a nota de uma questão específica."""
    qs = db.query(QuestionScore).filter(QuestionScore.id == score_id).first()
    if not qs:
        raise HTTPException(status_code=404, detail="Score não encontrado.")

    qs.final_score = payload.final_score
    qs.professor_comment = payload.professor_comment
    db.commit()

    sr = db.query(StudentResult).filter(StudentResult.id == qs.student_result_id).first()
    _recalc_total(db, sr)

    return {"status": "ok"}


@router.post("/results/{result_id}/approve", status_code=status.HTTP_200_OK)
def approve_result(result_id: UUID, db: Session = Depends(get_db)):
    """Marca resultado como revisado pelo professor."""
    sr = db.query(StudentResult).filter(StudentResult.id == result_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="Resultado não encontrado.")

    sr.status = ResultStatus.REVIEWED
    _recalc_total(db, sr)
    db.commit()

    remaining = (
        db.query(StudentResult)
        .filter(
            StudentResult.batch_id == sr.batch_id,
            StudentResult.status != ResultStatus.REVIEWED,
        )
        .count()
    )
    return {"status": "ok", "remaining": remaining}


@router.get("/batch/{batch_id}/export")
def export_batch(batch_id: UUID, db: Session = Depends(get_db)):
    """Exporta planilha Excel com as notas do lote."""
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")

    exam = db.query(Exam).filter(Exam.id == batch.exam_id).first()
    questions = (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam.id)
        .order_by(ExamQuestion.question_number)
        .all()
    )

    turma_name = "—"
    if exam.class_id:
        turma = db.query(Class).filter(Class.id == exam.class_id).first()
        if turma:
            turma_name = turma.name

    student_results = (
        db.query(StudentResult)
        .filter(StudentResult.batch_id == batch_id)
        .order_by(StudentResult.page_number)
        .all()
    )

    q_dicts = [
        {"number": q.question_number, "text": q.question_text, "max_score": q.max_score}
        for q in questions
    ]

    rows = []
    for sr in student_results:
        student = db.query(Student).filter(Student.id == sr.student_id).first() if sr.student_id else None
        scores_db = db.query(QuestionScore).filter(QuestionScore.student_result_id == sr.id).all()

        score_map = {}
        for s in scores_db:
            q = db.query(ExamQuestion).filter(ExamQuestion.id == s.question_id).first()
            if q:
                score_map[q.question_number] = s.final_score if s.final_score is not None else s.ai_score

        rows.append({
            "student_name": student.name if student else f"Aluno (pág. {sr.page_number})",
            "registration_number": student.registration_number if student else f"P{sr.page_number}",
            "curso": student.curso if student else "",
            "turma": turma_name,
            "scores": score_map,
            "total": sr.total_score,
        })

    xlsx_bytes = export_results_xlsx(exam.name, q_dicts, rows)

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="notas_{exam.name}.xlsx"'},
    )


def _build_detail(db: Session, sr: StudentResult) -> StudentResultDetail:
    student = db.query(Student).filter(Student.id == sr.student_id).first() if sr.student_id else None
    scores = db.query(QuestionScore).filter(QuestionScore.student_result_id == sr.id).all()

    details = []
    for s in scores:
        q = db.query(ExamQuestion).filter(ExamQuestion.id == s.question_id).first()
        if q:
            details.append(QuestionScoreDetail(
                id=s.id,
                question_number=q.question_number,
                question_text=q.question_text,
                max_score=q.max_score,
                ai_score=s.ai_score,
                ai_justification=s.ai_justification,
                final_score=s.final_score,
                professor_comment=s.professor_comment,
            ))
    details.sort(key=lambda x: x.question_number)

    return StudentResultDetail(
        id=sr.id,
        student_name=student.name if student else None,
        registration_number=student.registration_number if student else None,
        page_number=sr.page_number,
        total_score=sr.total_score,
        status=sr.status.value,
        scores=details,
    )


def _recalc_total(db: Session, sr: StudentResult) -> None:
    scores = db.query(QuestionScore).filter(QuestionScore.student_result_id == sr.id).all()
    sr.total_score = sum(
        (s.final_score if s.final_score is not None else s.ai_score) for s in scores
    )
    db.commit()
