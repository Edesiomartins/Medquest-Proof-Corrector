from uuid import uuid4

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from app.services.generator.answer_sheet import QuestionSlot
from app.services.generator.sheet_layout import (
    FIDUCIAL_OUTER_GAP,
    MARGIN,
    PAGE_TOP_CONTENT_INSET,
    QR_SIZE,
    compute_answer_sheet_pages,
)


def _questions(count: int) -> list[QuestionSlot]:
    return [
        QuestionSlot(
            number=i,
            text="Explique a estrutura anatomica indicada e sua relacao funcional.",
            max_score=1.0,
        )
        for i in range(1, count + 1)
    ]


def test_fiducials_bracket_question_area_not_header():
    pages, _ = compute_answer_sheet_pages(uuid4(), _questions(3), uuid4())
    page = pages[0]
    _, page_h = A4

    top_fiducial_y = max(f.y_pt for f in page.fiducials)
    first_box_top = page.boxes[0].y_bottom_pt + page.boxes[0].height_pt

    assert top_fiducial_y < page_h - MARGIN - QR_SIZE
    assert top_fiducial_y > first_box_top


def test_fiducials_stay_outside_answer_box_columns():
    pages, _ = compute_answer_sheet_pages(uuid4(), _questions(3), uuid4())
    page = pages[0]
    page_w, _ = A4
    left_fiducials = [f for f in page.fiducials if f.x_pt < page_w / 2]
    right_fiducials = [f for f in page.fiducials if f.x_pt > page_w / 2]

    epsilon = 0.01
    assert all(f.x_pt + f.w_pt <= MARGIN - FIDUCIAL_OUTER_GAP + epsilon for f in left_fiducials)
    assert all(f.x_pt >= page_w - MARGIN + FIDUCIAL_OUTER_GAP - epsilon for f in right_fiducials)


def test_continuation_pages_reserve_top_space_for_qr():
    pages, _ = compute_answer_sheet_pages(uuid4(), _questions(8), uuid4())

    assert len(pages) > 1
    first_box_top = pages[1].boxes[0].y_bottom_pt + pages[1].boxes[0].height_pt
    _, page_h = A4
    continuation_qr_bottom = page_h - MARGIN - PAGE_TOP_CONTENT_INSET - QR_SIZE

    assert first_box_top < continuation_qr_bottom - 5 * mm
