"""
Layout da folha-resposta (coordenadas em pontos PDF, origem inferior esquerda).

Deve permanecer alinhado com `answer_sheet._draw_sheet`: qualquer mudança visual no PDF
deve ser espelhada aqui para crops/OCR e para o manifesto JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm


# Mesmos valores que em answer_sheet._draw_sheet
MARGIN = 2 * cm
FIDUCIAL_MM = 4 * mm
# Recuo do primeiro texto útil abaixo do topo (fiduciais nos cantos superiores).
PAGE_TOP_CONTENT_INSET = 6 * mm
# Espaço entre a linha "(cont.)" e o baseline de "Questão N" (antes 10 mm; evita OCR pegar o cabeçalho).
CONTINUATION_GAP_BELOW_HEADER = 14 * mm
# Estimativa vertical mínima antes do bloco cinza (título + folga + enunciado curto).
QUESTION_BLOCK_OVERHEAD = 12 * mm


@dataclass
class FiducialBox:
    x_pt: float
    y_pt: float
    w_pt: float
    h_pt: float


@dataclass
class AnswerBoxPlacement:
    question_number: int
    """Retângulo da área cinza de resposta (ReportLab rect)."""
    x_pt: float
    y_bottom_pt: float
    width_pt: float
    height_pt: float


@dataclass
class ManifestPage:
    physical_index: int
    exam_id: str
    student_id: str
    page_in_student: int
    total_pages_for_student: int
    boxes: list[AnswerBoxPlacement] = field(default_factory=list)
    fiducials: list[FiducialBox] = field(default_factory=list)


def fiducials_for_page(width_pt: float, height_pt: float) -> list[FiducialBox]:
    """Marcadores nos cantos para alinhamento futuro de scans."""
    s = float(FIDUCIAL_MM)
    m = float(MARGIN)
    return [
        FiducialBox(x_pt=m, y_pt=m, w_pt=s, h_pt=s),
        FiducialBox(x_pt=width_pt - m - s, y_pt=m, w_pt=s, h_pt=s),
        FiducialBox(x_pt=m, y_pt=height_pt - m - s, w_pt=s, h_pt=s),
        FiducialBox(x_pt=width_pt - m - s, y_pt=height_pt - m - s, w_pt=s, h_pt=s),
    ]


def _wrap_text_lines(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        if len(cur) + len(word) + 1 > max_chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def compute_answer_sheet_pages(
    exam_id: UUID,
    questions: list[Any],  # QuestionSlot-like: number, text, max_score
    student_id: UUID,
    *,
    logo_bottom_y_after: float | None = None,
) -> tuple[list[ManifestPage], int]:
    """
    Simula a paginação de `_draw_sheet` e retorna páginas com boxes de resposta.

    `logo_bottom_y_after`: após desenhar a logo, equivale a `logo_y - 6*mm` no gerador.
    Se None, folha sem logo (`y = h - margin - PAGE_TOP_CONTENT_INSET` antes do cabeçalho).
    """
    w, h = A4
    margin = MARGIN
    usable_w = w - 2 * margin
    top_inset = PAGE_TOP_CONTENT_INSET
    cont_gap = CONTINUATION_GAP_BELOW_HEADER

    response_lines = 5
    response_line_gap = 5 * mm
    first_response_line_offset = 10 * mm
    response_bottom_padding = 3 * mm
    answer_area_h = (
        first_response_line_offset
        + (response_lines - 1) * response_line_gap
        + response_bottom_padding
    )
    spacing = 4 * mm

    if logo_bottom_y_after is not None:
        y = logo_bottom_y_after
    else:
        y = h - margin - top_inset

    # --- Cabeçalho (espelho exato de _draw_sheet) ---
    y -= 8 * mm
    y -= 12 * mm

    box_h = 22 * mm
    y -= box_h + 8 * mm

    y -= 6 * mm

    pages: list[ManifestPage] = []

    page_in_student = 0

    def new_manifest_page() -> ManifestPage:
        nonlocal page_in_student
        page_in_student += 1
        return ManifestPage(
            physical_index=0,
            exam_id=str(exam_id),
            student_id=str(student_id),
            page_in_student=page_in_student,
            total_pages_for_student=0,
            fiducials=fiducials_for_page(w, h),
        )

    current = new_manifest_page()

    for q in questions:
        needed = QUESTION_BLOCK_OVERHEAD + answer_area_h + spacing
        if y - needed < margin:
            pages.append(current)
            y = h - margin - top_inset
            current = new_manifest_page()
            # Página de continuação: linha "(cont.)" em `y`, depois `y -= cont_gap` até o baseline de "Questão N"
            y -= cont_gap

        # Baseline do "Questão N"; em seguida o PDF faz `y -= 5 mm`.
        y -= 5 * mm

        text_lines = _wrap_text_lines(q.text, 95)
        for _line in text_lines[:2]:
            y -= 4 * mm

        y -= 2 * mm

        box_x = margin
        box_y_bottom = y - answer_area_h
        current.boxes.append(
            AnswerBoxPlacement(
                question_number=q.number,
                x_pt=box_x,
                y_bottom_pt=box_y_bottom,
                width_pt=usable_w,
                height_pt=answer_area_h,
            )
        )

        y -= answer_area_h + spacing

    pages.append(current)

    total_pages = len(pages)
    for p in pages:
        p.total_pages_for_student = total_pages

    return pages, total_pages


def manifest_to_jsonable(pages: list[ManifestPage]) -> dict[str, Any]:
    """Serializa o manifesto para gravar em Exam.layout_manifest_json."""

    def box_dict(b: AnswerBoxPlacement) -> dict[str, Any]:
        return {
            "question_number": b.question_number,
            "x_pt": b.x_pt,
            "y_bottom_pt": b.y_bottom_pt,
            "width_pt": b.width_pt,
            "height_pt": b.height_pt,
        }

    def fid_dict(f: FiducialBox) -> dict[str, Any]:
        return {"x_pt": f.x_pt, "y_pt": f.y_pt, "width_pt": f.w_pt, "height_pt": f.h_pt}

    return {
        "version": 1,
        "pages": [
            {
                "physical_index": p.physical_index,
                "exam_id": p.exam_id,
                "student_id": p.student_id,
                "page_in_student": p.page_in_student,
                "total_pages_for_student": p.total_pages_for_student,
                "boxes": [box_dict(b) for b in p.boxes],
                "fiducials": [fid_dict(f) for f in p.fiducials],
            }
            for p in pages
        ],
    }


def dumps_manifest(pages: list[ManifestPage]) -> str:
    return json.dumps(manifest_to_jsonable(pages), ensure_ascii=False)


def pdf_answer_box_to_pil_pixels(
    x_pt: float,
    y_bottom_pt: float,
    width_pt: float,
    height_pt: float,
    page_height_pt: float,
    dpi: float,
) -> tuple[int, int, int, int]:
    """
    Converte retângulo PDF (origem inferior esquerda) para crop PIL (origem superior esquerda).

    Retorna (left, upper, right, lower) em pixels.
    """
    scale = dpi / 72.0
    y_top_pt = y_bottom_pt + height_pt
    left = int(x_pt * scale)
    right = int((x_pt + width_pt) * scale)
    upper = int((page_height_pt - y_top_pt) * scale)
    lower = int((page_height_pt - y_bottom_pt) * scale)
    return left, upper, right, lower


def merge_student_manifest_pages(all_pages: list[ManifestPage]) -> list[ManifestPage]:
    """Renumera physical_index globalmente após concatenar páginas de vários alunos."""
    out: list[ManifestPage] = []
    for i, p in enumerate(all_pages):
        np = ManifestPage(
            physical_index=i,
            exam_id=p.exam_id,
            student_id=p.student_id,
            page_in_student=p.page_in_student,
            total_pages_for_student=p.total_pages_for_student,
            boxes=list(p.boxes),
            fiducials=list(p.fiducials),
        )
        out.append(np)
    return out
