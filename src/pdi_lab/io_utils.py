"""Leitura, escrita e validação de imagens."""
from __future__ import annotations

import os

import cv2
import numpy as np


class LabError(Exception):
    """Erro de uso ou de dados; vira código de saída diferente de 0."""


def read_image(path: str, flags: int = cv2.IMREAD_UNCHANGED) -> np.ndarray:
    if not os.path.isfile(path):
        raise LabError(f"arquivo de entrada não encontrado: {path}")
    img = cv2.imread(path, flags)
    if img is None:
        raise LabError(f"falha ao abrir a imagem: {path}")
    return img


def write_image(path: str, img: np.ndarray) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".png", ".bmp", ".tif", ".tiff", ".pgm"):
        raise LabError(f"formato de saída deve ser sem perdas (PNG recomendado), recebido: '{ext or path}'")
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    if not cv2.imwrite(path, img):
        raise LabError(f"falha ao salvar a imagem: {path}")


def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    raise LabError(f"quantidade de canais inesperada: {img.shape[2]}")


def to_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if img.shape[2] == 3:
        return img
    raise LabError(f"quantidade de canais inesperada: {img.shape[2]}")


def validate_mask(mask: np.ndarray, ref_shape: tuple[int, int] | None = None) -> None:
    """Confirma máscara binária: 1 canal, uint8, valores apenas em {0, 255}."""
    if mask.ndim != 2:
        raise LabError(f"máscara deve ter 1 canal, tem {mask.shape[2]}")
    if mask.dtype != np.uint8:
        raise LabError(f"máscara deve ser uint8, é {mask.dtype}")
    values = set(np.unique(mask).tolist())
    if not values <= {0, 255}:
        extra = sorted(values - {0, 255})[:5]
        raise LabError(f"máscara não binária: valores fora de {{0,255}} encontrados, ex.: {extra}")
    if ref_shape is not None and mask.shape[:2] != tuple(ref_shape[:2]):
        raise LabError(f"dimensões da máscara {mask.shape[:2]} diferem da entrada {tuple(ref_shape[:2])}")


def mask_stats(mask: np.ndarray) -> dict:
    fg = int(np.count_nonzero(mask))
    total = int(mask.size)
    return {
        "width": int(mask.shape[1]),
        "height": int(mask.shape[0]),
        "channels": 1,
        "foreground_pixels": fg,
        "total_pixels": total,
        "foreground_ratio": round(fg / total, 6) if total else 0.0,
        "values": sorted(int(v) for v in np.unique(mask)),
    }
