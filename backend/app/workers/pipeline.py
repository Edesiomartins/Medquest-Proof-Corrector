import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.storage import path_from_local_url
from app.models.pipeline import UploadBatch, BatchStatus
from app.services.vision.pdf_parser import PDFParserService

logger = logging.getLogger(__name__)


def _fail_batch(db, batch: UploadBatch, msg: str) -> None:
    logger.error(msg)
    batch.status = BatchStatus.FAILED
    db.commit()


@celery_app.task(bind=True, max_retries=0)
def process_upload_batch(self, batch_id: str):
    """
    Worker principal que inicia o pipeline assim que um PDF é enviado.
    Fase 1: ingestão local do PDF e contagem de páginas (PyMuPDF).
    """
    db = SessionLocal()
    try:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if not batch:
            logger.warning("Batch %s não encontrado.", batch_id)
            return f"Error: Batch {batch_id} not found."

        batch.status = BatchStatus.PARSING
        db.commit()

        try:
            path = path_from_local_url(batch.file_url)
        except ValueError:
            _fail_batch(
                db,
                batch,
                f"[batch={batch_id}] URL de arquivo inválida (esperado prefixo local:): {batch.file_url!r}",
            )
            return "invalid file_url"

        if not path.is_file():
            _fail_batch(
                db,
                batch,
                f"[batch={batch_id}] Arquivo não encontrado em disco: {path}",
            )
            return "missing file"

        pdf_bytes = path.read_bytes()

        logger.info("[batch=%s] Extraindo páginas do PDF (%s bytes)...", batch_id, len(pdf_bytes))

        try:
            images = PDFParserService.extract_pages_as_images(pdf_bytes, dpi=300)
            batch.total_pages_detected = len(images)
        except Exception as exc:
            _fail_batch(
                db,
                batch,
                f"[batch={batch_id}] Falha ao ler PDF (arquivo corrompido ou não-PDF?): {exc}",
            )
            return "parse failed"

        db.commit()

        # Próximas fases: crops → OCR → grading (mantém PoC marcando revisão pendente)
        batch.status = BatchStatus.REVIEW_PENDING
        db.commit()

        logger.info(
            "[batch=%s] Pipeline (fase leitura) concluído: %s páginas.",
            batch_id,
            batch.total_pages_detected,
        )
        return f"Successfully parsed batch {batch_id}"

    except Exception as exc:
        db.rollback()
        try:
            batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
            if batch:
                batch.status = BatchStatus.FAILED
                db.commit()
        except Exception:
            db.rollback()
        logger.exception("[batch=%s] Erro inesperado no worker.", batch_id)
        return f"failed: {exc}"
    finally:
        db.close()
