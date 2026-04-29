from app.services.exam_grading_client import _normalize_grading_response, clamp_grade, parse_llm_json_response


def test_parse_llm_json_response_invalid_json_returns_safe_fallback():
    raw = """{
      "nota": 0.75
      "comentario": "faltou ATP"
    }"""
    parsed = parse_llm_json_response(raw)
    assert parsed["revisao_necessaria"] is True
    assert parsed["nota"] == 0.0
    assert "erro_parse" in parsed


def test_clamp_grade_marks_review_when_outside_scale():
    value, needs_review = clamp_grade(0.6)
    assert value in {0.5, 0.75}
    assert needs_review is True


def test_clamp_grade_accepts_valid_scale_without_review():
    value, needs_review = clamp_grade(0.75)
    assert value == 0.75
    assert needs_review is False


def test_grading_flags_when_answer_copies_question_statement():
    parsed = {
        "nota": 1,
        "comentario": "ok",
        "criterios_atendidos": [],
        "criterios_ausentes": [],
        "revisao_necessaria": False,
    }
    question = {
        "number": 1,
        "prompt": "Explique o mecanismo de contração muscular envolvendo actina, miosina e ATP.",
        "answer_transcription": "Explique o mecanismo de contração muscular envolvendo actina, miosina e ATP.",
        "reading_confidence": "alta",
    }
    rubric = {"max_score": 1.0}
    out = _normalize_grading_response(parsed, question, rubric, "{}")
    assert out["score"] == 0.0
    assert out["needs_human_review"] is True
    assert "cópia do enunciado" in (out["review_reason"] or "")


def test_grading_marks_review_when_required_key_is_misspelled():
    parsed = {
        "nota": 0.5,
        "comentario": "ok",
        "criterios_atendidos": ["x"],
        "criterios_austeis": [],
        "revisao_necessosa": " ",
    }
    question = {"number": 1, "prompt": "Q", "answer_transcription": "Resposta", "reading_confidence": "alta"}
    rubric = {"max_score": 1.0}
    out = _normalize_grading_response(parsed, question, rubric, "{}")
    assert out["score"] == 0.5
    assert out["needs_human_review"] is True
    assert out["schema_valid"] is False
    assert any("chaves ausentes" in w.lower() for w in out["parse_warnings"])


def test_grading_string_boolean_only_accepts_true_false_literals():
    parsed = {
        "nota": 0.5,
        "comentario": "ok",
        "criterios_atendidos": ["x"],
        "criterios_ausentes": [],
        "revisao_necessaria": "t",
    }
    question = {"number": 1, "prompt": "Q", "answer_transcription": "Resposta", "reading_confidence": "alta"}
    rubric = {"max_score": 1.0}
    out = _normalize_grading_response(parsed, question, rubric, "{}")
    assert out["needs_human_review"] is True
    assert any("revisao_necessaria" in w for w in out["parse_warnings"])
