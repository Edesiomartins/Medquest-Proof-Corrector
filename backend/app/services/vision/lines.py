"""Segmentação de linhas de texto manuscrito.

Item 11 do docs/HTR_PLANO_EXECUCAO.md. O problema: um bloco de cinco linhas
manuscritas é lido pior que cinco tiras separadas. Ascendentes e descendentes de
linhas vizinhas se sobrepõem — o "g" de uma linha invade o espaço do "t" da linha
de baixo —, o modelo pula linhas em blocos densos, e quando erra não há como
localizar onde.

O caminho óbvio seria mandar cada tira numa chamada. **Não é o que este módulo
faz**, e a razão é custo: cinco tiras são cinco chamadas por questão, e o projeto
opera sob restrição explícita de custo. Em vez disso, `restack_lines` reconstrói
o recorte com as linhas separadas por espaço em branco e centralizadas
verticalmente — o mesmo conteúdo, numa única imagem, sem a sobreposição que
atrapalha a leitura. Uma chamada, o benefício da separação.

As tiras individuais continuam disponíveis (`segment_lines`) para o que exige
localização: destacar na tela de revisão qual linha ficou duvidosa, e recortar
uma única linha quando a leitura dela falha.

O algoritmo é o perfil de projeção horizontal sobre o mapa de tinta: soma-se a
tinta de cada linha de pixels e cortam-se os vales. Resolve a maioria dos casos.
Linhas que literalmente se tocam exigiriam seam carving ou A*, e ficam para
quando houver medição mostrando que valem o custo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from app.services.vision.ink import DEFAULT_INK_THRESHOLD, ink_map

logger = logging.getLogger(__name__)

# Fração da tinta média de uma linha abaixo da qual a faixa conta como vale.
_VALLEY_RATIO = 0.12
# Altura mínima de uma linha, como fração da altura do recorte. Abaixo disso é
# ruído ou a cauda de um descendente, não uma linha de texto.
_MIN_LINE_HEIGHT_FRAC = 0.06
_MIN_LINE_HEIGHT_PX = 8
# Folga vertical em volta de cada linha, em frações da altura da linha: recupera
# ascendentes e descendentes que o perfil de projeção corta.
_LINE_PADDING_FRAC = 0.25
# Espaço branco inserido entre as linhas no reempilhamento.
_RESTACK_GAP_FRAC = 0.35


@dataclass(frozen=True)
class TextLine:
    top: int
    bottom: int

    @property
    def height(self) -> int:
        return self.bottom - self.top


def ink_profile(image: Image.Image | np.ndarray) -> np.ndarray:
    """Soma de tinta por linha de pixels — a base da segmentação."""
    rgb = np.asarray(image.convert("RGB")) if isinstance(image, Image.Image) else np.asarray(image)
    return (ink_map(rgb) >= DEFAULT_INK_THRESHOLD).sum(axis=1).astype(np.float32)


def segment_lines(image: Image.Image, *, max_lines: int = 24) -> list[TextLine]:
    """Encontra as linhas de texto pelo perfil de projeção horizontal.

    Devolve lista vazia quando não há texto ou quando a segmentação não é
    confiável — o chamador trata isso como "use o recorte inteiro", nunca como
    erro.
    """
    if image.height < 3 or image.width < 3:
        return []

    profile = ink_profile(image)
    active = profile[profile > 0]
    if active.size == 0:
        return []

    threshold = float(active.mean()) * _VALLEY_RATIO
    min_height = max(_MIN_LINE_HEIGHT_PX, int(image.height * _MIN_LINE_HEIGHT_FRAC))

    lines: list[TextLine] = []
    start: int | None = None
    for index, value in enumerate(profile):
        if value > threshold and start is None:
            start = index
        elif value <= threshold and start is not None:
            if index - start >= min_height:
                lines.append(TextLine(start, index))
            start = None
    if start is not None and len(profile) - start >= min_height:
        lines.append(TextLine(start, len(profile)))

    if len(lines) > max_lines:
        logger.info("Segmentação achou %d linhas (>%d); tratando como não confiável.", len(lines), max_lines)
        return []
    return lines


def _padded(line: TextLine, height: int) -> tuple[int, int]:
    pad = int(line.height * _LINE_PADDING_FRAC)
    return max(0, line.top - pad), min(height, line.bottom + pad)


def crop_lines(image: Image.Image) -> list[Image.Image]:
    """Tiras individuais, uma por linha, com folga para ascendentes e descendentes."""
    lines = segment_lines(image)
    strips = []
    for line in lines:
        top, bottom = _padded(line, image.height)
        if bottom - top >= _MIN_LINE_HEIGHT_PX:
            strips.append(image.crop((0, top, image.width, bottom)))
    return strips


def restack_lines(image: Image.Image, *, min_lines: int = 2) -> Image.Image:
    """Reconstrói o recorte com as linhas separadas por espaço em branco.

    O objetivo é matar a sobreposição entre linhas vizinhas — que é o que faz o
    modelo pular linha e confundir ascendente com descendente — **sem** pagar uma
    chamada por linha.

    Devolve a imagem original quando a segmentação não encontra pelo menos
    `min_lines` linhas: reempilhar uma linha só não faz nada, e reempilhar uma
    segmentação ruim faz mal.
    """
    lines = segment_lines(image)
    if len(lines) < min_lines:
        return image

    strips = []
    for line in lines:
        top, bottom = _padded(line, image.height)
        if bottom > top:
            strips.append(np.asarray(image.convert("RGB").crop((0, top, image.width, bottom))))
    if len(strips) < min_lines:
        return image

    gap = max(4, int(np.mean([s.shape[0] for s in strips]) * _RESTACK_GAP_FRAC))
    separator = np.full((gap, image.width, 3), 255, dtype=np.uint8)

    stacked: list[np.ndarray] = []
    for index, strip in enumerate(strips):
        if index:
            stacked.append(separator)
        stacked.append(strip)

    return Image.fromarray(np.vstack(stacked))


def deskew_line(strip: Image.Image, *, max_angle: float = 12.0) -> Image.Image:
    """Endireita uma linha isolada pela orientação da mancha de tinta.

    Serve para linhas escritas em subida ou descida dentro da caixa — comum em
    folha sem pauta. Ângulos acima de `max_angle` são ignorados: quase sempre são
    erro de estimativa, e girar demais estraga mais do que conserta.
    """
    rgb = np.asarray(strip.convert("RGB"))
    if rgb.shape[0] < 4 or rgb.shape[1] < 4:
        return strip

    mask = (ink_map(rgb) >= DEFAULT_INK_THRESHOLD).astype(np.uint8)
    points = cv2.findNonZero(mask)
    if points is None or len(points) < 20:
        return strip

    (_, _), (_, _), angle = cv2.minAreaRect(points)
    # minAreaRect devolve o ângulo em [-90, 0); normaliza para perto de zero.
    if angle < -45:
        angle += 90
    if abs(angle) > max_angle or abs(angle) < 0.2:
        return strip

    height, width = rgb.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        rgb,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return Image.fromarray(rotated)
