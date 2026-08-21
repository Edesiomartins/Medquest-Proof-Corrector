"""Normalização de scans: corrige perspectiva e rotação pelos fiduciais.

Este módulo era um stub que devolvia `(imagem, True, None)` — sucesso sempre.
Toda a lógica de `alignment_failed` do worker existia e nunca disparava. Ver
docs/HTR_PLANO_EXECUCAO.md, item 7.

Por que alinhar importa aqui: os recortes por manifesto (item 4) usam coordenadas
do PDF **gerado**. Uma página digitalizada torta não está nesse sistema de
coordenadas, então o recorte cai deslocado — e quanto mais apertado o recorte,
pior o efeito de um deslocamento. Além disso, 3 graus de rotação já degradam a
leitura de cursiva de forma perceptível e 5 graus são fatais.

A homografia dos quatro cantos endireita a página e põe os recortes no lugar.

Sobre medir a qualidade da digitalização: o erro de **reprojeção** da homografia
não serve para isso. Com exatamente quatro correspondências,
`getPerspectiveTransform` ajusta os quatro pontos de forma exata e o erro é
sempre zero — ele mede o próprio ajuste, não a página. O que serve é decompor o
desalinhamento em duas partes:

- `misalignment_px` — quanto os marcadores estavam fora do lugar antes de
  corrigir. Diz o tamanho da correção aplicada, não que a página seja ruim: um
  scanner que desloca a folha alguns milímetros produz valor alto e imagem
  perfeita.
- `perspective_residual_px` — o que sobra depois de descontar a melhor
  rotação-escala-translação. **Este** é o sinal de qualidade: rotação e escala
  são corrigíveis sem perda, mas deformação de perspectiva significa foto tirada
  em ângulo, e aí a resolução varia ao longo da página e o recorte esticado perde
  traço.
- `rotation_deg` — 3 graus já degradam a leitura de cursiva de forma
  perceptível; 5 são fatais. Corrigimos, mas vale registrar.

Decisão de projeto sobre falhas: a página só é reprovada quando **sabemos** que
os marcadores foram impressos, isto é, quando o manifesto declara ArUco. Em
provas antigas, com fiduciais quadrados, não encontrar os marcadores devolve
sucesso com aviso — reprovar ali inundaria a fila de revisão manual com páginas
que estão perfeitamente legíveis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.services.vision.sheet_geometry import ManifestPageGeometry

logger = logging.getLogger(__name__)

# Deformação de perspectiva, em px, além da qual a página é considerada mal
# capturada mesmo depois de corrigida. ~2,5 mm a 200 DPI.
MAX_PERSPECTIVE_RESIDUAL_PX = 20.0
# Mínimo de marcadores para resolver a homografia.
MIN_MARKERS_FOR_HOMOGRAPHY = 4

METHOD_ARUCO = "aruco"
METHOD_SQUARES = "squares"
METHOD_NONE = "none"


@dataclass
class AlignmentResult:
    image: Image.Image
    ok: bool
    reason: str | None = None
    misalignment_px: float | None = None
    """Distância média dos marcadores em relação ao esperado, ANTES de corrigir."""
    perspective_residual_px: float | None = None
    """Deformação que sobra depois de descontar rotação, escala e translação."""
    rotation_deg: float | None = None
    markers_found: int = 0
    method: str = METHOD_NONE


def align_scan_page(
    page_image: Image.Image,
    manifest_page: ManifestPageGeometry | None = None,
    dpi: float = 200,
) -> tuple[Image.Image, bool, str | None]:
    """Alinha a página escaneada aos cantos de referência.

    Mantém a forma de retorno `(imagem, sucesso, motivo_falha)` que o worker já
    consome. Para o resultado completo — desalinhamento, deformação de
    perspectiva, rotação, método usado, quantos marcadores foram achados — use
    `align_page_with_manifest`.
    """
    result = align_page_with_manifest(page_image, manifest_page, dpi=dpi)
    return result.image, result.ok, result.reason


def align_page_with_manifest(
    page_image: Image.Image,
    manifest_page: ManifestPageGeometry | None,
    dpi: float = 200,
    correct: bool = True,
) -> AlignmentResult:
    """Detecta os fiduciais e devolve a página endireitada.

    `correct=False` mede sem corrigir — útil para comparar o antes e o depois.
    """
    if manifest_page is None or not manifest_page.fiducials:
        # Sem referência não há como alinhar. Devolver falha aqui marcaria para
        # revisão toda prova sem manifesto, que é justamente o caso em que o
        # sistema já funcionava.
        return AlignmentResult(image=page_image, ok=True, method=METHOD_NONE)

    try:
        import cv2  # noqa: PLC0415 — opcional no ambiente de teste sem opencv
    except ImportError:
        logger.warning("opencv não instalado; alinhamento de página desativado.")
        return AlignmentResult(image=page_image, ok=True, method=METHOD_NONE)

    expected = _expected_centers_px(manifest_page, dpi)
    scale = dpi / 72.0
    target_size = (
        max(1, int(round(manifest_page.page_width_pt * scale))),
        max(1, int(round(manifest_page.page_height_pt * scale))),
    )
    if len(expected) < MIN_MARKERS_FOR_HOMOGRAPHY:
        return AlignmentResult(
            image=page_image,
            ok=True,
            reason="Manifesto sem os quatro fiduciais; alinhamento não aplicado.",
            method=METHOD_NONE,
        )

    if manifest_page.has_aruco:
        found, method = _detect_aruco(page_image, cv2), METHOD_ARUCO
    else:
        found, method = _detect_squares(page_image, expected, cv2), METHOD_SQUARES

    matched = [(found[key], expected[key]) for key in expected if key in found]
    if len(matched) < MIN_MARKERS_FOR_HOMOGRAPHY:
        return _detection_failed(page_image, manifest_page, len(matched), method)

    source = np.float32([point for point, _ in matched])
    target = np.float32([point for _, point in matched])
    matrix = cv2.getPerspectiveTransform(source[:4], target[:4])

    misalignment = float(np.linalg.norm(source - target, axis=1).mean())
    residual, rotation = _perspective_residual(source, target, cv2)

    corrected = page_image
    if correct:
        # A saída tem o tamanho da PÁGINA no DPI pedido, não o da entrada: assim
        # a mesma imagem serve para os recortes por manifesto, independentemente
        # de como a folha foi enquadrada na captura.
        warped = cv2.warpPerspective(
            np.array(page_image.convert("RGB")),
            matrix,
            target_size,
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        )
        corrected = Image.fromarray(warped)

    # Medido sempre sobre a página como ela chegou, corrigindo-a ou não: é o
    # estado de entrada que diz o quanto se deve desconfiar do resultado.
    too_distorted = residual > MAX_PERSPECTIVE_RESIDUAL_PX
    return AlignmentResult(
        image=corrected,
        ok=not too_distorted,
        reason=(
            f"Deformação de perspectiva alta ({residual:.1f} px); página fotografada "
            "em ângulo, com resolução variando ao longo da folha."
            if too_distorted
            else None
        ),
        misalignment_px=misalignment,
        perspective_residual_px=residual,
        rotation_deg=rotation,
        markers_found=len(matched),
        method=method,
    )


def _detection_failed(
    page_image: Image.Image,
    manifest_page: ManifestPageGeometry,
    found: int,
    method: str,
) -> AlignmentResult:
    """Marcadores insuficientes. Reprovar ou não depende de sabermos que existem."""
    if manifest_page.has_aruco:
        return AlignmentResult(
            image=page_image,
            ok=False,
            reason=(
                f"Apenas {found} de {MIN_MARKERS_FOR_HOMOGRAPHY} marcadores encontrados; "
                "página cortada, muito torta ou de outra prova."
            ),
            markers_found=found,
            method=method,
        )

    # Layout antigo: os quadrados são difíceis de detectar e reprovar aqui
    # inundaria a revisão manual com páginas legíveis.
    logger.info("Fiduciais quadrados não localizados (%d/%d); seguindo sem alinhar.", found, 4)
    return AlignmentResult(
        image=page_image,
        ok=True,
        reason=None,
        markers_found=found,
        method=method,
    )


def _expected_centers_px(
    manifest_page: ManifestPageGeometry,
    dpi: float,
) -> dict[int, tuple[float, float]]:
    """Centros esperados dos fiduciais, em pixels da **página de destino**.

    O alvo é o sistema de coordenadas da página do manifesto, não o da imagem
    que chegou. Derivar o tamanho da imagem de entrada só funcionaria se ela
    fosse exatamente a página — e não é, em foto de celular com mesa em volta ou
    em scanner cuja bandeja é maior que a folha. Ancorar na página é o que faz a
    correção também **enquadrar**, não só endireitar.

    Converte de pontos PDF (origem inferior esquerda) para pixels (origem
    superior esquerda).
    """
    scale = dpi / 72.0
    page_height_pt = manifest_page.page_height_pt

    centers: dict[int, tuple[float, float]] = {}
    for index, fiducial in enumerate(manifest_page.fiducials):
        key = fiducial.marker_id if fiducial.marker_id is not None else index
        x_pt, y_pt = fiducial.center_pt
        centers[key] = (x_pt * scale, (page_height_pt - y_pt) * scale)
    return centers


def _detect_aruco(page_image: Image.Image, cv2) -> dict[int, tuple[float, float]]:
    """Centros dos marcadores ArUco encontrados, por id."""
    from app.services.generator.sheet_layout import ARUCO_DICT_NAME  # noqa: PLC0415

    gray = np.array(page_image.convert("L"))
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, ARUCO_DICT_NAME))
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None:
        return {}
    return {
        int(marker_id): tuple(np.mean(corner.reshape(4, 2), axis=0).tolist())
        for marker_id, corner in zip(ids.flatten(), corners, strict=True)
    }


def _detect_squares(
    page_image: Image.Image,
    expected: dict[int, tuple[float, float]],
    cv2,
) -> dict[int, tuple[float, float]]:
    """Fiduciais quadrados do layout antigo, procurados perto de onde deveriam estar.

    Buscar a página inteira acharia todo bloco preto do enunciado. Restringir a
    busca à vizinhança da posição esperada é o que torna a detecção utilizável
    sem os ids que o ArUco fornece de graça.
    """
    gray = np.array(page_image.convert("L"))
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    found: dict[int, tuple[float, float]] = {}
    radius = max(20, int(min(page_image.width, page_image.height) * 0.04))

    for key, (cx, cy) in expected.items():
        x0 = max(0, int(cx - radius))
        y0 = max(0, int(cy - radius))
        x1 = min(page_image.width, int(cx + radius))
        y1 = min(page_image.height, int(cy + radius))
        window = binary[y0:y1, x0:x1]
        if window.size == 0:
            continue

        count, _, stats, centroids = cv2.connectedComponentsWithStats(window, connectivity=8)
        best = None
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            w = int(stats[label, cv2.CC_STAT_WIDTH])
            h = int(stats[label, cv2.CC_STAT_HEIGHT])
            if area < 25 or w == 0 or h == 0:
                continue
            # Quadrado: proporção perto de 1 e bem preenchido.
            if not 0.6 <= w / h <= 1.6:
                continue
            if area / float(w * h) < 0.7:
                continue
            if best is None or area > best[0]:
                best = (area, centroids[label])

        if best is not None:
            found[key] = (x0 + float(best[1][0]), y0 + float(best[1][1]))

    return found


def _perspective_residual(source: np.ndarray, target: np.ndarray, cv2) -> tuple[float, float]:
    """Separa o que é rotação/escala do que é deformação de perspectiva.

    Uma similaridade (rotação + escala + translação) absorve tudo que um scanner
    bem-comportado introduz. O que ela **não** absorve é perspectiva — página
    fotografada em ângulo. Esse resíduo é o sinal de qualidade útil, ao contrário
    do erro de reprojeção da homografia, que é zero por construção com quatro
    pontos.

    Retorna (resíduo em px, rotação em graus).
    """
    matrix, _ = cv2.estimateAffinePartial2D(
        source.reshape(-1, 1, 2),
        target.reshape(-1, 1, 2),
        method=cv2.LMEDS,
    )
    if matrix is None:
        return 0.0, 0.0

    homogeneous = np.hstack([source, np.ones((len(source), 1), dtype=np.float32)])
    projected = homogeneous @ matrix.T
    residual = float(np.linalg.norm(projected - target, axis=1).mean())
    rotation = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    return residual, rotation
