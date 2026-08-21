"""Item 2 (P0-B) do docs/HTR_PLANO_EXECUCAO.md.

`QUESTION_SEMANTIC_GUARDS` era um dicionario fixo de termos de fisiologia
muscular para as questoes 1, 2 e 3. Qualquer prova de outro assunto tinha essas
questoes zeradas indevidamente. A guarda passa a ser por prova (config), com
default permissivo.
"""

from app.services.visual_exam_pipeline import _semantic_guard_matches, _semantic_guards_from


CARDIO_Q1 = {
    "number": 1,
    "prompt": "Descreva as fases do ciclo cardiaco.",
    "expected_answer": "Sistole e diastole ventricular.",
}


def test_question_one_of_another_subject_is_not_zeroed_by_default():
    assert _semantic_guard_matches(1, CARDIO_Q1, guards={}) is True


def test_guard_can_be_configured_per_exam_and_still_catches_swapped_rubric():
    guards = {1: ["ciclo cardiaco", "sistole"]}

    assert _semantic_guard_matches(1, CARDIO_Q1, guards=guards) is True
    assert _semantic_guard_matches(1, {"prompt": "Explique a contracao muscular."}, guards=guards) is False


def test_guard_without_rubric_fails_closed():
    assert _semantic_guard_matches(1, None, guards={1: ["sistole"]}) is False


def test_guards_read_from_options():
    guards = _semantic_guards_from({"question_semantic_guards": {"2": ["lactato"]}}, None)

    assert guards == {2: ["lactato"]}


def test_guards_read_from_rubric_payload():
    guards = _semantic_guards_from({}, {"semantic_guards": {1: ["sistole", "Diastole"]}})

    assert guards == {1: ["sistole", "diastole"]}


def test_guards_default_to_empty():
    assert _semantic_guards_from(None, None) == {}
    assert _semantic_guards_from({}, {"questions": []}) == {}
