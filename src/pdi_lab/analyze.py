"""M2.2 — Componentes conexos e sequência morfológica."""
from __future__ import annotations

import csv
import json
import os

import cv2
import numpy as np

from .io_utils import LabError, mask_stats, validate_mask, write_image

OPS = {
    "erode": None,
    "dilate": None,
    "open": cv2.MORPH_OPEN,
    "close": cv2.MORPH_CLOSE,
}
SHAPES = {"rect": cv2.MORPH_RECT, "ellipse": cv2.MORPH_ELLIPSE, "cross": cv2.MORPH_CROSS}
DEFAULT_SEQUENCE = "open:ellipse:3:1,close:ellipse:5:1"


def parse_sequence(text: str) -> list[dict]:
    """Formato: op:forma:tamanho:iteracoes separados por vírgula.

    Ex.: open:ellipse:3:1,close:ellipse:5:1
    """
    steps = []
    for raw in [p.strip() for p in text.split(",") if p.strip()]:
        parts = raw.split(":")
        if len(parts) != 4:
            raise LabError(f"etapa morfológica inválida '{raw}' (use op:forma:tamanho:iteracoes)")
        op, shape, size, iters = parts
        if op not in OPS:
            raise LabError(f"operação morfológica desconhecida '{op}' (use {', '.join(OPS)})")
        if shape not in SHAPES:
            raise LabError(f"forma de elemento estruturante desconhecida '{shape}' (use {', '.join(SHAPES)})")
        try:
            size_i, iters_i = int(size), int(iters)
        except ValueError:
            raise LabError(f"tamanho e iterações devem ser inteiros em '{raw}'") from None
        if size_i < 1 or size_i % 2 == 0:
            raise LabError(f"tamanho do elemento estruturante deve ser ímpar >= 1 em '{raw}'")
        if iters_i < 1:
            raise LabError(f"iterações devem ser >= 1 em '{raw}'")
        steps.append({"op": op, "shape": shape, "size": size_i, "iterations": iters_i})
    if len(steps) < 2:
        raise LabError("a sequência morfológica precisa de pelo menos 2 operações")
    if not any(s["op"] in ("open", "close") for s in steps):
        raise LabError("a sequência morfológica precisa incluir abertura (open) ou fechamento (close)")
    return steps


def load_sequence_config(path: str) -> tuple[list[dict], dict]:
    if not os.path.isfile(path):
        raise LabError(f"arquivo de configuração não encontrado: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise LabError(f"configuração JSON inválida em {path}: {e}") from None
    seq = cfg.get("sequence")
    if not isinstance(seq, list):
        raise LabError(f"{path} deve conter a chave 'sequence' como lista")
    text = ",".join(f"{s['op']}:{s['shape']}:{s['size']}:{s.get('iterations', 1)}" for s in seq)
    return parse_sequence(text), cfg


def apply_step(mask: np.ndarray, step: dict) -> np.ndarray:
    k = cv2.getStructuringElement(SHAPES[step["shape"]], (step["size"], step["size"]))
    if step["op"] == "erode":
        return cv2.erode(mask, k, iterations=step["iterations"])
    if step["op"] == "dilate":
        return cv2.dilate(mask, k, iterations=step["iterations"])
    # Borda constante 0 para não criar objeto artificial na borda.
    return cv2.morphologyEx(
        mask, OPS[step["op"]], k, iterations=step["iterations"],
        borderType=cv2.BORDER_CONSTANT, borderValue=0,
    )


def components(mask: np.ndarray, connectivity: int, min_area: int = 0) -> tuple[list[dict], np.ndarray]:
    if connectivity not in (4, 8):
        raise LabError(f"--connectivity deve ser 4 ou 8, recebido: {connectivity}")
    n, labels, stats, cents = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8), connectivity=connectivity
    )
    rows = []
    for lab in range(1, n):  # 0 = fundo, fica de fora
        x, y, w, h, area = (int(v) for v in stats[lab])
        rows.append({
            "label": lab, "area": area, "x": x, "y": y, "width": w, "height": h,
            "cx": round(float(cents[lab][0]), 2), "cy": round(float(cents[lab][1]), 2),
            "kept": area >= min_area,
        })
    return rows, labels


def write_csv(path: str, rows: list[dict]) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["label", "area", "x", "y", "width", "height", "cx", "cy", "kept"])
        for r in rows:
            w.writerow([r["label"], r["area"], r["x"], r["y"], r["width"], r["height"],
                        r["cx"], r["cy"], "true" if r["kept"] else "false"])


def _color(lab: int) -> tuple[int, int, int]:
    # Cor determinística por rótulo (sem aleatoriedade).
    hue = (lab * 37) % 180
    px = np.uint8([[[hue, 220, 255]]])
    b, g, r = cv2.cvtColor(px, cv2.COLOR_HSV2BGR)[0, 0]
    return int(b), int(g), int(r)


def render_labels(labels: np.ndarray, rows: list[dict]) -> np.ndarray:
    """Rótulos coloridos; caixa verde = mantido, vermelha = removido pelo filtro."""
    out = np.zeros((*labels.shape, 3), np.uint8)
    for r in rows:
        out[labels == r["label"]] = _color(r["label"])
    for r in rows:
        color = (0, 255, 0) if r["kept"] else (0, 0, 255)
        cv2.rectangle(out, (r["x"], r["y"]), (r["x"] + r["width"] - 1, r["y"] + r["height"] - 1), color, 1)
        if r["kept"]:
            cv2.putText(out, str(r["label"]), (r["x"], max(r["y"] - 2, 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def _counts(rows: list[dict]) -> dict:
    kept = [r for r in rows if r["kept"]]
    return {
        "components_raw": len(rows),
        "components_filtered": len(kept),
        "area_total_raw": int(sum(r["area"] for r in rows)),
        "area_total_filtered": int(sum(r["area"] for r in kept)),
    }


def analyze(mask: np.ndarray, prefix: str, connectivity: int = 8, min_area: int = 0,
            sequence: list[dict] | None = None, config_source: str | None = None) -> dict:
    validate_mask(mask)
    if min_area < 0:
        raise LabError(f"--min-area deve ser inteiro não negativo, recebido: {min_area}")
    if connectivity not in (4, 8):
        raise LabError(f"--connectivity deve ser 4 ou 8, recebido: {connectivity}")
    sequence = sequence or parse_sequence(DEFAULT_SEQUENCE)

    # 1) cópia da máscara inicial
    write_image(f"{prefix}_stage0_initial.png", mask)

    # 2) rotulação da máscara inicial, 4 e 8, mesmos parâmetros
    init = {c: components(mask, c, min_area) for c in (4, 8)}
    init_rows, init_labels = init[connectivity]
    write_csv(f"{prefix}_initial.csv", init_rows)
    write_image(f"{prefix}_initial_labels.png", render_labels(init_labels, init_rows))

    # 3) sequência morfológica, um PNG por estágio
    stages = []
    cur = mask
    for i, step in enumerate(sequence, start=1):
        cur = apply_step(cur, step)
        name = f"{prefix}_stage{i}_{step['op']}.png"
        write_image(name, cur)
        stages.append({**step, "order": i, "file": os.path.basename(name),
                       "foreground_pixels": int(np.count_nonzero(cur))})
    final = cur
    write_image(f"{prefix}_final_mask.png", final)

    # 4) recontagem
    fin = {c: components(final, c, min_area) for c in (4, 8)}
    fin_rows, fin_labels = fin[connectivity]
    write_csv(f"{prefix}_final.csv", fin_rows)
    write_image(f"{prefix}_labels.png", render_labels(fin_labels, fin_rows))

    summary = {
        "connectivity": connectivity,
        "min_area": min_area,
        "foreground_convention": "objeto=255, fundo=0",
        "morphology_config": config_source or "argumento --morph",
        "sequence": stages,
        "initial": {
            "mask": mask_stats(mask),
            "selected": _counts(init_rows),
            "by_connectivity": {str(c): _counts(init[c][0]) for c in (4, 8)},
        },
        "final": {
            "mask": mask_stats(final),
            "selected": _counts(fin_rows),
            "by_connectivity": {str(c): _counts(fin[c][0]) for c in (4, 8)},
        },
    }
    with open(f"{prefix}_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return summary
