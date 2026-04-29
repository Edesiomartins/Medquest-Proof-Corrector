from uuid import UUID, uuid4

from app.services.vision.qr_decode import PageQrPayload
from app.workers.pipeline import _pick_student_id


def test_pick_student_prefers_manifest_over_conflicting_qr():
    exam_id = str(uuid4())
    manifest_student = str(uuid4())
    other_student = str(uuid4())
    qr = PageQrPayload(
        exam_id=exam_id,
        student_id=other_student,
        page_in_student=1,
        total_pages_for_student=1,
    )
    assert _pick_student_id(qr, manifest_student, exam_id) == UUID(manifest_student)


def test_pick_student_uses_qr_when_manifest_missing():
    exam_id = str(uuid4())
    sid = str(uuid4())
    qr = PageQrPayload(
        exam_id=exam_id,
        student_id=sid,
        page_in_student=1,
        total_pages_for_student=1,
    )
    assert _pick_student_id(qr, None, exam_id) == UUID(sid)


def test_pick_student_uses_manifest_when_qr_unreadable():
    exam_id = str(uuid4())
    manifest_student = str(uuid4())
    assert _pick_student_id(None, manifest_student, exam_id) == UUID(manifest_student)
