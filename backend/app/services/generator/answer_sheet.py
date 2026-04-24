"""Gera folhas-resposta em PDF personalizadas por aluno usando ReportLab."""

import io
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


@dataclass
class StudentInfo:
    name: str
    registration_number: str
    curso: str
    turma: str


@dataclass
class QuestionSlot:
    number: int
    text: str
    max_score: float


@dataclass
class LogoSpec:
    image: ImageReader
    width: float
    height: float


def generate_answer_sheets(
    exam_name: str,
    questions: list[QuestionSlot],
    students: list[StudentInfo],
    logo_bytes: bytes | None = None,
) -> bytes:
    """Gera um PDF com uma folha-resposta por aluno (1 página por aluno)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    logo = _load_logo(logo_bytes)

    for student in students:
        _draw_sheet(c, width, height, exam_name, questions, student, logo)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


def _draw_sheet(
    c: canvas.Canvas,
    w: float,
    h: float,
    exam_name: str,
    questions: list[QuestionSlot],
    student: StudentInfo,
    logo: LogoSpec | None,
):
    margin = 2 * cm
    y = h - margin

    if logo:
        max_logo_w = w - (2 * margin)
        max_logo_h = 24 * mm
        scale = min(max_logo_w / logo.width, max_logo_h / logo.height)
        draw_w = logo.width * scale
        draw_h = logo.height * scale
        logo_x = (w - draw_w) / 2
        logo_y = y - draw_h
        c.drawImage(
            logo.image,
            logo_x,
            logo_y,
            width=draw_w,
            height=draw_h,
            preserveAspectRatio=True,
            mask="auto",
        )
        y = logo_y - 6 * mm

    # --- Cabeçalho ---
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, y, exam_name)
    y -= 8 * mm

    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, y, "FOLHA DE RESPOSTAS — Preencha com letra legível")
    y -= 12 * mm

    # --- Dados do aluno ---
    c.setFont("Helvetica-Bold", 10)
    box_top = y + 2 * mm
    box_h = 22 * mm
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.rect(margin, y - box_h, w - 2 * margin, box_h + 2 * mm, stroke=1, fill=0)

    left = margin + 4 * mm
    c.setFont("Helvetica", 9)
    c.drawString(left, y - 5 * mm, f"Nome: {student.name}")
    c.drawString(left, y - 11 * mm, f"Matrícula: {student.registration_number}")
    c.drawString(left + 60 * mm, y - 11 * mm, f"Curso: {student.curso}")
    c.drawString(left + 120 * mm, y - 11 * mm, f"Turma: {student.turma}")

    y -= box_h + 8 * mm

    # --- Linha separadora ---
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.3)
    c.line(margin, y, w - margin, y)
    y -= 6 * mm

    # --- Questões ---
    usable_w = w - 2 * margin
    response_lines = 5
    response_line_gap = 5 * mm
    response_label_offset = 4 * mm
    first_response_line_offset = 10 * mm
    response_bottom_padding = 3 * mm
    answer_area_h = (
        first_response_line_offset
        + (response_lines - 1) * response_line_gap
        + response_bottom_padding
    )
    spacing = 4 * mm

    for q in questions:
        needed = 10 * mm + answer_area_h + spacing
        if y - needed < margin:
            c.showPage()
            y = h - margin
            c.setFont("Helvetica-Bold", 9)
            c.drawString(margin, y, f"{exam_name} — {student.name} (cont.)")
            y -= 10 * mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, y, f"Questão {q.number}")

        c.setFont("Helvetica", 8)
        c.drawRightString(w - margin, y, f"(vale {q.max_score} pts)")

        y -= 5 * mm

        c.setFont("Helvetica", 8)
        text_lines = _wrap_text(q.text, 95)
        for line in text_lines[:2]:
            c.drawString(margin + 2 * mm, y, line)
            y -= 4 * mm

        y -= 2 * mm

        c.setStrokeColor(colors.Color(0.8, 0.8, 0.8))
        c.setFillColor(colors.Color(0.97, 0.97, 0.97))
        c.setLineWidth(0.4)
        c.rect(margin, y - answer_area_h, usable_w, answer_area_h, stroke=1, fill=1)

        c.setFillColor(colors.Color(0.7, 0.7, 0.7))
        c.setFont("Helvetica-Oblique", 7)
        c.drawString(margin + 3 * mm, y - response_label_offset, "Resposta:")

        c.setStrokeColor(colors.Color(0.85, 0.85, 0.85))
        for i in range(response_lines):
            line_y = y - first_response_line_offset - (i * response_line_gap)
            c.line(margin + 2 * mm, line_y, w - margin - 2 * mm, line_y)

        c.setFillColor(colors.black)
        c.setStrokeColor(colors.black)

        y -= answer_area_h + spacing

    # --- Rodapé ---
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.grey)
    c.drawCentredString(w / 2, margin - 6 * mm, "Medquest Proof Corrector — Folha gerada automaticamente")
    c.setFillColor(colors.black)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def _load_logo(logo_bytes: bytes | None) -> LogoSpec | None:
    if not logo_bytes:
        return None

    try:
        image = ImageReader(io.BytesIO(logo_bytes))
        width, height = image.getSize()
    except Exception as exc:
        raise ValueError("Não foi possível ler o arquivo de logo enviado.") from exc

    if width <= 0 or height <= 0:
        raise ValueError("A imagem da logo é inválida.")
    return LogoSpec(image=image, width=float(width), height=float(height))
