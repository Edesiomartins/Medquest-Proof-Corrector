"""Armazenamento local de PDFs enviados (`local:` prefix em `file_url`)."""

from pathlib import Path
from uuid import UUID

from app.core.config import settings


def upload_root() -> Path:
    root = settings.UPLOAD_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def relative_batch_path(batch_id: UUID) -> str:
    return f"batches/{batch_id}.pdf"


def local_url(batch_id: UUID) -> str:
    return f"local:{relative_batch_path(batch_id)}"


def path_from_local_url(file_url: str) -> Path:
    if not file_url.startswith("local:"):
        raise ValueError("URL de arquivo não é local")
    rel = file_url[len("local:") :].lstrip("/")
    return upload_root() / rel


def write_batch_pdf(batch_id: UUID, data: bytes) -> str:
    rel = relative_batch_path(batch_id)
    dest = upload_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return local_url(batch_id)
