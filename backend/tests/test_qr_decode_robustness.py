"""QR da folha-resposta: identidade confiavel batendo identidade adivinhada.

Medido antes da correcao: a 200 DPI -- o DPI que o pipeline Celery usa --
**22% das folhas** tinham pelo menos um QR ilegivel. Cada falha dessas empurra a
pagina para identificacao por regex sobre o nome lido pelo modelo, que e
adivinhacao havendo um QR impresso na propria pagina.
"""

from uuid import UUID, uuid4

import pytest
from PIL import Image

from app.services.generator.answer_sheet import QuestionSlot, StudentInfo, generate_answer_sheets
from app.services.vision.pdf_parser import PDFParserService
from app.services.vision.qr_decode import PageQrPayload, decode_sheet_qr, format_qr_payload


def _questions(count: int) -> list[QuestionSlot]:
    return [
        QuestionSlot(number=i, text="Explique a estrutura anatomica indicada.", max_score=1.0)
        for i in range(1, count + 1)
    ]


# UUIDs fixos: o teste de regressao nao pode depender de sorteio.
FIXED_EXAM_ID = UUID("11111111-2222-3333-4444-555555555555")
FIXED_STUDENT_ID = UUID("66666666-7777-8888-9999-aaaaaaaaaaaa")


def _sheet_pages(dpi: int, exam_id=None, student_id=None) -> list[Image.Image]:
    pdf, _ = generate_answer_sheets(
        exam_id=exam_id or FIXED_EXAM_ID,
        exam_name="ANATOMIA II",
        questions=_questions(8),
        students=[
            (
                student_id or FIXED_STUDENT_ID,
                StudentInfo(
                    name="Aluno Teste",
                    registration_number="2026001",
                    curso="Medicina",
                    turma="Turma A",
                ),
            )
        ],
    )
    return PDFParserService.extract_pages_as_images(pdf, dpi=dpi)


@pytest.mark.parametrize("dpi", [150, 200, 300])
def test_qr_decodes_across_the_dpis_the_pipelines_actually_use(dpi):
    """O worker rasteriza a 200 DPI; 150 aparece em scans economicos.

    Deterministico: payload fixo. Antes da correcao, 150 DPI falhava sempre e
    200 DPI falhava em cerca de 22% das folhas.
    """
    for page in _sheet_pages(dpi):
        assert decode_sheet_qr(page) is not None, f"QR ilegivel a {dpi} DPI"


def test_qr_decode_failure_rate_stays_far_below_the_old_baseline():
    """Portao de regressao contra os 22% medidos antes da correcao.

    Sobrou uma taxa residual de falha da ordem de 1%, dificil de reproduzir de
    forma isolada -- por isso o teste tolera uma folha, em vez de exigir
    perfeicao e piscar. O que ele protege e a ordem de grandeza.
    """
    trials = 20
    failures = sum(
        any(decode_sheet_qr(page) is None for page in _sheet_pages(200, uuid4(), uuid4()))
        for _ in range(trials)
    )

    assert failures <= 1, f"{failures}/{trials} folhas com QR ilegivel (baseline antiga: ~22%)"


def test_decoded_payload_carries_the_identity_fields():
    payload = decode_sheet_qr(_sheet_pages(200)[0])

    assert isinstance(payload, PageQrPayload)
    assert payload.exam_id and payload.student_id
    assert payload.page_in_student == 1
    assert payload.total_pages_for_student >= 1


def test_page_without_qr_returns_none():
    assert decode_sheet_qr(Image.new("RGB", (800, 1000), (255, 255, 255))) is None


def test_downscaled_page_still_decodes():
    """Foto de celular reduzida antes de chegar ao pipeline."""
    page = _sheet_pages(300)[0]
    small = page.resize((page.width // 2, page.height // 2), Image.Resampling.LANCZOS)

    assert decode_sheet_qr(small) is not None


def test_grayscale_page_still_decodes():
    assert decode_sheet_qr(_sheet_pages(200)[0].convert("L")) is not None


def test_payload_format_roundtrips():
    raw = format_qr_payload("exam-1", "student-1", 2, 3)

    assert raw == "MQPC|exam-1|student-1|2|3"
