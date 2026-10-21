# pdi_lab — Laboratórios M2.1 e M2.2

Processamento de Imagens 2026-02 · UNIVALI · Mateus Rachadel Lohn

Entrega consolidada de **um único projeto** com duas operações:

| Lab | Operação | O que faz |
|---|---|---|
| M2.1 | `segment` | gera máscara binária (0 = fundo, 255 = objeto) por `fixed`, `otsu`, `adaptive` ou `hsv` |
| M2.2 | `analyze` | rotula componentes (4/8), aplica sequência morfológica, reconta e exporta CSV/JSON/PNG |

**Linguagem:** Python 3.9+ · **Dependências:** `numpy`, `opencv-python`, `pytest` (ver `requirements.txt`).

## Preparação

Na raiz do projeto (Linux/macOS ou MSYS2 UCRT64 / PowerShell no Windows):

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

O `requirements.txt` instala o pacote em modo editável (`-e .`), então `python -m pdi_lab` funciona de qualquer pasta. Alternativa sem instalar o pacote: `PYTHONPATH=src python -m pdi_lab ...`.

## Testes

```bash
python -m pytest
```

37 testes: casos sintéticos (limiar, faixa HSV que cruza H=0, diagonal 4×8, abertura sobre ruído, fechamento de furo, máscara vazia, objeto na borda), as duas imagens reais nas duas configurações, validação de máscara binária, soma das áreas = pixels de primeiro plano, determinismo e erros com código ≠ 0.

## Execução

```bash
python -m pdi_lab --help
```

### Reproduzir tudo de uma vez

```bash
python scripts/run_study.py      # todas as máscaras, overlays, CSVs, JSONs e estágios
python scripts/make_figures.py   # figuras do REPORT.md em results/figures/
```

### M2.1 — `segment` (comandos usados no relatório)

Moedas (`coins.png`, caso difícil: iluminação irregular):

```bash
# configuração 1: limiar fixo
python -m pdi_lab --input images/input/coins.png --output images/output/coins_fixed_mask.png \
  --operation segment --method fixed --threshold 110 --overlay images/output/coins_fixed_overlay.png

# configuração 2 (escolhida): adaptativo gaussiano com pré-processamento
python -m pdi_lab --input images/input/coins.png --output images/output/coins_adaptive_mask.png \
  --operation segment --method adaptive --blur 5 --block-size 151 --c -10 \
  --overlay images/output/coins_adaptive_overlay.png

# referência adicional: Otsu
python -m pdi_lab --input images/input/coins.png --output images/output/coins_otsu_mask.png \
  --operation segment --method otsu --blur 5
```

Confeitos (`smarties.png`, caso favorável: fundo branco; objetos escuros em cinza → `--invert`):

```bash
# configuração 1: limiar fixo invertido
python -m pdi_lab --input images/input/smarties.png --output images/output/smarties_fixed_mask.png \
  --operation segment --method fixed --threshold 200 --invert \
  --overlay images/output/smarties_fixed_overlay.png

# configuração 2 (escolhida): intervalo HSV por saturação
python -m pdi_lab --input images/input/smarties.png --output images/output/smarties_hsv_mask.png \
  --operation segment --method hsv --blur 3 --hsv-lower 0,80,0 --hsv-upper 179,255,255 \
  --overlay images/output/smarties_hsv_overlay.png

# demonstração de faixa que cruza a descontinuidade do matiz (só vermelhos)
python -m pdi_lab --input images/input/smarties.png --output images/output/smarties_hsv_red_mask.png \
  --operation segment --method hsv --blur 3 --hsv-lower 170,120,60 --hsv-upper 8,255,255
```

O `segment` imprime um JSON com parâmetros efetivos (inclusive o limiar calculado pelo Otsu), contagem e proporção de pixels de primeiro plano e o conjunto de valores da máscara (sempre `[0, 255]`, verificado antes de salvar).

### M2.2 — `analyze`

```bash
python -m pdi_lab --input images/output/coins_adaptive_mask.png --output results/coins \
  --operation analyze --connectivity 8 --min-area 300 --morph-config config/coins_morph.json

python -m pdi_lab --input images/output/smarties_hsv_mask.png --output results/smarties \
  --operation analyze --connectivity 8 --min-area 150 --morph-config config/smarties_morph.json
```

A sequência também pode ser passada direto por argumento, sem arquivo:

```bash
python -m pdi_lab --input images/output/coins_adaptive_mask.png --output results/coins \
  --operation analyze --connectivity 8 --min-area 300 --morph open:ellipse:5:1,close:ellipse:7:1
```

Variantes usadas na discussão (conectividade 4, fechamento 9×9, máscara do limiar fixo) estão em `scripts/run_study.py` e saem em `results/variants/`.

## Parâmetros

| Argumento | Operação | Valores | Padrão |
|---|---|---|---|
| `--input` | ambas | imagem (segment) ou máscara binária 1 canal (analyze) | obrigatório |
| `--output` | ambas | PNG/BMP/TIFF da máscara (segment); **prefixo** (analyze) | obrigatório |
| `--operation` | — | `segment`, `analyze` | obrigatório |
| `--method` | segment | `fixed`, `otsu`, `adaptive`, `hsv` | `fixed` |
| `--threshold` | fixed | inteiro 0–255; objeto = pixel **>** T | 128 |
| `--invert` | fixed/otsu/adaptive/hsv | objeto escuro: pixel **≤** T vira 255 | desligado |
| `--blur` | todos | Gaussiano k×k, k ímpar; 0 desliga | 0 |
| `--block-size` | adaptive | ímpar ≥ 3 | 51 |
| `--c` | adaptive | constante subtraída da média local (negativo = mais exigente) | 0 |
| `--hsv-lower`, `--hsv-upper` | hsv | `H,S,V` no intervalo do OpenCV (H 0–179, S/V 0–255). Se Hmin > Hmax a faixa cruza H=0 e é dividida em [Hmin,179] ∪ [0,Hmax] | 0,0,0 / 179,255,255 |
| `--overlay` | segment | PNG opcional com máscara sobre o original | — |
| `--connectivity` | analyze | 4 ou 8 | 8 |
| `--min-area` | analyze | inteiro ≥ 0; componente com área < valor recebe `kept=false` | 0 |
| `--morph` | analyze | `op:forma:tamanho:iterações,...`; op ∈ erode, dilate, open, close; forma ∈ rect, ellipse, cross; tamanho ímpar | `open:ellipse:3:1,close:ellipse:5:1` |
| `--morph-config` | analyze | JSON com `sequence` (ver `config/`); prevalece sobre `--morph` | — |

A sequência precisa ter pelo menos 2 operações e incluir `open` ou `close`. Morfologia usa borda constante 0.

## Saídas do `analyze` (para o prefixo `results/cena`)

| Arquivo | Conteúdo |
|---|---|
| `cena_stage0_initial.png` | cópia da máscara inicial |
| `cena_stage<i>_<op>.png` | máscara após o i-ésimo estágio (ex.: `cena_stage1_open.png`, `cena_stage2_close.png`) |
| `cena_final_mask.png` | máscara final (igual ao último estágio) |
| `cena_initial.csv` / `cena_final.csv` | `label,area,x,y,width,height,cx,cy,kept` na conectividade escolhida; fundo fora |
| `cena_initial_labels.png` / `cena_labels.png` | rótulos coloridos; caixa verde = mantido, vermelha = removido pelo `--min-area` |
| `cena_summary.json` | conectividade, sequência e parâmetros, contagens brutas/filtradas e áreas antes/depois (em 4 e 8) |

## Códigos de saída

`0` sucesso · `1` erro de dados/parâmetro (arquivo inexistente, imagem ilegível, método/operação desconhecida, valor fora do intervalo, máscara não binária, JPEG na saída) · `2` argumento ausente ou de tipo inválido · `3` erro interno do OpenCV. Mensagens vão para `stderr` começando com `erro:`.

## Estrutura

```text
lab_m2_mateus_lohn/
├── README.md  REPORT.md  AI_USAGE.md  lab.json  requirements.txt  pyproject.toml
├── src/pdi_lab/      cli.py, segment.py (M2.1), analyze.py (M2.2), io_utils.py
├── tests/            test_pdi_lab.py
├── config/           sequências morfológicas em JSON
├── scripts/          run_study.py, make_figures.py
├── images/input/     originais sem alteração (coins.png, smarties.png)
├── images/output/    máscaras e overlays da M2.1
└── results/          saídas da M2.2, variantes e figuras
```
