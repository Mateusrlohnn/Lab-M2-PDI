"""Testes mínimos M2.1 e M2.2. Executar na raiz: python -m pytest"""
import csv
import json
import os
import subprocess
import sys

import cv2
import numpy as np
import pytest

from pdi_lab.analyze import analyze, apply_step, components, parse_sequence
from pdi_lab.io_utils import LabError, validate_mask
from pdi_lab.segment import segment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "images", "input")

# Configurações do estudo (as mesmas do README).
CASES = {
    "coins": {
        "fixed": ["--method", "fixed", "--threshold", "110"],
        "second": ["--method", "adaptive", "--blur", "5", "--block-size", "151", "--c", "-10"],
        "morph": "open:ellipse:5:1,close:ellipse:7:1",
        "min_area": "300",
    },
    "smarties": {
        "fixed": ["--method", "fixed", "--threshold", "200", "--invert"],
        "second": ["--method", "hsv", "--blur", "3", "--hsv-lower", "0,80,0", "--hsv-upper", "179,255,255"],
        "morph": "close:ellipse:7:1,open:ellipse:15:1",
        "min_area": "150",
    },
}


def cli(*args):
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    return subprocess.run([sys.executable, "-m", "pdi_lab", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True)


def assert_binary_mask(path, shape):
    m = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    assert m is not None
    assert m.ndim == 2, "máscara deve ter 1 canal"
    assert m.shape == shape[:2], "dimensões devem ser iguais às da entrada"
    assert set(np.unique(m).tolist()) <= {0, 255}
    return m


# ---------------------------------------------------------------- M2.1

def test_fixed_threshold_synthetic_at_and_around_threshold():
    img = np.array([[0, 119, 120, 121, 255]], np.uint8)
    mask, _ = segment(img, "fixed", threshold=120)
    # pixel > T vira objeto; pixel == T fica fundo
    assert mask.tolist() == [[0, 0, 0, 255, 255]]
    inv, _ = segment(img, "fixed", threshold=120, invert=True)
    assert inv.tolist() == [[255, 255, 255, 0, 0]]


def test_otsu_separates_two_levels():
    img = np.zeros((10, 10), np.uint8)
    img[:, 5:] = 200
    mask, p = segment(img, "otsu")
    assert np.all(mask[:, 5:] == 255) and np.all(mask[:, :5] == 0)
    assert 0 <= p["otsu_threshold"] < 200


def test_hsv_hue_wraparound():
    # vermelho com H=175 e H=5 (cruzam a descontinuidade), verde H=60
    hsv = np.array([[[175, 255, 255], [5, 255, 255], [60, 255, 255]]], np.uint8)
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    mask, p = segment(bgr, "hsv", hsv_lower="170,100,100", hsv_upper="10,255,255")
    assert mask.tolist() == [[255, 255, 0]]
    assert p["hue_ranges"] == [[170, 179], [0, 10]]


def test_validate_mask_rejects_non_binary():
    with pytest.raises(LabError):
        validate_mask(np.array([[0, 128]], np.uint8))
    with pytest.raises(LabError):
        validate_mask(np.zeros((2, 2, 3), np.uint8))


@pytest.mark.parametrize("name", list(CASES))
@pytest.mark.parametrize("config", ["fixed", "second"])
def test_real_images_both_configs(tmp_path, name, config):
    src = os.path.join(INPUT, f"{name}.png")
    out = str(tmp_path / f"{name}_{config}.png")
    r = cli("--input", src, "--output", out, "--operation", "segment", *CASES[name][config])
    assert r.returncode == 0, r.stderr
    shape = cv2.imread(src, cv2.IMREAD_UNCHANGED).shape
    m = assert_binary_mask(out, shape)
    info = json.loads(r.stdout)
    assert info["stats"]["foreground_pixels"] == int(np.count_nonzero(m))
    assert 0 < info["stats"]["foreground_ratio"] < 1


def test_fixed_threshold_limitation_on_coins(tmp_path):
    """Limitação observável: com iluminação irregular, o limiar fixo marca o
    fundo claro do canto superior esquerdo como objeto; o adaptativo não."""
    src = os.path.join(INPUT, "coins.png")
    corner = (slice(0, 25), slice(0, 60))  # região de fundo
    fx = str(tmp_path / "f.png"); ad = str(tmp_path / "a.png")
    assert cli("--input", src, "--output", fx, "--operation", "segment", *CASES["coins"]["fixed"]).returncode == 0
    assert cli("--input", src, "--output", ad, "--operation", "segment", *CASES["coins"]["second"]).returncode == 0
    f = cv2.imread(fx, 0)[corner].mean() / 255
    a = cv2.imread(ad, 0)[corner].mean() / 255
    assert f > 0.5 and a < 0.1


@pytest.mark.parametrize("args", [
    ["--input", "images/input/nao_existe.png", "--output", "x.png", "--operation", "segment"],
    ["--input", "images/input/coins.png", "--output", "x.png", "--operation", "segment", "--method", "kmeans"],
    ["--input", "images/input/coins.png", "--output", "x.png", "--operation", "segment", "--threshold", "300"],
    ["--input", "images/input/coins.png", "--output", "x.png", "--operation", "segment", "--method", "adaptive", "--block-size", "10"],
    ["--input", "images/input/coins.png", "--output", "x.png", "--operation", "segment", "--blur", "4"],
    ["--input", "images/input/smarties.png", "--output", "x.png", "--operation", "segment", "--method", "hsv", "--hsv-lower", "200,0,0"],
    ["--input", "images/input/coins.png", "--output", "x.jpg", "--operation", "segment"],
    ["--input", "images/input/coins.png", "--output", "x.png", "--operation", "blur"],
    ["--input", "images/input/coins.png", "--output", "x.png", "--operation", "segment", "--threshold", "abc"],
])
def test_errors_return_nonzero(args, tmp_path):
    args = [a if a != "x.png" and a != "x.jpg" else str(tmp_path / a) for a in args]
    r = cli(*args)
    assert r.returncode != 0
    assert "erro" in r.stderr
    assert not os.path.exists(str(tmp_path / "x.png"))


def test_corrupted_image_fails(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"isto nao e uma imagem")
    r = cli("--input", str(bad), "--output", str(tmp_path / "o.png"), "--operation", "segment")
    assert r.returncode != 0


# ---------------------------------------------------------------- M2.2

def test_diagonal_4_vs_8():
    m = np.zeros((4, 4), np.uint8)
    m[1, 1] = m[2, 2] = 255
    assert len(components(m, 4)[0]) == 2
    assert len(components(m, 8)[0]) == 1


def test_opening_removes_isolated_noise():
    m = np.zeros((30, 30), np.uint8)
    m[8:22, 8:22] = 255          # região principal 14x14
    m[2, 27] = 255               # ruído isolado
    m[27, 3] = 255
    out = apply_step(m, {"op": "open", "shape": "rect", "size": 3, "iterations": 1})
    assert len(components(m, 8)[0]) == 3
    assert len(components(out, 8)[0]) == 1
    assert np.array_equal(out[8:22, 8:22], m[8:22, 8:22])  # quadrado preservado


def test_closing_fills_small_hole():
    m = np.zeros((30, 30), np.uint8)
    m[5:25, 5:25] = 255
    m[14:16, 14:16] = 0          # furo 2x2
    out = apply_step(m, {"op": "close", "shape": "rect", "size": 5, "iterations": 1})
    assert np.all(out[14:16, 14:16] == 255)
    assert np.count_nonzero(out) == 20 * 20


def test_empty_mask_counts_zero(tmp_path):
    s = analyze(np.zeros((20, 20), np.uint8), str(tmp_path / "vazia"))
    assert s["initial"]["selected"]["components_raw"] == 0
    assert s["final"]["selected"]["components_raw"] == 0
    with open(tmp_path / "vazia_final.csv") as f:
        assert len(list(csv.reader(f))) == 1  # só cabeçalho


def test_object_touching_border():
    m = np.zeros((20, 20), np.uint8)
    m[0:5, 0:6] = 255
    rows, _ = components(m, 8)
    assert len(rows) == 1
    r = rows[0]
    assert (r["x"], r["y"], r["width"], r["height"], r["area"]) == (0, 0, 6, 5, 30)
    # abertura não deve apagar nem criar objeto por causa da borda
    out = apply_step(m, {"op": "open", "shape": "rect", "size": 3, "iterations": 1})
    assert np.count_nonzero(out) == 30


def test_min_area_marks_kept(tmp_path):
    m = np.zeros((20, 20), np.uint8)
    m[2:8, 2:8] = 255   # 36 px
    m[15, 15] = 255     # 1 px
    rows, _ = components(m, 8, min_area=20)
    assert sorted((r["area"], r["kept"]) for r in rows) == [(1, False), (36, True)]


@pytest.mark.parametrize("extra", [
    ["--connectivity", "6"],
    ["--min-area", "-1"],
    ["--morph", "open:ellipse:3:1"],                     # só uma operação
    ["--morph", "erode:rect:3:1,dilate:rect:3:1"],        # sem open/close
    ["--morph", "open:ellipse:4:1,close:ellipse:5:1"],    # tamanho par
    ["--morph", "open:star:3:1,close:ellipse:5:1"],
    ["--morph-config", "config/nao_existe.json"],
])
def test_analyze_invalid_params(tmp_path, extra):
    mask = tmp_path / "m.png"
    cv2.imwrite(str(mask), np.zeros((10, 10), np.uint8))
    r = cli("--input", str(mask), "--output", str(tmp_path / "r"), "--operation", "analyze", *extra)
    assert r.returncode != 0
    assert "erro" in r.stderr


def test_analyze_rejects_non_binary_mask(tmp_path):
    p = tmp_path / "g.png"
    cv2.imwrite(str(p), np.full((10, 10), 128, np.uint8))
    r = cli("--input", str(p), "--output", str(tmp_path / "r"), "--operation", "analyze")
    assert r.returncode != 0


@pytest.mark.parametrize("name", list(CASES))
def test_full_pipeline_real_images(tmp_path, name):
    case = CASES[name]
    mask = str(tmp_path / f"{name}_mask.png")
    r = cli("--input", os.path.join(INPUT, f"{name}.png"), "--output", mask,
            "--operation", "segment", *case["second"])
    assert r.returncode == 0, r.stderr
    prefix = str(tmp_path / name)
    r = cli("--input", mask, "--output", prefix, "--operation", "analyze",
            "--connectivity", "8", "--min-area", case["min_area"], "--morph", case["morph"])
    assert r.returncode == 0, r.stderr

    for suf in ("_stage0_initial.png", "_stage1_" + case["morph"].split(":")[0] + ".png",
                "_final_mask.png", "_initial.csv", "_final.csv", "_labels.png", "_summary.json"):
        assert os.path.isfile(prefix + suf), suf

    m = cv2.imread(mask, 0)
    with open(prefix + "_initial.csv") as f:
        rows = list(csv.DictReader(f))
    # soma das áreas brutas == pixels de primeiro plano da máscara (antes do filtro)
    assert sum(int(r["area"]) for r in rows) == int(np.count_nonzero(m))
    assert all(r["kept"] in ("true", "false") for r in rows)
    assert all(int(r["label"]) > 0 for r in rows)  # fundo fora do CSV

    with open(prefix + "_summary.json") as f:
        s = json.load(f)
    fm = cv2.imread(prefix + "_final_mask.png", 0)
    assert s["final"]["selected"]["area_total_raw"] == int(np.count_nonzero(fm))
    assert s["connectivity"] == 8 and len(s["sequence"]) >= 2


def test_deterministic(tmp_path):
    src = os.path.join(INPUT, "smarties.png")
    a, b = str(tmp_path / "a.png"), str(tmp_path / "b.png")
    for out in (a, b):
        assert cli("--input", src, "--output", out, "--operation", "segment", *CASES["smarties"]["second"]).returncode == 0
    assert np.array_equal(cv2.imread(a, 0), cv2.imread(b, 0))


def test_config_file_matches_arg(tmp_path):
    seq_text = "open:ellipse:5:1,close:ellipse:7:1"
    m = np.zeros((40, 40), np.uint8)
    m[5:20, 5:20] = 255
    m[30, 30] = 255
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"sequence": [
        {"op": "open", "shape": "ellipse", "size": 5, "iterations": 1},
        {"op": "close", "shape": "ellipse", "size": 7, "iterations": 1}]}))
    from pdi_lab.analyze import load_sequence_config
    assert load_sequence_config(str(cfg))[0] == parse_sequence(seq_text)
