#!/usr/bin/env bash
# Prepara los datos del issue #103 (A4): conjuntos, Top-3 y entradas A/B. Genera la evidencia
# versionada en proyecto_de_grado/docs/evidencias_clasificacion_a4/.
# Uso (desde cualquier carpeta):  bash scripts/preparar_clasificacion_a4.sh
# Requiere: arbol git LIMPIO (para que los manifiestos digan dirty:false), GPU CUDA, y los datos
# de data/raw (dvc pull data/raw.dvc). La descarga de ACL OCL usa red solo si falta
# manifiesto_ocl.json; los articulos ya descargados en cache_ocl no se vuelven a bajar.
# Nunca sobrescribe: si una salida ya existe, ese paso se omite (borre el archivo para repetirlo).
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
unset VIRTUAL_ENV
export PYTHONPATH=.
export HF_HUB_OFFLINE=1

P=(uv run --project packages/clasificacion-funcion)
PM=(uv run --project packages/clasificacion-funcion --group modelo)
EV=proyecto_de_grado/docs/evidencias_clasificacion_a4

paso() { printf '\n==> %s\n' "$*"; }

paso "Arbol git limpio (los manifiestos registran git HEAD y dirty)"
if [ -n "$(git status --porcelain)" ] && [ "${PERMITIR_SUCIO:-0}" != "1" ]; then
  git status --short >&2
  echo "Error: hay cambios sin commitear (PERMITIR_SUCIO=1 para continuar de todos modos)." >&2
  exit 1
fi

paso "Tests del paquete (sin torch) y con el grupo modelo"
(cd packages/clasificacion-funcion && uv sync --locked && uv run pytest -q \
  && uv sync --group modelo && uv run --group modelo pytest -q)

paso "torch / CUDA"
"${PM[@]}" python -c "import torch;print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"

[ -f data/raw/contexts.json ] || { echo "Falta data/raw: dvc pull data/raw.dvc" >&2; exit 1; }

paso "1/4 preparar (train/val/eval 2015/Gold v2 ciego + fugas)"
if [ -f "$EV/manifiesto_preparacion.json" ]; then echo "ya existe: se omite"; else
  "${P[@]}" python -m clasificacion_funcion.cli preparar --solo-validar
  "${P[@]}" python -m clasificacion_funcion.cli preparar
fi

paso "2/4 descarga de ACL OCL (omite lo ya descargado)"
if [ -f "$EV/manifiesto_ocl.json" ]; then echo "ya existe: se omite"; else
  "${P[@]}" python -m clasificacion_funcion.descarga_ocl
fi

paso "3/4 Top-3 con SciBERT base + regresion contra A1 (GPU)"
if [ -f "$EV/manifiesto_recuperacion.json" ]; then echo "ya existe: se omite"; else
  "${P[@]}" python -m clasificacion_funcion.cli recuperar --solo-validar
  "${PM[@]}" python -m clasificacion_funcion.cli_modelo recuperar --device cuda
fi

paso "4/4 interseccion A/B (revise bloqueos_cobertura en manifiesto_entradas.json)"
if [ -f "$EV/manifiesto_entradas.json" ]; then echo "ya existe: se omite"; else
  "${P[@]}" python -m clasificacion_funcion.cli entradas
fi

paso "Listo. Revise 'git status' y commitee la evidencia; luego: bash scripts/entrenar_clasificacion_a4.sh"
