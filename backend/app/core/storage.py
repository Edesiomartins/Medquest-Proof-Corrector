"""Armazenamento local de PDFs e recortes de resposta (`local:` prefix em `file_url`)."""

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
    """Resolve uma URL `local:` para um caminho real, sem sair da raiz de upload.

    O valor chega do banco (`UploadBatch.file_url`, `QuestionScore.answer_crop_path`)
    e vai virar leitura de arquivo servida por HTTP. Tratá-lo como confiável seria
    entregar leitura arbitrária de disco a quem conseguisse gravar nessas colunas —
    então a resolução é confinada aqui, num lugar só.
    """
    if not file_url.startswith("local:"):
        raise ValueError("URL de arquivo não é local")

    rel = file_url[len("local:") :].lstrip("/\\")
    if not rel:
        raise ValueError("URL de arquivo local vazia")

    # `Path(base) / "C:/Windows/..."` devolve o caminho da direita, ignorando a
    # base — o mesmo vale para UNC (`//servidor/share`). Sem esta checagem, tirar
    # a barra inicial não bastaria para confinar o caminho.
    if Path(rel).anchor or Path(rel).is_absolute():
        raise ValueError(f"Caminho absoluto não é permitido: {file_url!r}")

    root = upload_root()
    candidate = (root / rel).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Caminho fora da raiz de upload: {file_url!r}")
    return candidate


def write_batch_pdf(batch_id: UUID, data: bytes) -> str:
    rel = relative_batch_path(batch_id)
    dest = upload_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return local_url(batch_id)


def relative_answer_crop_path(batch_id: UUID, page_number: int, question_number: int) -> str:
    return f"crops/{batch_id}/p{int(page_number):03d}_q{int(question_number):03d}.png"


def write_answer_crop(
    batch_id: UUID,
    page_number: int,
    question_number: int,
    png_bytes: bytes,
) -> str:
    """Grava o recorte da caixa de resposta e devolve a URL `local:` correspondente.

    O nome é determinístico por (lote, página, questão): reprocessar o mesmo lote
    sobrescreve o recorte em vez de acumular cópias órfãs.
    """
    rel = relative_answer_crop_path(batch_id, page_number, question_number)
    dest = upload_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(png_bytes)
    return f"local:{rel}"
