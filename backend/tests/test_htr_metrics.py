"""Item 3 do docs/HTR_PLANO_EXECUCAO.md: metricas de leitura manuscrita."""

import pytest

from app.services.vision.htr_metrics import (
    Sample,
    character_error_rate,
    evaluate,
    levenshtein,
    normalize_text,
    word_error_rate,
)


# --- distancia de edicao ------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("", "", 0),
        ("abc", "abc", 0),
        ("abc", "", 3),
        ("", "abc", 3),
        ("actina", "actino", 1),
        ("miosina", "meosina", 1),
        ("gato", "rato", 1),
        ("contracao", "contraao", 1),
    ],
)
def test_levenshtein(a, b, expected):
    assert levenshtein(a, b) == expected


# --- normalizacao -------------------------------------------------------------


def test_whitespace_is_collapsed_because_line_breaks_are_not_reading_errors():
    assert normalize_text("actina  e\n\n miosina") == "actina e miosina"


def test_accents_count_as_errors_by_default():
    """Em portugues o acento muda a palavra; ignora-lo esconderia falha real."""
    assert character_error_rate("contração", "contracao") > 0


def test_accents_can_be_ignored_on_demand():
    assert character_error_rate("contração", "contracao", strip_accents=True) == 0.0


def test_case_is_folded():
    assert character_error_rate("Actina", "actina") == 0.0


# --- CER e WER ----------------------------------------------------------------


def test_perfect_read_scores_zero():
    assert character_error_rate("actina e miosina", "actina e miosina") == 0.0


def test_cer_is_proportional_to_the_reference_length():
    """Um caractere errado pesa menos numa resposta longa do que numa curta."""
    short = character_error_rate("actina", "actino")
    long = character_error_rate("actina e miosina deslizam", "actino e miosina deslizam")

    assert short > long


def test_cer_distinguishes_an_accent_from_a_whole_wrong_word():
    """A WER trata os dois como um erro; a CER e que prediz o trabalho do revisor."""
    accent = character_error_rate("contração muscular", "contracao muscular")
    whole = character_error_rate("contração muscular", "contração esqueletica")

    assert accent < whole
    assert word_error_rate("contração muscular", "contracao muscular") == word_error_rate(
        "contração muscular", "contração esqueletica"
    )


def test_empty_reference_with_empty_hypothesis_is_a_perfect_read():
    assert character_error_rate("", "") == 0.0


def test_empty_reference_with_text_is_full_error_not_infinity():
    assert character_error_rate("", "inventou isto") == 1.0


def test_wer_counts_words():
    assert word_error_rate("fibras tipo um", "fibras tipo dois") == pytest.approx(1 / 3)


# --- relatorio ----------------------------------------------------------------


def test_empty_set_reports_nothing_without_crashing():
    assert evaluate([]).samples == 0


def test_report_averages_over_samples():
    report = evaluate(
        [
            Sample(reference="actina", hypothesis="actina"),
            Sample(reference="miosina", hypothesis="miosino"),
        ]
    )

    assert report.samples == 2
    assert 0 < report.cer < 0.5
    assert report.perfect_reads == 1


def test_hallucination_in_an_empty_box_is_counted_separately():
    """O erro mais grave do sistema: nota atribuida a resposta inexistente."""
    report = evaluate(
        [
            Sample(reference="", hypothesis=""),
            Sample(reference="", hypothesis="o aluno escreveu algo"),
            Sample(reference="actina", hypothesis="actina"),
        ]
    )

    assert report.empty_boxes == 2
    assert report.hallucinated_empty == 1
    assert report.hallucination_rate == 0.5


def test_missed_answer_is_counted_separately_from_hallucination():
    report = evaluate([Sample(reference="actina e miosina", hypothesis="")])

    assert report.missed_answers == 1
    assert report.hallucinated_empty == 0


def test_hallucination_rate_is_zero_when_there_are_no_empty_boxes():
    report = evaluate([Sample(reference="actina", hypothesis="actina")])

    assert report.hallucination_rate == 0.0


# --- calibracao da confianca --------------------------------------------------


def test_well_calibrated_confidence_correlates_negatively_with_error():
    """Confianca alta deve vir com CER baixo. Correlacao negativa forte."""
    report = evaluate(
        [
            Sample(reference="actina e miosina", hypothesis="actina e miosina", confidence="alta"),
            Sample(reference="fibras tipo um", hypothesis="fibras tipo um", confidence="alta"),
            Sample(reference="lactato acumula", hypothesis="lactato acamula", confidence="media"),
            Sample(reference="acido latico", hypothesis="acido lotico", confidence="media"),
            Sample(reference="sarcomero encurta", hypothesis="xxxxx yyyyy", confidence="baixa"),
            Sample(reference="troponina liga", hypothesis="zzzz aaaa", confidence="baixa"),
        ]
    )

    assert report.confidence_cer_correlation < -0.7


def test_uninformative_confidence_shows_near_zero_correlation():
    """VLM que reporta 'alta' sempre: o gate de revisao fica preso a um numero sem sentido."""
    report = evaluate(
        [
            Sample(reference="actina", hypothesis="actina", confidence="alta"),
            Sample(reference="miosina", hypothesis="xxxxxxx", confidence="alta"),
            Sample(reference="lactato", hypothesis="lactato", confidence="alta"),
            Sample(reference="troponina", hypothesis="yyyyyyyy", confidence="alta"),
        ]
    )

    # Sem variacao na confianca nao ha correlacao a calcular.
    assert report.confidence_cer_correlation is None


def test_correlation_needs_enough_samples():
    assert evaluate([Sample("a", "a", confidence="alta")]).confidence_cer_correlation is None


# --- estratificacao -----------------------------------------------------------


def test_strata_expose_pockets_that_the_average_hides():
    """As falhas se concentram em bolsoes; a media esconde qual."""
    report = evaluate(
        [
            Sample("actina", "actina", strata=("bastao",)),
            Sample("miosina", "miosina", strata=("bastao",)),
            Sample("lactato", "lactato", strata=("bastao",)),
            Sample("sarcomero", "sarcomero", strata=("bastao",)),
            Sample("troponina", "trxpxnxna", strata=("cursiva_ligada", "lapis")),
            Sample("actina", "xxxxxx", strata=("cursiva_ligada", "lapis")),
        ]
    )

    assert report.by_stratum["bastao"].cer == 0.0
    assert report.by_stratum["cursiva_ligada"].cer > 0.4
    assert report.by_stratum["lapis"].samples == 2
    # A media global fica no meio e nao denuncia o bolsao.
    assert report.by_stratum["bastao"].cer < report.cer < report.by_stratum["cursiva_ligada"].cer


def test_report_serializes_to_a_dict():
    payload = evaluate([Sample("actina", "actino", confidence="media", strata=("bastao",))]).as_dict()

    assert payload["samples"] == 1
    assert "cer" in payload
    assert "by_stratum" in payload
