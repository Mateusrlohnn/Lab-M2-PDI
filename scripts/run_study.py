"""Reproduz todas as saídas da M2.1 e M2.2 chamando o pdi_lab pela CLI.

Uso (na raiz do projeto, com o ambiente preparado):  python scripts/run_study.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
ENV = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))

SEG = [
    # M2.1 — duas configurações por imagem (+ Otsu como referência)
    ("coins", "fixed",    ["--method", "fixed", "--threshold", "110"]),
    ("coins", "otsu",     ["--method", "otsu", "--blur", "5"]),
    ("coins", "adaptive", ["--method", "adaptive", "--blur", "5", "--block-size", "151", "--c", "-10"]),
    ("smarties", "fixed", ["--method", "fixed", "--threshold", "200", "--invert"]),
    ("smarties", "otsu",  ["--method", "otsu", "--invert"]),
    ("smarties", "hsv",   ["--method", "hsv", "--blur", "3", "--hsv-lower", "0,80,0", "--hsv-upper", "179,255,255"]),
    # Demonstração da faixa que cruza H=0 (apenas confeitos vermelhos)
    ("smarties", "hsv_red", ["--method", "hsv", "--blur", "3", "--hsv-lower", "170,120,60", "--hsv-upper", "8,255,255"]),
]

ANALYZE = [
    # (nome do caso, máscara de trabalho, prefixo, conectividade, min-area, config)
    ("coins",    "images/output/coins_adaptive_mask.png", "results/coins",    "8", "300", "config/coins_morph.json"),
    ("smarties", "images/output/smarties_hsv_mask.png",   "results/smarties", "8", "150", "config/smarties_morph.json"),
    # Variantes de estudo
    ("coins_c4", "images/output/coins_adaptive_mask.png", "results/variants/coins_c4", "4", "300", "config/coins_morph.json"),
    ("smarties_c4", "images/output/smarties_hsv_mask.png", "results/variants/smarties_c4", "4", "150", "config/smarties_morph.json"),
    ("coins_close9", "images/output/coins_adaptive_mask.png", "results/variants/coins_close9", "8", "300", "config/coins_morph_close9.json"),
    ("coins_fixed", "images/output/coins_fixed_mask.png", "results/variants/coins_fixed", "8", "300", "config/coins_morph.json"),
]


def run(args):
    cmd = [sys.executable, "-m", "pdi_lab", *args]
    print("$ pdi_lab " + " ".join(args))
    r = subprocess.run(cmd, env=ENV, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        sys.exit(r.returncode)


for name, cfg, extra in SEG:
    run(["--input", f"images/input/{name}.png", "--output", f"images/output/{name}_{cfg}_mask.png",
         "--operation", "segment", "--overlay", f"images/output/{name}_{cfg}_overlay.png", *extra])

for _, mask, prefix, conn, ma, cfg in ANALYZE:
    run(["--input", mask, "--output", prefix, "--operation", "analyze",
         "--connectivity", conn, "--min-area", ma, "--morph-config", cfg])
