"""Interface de linha de comando do pdi_lab (operações segment e analyze)."""
from __future__ import annotations

import argparse
import json
import sys

import cv2

from . import analyze as an
from . import segment as sg
from .io_utils import LabError, mask_stats, read_image, validate_mask, write_image

OPERATIONS = ("segment", "analyze")


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # erro de argumento -> código 2 com mensagem clara
        self.print_usage(sys.stderr)
        print(f"erro: {message}", file=sys.stderr)
        sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="pdi_lab", description="Laboratórios M2.1 (segment) e M2.2 (analyze).")
    p.add_argument("--input", required=True, help="imagem de entrada (segment) ou máscara binária (analyze)")
    p.add_argument("--output", required=True, help="arquivo PNG da máscara (segment) ou prefixo de saída (analyze)")
    p.add_argument("--operation", required=True, help="segment | analyze")

    g = p.add_argument_group("segment (M2.1)")
    g.add_argument("--method", default="fixed", help="fixed | otsu | adaptive | hsv (padrão: fixed)")
    g.add_argument("--threshold", type=int, default=128, help="limiar fixo em [0,255] (padrão: 128)")
    g.add_argument("--invert", action="store_true", help="objeto escuro: pixel <= T vira 255")
    g.add_argument("--blur", type=int, default=0, help="pré-processamento: Gaussiano k×k, k ímpar; 0 desliga")
    g.add_argument("--block-size", type=int, default=51, help="adaptive: vizinhança ímpar >= 3 (padrão: 51)")
    g.add_argument("--c", type=float, default=0.0, help="adaptive: constante subtraída da média (padrão: 0)")
    g.add_argument("--hsv-lower", default="0,0,0", help="hsv: H,S,V mínimos (H 0-179, S/V 0-255)")
    g.add_argument("--hsv-upper", default="179,255,255", help="hsv: H,S,V máximos; Hmin > Hmax = faixa que cruza 0")
    g.add_argument("--overlay", default=None, help="opcional: PNG com a sobreposição máscara/original")

    a = p.add_argument_group("analyze (M2.2)")
    a.add_argument("--connectivity", type=int, default=8, help="4 ou 8 (padrão: 8)")
    a.add_argument("--min-area", type=int, default=0, help="área mínima em pixels para manter (padrão: 0)")
    a.add_argument("--morph", default=None,
                   help=f"sequência op:forma:tam:iter,... (padrão: {an.DEFAULT_SEQUENCE})")
    a.add_argument("--morph-config", default=None, help="arquivo JSON com a chave 'sequence' (prevalece sobre --morph)")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.operation not in OPERATIONS:
            raise LabError(f"operação desconhecida: '{args.operation}' (use {', '.join(OPERATIONS)})")

        if args.operation == "segment":
            img = read_image(args.input, cv2.IMREAD_COLOR if args.method == "hsv" else cv2.IMREAD_UNCHANGED)
            mask, params = sg.segment(
                img, args.method, threshold=args.threshold, invert=args.invert, blur=args.blur,
                block_size=args.block_size, c=args.c, hsv_lower=args.hsv_lower, hsv_upper=args.hsv_upper,
            )
            validate_mask(mask, img.shape)
            write_image(args.output, mask)
            if args.overlay:
                write_image(args.overlay, sg.overlay(img, mask))
            print(json.dumps({"input": args.input, "output": args.output, "params": params,
                              "stats": mask_stats(mask)}, ensure_ascii=False))
            return 0

        # analyze
        mask = read_image(args.input, cv2.IMREAD_UNCHANGED)
        if args.morph_config:
            seq, _ = an.load_sequence_config(args.morph_config)
            source = args.morph_config
        else:
            seq = an.parse_sequence(args.morph or an.DEFAULT_SEQUENCE)
            source = f"--morph {args.morph or an.DEFAULT_SEQUENCE}"
        summary = an.analyze(mask, args.output, connectivity=args.connectivity,
                             min_area=args.min_area, sequence=seq, config_source=source)
        s0, s1 = summary["initial"], summary["final"]
        print(json.dumps({
            "connectivity": args.connectivity, "min_area": args.min_area,
            "initial_raw": s0["selected"]["components_raw"], "initial_filtered": s0["selected"]["components_filtered"],
            "final_raw": s1["selected"]["components_raw"], "final_filtered": s1["selected"]["components_filtered"],
            "initial_c4_c8": [s0["by_connectivity"]["4"]["components_raw"], s0["by_connectivity"]["8"]["components_raw"]],
        }, ensure_ascii=False))
        return 0

    except LabError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1
    except cv2.error as e:
        print(f"erro do OpenCV: {e}", file=sys.stderr)
        return 3


def main() -> None:
    sys.exit(run())
