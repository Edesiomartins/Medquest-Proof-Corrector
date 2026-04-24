import asyncio
import io
import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.storage import path_from_local_url
from app.models.exam import Exam, ExamQuestion
from app.models.grading import QuestionScore, ResultStatus, StudentResult
from app.models.pipeline import BatchStatus, UploadBatch
from app.models.student import Student
from app.services.llm.grading import QuestionSpec, VisionGradingService
from app.services.vision.pdf_parser import PDFParserService

logger = logging.getLogger(__name__)


def _fail(db, batch: UploadBatch, msg: str) -> None:
    logger.error(msg)
    batch.status = BatchStatus.FAILED
    db.commit()


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=0)
def process_upload_batch(self, batch_id: str):
    """
    Pipeline simplificado:
    1. Abre PDF, extrai cada página como imagem
    2. Associa cada página a um aluno (pela ordem do CSV)
    3. Envia cada imagem ao LLM com visão + gabarito
    4. Salva notas por questão
    """
    db = SessionLocal()
    try:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if not batch:
            logger.warning("Batch %s não encontrado.", batch_id)
            return

        exam = db.query(Exam).filter(Exam.id == batch.exam_id).first()
        if not exam:
            _fail(db, batch, f"[batch={batch_id}] Prova não encontrada.")
            return

        questions = (
            db.query(ExamQuestion)
            .filter(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.question_number)
            .all()
        )
        if not questions:
            _fail(db, batch, f"[batch={batch_id}] Prova sem questões.")
            return

        students: list = []
        if exam.class_id:
            students = (
                db.query(Student)
                .filter(Student.class_id == exam.class_id)
                .order_by(Student.registration_number)
                .all()
            )

        batch.status = BatchStatus.PROCESSING
        db.commit()

        # 1. Extrair páginas
        try:
            pdf_path = path_from_local_url(batch.file_url)
        except ValueError:
            _fail(db, batch, f"[batch={batch_id}] URL inválida: {batch.file_url!r}")
            return

        if not pdf_path.is_file():
            _fail(db, batch, f"[batch={batch_id}] Arquivo não encontrado: {pdf_path}")
            return

        pdf_bytes = pdf_path.read_bytes()
        try:
            page_images = PDFParserService.extract_pages_as_images(pdf_bytes, dpi=200)
            batch.total_pages = len(page_images)
            db.commit()
        except Exception as exc:
            _fail(db, batch, f"[batch={batch_id}] Falha ao ler PDF: {exc}")
            return

        logger.info("[batch=%s] %d páginas extraídas.", batch_id, len(page_images))

        question_specs = [
            QuestionSpec(
                question_number=q.question_number,
                question_text=q.question_text,
                expected_answer=q.expected_answer,
                max_score=q.max_score,
            )
            for q in questions
        ]

        # 2. Processar cada página
        for page_idx, page_img in enumerate(page_images):
            student = students[page_idx] if page_idx < len(students) else None

            student_result = StudentResult(
                batch_id=batch.id,
                student_id=student.id if student else None,
                page_number=page_idx + 1,
                status=ResultStatus.PENDING,
            )
            db.add(student_result)
            db.flush()

            # Converter imagem para PNG bytes
            img_buf = io.BytesIO()
            page_img.save(img_buf, format="PNG")
            img_bytes = img_buf.getvalue()

            # 3. Enviar para LLM com visão
            try:
                result = _run_async(
                    VisionGradingService.grade_page(img_bytes, question_specs)
                )

                for grade in result.grades:
                    q_model = next(
                        (q for q in questions if q.question_number == grade.question_number),
                        None,
                    )
                    if not q_model:
                        continue

                    score = QuestionScore(
                        student_result_id=student_result.id,
                        question_id=q_model.id,
                        ai_score=grade.score,
                        ai_justification=grade.justification,
                        final_score=grade.score,
                    )
                    db.add(score)

                student_result.total_score = result.total_score
                student_result.status = ResultStatus.GRADED
                db.commit()

                logger.info(
                    "[batch=%s] Página %d/%d corrigida: %.2f pts",
                    batch_id, page_idx + 1, len(page_images), result.total_score,
                )

            except Exception as exc:
                logger.error(
                    "[batch=%s] Erro na página %d: %s", batch_id, page_idx + 1, exc,
                )
                for q in questions:
                    db.add(QuestionScore(
                        student_result_id=student_result.id,
                        question_id=q.id,
                        ai_score=0,
                        ai_justification=f"Erro no processamento: {exc}",
                        final_score=None,
                    ))
                student_result.status = ResultStatus.GRADED
                db.commit()

        batch.status = BatchStatus.REVIEW_PENDING
        db.commit()

        logger.info("[batch=%s] Pipeline concluído: %d provas.", batch_id, len(page_images))

    except Exception as exc:
        db.rollback()
        try:
            batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
            if batch:
                batch.status = BatchStatus.FAILED
                db.commit()
        except Exception:
            db.rollback()
        logger.exception("[batch=%s] Erro inesperado.", batch_id)
    finally:
        db.close()
