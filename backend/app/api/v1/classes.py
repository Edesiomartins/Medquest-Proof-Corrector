import csv
import io
from typing import List
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.student import Student
from app.models.user import Class
from app.schemas.classes import ClassCreate, ClassSummary

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


@router.post("/{class_id}/students/csv")
async def upload_students_csv(
    class_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Importa CSV com colunas: matrícula, nome, curso (opcional).
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

    pending_rows: List[tuple[str, str, str]] = []

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
            if col_matricula != -1 and col_nome != -1:
                header_found = True
            continue

        if len(row) <= max(col_matricula, col_nome):
            continue

        registration_number = str(row[col_matricula]).strip()
        name = str(row[col_nome]).strip()
        curso = str(row[col_curso]).strip() if col_curso != -1 and col_curso < len(row) else ""

        if name and registration_number:
            pending_rows.append((registration_number, name, curso))

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
