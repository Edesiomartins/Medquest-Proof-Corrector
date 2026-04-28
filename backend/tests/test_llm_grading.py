from app.services.llm.grading import QuestionSpec, _parse_single_question_json


def test_parse_single_question_json_extracts_wrapped_json():
    question = QuestionSpec(
        question_number=1,
        question_text="Explique o papel do cálcio.",
        expected_answer="Cálcio permite a interação actina-miosina.",
        max_score=1.0,
    )
    raw = """Aqui está a correção:
```json
{
  "question_number": 1,
  "score": 0.75,
  "justification": "Resposta parcialmente correta.",
  "criteria_met": ["menciona cálcio"],
  "criteria_missing": ["não menciona ATP"],
  "grading_confidence": 0.82,
  "manual_review_required": false,
  "manual_review_reason": null
}
```"""

    grade, parse_ok = _parse_single_question_json(raw, question)

    assert parse_ok is True
    assert grade.score == 0.75
    assert grade.grading_confidence == 0.82
