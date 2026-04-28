from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)


def normalize_page_image(image_path: str) -> str:
    """
    Gera uma versão normalizada da página para leitura visual multimodal.

    A normalização é conservadora: corrige EXIF, melhora contraste e nitidez,
    sem remover informação manuscrita nem depender de OCR clássico.
    """
    source = Path(image_path)
    if not source.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {source}")

    with Image.open(source) as img:
        image = ImageOps.exif_transpose(img).convert("RGB")
        image = _normalize_contrast(image)

        output_path = source.with_name(f"{source.stem}_normalized.png")
        image.save(output_path, format="PNG", optimize=True)
        logger.info("Normalized exam page image: %s", output_path)
        return str(output_path)


def maybe_crop_answer_regions(image_path: str) -> dict:
    """
    Tenta encontrar regiões de resposta sem tornar o pipeline dependente disso.

    Retorna sempre fallback_image com a página inteira. Se o OpenCV detectar
    caixas grandes compatíveis com áreas de resposta, também salva crops.
    """
    source = Path(image_path)
    result = {
        "fallback_image": str(source),
        "regions": [],
        "strategy": "full_page_fallback",
        "notes": "Página inteira disponível para o modelo de visão.",
    }

    try:
        import cv2
        import numpy as np
    except ImportError:
        result["notes"] = "OpenCV indisponível; usando página inteira."
        return result

    try:
        with Image.open(source) as img:
            rgb = img.convert("RGB")
            width, height = rgb.size
            gray = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 40, 120)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            candidates: list[tuple[int, int, int, int]] = []
            page_area = width * height
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h
                if area < page_area * 0.025:
                    continue
                if w < width * 0.35 or h < height * 0.05:
                    continue
                if y < height * 0.10:
                    continue
                candidates.append((x, y, w, h))

            candidates = _dedupe_boxes(candidates)
            if not candidates:
                return result

            crop_dir = source.with_name(f"{source.stem}_answer_regions")
            crop_dir.mkdir(parents=True, exist_ok=True)
            for index, (x, y, w, h) in enumerate(candidates[:12], start=1):
                pad_x = int(w * 0.02)
                pad_y = int(h * 0.04)
                box = (
                    max(0, x - pad_x),
                    max(0, y - pad_y),
                    min(width, x + w + pad_x),
                    min(height, y + h + pad_y),
                )
                crop_path = crop_dir / f"answer_region_{index:02d}.png"
                rgb.crop(box).save(crop_path, format="PNG", optimize=True)
                result["regions"].append(
                    {
                        "index": index,
                        "image_path": str(crop_path),
                        "box": {"x": box[0], "y": box[1], "w": box[2] - box[0], "h": box[3] - box[1]},
                    }
                )

            result["strategy"] = "detected_regions_with_full_page_fallback"
            result["notes"] = "Regiões candidatas detectadas; fallback de página inteira preservado."
            return result
    except Exception as exc:
        logger.warning("Falha ao tentar recortar regiões de resposta: %s", exc)
        result["notes"] = f"Recorte automático falhou; usando página inteira. Erro: {exc}"
        return result


def _normalize_contrast(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.25)
    gray = ImageEnhance.Sharpness(gray).enhance(1.15)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    return ImageOps.colorize(gray, black="#111111", white="#ffffff")


def _dedupe_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    kept: list[tuple[int, int, int, int]] = []
    for box in boxes:
        if any(_overlap_ratio(box, other) > 0.65 for other in kept):
            continue
        kept.append(box)
    return kept


def _overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    smallest = min(aw * ah, bw * bh)
    return inter / smallest if smallest else 0.0


crop_answer_regions_if_possible = maybe_crop_answer_regions
