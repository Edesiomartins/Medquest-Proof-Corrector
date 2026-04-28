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


def test_parse_single_question_json_accepts_portuguese_aliases_and_clamps_score():
    question = QuestionSpec(
        question_number=3,
        question_text="Explique a dor muscular pós-exercício.",
        expected_answer="Acúmulo de metabólitos e inflamação local.",
        max_score=1.0,
    )
    raw = """{
      "questao": 3,
      "nota": 1.8,
      "nota_maxima": 1.0,
      "comentario": "Resposta parcialmente adequada.",
      "criterios_atendidos": ["menciona ácido lático"],
      "criterios_ausentes": ["não explica recuperação"],
      "confianca": 0.9,
      "revisao_necessaria": false,
      "motivo_revisao": null
    }"""

    grade, parse_ok = _parse_single_question_json(raw, question)

    assert parse_ok is False
    assert grade.question_number == 3
    assert grade.score == 1.0
    assert grade.grading_confidence == 0.9
