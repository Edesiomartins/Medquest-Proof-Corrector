import csv
import io
from typing import List
from uuid import UUID

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import Response

from app.core.config import settings
from app.core.database import get_db
from app.models.student import Student
from app.models.user import Class
from app.schemas.classes import ClassCreate, ClassSummary
from app.services.generator.pdf_builder import PDFBuilderService

router = APIRouter(prefix="/classes", tags=["Classes & Roster"])

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
    Importa CSV com cabeçalho variável; detecta colunas de matrícula e nome.
    Transação única; atualiza nome se a matrícula já existir na turma.
    """
    try:
        cid = UUID(class_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="ID da turma deve ser um UUID válido.") from e

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="O arquivo precisa ser um .csv válido.")

    contents = await file.read()
    if len(contents) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"CSV excede o tamanho máximo de {settings.MAX_CSV_MB} MB.",
        )

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
    col_idx_matricula = -1
    col_idx_nome = -1

    pending_rows: List[tuple[str, str]] = []

    for row in rows_iter:
        if not row:
            continue

        if not header_found:
            row_lower = [str(cell).lower().strip() for cell in row]
            for i, cell in enumerate(row_lower):
                if "matrícula" in cell or "matricula" in cell:
                    col_idx_matricula = i
                if "nome do aluno" in cell or "nome" in cell:
                    col_idx_nome = i
            if col_idx_matricula != -1 and col_idx_nome != -1:
                header_found = True
            continue

        if len(row) <= max(col_idx_matricula, col_idx_nome):
            continue

        registration_number = str(row[col_idx_matricula]).strip()
        name = str(row[col_idx_nome]).strip()
        if name and registration_number:
            pending_rows.append((registration_number, name))

    if not header_found:
        raise HTTPException(
            status_code=400,
            detail='Não foi encontrado cabeçalho com colunas de "Matrícula" e nome do aluno.',
        )

    if len(pending_rows) > settings.MAX_CSV_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"Máximo de {settings.MAX_CSV_ROWS} alunos por importação.",
        )

    try:
        existing_class = db.query(Class).filter(Class.id == cid).first()
        if not existing_class:
            db.add(Class(id=cid, name=f"Turma {str(cid)[:8]}"))
            db.flush()

        for registration_number, name in pending_rows:
            existing = (
                db.query(Student)
                .filter(
                    Student.class_id == cid,
                    Student.registration_number == registration_number,
                )
                .first()
            )
            if existing:
                if existing.name != name:
                    existing.name = name
                    students_updated += 1
            else:
                db.add(
                    Student(
                        class_id=cid,
                        name=name,
                        registration_number=registration_number,
                    )
                )
                students_inserted += 1

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Erro ao inserir alunos no banco de dados.",
        )

    if students_inserted == 0 and students_updated == 0:
        raise HTTPException(
            status_code=400,
            detail="Nenhuma linha de aluno válida encontrada após o cabeçalho.",
        )

    return {
        "message": (
            f"{students_inserted} alunos novos, {students_updated} atualizados "
            f"na turma {class_id}."
        ),
        "inserted": students_inserted,
        "updated": students_updated,
    }


@router.get("/{class_id}/exams/{exam_id}/generate-pdfs")
async def generate_exam_batch(class_id: str, exam_id: str, db: Session = Depends(get_db)):
    students = db.query(Student).filter(Student.class_id == class_id).all()
    if not students:
        raise HTTPException(
            status_code=404,
            detail="Nenhum aluno cadastrado nesta turma. Faça o upload do CSV primeiro.",
        )

    pdf_bytes = PDFBuilderService.generate_class_exam_batch(exam_id=exam_id, students=students)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cadernos_turma_{class_id}.pdf"'
        },
    )
