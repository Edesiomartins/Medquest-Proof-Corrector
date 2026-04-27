"""Decodificação de QR Code nas páginas escaneadas (OpenCV)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

PREFIX = "MQPC"


@dataclass
class PageQrPayload:
    exam_id: str
    student_id: str
    page_in_student: int
    total_pages_for_student: int


def decode_sheet_qr(image: Image.Image) -> PageQrPayload | None:
    """
    Lê o QR no formato `MQPC|<exam_id>|<student_id>|<page>|<total_pages>`.
    Retorna None se não encontrar ou se o formato for inválido.
    """
    try:
        import cv2  # noqa: PLC0415 — opcional no ambiente de teste sem opencv
    except ImportError:
        logger.warning("opencv não instalado; QR não será decodificado.")
        return None

    rgb = np.array(image.convert("RGB"))
    bgr = rgb[:, :, ::-1].copy()
    det = cv2.QRCodeDetector()
    ok, decoded, _, _ = det.detectAndDecodeMulti(bgr)
    if not ok or not decoded:
        return None

    for raw in decoded:
        if not raw:
            continue
        payload = _parse_payload(raw)
        if payload:
            return payload
    return None


def _parse_payload(raw: str) -> PageQrPayload | None:
    parts = raw.strip().split("|")
    if len(parts) != 5 or parts[0] != PREFIX:
        return None
    try:
        _, exam_id, student_id, page_s, total_s = parts
        return PageQrPayload(
            exam_id=exam_id.strip(),
            student_id=student_id.strip(),
            page_in_student=int(page_s),
            total_pages_for_student=int(total_s),
        )
    except (ValueError, IndexError):
        return None


def format_qr_payload(
    exam_id: str,
    student_id: str,
    page_in_student: int,
    total_pages_for_student: int,
) -> str:
    return f"{PREFIX}|{exam_id}|{student_id}|{page_in_student}|{total_pages_for_student}"
