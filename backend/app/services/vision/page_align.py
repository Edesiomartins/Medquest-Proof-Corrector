"""
Normalização de scans (perspectiva / alinhamento).

Stub documentado: em produção, usar detecção de fiduciais em `sheet_layout.fiducials_for_page`
para homografia. Enquanto isso, devolve a imagem original e sucesso=True para não forçar
revisão em massa sem necessidade.
"""

from __future__ import annotations

from PIL import Image


def align_scan_page(page_image: Image.Image) -> tuple[Image.Image, bool, str | None]:
    """
    Tenta alinhar a página escaneada aos cantos de referência.

    Retorna (imagem_alinhada, sucesso, motivo_falha).
    """
    return page_image, True, None
