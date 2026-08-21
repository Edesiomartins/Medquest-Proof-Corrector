"""Item 7 do docs/HTR_PLANO_EXECUCAO.md: homografia pelos fiduciais.

`align_scan_page` era um stub que devolvia sucesso SEMPRE, entao toda a logica de
`alignment_failed` do worker existia e nunca disparava. Sem alinhamento, os
recortes por manifesto do item 4 caem no lugar errado assim que a pagina chega
torta -- e 3 graus de rotacao ja degradam a leitura de cursiva de forma
perceptivel; 5 graus sao fatais.

Decisao do usuario: ArUco so em provas novas. O detector aceita os dois formatos,
escolhendo pelo estilo gravado no manifesto, para que provas ja impressas
continuem casando.
"""

from uuid import uuid4

import numpy as np
import pytest
from PIL import Image

from app.services.generator.answer_sheet import QuestionSlot, StudentInfo, generate_answer_sheets
from app.services.generator.sheet_layout import (
    FIDUCIAL_STYLE_ARUCO,
    FIDUCIAL_STYLE_SQUARE,
    compute_answer_sheet_pages,
)
from app.services.vision.page_align import align_page_with_manifest, align_scan_page
from app.services.vision.pdf_parser import PDFParserService
from app.services.vision.sheet_geometry import load_manifest

DPI = 200


def _questions(count: int) -> list[QuestionSlot]:
    return [
        QuestionSlot(number=i, text="Explique a estrutura anatomica indicada.", max_score=1.0)
        for i in range(1, count + 1)
    ]


@pytest.fixture(scope="module")
def sheet():
    pdf, manifest = generate_answer_sheets(
        exam_id=uuid4(),
        exam_name="ANATOMIA II",
        questions=_questions(4),
        students=[
            (
                uuid4(),
                StudentInfo(
                    name="Aluno Teste",
                    registration_number="2026001",
                    curso="Medicina",
                    turma="Turma A",
                ),
            )
        ],
    )
    pages = PDFParserService.extract_pages_as_images(pdf, dpi=DPI)
    return pages[0], load_manifest(manifest).page(0)


def _warp(image: Image.Image, corners_shift_px: float) -> Image.Image:
    """Simula digitalizacao torta: empurra os cantos da pagina."""
    import cv2

    w, h = image.size
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    d = corners_shift_px
    dst = np.float32([[d, d * 0.6], [w - d * 0.4, d], [w - d, h - d * 0.5], [d * 0.5, h - d]])
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(
        np.array(image.convert("RGB")), matrix, (w, h), borderValue=(255, 255, 255)
    )
    return Image.fromarray(warped)


# --- geometria dos marcadores -------------------------------------------------


def test_new_sheets_carry_aruco_fiducials_with_distinct_ids():
    pages, _ = compute_answer_sheet_pages(uuid4(), _questions(3), uuid4())
    page = pages[0]

    assert page.fiducial_style == FIDUCIAL_STYLE_ARUCO
    ids = [f.marker_id for f in page.fiducials]
    assert len(ids) == 4
    assert len(set(ids)) == 4
    assert all(i is not None for i in ids)


def test_marker_ids_map_to_the_four_corners():
    pages, _ = compute_answer_sheet_pages(uuid4(), _questions(3), uuid4())
    page = pages[0]
    from reportlab.lib.pagesizes import A4

    page_w, _ = A4
    by_id = {f.marker_id: f for f in page.fiducials}
    lows = [f for f in page.fiducials if f.y_pt < min(x.y_pt for x in page.fiducials) + 1]

    # Cada id ocupa um canto distinto: dois em baixo, dois em cima, dois a
    # esquerda, dois a direita.
    assert len(lows) == 2
    assert len({f.x_pt < page_w / 2 for f in by_id.values()}) == 2


def test_manifest_records_the_fiducial_style_so_the_detector_can_choose(sheet):
    _, manifest_page = sheet

    assert manifest_page.fiducial_style == FIDUCIAL_STYLE_ARUCO
    assert all(f.marker_id is not None for f in manifest_page.fiducials)


def test_legacy_manifest_without_style_reads_as_squares():
    legacy = {
        "version": 1,
        "pages": [
            {
                "physical_index": 0,
                "exam_id": "e",
                "student_id": "s",
                "page_in_student": 1,
                "total_pages_for_student": 1,
                "boxes": [],
                "fiducials": [{"x_pt": 1.0, "y_pt": 2.0, "width_pt": 11.0, "height_pt": 11.0}],
            }
        ],
    }

    page = load_manifest(legacy).page(0)

    assert page.fiducial_style == FIDUCIAL_STYLE_SQUARE
    assert page.fiducials[0].marker_id is None


# --- deteccao -----------------------------------------------------------------


def test_markers_are_detectable_in_the_rendered_sheet(sheet):
    page_image, manifest_page = sheet

    result = align_page_with_manifest(page_image, manifest_page, dpi=DPI)

    assert result.method == "aruco"
    assert result.markers_found == 4


def test_already_straight_page_needs_almost_no_correction(sheet):
    page_image, manifest_page = sheet

    result = align_page_with_manifest(page_image, manifest_page, dpi=DPI)

    assert result.ok is True
    assert result.misalignment_px < 5.0
    assert result.perspective_residual_px < 2.0
    assert abs(result.rotation_deg) < 0.5


def test_reprojection_error_is_not_used_as_a_quality_signal(sheet):
    """Com quatro pontos a homografia ajusta exato: o erro seria sempre zero.

    Este teste existe para que ninguem reintroduza a metrica achando que ela
    mede a qualidade da digitalizacao. O que mede e o residuo de perspectiva.
    """
    result = align_page_with_manifest(_warp(sheet[0], 40), sheet[1], dpi=DPI, correct=False)

    assert not hasattr(result, "reprojection_error_px")
    assert result.perspective_residual_px is not None


def test_warped_page_is_straightened(sheet):
    """O teste que importa: pagina torta volta ao lugar que o manifesto descreve."""
    page_image, manifest_page = sheet
    crooked = _warp(page_image, corners_shift_px=40)

    before = align_page_with_manifest(crooked, manifest_page, dpi=DPI, correct=False)
    after = align_page_with_manifest(crooked, manifest_page, dpi=DPI)

    assert before.misalignment_px > 15.0
    # Depois da correcao os marcadores caem onde o manifesto diz que estao.
    recheck = align_page_with_manifest(after.image, manifest_page, dpi=DPI, correct=False)
    assert recheck.misalignment_px < 5.0
    assert recheck.perspective_residual_px < before.perspective_residual_px


def test_correction_preserves_page_size(sheet):
    page_image, manifest_page = sheet

    result = align_page_with_manifest(_warp(page_image, 30), manifest_page, dpi=DPI)

    assert result.image.size == page_image.size


def test_answer_box_lands_on_its_content_after_correction(sheet):
    """Sem alinhamento, o recorte do item 4 pega a caixa errada numa pagina torta."""
    from app.services.vision.sheet_geometry import crop_box_from_image

    page_image, manifest_page = sheet
    box = manifest_page.boxes[0]
    page_h_pt = manifest_page.page_height_pt

    reference = crop_box_from_image(page_image, box, page_h_pt, DPI)
    crooked = _warp(page_image, corners_shift_px=40)
    corrected = align_page_with_manifest(crooked, manifest_page, dpi=DPI).image

    naive = crop_box_from_image(crooked, box, page_h_pt, DPI)
    fixed = crop_box_from_image(corrected, box, page_h_pt, DPI)

    assert _difference(fixed, reference) < _difference(naive, reference)


def _difference(a: Image.Image, b: Image.Image) -> float:
    b = b.resize(a.size)
    return float(
        np.abs(
            np.asarray(a.convert("L"), dtype=np.float32)
            - np.asarray(b.convert("L"), dtype=np.float32)
        ).mean()
    )


# --- falhas e compatibilidade -------------------------------------------------


def test_blank_page_with_aruco_manifest_is_reported_as_failed(sheet):
    """Prova nova: sabemos que os marcadores foram impressos. Nao achar e sinal real."""
    _, manifest_page = sheet
    blank = Image.new("RGB", (1654, 2339), (255, 255, 255))

    result = align_page_with_manifest(blank, manifest_page, dpi=DPI)

    assert result.ok is False
    assert result.reason


def test_legacy_squares_manifest_does_not_flood_review_when_detection_fails():
    """Provas antigas: nao ha ArUco impresso. Falhar aqui inundaria a fila de revisao."""
    legacy = load_manifest(
        {
            "version": 1,
            "pages": [
                {
                    "physical_index": 0,
                    "exam_id": "e",
                    "student_id": "s",
                    "page_in_student": 1,
                    "total_pages_for_student": 1,
                    "boxes": [],
                    "fiducials": [{"x_pt": 40.0, "y_pt": 56.0, "width_pt": 11.0, "height_pt": 11.0}],
                }
            ],
        }
    ).page(0)
    blank = Image.new("RGB", (1654, 2339), (255, 255, 255))

    result = align_page_with_manifest(blank, legacy, dpi=DPI)

    assert result.ok is True


def test_without_manifest_the_page_passes_through_untouched():
    page = Image.new("RGB", (400, 500), (250, 250, 250))

    image, ok, reason = align_scan_page(page)

    assert ok is True
    assert reason is None
    assert image.size == page.size


def test_align_scan_page_keeps_its_three_tuple_shape(sheet):
    page_image, manifest_page = sheet

    image, ok, reason = align_scan_page(page_image, manifest_page=manifest_page, dpi=DPI)

    assert isinstance(ok, bool)
    assert reason is None or isinstance(reason, str)
    assert image.size == page_image.size


def _phone_photo(image: Image.Image, degrees: float, pad: int = 200) -> Image.Image:
    """Folha fotografada sobre uma mesa: fundo em volta e rotacao.

    E o caso que mais importa na pratica e o que a versao anterior deste modulo
    nao tratava: ela supunha que a imagem recebida ERA a pagina.
    """
    import cv2

    table = (120, 115, 110)
    arr = np.array(image.convert("RGB"))
    arr = cv2.copyMakeBorder(arr, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=table)
    h, w = arr.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return Image.fromarray(cv2.warpAffine(arr, matrix, (w, h), borderValue=table))


@pytest.mark.parametrize("degrees", [0, 3, 8, 12])
def test_photo_with_background_is_framed_and_straightened(sheet, degrees):
    from app.services.vision.sheet_geometry import crop_box_from_image

    page_image, manifest_page = sheet
    box = manifest_page.boxes[0]
    reference = crop_box_from_image(page_image, box, manifest_page.page_height_pt, DPI)

    photo = _phone_photo(page_image, degrees)
    result = align_page_with_manifest(photo, manifest_page, dpi=DPI)

    naive = crop_box_from_image(photo, box, manifest_page.page_height_pt, DPI)
    fixed = crop_box_from_image(result.image, box, manifest_page.page_height_pt, DPI)

    assert result.ok is True
    assert abs(result.rotation_deg - degrees) < 0.5
    # O recorte alinhado bate com a referencia; o ingenuo pega outra coisa.
    assert _difference(fixed, reference) < 5.0
    assert _difference(naive, reference) > 10.0


def test_output_is_the_page_at_the_requested_dpi_not_the_input_frame(sheet):
    """Enquadramento faz parte da correcao: a saida e a PAGINA, nao a foto."""
    page_image, manifest_page = sheet
    photo = _phone_photo(page_image, 5)

    result = align_page_with_manifest(photo, manifest_page, dpi=DPI)

    expected = (
        round(manifest_page.page_width_pt * DPI / 72.0),
        round(manifest_page.page_height_pt * DPI / 72.0),
    )
    assert result.image.size != photo.size
    assert abs(result.image.width - expected[0]) <= 1
    assert abs(result.image.height - expected[1]) <= 1


def test_manifest_records_the_page_size(sheet):
    from reportlab.lib.pagesizes import A4

    _, manifest_page = sheet

    assert round(manifest_page.page_width_pt) == round(A4[0])
    assert round(manifest_page.page_height_pt) == round(A4[1])


def test_legacy_manifest_falls_back_to_a4():
    page = load_manifest(
        {
            "version": 1,
            "pages": [
                {
                    "physical_index": 0,
                    "exam_id": "e",
                    "student_id": "s",
                    "page_in_student": 1,
                    "total_pages_for_student": 1,
                    "boxes": [],
                    "fiducials": [],
                }
            ],
        }
    ).page(0)

    from reportlab.lib.pagesizes import A4

    assert round(page.page_height_pt) == round(A4[1])
