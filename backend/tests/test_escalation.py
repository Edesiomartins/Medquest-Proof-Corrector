"""Itens 12 (TTA) e 8 (consenso) do docs/HTR_PLANO_EXECUCAO.md.

A autoavaliacao do modelo e mal calibrada -- ele reporta "alta" ao alucinar texto
em caixa vazia. A concordancia entre leituras independentes, medida em CER, e
ancorada em evidencia: se as leituras convergem, provavelmente estao certas; se
divergem, o traco e ambiguo e a questao precisa de gente.

Custo: nada disto roda por padrao. So entra quando a primeira leitura declara
confianca baixa.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.vision.escalation import (
    AGREEMENT_CER,
    Consensus,
    Hypothesis,
    build_tta_variants,
    pick_consensus,
    should_escalate,
)


@pytest.fixture
def crop(tmp_path):
    img = Image.new("RGB", (400, 150), (222, 222, 222))
    draw = ImageDraw.Draw(img)
    for offset in (0, 45, 90):
        points = [(20 + i * 9, 30 + offset + int(6 * np.sin(i / 1.5))) for i in range(40)]
        draw.line(points, fill=(28, 42, 120), width=3, joint="curve")
    path = tmp_path / "q01.png"
    img.save(path)
    return path


# --- quando escalar -----------------------------------------------------------


def test_low_confidence_escalates_when_enabled():
    assert should_escalate("baixa", enabled=True) is True


@pytest.mark.parametrize("confidence", ["alta", "media", "", None])
def test_confident_reading_never_escalates(confidence):
    """Escalar por padrao multiplicaria o custo de toda prova."""
    assert should_escalate(confidence, enabled=True) is False


def test_disabled_escalation_never_runs():
    assert should_escalate("baixa", enabled=False) is False


# --- variantes de imagem (TTA) ------------------------------------------------


def test_builds_the_requested_number_of_variants(crop, tmp_path):
    variants = build_tta_variants(str(crop), tmp_path / "tta", limit=2)

    assert len(variants) == 2
    assert all(Path(path).is_file() for _, path in variants)


def test_upscale_comes_first_because_resolution_is_the_main_failure(crop, tmp_path):
    variants = build_tta_variants(str(crop), tmp_path / "tta", limit=1)

    assert variants[0][0] == "upscale_2x"


def test_upscale_variant_is_actually_bigger(crop, tmp_path):
    (_, path), *_ = build_tta_variants(str(crop), tmp_path / "tta", limit=1)

    with Image.open(path) as variant, Image.open(crop) as original:
        assert variant.width == original.width * 2


def test_limit_zero_builds_nothing(crop, tmp_path):
    assert build_tta_variants(str(crop), tmp_path / "tta", limit=0) == []


def test_unreadable_crop_yields_no_variants(tmp_path):
    broken = tmp_path / "quebrado.png"
    broken.write_bytes(b"isto nao e um png")

    assert build_tta_variants(str(broken), tmp_path / "tta") == []


def test_line_restacking_variant_is_skipped_when_it_changes_nothing(tmp_path):
    """Reenviar imagem identica gastaria uma chamada por nada."""
    single = Image.new("RGB", (300, 60), (255, 255, 255))
    ImageDraw.Draw(single).line([(20, 30), (280, 30)], fill=(20, 20, 20), width=3)
    path = tmp_path / "uma_linha.png"
    single.save(path)

    names = [name for name, _ in build_tta_variants(str(path), tmp_path / "tta", limit=3)]

    assert "linhas_separadas" not in names


# --- consenso -----------------------------------------------------------------


def _hyp(text, source="modelo", confidence="baixa"):
    return Hypothesis(text=text, source=source, reported_confidence=confidence)


def test_converging_readings_produce_high_confidence():
    result = pick_consensus(
        [
            _hyp("actina e miosina deslizam", "original"),
            _hyp("actina e miosina deslizam", "upscale_2x"),
            _hyp("actina e miosina deslizam", "gemini"),
        ]
    )

    assert result.confidence == "alta"
    assert result.needs_human is False
    assert result.agreement_cer < AGREEMENT_CER


def test_minor_divergence_is_flagged_for_a_look():
    result = pick_consensus(
        [
            _hyp("acumulo de lactato causa a queimacao", "original"),
            _hyp("acumulo de lactato causa a queimacao", "upscale_2x"),
            _hyp("acumulo de loctato causa a queimacao", "gemini"),
        ]
    )

    assert result.confidence in {"alta", "media"}
    assert "lactato" in result.text


def test_wild_disagreement_goes_to_a_human():
    result = pick_consensus(
        [
            _hyp("actina e miosina", "original"),
            _hyp("xxxxx yyyyy zzz", "upscale_2x"),
            _hyp("nada a ver com isso aqui", "gemini"),
        ]
    )

    assert result.confidence == "baixa"
    assert result.needs_human is True
    assert "discordam" in result.reason


def test_consensus_never_invents_text_no_model_produced():
    """O resultado vira nota: inventar uma fusao seria pior que escolher uma leitura."""
    texts = ["actina e miosina", "actina e miosino", "octina e miosina"]

    result = pick_consensus([_hyp(t) for t in texts])

    assert result.text in texts


def test_medoid_picks_the_most_central_reading():
    """Duas leituras concordam e uma destoa: a escolhida e a que tem apoio."""
    result = pick_consensus(
        [
            _hyp("fibras tipo um sao lentas", "original"),
            _hyp("fibras tipo um sao lentas", "upscale_2x"),
            _hyp("completamente outra coisa", "gemini"),
        ]
    )

    assert result.text == "fibras tipo um sao lentas"


def test_alternatives_are_offered_to_the_reviewer():
    """A tela de revisao mostra as hipoteses divergentes como sugestao clicavel."""
    result = pick_consensus(
        [_hyp("actina e miosina", "original"), _hyp("octina e miosino", "gemini")]
    )

    assert "octina e miosino" in result.alternatives or "actina e miosina" in result.alternatives
    assert result.text not in result.alternatives


def test_all_empty_readings_mean_an_empty_box_not_a_failure():
    result = pick_consensus([_hyp(""), _hyp("   "), _hyp("")])

    assert result.text == ""
    assert result.needs_human is False


def test_single_reading_keeps_its_reported_confidence():
    result = pick_consensus([_hyp("actina", confidence="baixa")])

    assert result.confidence == "baixa"
    assert result.needs_human is True
    assert "segunda opini" in result.reason


def test_empty_hypotheses_are_ignored_in_the_vote():
    """Uma variante que falhou nao pode arrastar a concordancia para baixo."""
    result = pick_consensus(
        [_hyp("actina e miosina"), _hyp(""), _hyp("actina e miosina")]
    )

    assert result.text == "actina e miosina"
    assert result.confidence == "alta"


def test_returns_a_consensus_object_with_the_hypotheses_kept():
    hypotheses = [_hyp("a"), _hyp("b")]

    result = pick_consensus(hypotheses)

    assert isinstance(result, Consensus)
    assert result.hypotheses == hypotheses
