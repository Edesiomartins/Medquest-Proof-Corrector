"""Item 1 (P0-A) do docs/HTR_PLANO_EXECUCAO.md: a transcricao tem de ser cega.

O gabarito (`expected_answer`, criterios de correcao) nao pode chegar ao prompt
da etapa de visao, sob pena de o modelo completar palavras ilegiveis com a
resposta esperada e esconder as falhas de leitura.
"""

import json

import pytest

from app.services import visual_exam_pipeline
from app.services.openrouter_vision_client import _build_prompt


RUBRIC = {
    "questions": [
        {
            "number": 1,
            "prompt": "Explique o mecanismo de contracao muscular.",
            "max_score": 2.0,
            "expected_answer": "Deslizamento dos filamentos de actina e miosina.",
            "correction_criteria": "Citar actina e miosina vale 2,0.",
        },
        {
            "number": 2,
            "prompt": "Diferencie fibras tipo I e tipo II.",
            "max_score": 2.0,
            "rubric": "Tipo I lenta e oxidativa; tipo II rapida e glicolitica.",
        },
    ]
}

LEAKY_TERMS = [
    "actina",
    "miosina",
    "oxidativa",
    "glicolitica",
    "Citar actina",
]


def _blob(payload) -> str:
    return json.dumps(payload, ensure_ascii=False).lower()


def test_transcription_outline_keeps_numbering_and_prompts():
    outline = visual_exam_pipeline._question_outline_for_transcription(RUBRIC)

    numbers = [item["number"] for item in outline["questions"]]
    assert numbers == [1, 2]
    assert "contracao muscular" in _blob(outline)


@pytest.mark.parametrize("term", LEAKY_TERMS)
def test_transcription_outline_never_leaks_the_answer_key(term):
    outline = visual_exam_pipeline._question_outline_for_transcription(RUBRIC)

    assert term.lower() not in _blob(outline)


def test_transcription_outline_drops_answer_key_fields():
    outline = visual_exam_pipeline._question_outline_for_transcription(RUBRIC)

    for item in outline["questions"]:
        assert "expected_answer" not in item
        assert "rubric" not in item
        assert "correction_criteria" not in item


@pytest.mark.parametrize(
    "context",
    [
        {"rubric_summary": RUBRIC},
        {"question_outline": {"questions": [{"number": 1, "expected_answer": "actina"}]}},
        {"nested": {"deep": [{"correction_criteria": "Citar actina e miosina."}]}},
    ],
)
def test_vision_prompt_strips_answer_key_keys_even_if_caller_passes_them(context):
    """Defesa em profundidade: o cliente de visao e generico e nao pode confiar no chamador."""
    prompt = _build_prompt(context).lower()

    assert "actina" not in prompt
    assert "miosina" not in prompt
    assert "expected_answer" not in prompt
    assert "correction_criteria" not in prompt


def test_vision_prompt_preserves_harmless_context():
    prompt = _build_prompt({"page_number": 3, "detected_answer_regions": 2})

    assert "page_number" in prompt
    assert "detected_answer_regions" in prompt
