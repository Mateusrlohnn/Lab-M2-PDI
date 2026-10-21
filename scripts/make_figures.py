"""Monta as figuras do REPORT.md a partir das saídas do run_study.py.

Uso: python scripts/make_figures.py   (gera results/figures/*.png)
"""
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
OUT = "results/figures"
os.makedirs(OUT, exist_ok=True)


def load(p):
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"faltando {p}; rode antes: python scripts/run_study.py")
    return im


def tile(img, title):
    pad = np.full((24, img.shape[1], 3), 255, np.uint8)
    cv2.putText(pad, title, (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return cv2.copyMakeBorder(np.vstack([pad, img]), 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(180, 180, 180))


def row(items, path):
    cv2.imwrite(path, np.hstack([tile(load(p), t) for p, t in items]))


def grid(rows, path):
    cv2.imwrite(path, np.vstack([np.hstack([tile(load(p), t) for p, t in r]) for r in rows]))


# M2.1
grid([[("images/input/coins.png", "original"),
       ("images/output/coins_fixed_mask.png", "fixed T=110"),
       ("images/output/coins_adaptive_mask.png", "adaptive bs=151 C=-10 blur5")],
      [("images/output/coins_otsu_mask.png", "otsu blur5 (T=104)"),
       ("images/output/coins_fixed_overlay.png", "overlay fixed"),
       ("images/output/coins_adaptive_overlay.png", "overlay adaptive")]],
     f"{OUT}/m21_coins.png")
grid([[("images/input/smarties.png", "original"),
       ("images/output/smarties_fixed_mask.png", "fixed T=200 inv"),
       ("images/output/smarties_hsv_mask.png", "hsv S>=80 blur3")],
      [("images/output/smarties_otsu_mask.png", "otsu inv (T=176)"),
       ("images/output/smarties_fixed_overlay.png", "overlay fixed"),
       ("images/output/smarties_hsv_overlay.png", "overlay hsv")]],
     f"{OUT}/m21_smarties.png")
row([("images/input/smarties.png", "original"),
     ("images/output/smarties_hsv_red_mask.png", "hsv vermelho H 170..8")],
    f"{OUT}/m21_smarties_red_wrap.png")

# M2.2
row([("results/coins_stage0_initial.png", "0 inicial"),
     ("results/coins_stage1_open.png", "1 open ellipse 5"),
     ("results/coins_stage2_close.png", "2 close ellipse 7"),
     ("results/coins_labels.png", "rotulos c8, min-area 300")],
    f"{OUT}/m22_coins_stages.png")
row([("results/smarties_stage0_initial.png", "0 inicial"),
     ("results/smarties_stage1_close.png", "1 close ellipse 7"),
     ("results/smarties_stage2_open.png", "2 open ellipse 15"),
     ("results/smarties_labels.png", "rotulos c8, min-area 150")],
    f"{OUT}/m22_smarties_stages.png")
row([("results/coins_labels.png", "close 7 (escolhido)"),
     ("results/variants/coins_close9_labels.png", "close 9: fusao")],
    f"{OUT}/m22_coins_close9.png")
row([("results/smarties_labels.png", "conectividade 8"),
     ("results/variants/smarties_c4_labels.png", "conectividade 4")],
    f"{OUT}/m22_smarties_c4_c8.png")
print("figuras em", OUT)
