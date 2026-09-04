"""Correção prática: abreviações anatômicas, núcleo da resposta e semelhança."""

from app.services.exam_grading_client import grade_practical_answer


def _grade(expected: str, answer: str, max_score: float = 1.0) -> dict:
    return grade_practical_answer(
        {"number": 1, "reading_confidence": "alta", "max_score": max_score},
        {"expected_answer": expected, "max_score": max_score},
        answer,
        reading_confidence="alta",
    )


def test_bone_abbreviation_with_extra_words_is_correct():
    """Caso real: 'O.' é osso, e 'do pé' é contexto que o aluno acrescentou."""
    out = _grade("O. Calcaneo D.", "osso calcaneo do pe d")

    assert out["score"] == 1.0
    assert out["verdict"] == "correta"
    assert out["needs_human_review"] is False


def test_filler_words_do_not_block_match():
    out = _grade("Músculo Sóleo Esquerdo", "o musculo soleo do lado esquerdo")

    assert out["score"] == 1.0
    assert out["verdict"] == "correta"


def test_conflicting_structure_class_is_wrong():
    """Artéria femoral e nervo femoral são estruturas diferentes."""
    out = _grade("A. Femoral D.", "n. femoral d")

    assert out["score"] == 0.0
    assert out["verdict"] == "incorreta"
    assert "estrutura" in out["justification"].lower()


def test_omitted_structure_class_is_tolerated():
    out = _grade("A. Femoral D.", "femoral direita")

    assert out["score"] == 1.0
    assert out["verdict"] == "correta"


def test_partial_core_is_pending_review():
    """Falta 'braquial': não zera, fica pendente para o professor decidir."""
    out = _grade("M. Bíceps Braquial D.", "m biceps direito")

    assert out["score"] is None
    assert out["needs_human_review"] is True
    assert out["verdict"] == "revisao_pendente"


def test_unrelated_answer_is_wrong():
    out = _grade("M. Bíceps Braquial D.", "triceps direito")

    assert out["score"] == 0.0
    assert out["verdict"] == "incorreta"
    assert out["needs_human_review"] is False


def test_ocr_typo_in_core_is_pending_review():
    """'bucinafor' está a uma letra de 'bucinador': dúvida, não erro."""
    out = _grade("Músculo Bucinador E", "M. Bucinafor E.")

    assert out["score"] is None
    assert out["needs_human_review"] is True


def test_anterior_and_posterior_are_not_interchangeable():
    """A tolerância a erro de leitura não pode igualar anterior e posterior.

    Sobra 'tibial' como acerto parcial, o que cai na regra do núcleo
    incompleto: pendente, nunca nota cheia.
    """
    out = _grade("M. Tibial Anterior D.", "m tibial posterior d")

    assert out["score"] is None
    assert out["verdict"] == "revisao_pendente"


def test_wrong_laterality_still_zeroes():
    out = _grade("Latissimo do dorso direito", "m. latissimo do dorso E.")

    assert out["score"] == 0.0
    assert out["verdict"] == "incorreta"
    assert "lateralidade" in out["justification"].lower()
