"""Item 11 do docs/HTR_PLANO_EXECUCAO.md: segmentacao de linhas.

Um bloco de cinco linhas manuscritas e lido pior que cinco tiras: ascendentes e
descendentes de linhas vizinhas se sobrepoem, o modelo pula linha em bloco denso,
e quando erra nao da para localizar onde.

O modulo resolve isso SEM multiplicar chamadas: reempilha as linhas com espaco em
branco entre elas, numa unica imagem. Mandar cinco tiras seriam cinco chamadas
por questao, e o projeto opera sob restricao de custo.
"""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.vision.lines import (
    crop_lines,
    deskew_line,
    ink_profile,
    restack_lines,
    segment_lines,
)


WIDTH, HEIGHT = 500, 260
GRAY_BOX = (222, 222, 222)
BLUE_PEN = (28, 42, 120)


def _blank(size=(WIDTH, HEIGHT), color=GRAY_BOX) -> Image.Image:
    return Image.new("RGB", size, color)


def _handwriting(line_tops: list[int], amplitude: int = 7, width: int = 3) -> Image.Image:
    """Linhas manuscritas aproximadas: ondas continuas, nao blocos."""
    img = _blank()
    draw = ImageDraw.Draw(img)
    for top in line_tops:
        points = [
            (25 + i * 11, top + int(amplitude * np.sin(i / 1.5)))
            for i in range(40)
        ]
        draw.line(points, fill=BLUE_PEN, width=width, joint="curve")
    return img


# --- perfil e segmentacao -----------------------------------------------------


def test_ink_profile_peaks_where_the_lines_are():
    image = _handwriting([60, 140])

    profile = ink_profile(image)

    assert profile[55:75].sum() > profile[100:120].sum()


def test_finds_one_line_per_written_row():
    assert len(segment_lines(_handwriting([50, 120, 190]))) == 3


def test_blank_crop_has_no_lines():
    assert segment_lines(_blank()) == []


def test_single_line_is_found():
    assert len(segment_lines(_handwriting([120]))) == 1


def test_lines_do_not_overlap_and_come_in_order():
    lines = segment_lines(_handwriting([50, 120, 190]))

    for previous, following in zip(lines, lines[1:], strict=False):
        assert previous.bottom <= following.top


def test_noise_speck_is_not_a_line():
    img = _blank()
    ImageDraw.Draw(img).ellipse([300, 30, 303, 33], fill=BLUE_PEN)

    assert segment_lines(img) == []


def test_absurd_segmentation_is_reported_as_unreliable():
    """Melhor devolver nada do que devolver trinta 'linhas' de ruido."""
    img = _blank()
    draw = ImageDraw.Draw(img)
    for y in range(5, HEIGHT - 5, 7):
        draw.line([(20, y), (WIDTH - 20, y)], fill=BLUE_PEN, width=2)

    assert segment_lines(img, max_lines=6) == []


def test_degenerate_sizes_do_not_crash():
    assert segment_lines(Image.new("RGB", (2, 2), (255, 255, 255))) == []


# --- tiras --------------------------------------------------------------------


def test_crop_lines_returns_one_strip_per_line():
    strips = crop_lines(_handwriting([50, 120, 190]))

    assert len(strips) == 3
    assert all(strip.width == WIDTH for strip in strips)


def test_strips_include_padding_for_ascenders_and_descenders():
    """Cortar rente ao perfil decapitaria o 'l' e cortaria a perna do 'g'."""
    lines = segment_lines(_handwriting([120]))
    strips = crop_lines(_handwriting([120]))

    assert strips[0].height > lines[0].height


# --- reempilhamento -----------------------------------------------------------


def test_restack_normalizes_spacing_without_losing_lines():
    """O ponto do item 11: separar sem gastar uma chamada por linha.

    Reempilhar nao necessariamente aumenta a imagem -- num recorte com muito
    espaco morto ela encolhe, o que tambem e bom, porque pixel vazio enviado ao
    modelo e pixel desperdicado. O que nao pode acontecer e perder linha.
    """
    original = _handwriting([50, 120, 190])

    restacked = restack_lines(original)

    assert restacked.width == original.width
    assert len(segment_lines(restacked)) == len(segment_lines(original))


def test_restack_gives_every_gap_a_healthy_share_of_the_line_height():
    """A sobreposicao entre linhas vizinhas e o que faz o modelo pular linha."""
    restacked = restack_lines(_handwriting([50, 90, 130], amplitude=12, width=4))

    lines = segment_lines(restacked)
    gaps = [b.top - a.bottom for a, b in zip(lines, lines[1:], strict=False)]
    mean_height = sum(line.height for line in lines) / len(lines)

    assert gaps
    assert min(gaps) > mean_height * 0.15


def test_restacked_image_still_has_the_same_number_of_lines():
    restacked = restack_lines(_handwriting([50, 120, 190]))

    assert len(segment_lines(restacked)) == 3


def test_restack_leaves_a_single_line_alone():
    """Reempilhar uma linha so nao faz nada; devolver a original evita reprocessar."""
    original = _handwriting([120])

    assert restack_lines(original) is original


def test_restack_leaves_a_blank_crop_alone():
    original = _blank()

    assert restack_lines(original) is original


def test_restack_increases_the_gap_between_lines():
    original = _handwriting([50, 90, 130], amplitude=12, width=4)
    restacked = restack_lines(original)

    before = _min_valley_width(ink_profile(original))
    after = _min_valley_width(ink_profile(restacked))

    assert after > before


def _min_valley_width(profile: np.ndarray) -> int:
    """Menor sequencia de linhas sem tinta entre duas com tinta."""
    empty_runs = []
    run = 0
    seen_ink = False
    for value in profile:
        if value > 0:
            if run and seen_ink:
                empty_runs.append(run)
            run = 0
            seen_ink = True
        elif seen_ink:
            run += 1
    return min(empty_runs) if empty_runs else 0


# --- deskew -------------------------------------------------------------------


def test_deskew_straightens_a_sloping_line():
    img = Image.new("RGB", (400, 90), GRAY_BOX)
    ImageDraw.Draw(img).line([(20, 65), (380, 25)], fill=BLUE_PEN, width=4)

    straightened = deskew_line(img)

    assert _vertical_spread(straightened) < _vertical_spread(img)


def test_deskew_leaves_a_straight_line_alone():
    img = Image.new("RGB", (400, 90), GRAY_BOX)
    ImageDraw.Draw(img).line([(20, 45), (380, 45)], fill=BLUE_PEN, width=4)

    assert deskew_line(img) is img


def test_deskew_ignores_implausible_angles():
    """Angulo grande quase sempre e erro de estimativa; girar estragaria mais."""
    img = Image.new("RGB", (200, 200), GRAY_BOX)
    ImageDraw.Draw(img).line([(20, 20), (60, 180)], fill=BLUE_PEN, width=4)

    assert deskew_line(img, max_angle=5.0) is img


def test_deskew_handles_an_empty_strip():
    blank = Image.new("RGB", (200, 40), (255, 255, 255))

    assert deskew_line(blank) is blank


def _vertical_spread(image: Image.Image) -> float:
    profile = ink_profile(image)
    rows = np.nonzero(profile)[0]
    return float(rows.max() - rows.min()) if rows.size else 0.0
