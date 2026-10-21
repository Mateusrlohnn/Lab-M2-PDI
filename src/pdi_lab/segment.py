"""M2.1 — Geração de máscara binária (fixed, otsu, adaptive, hsv)."""
from __future__ import annotations

import cv2
import numpy as np

from .io_utils import LabError, to_bgr, to_gray

METHODS = ("fixed", "otsu", "adaptive", "hsv")


def parse_hsv(text: str, name: str) -> tuple[int, int, int]:
    try:
        h, s, v = (int(p) for p in text.split(","))
    except ValueError:
        raise LabError(f"{name} deve ter o formato H,S,V com inteiros, recebido: '{text}'") from None
    if not (0 <= h <= 179 and 0 <= s <= 255 and 0 <= v <= 255):
        raise LabError(f"{name} fora do intervalo do OpenCV (H 0-179, S 0-255, V 0-255): '{text}'")
    return h, s, v


def preprocess(img: np.ndarray, blur: int) -> np.ndarray:
    if blur < 0 or (blur > 0 and blur % 2 == 0):
        raise LabError(f"--blur deve ser 0 (desligado) ou ímpar positivo, recebido: {blur}")
    if blur > 0:
        return cv2.GaussianBlur(img, (blur, blur), 0)
    return img


def segment(
    img: np.ndarray,
    method: str,
    threshold: int = 128,
    invert: bool = False,
    blur: int = 0,
    block_size: int = 51,
    c: float = 0.0,
    hsv_lower: str = "0,0,0",
    hsv_upper: str = "179,255,255",
) -> tuple[np.ndarray, dict]:
    """Retorna (máscara 0/255, parâmetros efetivos).

    Convenção: 255 = objeto. Para limiares em cinza, sem --invert o objeto
    é o que é MAIS CLARO que o limiar (pixel > T -> 255); com --invert,
    o objeto é o que é mais escuro (pixel <= T -> 255).
    """
    if method not in METHODS:
        raise LabError(f"método desconhecido: '{method}' (use {', '.join(METHODS)})")

    params: dict = {"method": method, "blur": blur}
    work = preprocess(img, blur)
    ttype = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY

    if method == "fixed":
        if not 0 <= threshold <= 255:
            raise LabError(f"--threshold deve estar em [0, 255], recebido: {threshold}")
        gray = to_gray(work)
        _, mask = cv2.threshold(gray, threshold, 255, ttype)
        params.update(threshold=threshold, invert=invert)

    elif method == "otsu":
        gray = to_gray(work)
        t, mask = cv2.threshold(gray, 0, 255, ttype | cv2.THRESH_OTSU)
        params.update(otsu_threshold=float(t), invert=invert)

    elif method == "adaptive":
        if block_size < 3 or block_size % 2 == 0:
            raise LabError(f"--block-size deve ser ímpar e >= 3, recebido: {block_size}")
        gray = to_gray(work)
        mask = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, ttype, block_size, c
        )
        params.update(block_size=block_size, c=c, invert=invert, adaptive="gaussian")

    else:  # hsv
        lo = parse_hsv(hsv_lower, "--hsv-lower")
        hi = parse_hsv(hsv_upper, "--hsv-upper")
        if lo[1] > hi[1] or lo[2] > hi[2]:
            raise LabError("em --hsv-lower/--hsv-upper, S e V mínimos não podem exceder os máximos")
        hsv = cv2.cvtColor(to_bgr(work), cv2.COLOR_BGR2HSV)
        if lo[0] <= hi[0]:
            mask = cv2.inRange(hsv, lo, hi)
            hue_ranges = [[lo[0], hi[0]]]
        else:
            # Faixa que cruza a descontinuidade do matiz (ex.: vermelho 170..10):
            # dividida em [Hmin, 179] e [0, Hmax].
            m1 = cv2.inRange(hsv, lo, (179, hi[1], hi[2]))
            m2 = cv2.inRange(hsv, (0, lo[1], lo[2]), hi)
            mask = cv2.bitwise_or(m1, m2)
            hue_ranges = [[lo[0], 179], [0, hi[0]]]
        if invert:
            mask = cv2.bitwise_not(mask)
        params.update(hsv_lower=list(lo), hsv_upper=list(hi), hue_ranges=hue_ranges, invert=invert)

    return mask.astype(np.uint8), params


def overlay(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Original com o primeiro plano tingido de verde e contorno vermelho."""
    base = to_bgr(img).copy()
    tint = base.copy()
    tint[mask > 0] = (0, 200, 0)
    out = cv2.addWeighted(base, 0.6, tint, 0.4, 0)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(out, contours, -1, (0, 0, 255), 1)
    return out
