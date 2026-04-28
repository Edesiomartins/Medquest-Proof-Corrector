import json
import uuid

from app.api.v1.visual_exam_analysis import _persist_visual_answers


class _FakeDb:
    def __init__(self) -> None:
        self.items = []

    def add(self, item):
        self.items.append(item)


def test_persist_visual_answers_stores_identity_and_ocr_fields():
    db = _FakeDb()
    run_id = uuid.uuid4()
    students = [
        {
            "detected_student_name": "ALUNO 01",
            "detected_registration": "24102MED001",
            "detected_student_code": "001",
            "physical_page": 8,
            "student": {"class": "T1"},
            "questions": [
                {
                    "number": 1,
                    "prompt_detected": "Q1",
                    "extracted_answer": "Eita, essa me pegou...",
                    "reading_confidence": "media",
                    "ocr_confidence": 0.91,
                    "reading_notes": "",
                    "image_region": {"x": 10, "y": 20, "w": 30, "h": 40},
                    "grade": {
                        "score": 0.5,
                        "max_score": 1.0,
                        "verdict": "parcial",
                        "justification": "ok",
                        "detected_concepts": [],
                        "missing_concepts": [],
                        "needs_human_review": False,
                        "review_reason": "",
                    },
                }
            ],
        }
    ]

    _persist_visual_answers(db, run_id, students)
    assert len(db.items) == 1

    row = db.items[0]
    assert row.detected_student_code == "001"
    assert row.page_number == 8
    assert row.ocr_confidence == 0.91
    assert row.answer_transcription == "Eita, essa me pegou..."
    assert json.loads(row.image_region) == {"x": 10, "y": 20, "w": 30, "h": 40}
