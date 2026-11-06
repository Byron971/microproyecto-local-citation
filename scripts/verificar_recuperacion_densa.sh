#!/usr/bin/env bash
# Verificacion completa del paquete recuperacion-densa (issue #102).
# Uso (desde cualquier carpeta):  bash scripts/verificar_recuperacion_densa.sh
# Requiere red SOLO para --resolver y la descarga del modelo; GPU CUDA para las corridas cuda.
# Las carpetas de corrida no se sobrescriben: si ya existen, el script se detiene.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

P=(uv run --project packages/recuperacion-densa)
R=proyecto_de_grado/artifacts/recuperacion_densa_a1
MANIFIESTO_MODELO=proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json
unset VIRTUAL_ENV  # evita el aviso de uv sobre el entorno activo

paso() { printf '\n==> %s\n' "$*"; }

for d in ensayo_20 corrida_cuda_1 corrida_cuda_2 cpu_60; do
  if [ -e "$R/$d" ] && [ -n "$(ls -A "$R/$d" 2>/dev/null)" ]; then
    echo "Error: $R/$d ya existe con contenido; muevalo o borrelo antes de repetir." >&2
    exit 1
  fi
done

paso "Paquete: lock, sync y tests (sin torch)"
(cd packages/recuperacion-densa && uv lock && uv sync --locked && uv run pytest -q)

paso "Paquete: tests con el grupo modelo (incluye BERT diminuto)"
(cd packages/recuperacion-densa && uv sync --group modelo && uv run --group modelo pytest -q)

paso "torch / CUDA"
(cd packages/recuperacion-densa && uv run --group modelo python -c \
  "import torch;print(torch.__version__,torch.version.cuda,torch.cuda.is_available())")

paso "Resolver SHA actual del modelo (compare con REVISION_SCIBERT en revision.py)"
"${P[@]}" --group modelo python -m recuperacion_densa.descarga_modelo --resolver

if [ -e "$MANIFIESTO_MODELO" ]; then
  paso "Descarga omitida: ya existe $MANIFIESTO_MODELO"
else
  paso "Descarga del modelo (red, una vez)"
  "${P[@]}" --group modelo python -m recuperacion_densa.descarga_modelo
fi

paso "Validar corpus (esperar 605 contextos / 91 articulos)"
"${P[@]}" python -m recuperacion_densa.cli --solo-validar

export HF_HUB_OFFLINE=1

paso "Ensayo de 20 contextos (CUDA)"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --limite 20 --device cuda --salida "$R/ensayo_20"

paso "Corrida CUDA 1 (sin cache)"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --device cuda --sin-cache --salida "$R/corrida_cuda_1"

paso "Corrida CUDA 2 (con cache)"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --device cuda --salida "$R/corrida_cuda_2"

paso "Determinismo: CUDA 1 vs CUDA 2"
cmp "$R/corrida_cuda_1/resumen.json" "$R/corrida_cuda_2/resumen.json"
cmp "$R/corrida_cuda_1/top3.csv" "$R/corrida_cuda_2/top3.csv"
echo "OK: resumen.json y top3.csv identicos"

paso "Corrida CPU (60 contextos) para comparar CPU/CUDA"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --device cpu --limite 60 --sin-cache --salida "$R/cpu_60"

paso "Diff fuera del paquete (debe estar vacio)"
cambios="$(git diff --stat main...HEAD -- src/app proyecto_de_grado/src)"
if [ -n "$cambios" ]; then
  echo "$cambios"
  echo "Error: hay cambios en src/app o proyecto_de_grado/src." >&2
  exit 1
fi
echo "OK: sin cambios en src/app ni proyecto_de_grado/src"

paso "Verificacion terminada. Compare cpu_60 con corrida_cuda_1 (primeros 60 contextos)."
