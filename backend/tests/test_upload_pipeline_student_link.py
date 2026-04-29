from uuid import UUID, uuid4

from app.services.vision.qr_decode import PageQrPayload
from app.workers.pipeline import (
    IDENTITY_SOURCE_MANIFEST_FALLBACK,
    IDENTITY_SOURCE_QR,
    IDENTITY_SOURCE_ANONYMOUS,
    _pick_student_identity,
)


def test_pick_student_prefers_qr_over_manifest_when_exam_matches():
    exam_id = str(uuid4())
    uuid_01 = str(uuid4())
    uuid_09 = str(uuid4())
    qr = PageQrPayload(
        exam_id=exam_id,
        student_id=uuid_09,
        page_in_student=1,
        total_pages_for_student=1,
    )
    sid, src = _pick_student_identity(qr, uuid_01, exam_id, None)
    assert sid == UUID(uuid_09)
    assert src == IDENTITY_SOURCE_QR


def test_pick_student_manifest_fallback_when_no_qr():
    exam_id = str(uuid4())
    uuid_01 = str(uuid4())
    sid, src = _pick_student_identity(None, uuid_01, exam_id, None)
    assert sid == UUID(uuid_01)
    assert src == IDENTITY_SOURCE_MANIFEST_FALLBACK


def test_pick_student_anonymous_when_no_qr_and_no_manifest():
    exam_id = str(uuid4())
    sid, src = _pick_student_identity(None, None, exam_id, None)
    assert sid is None
    assert src == IDENTITY_SOURCE_ANONYMOUS


def test_qr_exam_mismatch_ignores_qr_uses_manifest():
    exam_id = str(uuid4())
    uuid_01 = str(uuid4())
    uuid_09 = str(uuid4())
    qr = PageQrPayload(
        exam_id="outro-exam-id",
        student_id=uuid_09,
        page_in_student=1,
        total_pages_for_student=1,
    )
    sid, src = _pick_student_identity(qr, uuid_01, exam_id, None)
    assert sid == UUID(uuid_01)
    assert src == IDENTITY_SOURCE_MANIFEST_FALLBACK
