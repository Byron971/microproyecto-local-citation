#!/usr/bin/env bash
# Verificacion completa del paquete recuperacion-densa (issue #102) y regeneracion de la evidencia.
# Uso (desde cualquier carpeta):  bash scripts/verificar_recuperacion_densa.sh
# Requiere: arbol git LIMPIO (para que manifiesto.json diga dirty:false), red solo para
# dvc pull / descarga OCL / verificar el modelo, y GPU CUDA para las corridas cuda.
# Las carpetas de corrida no se sobrescriben: si ya existen, el script se detiene.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

P=(uv run --project packages/recuperacion-densa)
R=proyecto_de_grado/artifacts/recuperacion_densa_a1
EV=proyecto_de_grado/docs/evidencias_recuperacion_densa_a1
MANIFIESTO_MODELO=$EV/manifiesto_modelo.json
CACHE_OCL=proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl
CACHE_VERIF=$R/cache_verificacion
# Conteo esperado tras --solo-validar (603 = 605 menos 2 autocitas; fijado en la 1a corrida).
CONTEXTOS_ESPERADOS=603
ARTICULOS_ESPERADOS=89
unset VIRTUAL_ENV  # evita el aviso de uv sobre el entorno activo

paso() { printf '\n==> %s\n' "$*"; }

paso "Arbol git limpio (garantiza dirty:false en manifiesto.json)"
if [ -n "$(git status --porcelain)" ]; then
  git status --short >&2
  echo "Error: hay cambios sin commitear; commitee antes de generar la evidencia." >&2
  exit 1
fi

for d in ensayo_20 corrida_cuda_1 corrida_cuda_2 cpu_60 cache_verificacion; do
  if [ -e "$R/$d" ] && [ -n "$(ls -A "$R/$d" 2>/dev/null)" ]; then
    echo "Error: $R/$d ya existe con contenido; muevalo o borrelo antes de repetir." >&2
    exit 1
  fi
done

paso "Paquete: lock, sync y tests (sin torch)"
(cd packages/recuperacion-densa && uv lock --check && uv sync --locked && uv run pytest -q)

paso "Paquete auditoria-corpus: sync y tests"
(cd packages/auditoria-corpus && uv sync --locked && uv run pytest -q)

paso "Paquete: tests con el grupo modelo (incluye BERT diminuto)"
(cd packages/recuperacion-densa && uv sync --group modelo && uv run --group modelo pytest -q)

paso "torch / CUDA"
(cd packages/recuperacion-densa && uv run --group modelo python -c \
  "import torch;print(torch.__version__,torch.version.cuda,torch.cuda.is_available())")

paso "Datos de entrada"
if [ ! -f data/raw/train.json ]; then
  echo "Falta data/raw/train.json: dvc pull data/raw.dvc"
  dvc pull data/raw.dvc
fi
if [ -z "$(ls -A "$CACHE_OCL" 2>/dev/null)" ]; then
  echo "Falta la cache OCL: descarga (200 articulos, semilla 101)"
  uv run --project packages/auditoria-corpus python -m auditoria_corpus.descarga --n 200 --semilla 101
fi

paso "Resolver SHA actual del modelo (compare con REVISION_SCIBERT en revision.py)"
"${P[@]}" --group modelo python -m recuperacion_densa.descarga_modelo --resolver

paso "Modelo: descarga si falta el manifiesto; si existe, solo verifica el snapshot"
"${P[@]}" --group modelo python -m recuperacion_densa.descarga_modelo

paso "Validar corpus (esperar $CONTEXTOS_ESPERADOS contextos / $ARTICULOS_ESPERADOS articulos)"
salida_validar="$("${P[@]}" python -m recuperacion_densa.cli --solo-validar)"
echo "$salida_validar"
grep -q "Corpus valido: $CONTEXTOS_ESPERADOS contextos / $ARTICULOS_ESPERADOS articulos" <<<"$salida_validar" || {
  echo "Error: conteo distinto de $CONTEXTOS_ESPERADOS contextos / $ARTICULOS_ESPERADOS articulos." >&2
  exit 1
}

export HF_HUB_OFFLINE=1

paso "Ensayo de 20 contextos (CUDA, sin cache)"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --limite 20 --device cuda --sin-cache --salida "$R/ensayo_20"

paso "Corrida CUDA 1 (cache en frio: la escribe)"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --device cuda --cache "$CACHE_VERIF" --salida "$R/corrida_cuda_1"

paso "Corrida CUDA 2 (cache en caliente: misma cache)"
"${P[@]}" --group modelo python -m recuperacion_densa.cli_modelo --device cuda --cache "$CACHE_VERIF" --salida "$R/corrida_cuda_2"

paso "Cache en caliente: 100 % de aciertos"
"${P[@]}" python - "$R" <<'PY'
import json, sys
r = sys.argv[1]
total = json.load(open(f"{r}/corrida_cuda_2/resumen.json"))["validacion"]["chunks_unicos"]
lat = lambda d: json.load(open(f"{r}/{d}/latencias_resumen.json"))["embedding_articulo"]["chunks_en_cache"]
frio, caliente = lat("corrida_cuda_1"), lat("corrida_cuda_2")
# en frio solo puede acertar un texto repetido entre articulos distintos (misma clave por texto)
assert frio < 0.01 * total, f"demasiados aciertos de cache en frio ({frio}/{total})"
assert caliente == total, f"aciertos en cache {caliente} != chunks {total}"
print(f"OK: frio={frio}, caliente={caliente}/{total}")
PY

paso "Determinismo: CUDA 1 (frio) vs CUDA 2 (caliente)"
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

paso "Comparaciones y evidencia versionada en $EV"
mkdir -p "$EV"
rm -f "$EV/cpu_vs_cuda_60.json" "$EV/cuda_frio_vs_caliente.json"
"${P[@]}" python -m recuperacion_densa.comparar_corridas "$R/cpu_60" "$R/corrida_cuda_1" --salida "$EV/cpu_vs_cuda_60.json"
"${P[@]}" python -m recuperacion_densa.comparar_corridas "$R/corrida_cuda_1" "$R/corrida_cuda_2" --salida "$EV/cuda_frio_vs_caliente.json"
for f in "$R"/corrida_cuda_1/*; do
  cp -f "$f" "$EV/$(basename "$f")"
done
echo "Copiado: $(ls "$R/corrida_cuda_1" | tr '\n' ' ')"

paso "Verificacion terminada. Revise 'git status' y commitee la evidencia."
