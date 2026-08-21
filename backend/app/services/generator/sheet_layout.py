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
from reportlab.pdfbase.pdfmetrics import stringWidth


# Mesmos valores que em answer_sheet._draw_sheet
MARGIN = 2 * cm
FIDUCIAL_MM = 4 * mm
FIDUCIAL_OUTER_GAP = 2 * mm

# --- Fiduciais -----------------------------------------------------------------
# Provas antigas trazem quadrados sólidos de 4 mm; provas novas trazem marcadores
# ArUco, detectados de forma muito mais robusta pelo `cv2.aruco`. O estilo vai
# gravado no manifesto para que o detector escolha sozinho e as provas já
# impressas continuem casando (docs/HTR_PLANO_EXECUCAO.md, item 7).
FIDUCIAL_STYLE_SQUARE = "square"
FIDUCIAL_STYLE_ARUCO = "aruco"
DEFAULT_FIDUCIAL_STYLE = FIDUCIAL_STYLE_ARUCO

ARUCO_DICT_NAME = "DICT_4X4_50"
# Um marcador 4x4 com borda ocupa 6 células. A 8 mm cada célula tem 1,33 mm, o
# que dá ~10 px por célula a 200 DPI — folgado para o detector. A 4 mm seriam
# ~5 px, no limite do que se detecta, e é por isso que o ArUco é maior que o
# quadrado que ele substitui.
ARUCO_FIDUCIAL_MM = 8 * mm
ARUCO_GRID_CELLS = 6

# Ids por canto. A ordem casa com a que `fiducials_for_page` devolve.
ARUCO_ID_BOTTOM_LEFT = 0
ARUCO_ID_BOTTOM_RIGHT = 1
ARUCO_ID_TOP_LEFT = 2
ARUCO_ID_TOP_RIGHT = 3

# Versão 1: quadrados, sem `fiducial_style`. Versão 2: estilo e ids explícitos.
MANIFEST_VERSION = 2
QR_SIZE = 18 * mm
# Topo da caixa de identificação até o topo do QR (evita QR “vazar” para fora da caixa).
QR_TOP_PADDING_COMPACT = 3 * mm
QR_TOP_PADDING_FULL = 2 * mm
# Altura da caixa cinza do cabeçalho: deve cobrir QR (18 mm) + margens + linhas de texto (até ~15 mm).
HEADER_STUDENT_BOX_H_COMPACT = 23 * mm
HEADER_STUDENT_BOX_H_FULL = 22 * mm
# Espaço entre a linha divisória (após a caixa) e o baseline de “Questão N”.
HEADER_DIVIDER_BELOW_GAP_COMPACT = 6 * mm
HEADER_DIVIDER_BELOW_GAP_FULL = 6 * mm
# Recuo do primeiro texto útil abaixo do topo.
PAGE_TOP_CONTENT_INSET = 6 * mm
# Espaço entre a linha "(cont.)" e o baseline de "Questão N"; inclui o QR no topo.
CONTINUATION_GAP_BELOW_HEADER = QR_SIZE + 10 * mm
QUESTION_TEXT_MAX_CHARS = 95
QUESTION_TEXT_FONT_NAME = "Helvetica"
QUESTION_TEXT_FONT_SIZE = 8
QUESTION_TITLE_GAP = 5 * mm
QUESTION_TEXT_LINE_GAP = 4 * mm
QUESTION_TEXT_BOTTOM_GAP = 2 * mm
# Mantido para compatibilidade com imports antigos; o cálculo atual usa o texto real.
QUESTION_BLOCK_OVERHEAD = QUESTION_TITLE_GAP + (2 * QUESTION_TEXT_LINE_GAP) + QUESTION_TEXT_BOTTOM_GAP
DEFAULT_RESPONSE_LINES = 5
# Folha prática: uma linha de escrita; valor só para referência (override em practical_answer_sheet_options).
PRACTICAL_RESPONSE_LINES = 1

# --- Autoajuste da folha prática ---------------------------------------------
# Objetivo: manter TODAS as questões numa única página, dimensionando a caixa de
# resposta para preencher o espaço disponível (menos questões => caixas maiores).
# Limites da altura da caixa de resposta (mantém legível e evita exageros).
PRACTICAL_AUTOFIT_MIN_BOX_H = 5 * mm
PRACTICAL_AUTOFIT_MAX_BOX_H = 18 * mm
# Espaço ACIMA do enunciado (separa da caixa de resposta da questão anterior).
# Deve ser grande o suficiente para o enunciado ficar visualmente mais próximo
# da sua própria caixa de resposta do que da caixa da questão anterior.
PRACTICAL_AUTOFIT_SPACING = 6 * mm
# Padding inferior dentro da caixa de resposta.
PRACTICAL_AUTOFIT_RESPONSE_PADDING = 2 * mm
# Offset mínimo da linha de escrita a partir do topo da caixa.
PRACTICAL_AUTOFIT_MIN_LINE_OFFSET = 4 * mm
# Folga de segurança: evita encostar no limite exato da página (arredondamento de
# ponto flutuante) e garante que todas as questões realmente caibam na página.
PRACTICAL_AUTOFIT_SAFETY_SLACK = 2 * mm


@dataclass
class FiducialBox:
    x_pt: float
    y_pt: float
    w_pt: float
    h_pt: float
    marker_id: int | None = None
    """Id ArUco. `None` nos fiduciais quadrados do layout antigo."""


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
    fiducial_style: str = DEFAULT_FIDUCIAL_STYLE
    # Tamanho da página em pontos PDF. Sem ele, o alinhamento teria de supor que
    # a imagem digitalizada é exatamente a página — o que é falso em foto de
    # celular, que traz mesa em volta, e em scanner com folha menor que a bandeja.
    page_width_pt: float = float(A4[0])
    page_height_pt: float = float(A4[1])


def fiducial_size_pt(style: str = DEFAULT_FIDUCIAL_STYLE) -> float:
    return float(ARUCO_FIDUCIAL_MM if style == FIDUCIAL_STYLE_ARUCO else FIDUCIAL_MM)


def fiducials_for_page(
    width_pt: float,
    height_pt: float,
    question_area_top_pt: float | None = None,
    style: str = DEFAULT_FIDUCIAL_STYLE,
) -> list[FiducialBox]:
    """Marcadores laterais delimitando a área útil das questões.

    Os quatro cantos são o que permite recuperar a homografia de uma página
    digitalizada torta. Cada um leva um id distinto no estilo ArUco: sem isso, um
    marcador confundido com outro produz uma correção pior que nenhuma.
    """
    s = fiducial_size_pt(style)
    m = float(MARGIN)
    gap = float(FIDUCIAL_OUTER_GAP)
    left_x = max(0.0, m - s - gap)
    right_x = min(width_pt - s, width_pt - m + gap)
    top_y = (
        height_pt - m - s
        if question_area_top_pt is None
        else float(question_area_top_pt) - s
    )
    top_y = min(top_y, height_pt - m - s)
    top_y = max(top_y, m + (2 * s))

    aruco = style == FIDUCIAL_STYLE_ARUCO
    return [
        FiducialBox(left_x, m, s, s, ARUCO_ID_BOTTOM_LEFT if aruco else None),
        FiducialBox(right_x, m, s, s, ARUCO_ID_BOTTOM_RIGHT if aruco else None),
        FiducialBox(left_x, top_y, s, s, ARUCO_ID_TOP_LEFT if aruco else None),
        FiducialBox(right_x, top_y, s, s, ARUCO_ID_TOP_RIGHT if aruco else None),
    ]


def aruco_cell_grid(marker_id: int) -> list[list[bool]]:
    """Matriz 6x6 do marcador (True = célula preta).

    Devolver a grade em vez de um bitmap deixa o gerador desenhar o marcador como
    vetor no PDF. Bitmap escalado sofre interpolação na rasterização e as bordas
    das células — que é exatamente o que o detector mede — chegam borradas.
    """
    import cv2  # noqa: PLC0415 — só o gerador precisa

    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, ARUCO_DICT_NAME))
    image = cv2.aruco.generateImageMarker(dictionary, int(marker_id), ARUCO_GRID_CELLS)
    return [[bool(value < 128) for value in row] for row in image]


def wrap_question_text(
    text: str,
    max_width_pt: float | None = None,
    *,
    font_name: str = QUESTION_TEXT_FONT_NAME,
    font_size: float = QUESTION_TEXT_FONT_SIZE,
    max_chars: int = QUESTION_TEXT_MAX_CHARS,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""

    if max_width_pt is not None:
        for word in words:
            candidate = f"{cur} {word}".strip()
            if cur and stringWidth(candidate, font_name, font_size) > max_width_pt:
                lines.append(cur)
                cur = word
            else:
                cur = candidate
        if cur:
            lines.append(cur)
        return lines

    for word in words:
        if len(cur) + len(word) + 1 > max_chars:
            if cur:
                lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def question_block_height(
    text: str,
    answer_area_h: float,
    spacing: float,
    question_text_width: float | None = None,
    *,
    title_gap: float | None = None,
    text_bottom_gap: float | None = None,
    question_prefix: str = "",
) -> float:
    """Altura real ocupada por uma questão antes de avançar para a próxima."""
    tg = title_gap if title_gap is not None else QUESTION_TITLE_GAP
    tbg = text_bottom_gap if text_bottom_gap is not None else QUESTION_TEXT_BOTTOM_GAP
    text_lines = wrap_question_text(f"{question_prefix}{text}", question_text_width)
    return (
        tg
        + (len(text_lines) * QUESTION_TEXT_LINE_GAP)
        + tbg
        + answer_area_h
        + spacing
    )


def compute_answer_sheet_pages(
    exam_id: UUID,
    questions: list[Any],  # QuestionSlot-like: number, text, max_score
    student_id: UUID,
    *,
    logo_bottom_y_after: float | None = None,
    response_lines: int = DEFAULT_RESPONSE_LINES,
    compact_header: bool = True,
    question_spacing: float | None = None,
    question_title_gap: float | None = None,
    question_text_bottom_gap: float | None = None,
    first_response_line_offset: float | None = None,
    response_bottom_padding: float | None = None,
    logo_max_height: float | None = None,
    logo_bottom_gap: float | None = None,
    header_title_gap: float | None = None,
    header_subtitle_gap: float | None = None,
    header_box_h: float | None = None,
    header_box_bottom_gap: float | None = None,
    header_divider_below_gap: float | None = None,
    header_title_font_size: float | None = None,
    header_subtitle_font_size: float | None = None,
    inline_question_prompt: bool = False,
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

    normalized_response_lines = max(1, response_lines)
    response_line_gap = 5 * mm
    froff = first_response_line_offset if first_response_line_offset is not None else 10 * mm
    rbpad = response_bottom_padding if response_bottom_padding is not None else 3 * mm
    answer_area_h = (
        froff
        + (normalized_response_lines - 1) * response_line_gap
        + rbpad
    )
    spacing = question_spacing if question_spacing is not None else 4 * mm
    title_gap = question_title_gap if question_title_gap is not None else QUESTION_TITLE_GAP
    text_bottom_gap = (
        question_text_bottom_gap if question_text_bottom_gap is not None else QUESTION_TEXT_BOTTOM_GAP
    )

    if logo_bottom_y_after is not None:
        y = logo_bottom_y_after
    else:
        y = h - margin - top_inset

    # --- Cabeçalho (espelho exato de _draw_sheet) ---
    if compact_header:
        header_title_gap_eff = header_title_gap if header_title_gap is not None else 6 * mm
        header_subtitle_gap_eff = header_subtitle_gap if header_subtitle_gap is not None else 8 * mm
        box_h = float(header_box_h if header_box_h is not None else HEADER_STUDENT_BOX_H_COMPACT)
        box_bottom_gap = header_box_bottom_gap if header_box_bottom_gap is not None else 5 * mm
        divider_gap = float(
            header_divider_below_gap
            if header_divider_below_gap is not None
            else HEADER_DIVIDER_BELOW_GAP_COMPACT
        )
    else:
        header_title_gap_eff = header_title_gap if header_title_gap is not None else 8 * mm
        header_subtitle_gap_eff = header_subtitle_gap if header_subtitle_gap is not None else 12 * mm
        box_h = float(header_box_h if header_box_h is not None else HEADER_STUDENT_BOX_H_FULL)
        box_bottom_gap = header_box_bottom_gap if header_box_bottom_gap is not None else 8 * mm
        divider_gap = float(
            header_divider_below_gap
            if header_divider_below_gap is not None
            else HEADER_DIVIDER_BELOW_GAP_FULL
        )

    y -= header_title_gap_eff
    y -= header_subtitle_gap_eff
    y -= box_h + box_bottom_gap

    current_question_area_top_y = y
    y -= divider_gap

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
            page_width_pt=float(w),
            page_height_pt=float(h),
        )

    current = new_manifest_page()
    current.fiducials = fiducials_for_page(w, h, current_question_area_top_y)

    for q in questions:
        needed = question_block_height(
            q.text,
            answer_area_h,
            spacing,
            usable_w,
            title_gap=title_gap,
            text_bottom_gap=text_bottom_gap,
            question_prefix=f"Questão {q.number} - " if inline_question_prompt else "",
        )
        if y - needed < margin:
            pages.append(current)
            y = h - margin - top_inset
            current = new_manifest_page()
            # Página de continuação: linha "(cont.)" em `y`, depois `y -= cont_gap` até o baseline de "Questão N"
            y -= cont_gap
            current.fiducials = fiducials_for_page(w, h, y + 6 * mm)

        if inline_question_prompt:
            text_lines = wrap_question_text(f"Questão {q.number} - {q.text}", usable_w)
        else:
            # Baseline do "Questão N"; em seguida o PDF faz `y -= title_gap`.
            y -= title_gap
            text_lines = wrap_question_text(q.text, usable_w)
        for _line in text_lines:
            y -= QUESTION_TEXT_LINE_GAP

        y -= text_bottom_gap

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


def autofit_practical_options(
    questions: list[Any],  # QuestionSlot-like: number, text
    base_options: dict[str, Any] | None = None,
    *,
    has_logo: bool = True,
) -> dict[str, Any]:
    """
    Dimensiona a caixa de resposta da folha prática para que TODAS as questões
    caibam em uma única página, preenchendo o espaço disponível: menos questões
    geram caixas maiores; mais questões geram caixas menores (até o mínimo
    legível). Se nem no tamanho mínimo couber tudo, o layout naturalmente segue
    para uma página extra.

    Retorna uma cópia de ``base_options`` com os overrides de espaçamento/caixa.
    Como devolve valores numéricos concretos, `compute_answer_sheet_pages` e
    `_draw_sheet` permanecem espelhados automaticamente.
    """
    base = dict(base_options or {})
    n = len(questions)
    if n <= 0:
        return base

    w, h = A4
    margin = MARGIN
    usable_w = w - 2 * margin

    # Altura consumida pelo cabeçalho da 1ª página (espelha compute_answer_sheet_pages,
    # cabeçalho compacto). Assume a logo na altura máxima (estimativa conservadora:
    # menos espaço disponível => caixas levemente menores, mas sem estouro).
    logo_max_h = float(base.get("logo_max_height", 14 * mm)) if has_logo else 0.0
    logo_bottom_gap = float(base.get("logo_bottom_gap", 5 * mm)) if has_logo else 0.0
    header_title_gap = float(base.get("header_title_gap", 4 * mm))
    header_subtitle_gap = float(base.get("header_subtitle_gap", 4 * mm))
    header_box_h = float(base.get("header_box_h", HEADER_STUDENT_BOX_H_COMPACT))
    header_box_bottom_gap = float(base.get("header_box_bottom_gap", 2 * mm))
    header_divider_below_gap = float(
        base.get("header_divider_below_gap", HEADER_DIVIDER_BELOW_GAP_COMPACT)
    )

    y = h - margin - PAGE_TOP_CONTENT_INSET
    y -= logo_max_h + logo_bottom_gap
    y -= header_title_gap
    y -= header_subtitle_gap
    y -= header_box_h + header_box_bottom_gap
    y -= header_divider_below_gap
    avail = y - margin
    if avail <= 0:
        return base

    # Altura do bloco de texto da questão (sem a caixa nem o espaçamento).
    title_gap = float(base.get("question_title_gap", 0.0))
    bottom_gap = float(base.get("question_text_bottom_gap", 0.5 * mm))
    inline = bool(base.get("inline_question_prompt", True))
    max_lines = 1
    for q in questions:
        prefix = f"Questão {getattr(q, 'number', '')} - " if inline else ""
        lines = wrap_question_text(f"{prefix}{getattr(q, 'text', '')}", usable_w)
        max_lines = max(max_lines, len(lines))
    text_block = title_gap + (max_lines * QUESTION_TEXT_LINE_GAP) + bottom_gap

    spacing = PRACTICAL_AUTOFIT_SPACING
    fixed_per_q = text_block + spacing

    # Dimensiona a caixa para que todas as N questões preencham a página (uma só).
    usable_avail = max(0.0, avail - PRACTICAL_AUTOFIT_SAFETY_SLACK)
    box_h = usable_avail / n - fixed_per_q
    box_h = max(PRACTICAL_AUTOFIT_MIN_BOX_H, min(PRACTICAL_AUTOFIT_MAX_BOX_H, box_h))

    # Converte a altura da caixa em offsets (folha prática usa 1 linha de escrita):
    # answer_area_h == first_response_line_offset + response_bottom_padding.
    rbpad = PRACTICAL_AUTOFIT_RESPONSE_PADDING
    froff = box_h - rbpad
    if froff < PRACTICAL_AUTOFIT_MIN_LINE_OFFSET:
        froff = PRACTICAL_AUTOFIT_MIN_LINE_OFFSET
        rbpad = max(0.0, box_h - froff)

    base.update(
        {
            "response_lines": 1,
            "question_spacing": spacing,
            "question_text_bottom_gap": bottom_gap,
            "first_response_line_offset": froff,
            "response_bottom_padding": rbpad,
        }
    )
    return base


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
        payload = {"x_pt": f.x_pt, "y_pt": f.y_pt, "width_pt": f.w_pt, "height_pt": f.h_pt}
        if f.marker_id is not None:
            payload["marker_id"] = f.marker_id
        return payload

    return {
        "version": MANIFEST_VERSION,
        "aruco_dict": ARUCO_DICT_NAME,
        "pages": [
            {
                "physical_index": p.physical_index,
                "exam_id": p.exam_id,
                "student_id": p.student_id,
                "page_in_student": p.page_in_student,
                "total_pages_for_student": p.total_pages_for_student,
                "boxes": [box_dict(b) for b in p.boxes],
                "fiducials": [fid_dict(f) for f in p.fiducials],
                "fiducial_style": p.fiducial_style,
                "page_width_pt": p.page_width_pt,
                "page_height_pt": p.page_height_pt,
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
            fiducial_style=p.fiducial_style,
            page_width_pt=p.page_width_pt,
            page_height_pt=p.page_height_pt,
        )
        out.append(np)
    return out
