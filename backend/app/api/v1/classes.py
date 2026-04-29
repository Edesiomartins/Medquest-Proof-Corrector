import csv
import io
from typing import List
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.exam import Exam
from app.models.grading import StudentResult
from app.models.student import Student
from app.models.user import Class
from app.schemas.classes import ClassCreate, ClassSummary, StudentResponse

router = APIRouter(
    prefix="/classes",
    tags=["Classes & Roster"],
    dependencies=[Depends(get_current_user)],
)

_MAX_CSV_BYTES = settings.MAX_CSV_MB * 1024 * 1024


@router.post("", response_model=ClassSummary, status_code=201)
def create_class(body: ClassCreate, db: Session = Depends(get_db)):
    c = Class(name=body.name.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return ClassSummary(id=c.id, name=c.name, student_count=0)


@router.get("", response_model=List[ClassSummary])
def list_classes(db: Session = Depends(get_db)):
    classes = db.query(Class).order_by(Class.name).all()
    out: List[ClassSummary] = []
    for c in classes:
        n = db.query(Student).filter(Student.class_id == c.id).count()
        out.append(ClassSummary(id=c.id, name=c.name, student_count=n))
    return out


@router.get("/{class_id}", response_model=ClassSummary)
def get_class(class_id: UUID, db: Session = Depends(get_db)):
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Turma não encontrada.")
    n = db.query(Student).filter(Student.class_id == c.id).count()
    return ClassSummary(id=c.id, name=c.name, student_count=n)


@router.put("/{class_id}", response_model=ClassSummary)
def update_class(class_id: UUID, body: ClassCreate, db: Session = Depends(get_db)):
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Turma não encontrada.")
    c.name = body.name.strip()
    db.commit()
    db.refresh(c)
    n = db.query(Student).filter(Student.class_id == c.id).count()
    return ClassSummary(id=c.id, name=c.name, student_count=n)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(class_id: UUID, db: Session = Depends(get_db)):
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Turma não encontrada.")

    student_ids = [
        row[0]
        for row in db.query(Student.id)
        .filter(Student.class_id == class_id)
        .all()
    ]
    if student_ids:
        db.query(StudentResult).filter(StudentResult.student_id.in_(student_ids)).update(
            {StudentResult.student_id: None},
            synchronize_session=False,
        )

    db.query(Exam).filter(Exam.class_id == class_id).update(
        {Exam.class_id: None},
        synchronize_session=False,
    )
    db.query(Student).filter(Student.class_id == class_id).delete(synchronize_session=False)
    db.delete(c)
    db.commit()


@router.get("/{class_id}/students", response_model=List[StudentResponse])
def list_students(class_id: UUID, db: Session = Depends(get_db)):
    c = db.query(Class).filter(Class.id == class_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Turma não encontrada.")
    return (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.name)
        .all()
    )


@router.delete("/{class_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(class_id: UUID, student_id: UUID, db: Session = Depends(get_db)):
    s = db.query(Student).filter(
        Student.id == student_id, Student.class_id == class_id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")
    db.delete(s)
    db.commit()


@router.post("/{class_id}/students/csv")
async def upload_students_csv(
    class_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Importa CSV com colunas: matrícula, nome, curso (opcional) e turma (opcional).
    Detecta cabeçalho automaticamente. Atualiza se matrícula já existir.
    """
    try:
        cid = UUID(class_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="ID da turma deve ser UUID válido.") from e

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="O arquivo precisa ser .csv.")

    contents = await file.read()
    if len(contents) > _MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail=f"CSV excede {settings.MAX_CSV_MB} MB.")

    try:
        decoded = contents.decode("utf-8")
    except UnicodeDecodeError:
        decoded = contents.decode("latin1")

    first_line = decoded.split("\n", 1)[0]
    delimiter = ";" if ";" in first_line else ","

    reader = csv.reader(io.StringIO(decoded), delimiter=delimiter)

    students_inserted = 0
    students_updated = 0
    header_found = False
    col_matricula = -1
    col_nome = -1
    col_curso = -1
    col_turma = -1

    pending_rows: List[tuple[str, str, str]] = []
    turma_from_csv: str = ""

    for row in reader:
        if not row:
            continue

        if not header_found:
            row_lower = [str(cell).lower().strip() for cell in row]
            for i, cell in enumerate(row_lower):
                if "matrícula" in cell or "matricula" in cell:
                    col_matricula = i
                if "nome do aluno" in cell or "nome" in cell:
                    col_nome = i
                if "curso" in cell:
                    col_curso = i
                if "turma" in cell:
                    col_turma = i
            if col_matricula != -1 and col_nome != -1:
                header_found = True
            continue

        if len(row) <= max(col_matricula, col_nome):
            continue

        registration_number = str(row[col_matricula]).strip()
        name = str(row[col_nome]).strip()
        curso = str(row[col_curso]).strip() if col_curso != -1 and col_curso < len(row) else ""
        turma = str(row[col_turma]).strip() if col_turma != -1 and col_turma < len(row) else ""

        if name and registration_number:
            pending_rows.append((registration_number, name, curso))
            if not turma_from_csv and turma:
                turma_from_csv = turma

    if not header_found:
        raise HTTPException(
            status_code=400,
            detail='Cabeçalho não encontrado. Esperado colunas "Matrícula" e "Nome".',
        )

    if len(pending_rows) > settings.MAX_CSV_ROWS:
        raise HTTPException(status_code=413, detail=f"Máximo {settings.MAX_CSV_ROWS} alunos.")

    try:
        existing_class = db.query(Class).filter(Class.id == cid).first()
        if not existing_class:
            db.add(Class(id=cid, name=f"Turma {str(cid)[:8]}"))
            db.flush()
            existing_class = db.query(Class).filter(Class.id == cid).first()

        if existing_class and turma_from_csv:
            existing_class.name = turma_from_csv

        for registration_number, name, curso in pending_rows:
            existing = (
                db.query(Student)
                .filter(Student.class_id == cid, Student.registration_number == registration_number)
                .first()
            )
            if existing:
                if existing.name != name or existing.curso != curso:
                    existing.name = name
                    existing.curso = curso
                    students_updated += 1
            else:
                db.add(Student(
                    class_id=cid,
                    name=name,
                    registration_number=registration_number,
                    curso=curso,
                ))
                students_inserted += 1

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Erro ao inserir alunos.")

    if students_inserted == 0 and students_updated == 0:
        raise HTTPException(status_code=400, detail="Nenhuma linha de aluno válida encontrada.")

    return {
        "message": f"{students_inserted} novos, {students_updated} atualizados.",
        "inserted": students_inserted,
        "updated": students_updated,
    }
