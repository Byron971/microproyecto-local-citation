#!/usr/bin/env bash
# Entrena y puntua la matriz del issue #103 (A4): {SciBERT, SPECTER} x {Entrada A, Entrada B}
# x 3 semillas, mas las ablaciones de seccion (SciBERT) y el sondeo con secciones barajadas.
# TODO es PROVISIONAL: etiquetas Haiku, Gold humano v2 no congelado (#100).
#
# Uso (desde cualquier carpeta):
#   bash scripts/entrenar_clasificacion_a4.sh                 # matriz 2x2 completa (12 corridas)
#   DRY=1 bash scripts/entrenar_clasificacion_a4.sh           # ensayo: 64 casos, 1 epoca, salida en /tmp
#   ABLACIONES=1 bash scripts/entrenar_clasificacion_a4.sh    # ademas B_sin_seccion y B_barajada (SciBERT)
# Variables opcionales: ENCODERS="scibert specter"  SEMILLAS="42 1234 2026"  ENTRADAS="A B"
#                       PERMITIR_SUCIO=1 (no exigir arbol git limpio)
#
# Requiere haber ejecutado antes scripts/preparar_clasificacion_a4.sh. Es idempotente y nunca
# sobrescribe: una corrida ya existente se omite; para repetirla borre su carpeta.
# Checkpoints (gitignored):  proyecto_de_grado/artifacts/clasificacion_a4/corridas/<corrida>/
# Evidencia versionable:     proyecto_de_grado/docs/evidencias_clasificacion_a4/<corrida>/
# Estimacion (RTX 4070 SUPER, medida con 4 pasos): ~0,15 s por lote de 8 en la Entrada B, es decir
# ~25 s por epoca y ~2-3 min por corrida con parada temprana; la matriz 2x2 deberia tomar ~30 min.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"
unset VIRTUAL_ENV
export PYTHONPATH=.
export HF_HUB_OFFLINE=1

ENCODERS="${ENCODERS:-scibert specter}"
SEMILLAS="${SEMILLAS:-42 1234 2026}"
ENTRADAS="${ENTRADAS:-A B}"
ABLACIONES="${ABLACIONES:-0}"
DRY="${DRY:-0}"

PM=(uv run --project packages/clasificacion-funcion --group modelo python -m clasificacion_funcion.cli_modelo)
ART=proyecto_de_grado/artifacts/clasificacion_a4
EV=proyecto_de_grado/docs/evidencias_clasificacion_a4
CORRIDAS="$ART/corridas"
SALIDA_EV="$EV"
EXTRA=()
if [ "$DRY" = "1" ]; then
  TMP="$(mktemp -d /tmp/a4_dry_XXXXXX)"
  CORRIDAS="$TMP/corridas"; SALIDA_EV="$TMP/ev"
  EXTRA=(--limite 64)
  EPOCAS=(--epocas 1)
  echo "DRY=1: 64 casos, 1 epoca; salidas en $TMP (se pueden borrar)"
else
  EPOCAS=()
fi

paso() { printf '\n==> %s\n' "$*"; }

if [ "$DRY" != "1" ] && [ -n "$(git status --porcelain)" ] && [ "${PERMITIR_SUCIO:-0}" != "1" ]; then
  git status --short >&2
  echo "Error: hay cambios sin commitear; los manifiestos quedarian con dirty:true." >&2
  echo "Commitee, o use PERMITIR_SUCIO=1 / DRY=1." >&2
  exit 1
fi

paso "Prerrequisitos"
for f in "$EV/manifiesto_entradas.json" "$EV/manifiesto_modelo_scibert.json" \
         "$EV/manifiesto_modelo_specter.json" "$ART/entradas/entradas_train.jsonl" \
         "$ART/entradas/entradas_val.jsonl" "$ART/entradas/entradas_eval_2015.jsonl" \
         "$ART/entradas/entradas_gold_v2.jsonl"; do
  [ -f "$f" ] || { echo "Falta $f: ejecute scripts/preparar_clasificacion_a4.sh" >&2; exit 1; }
done
uv run --project packages/clasificacion-funcion --group modelo python - <<'PY'
import json, torch
assert torch.cuda.is_available(), "CUDA no disponible"
m = json.load(open("proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_entradas.json"))
print("torch", torch.__version__, "|", torch.cuda.get_device_name(0))
for b in m.get("bloqueos_cobertura", []):
    print("AVISO cobertura:", b["conjunto"], b["cobertura_pct"], "% < umbral", b["umbral_pct"], "%")
PY

mkdir -p "$ART/logs"
LOG="$ART/logs/entrenamiento_$(date +%Y%m%d_%H%M%S).log"
[ "$DRY" = "1" ] && LOG="$TMP/entrenamiento.log"
echo "Log: $LOG"

correr() {  # correr <encoder> <entrada> <semilla>
  local enc="$1" ent="$2" sem="$3" nombre="${1}_${2}_${3}"
  local run="$CORRIDAS/$nombre" ev="$SALIDA_EV/$nombre"
  if [ -n "$(ls -A "$run" 2>/dev/null)" ]; then
    echo "[$nombre] checkpoint ya existe: se omite el entrenamiento"
  else
    paso "[$nombre] entrenar"
    "${PM[@]}" entrenar --encoder "$enc" --entrada "$ent" --semilla "$sem" \
      --corridas "$CORRIDAS" --device cuda "${EXTRA[@]}" "${EPOCAS[@]}"
  fi
  if [ -f "$ev/predicciones_gold_v2.jsonl" ]; then
    echo "[$nombre] predicciones ya existen: se omite"
  else
    paso "[$nombre] predecir (eval 2015 provisional + Gold v2 ciego)"
    "${PM[@]}" predecir --corrida "$run" --salida "$ev" --device cuda "${EXTRA[@]}"
  fi
}

sondeo() {  # sondeo <encoder> <semilla>: modelo B evaluado con secciones barajadas (sin reentrenar)
  local nombre="${1}_B_${2}" ev="$SALIDA_EV/${1}_B_${2}"
  if [ -f "$ev/predicciones_eval_B_barajada.jsonl" ]; then
    echo "[$nombre] sondeo ya existe: se omite"
  else
    paso "[$nombre] sondeo con secciones barajadas"
    "${PM[@]}" predecir --corrida "$CORRIDAS/$nombre" --salida "$ev" --entrada-eval B_barajada \
      --device cuda "${EXTRA[@]}"
  fi
}

{
  inicio=$SECONDS
  for enc in $ENCODERS; do
    for ent in $ENTRADAS; do
      for sem in $SEMILLAS; do
        t0=$SECONDS
        correr "$enc" "$ent" "$sem"
        echo "[${enc}_${ent}_${sem}] $((SECONDS - t0)) s"
        if [ "$ent" = "B" ]; then sondeo "$enc" "$sem"; fi
      done
    done
  done
  if [ "$ABLACIONES" = "1" ]; then
    for ent in B_sin_seccion B_barajada; do
      for sem in $SEMILLAS; do correr scibert "$ent" "$sem"; done
    done
  fi
  paso "Resumen (F1 macro; eval PROVISIONAL con etiquetas Haiku)"
  python3 - "$SALIDA_EV" <<'PY'
import json, pathlib, sys
rows = []
for d in sorted(pathlib.Path(sys.argv[1]).glob("*_*_*")):
    v, e = d / "metricas_val.json", d / "metricas_eval.json"
    if v.is_file() and e.is_file():
        rows.append((d.name, json.load(open(v))["f1_macro"], json.load(open(e))["f1_macro"],
                     json.load(open(e))["accuracy"]))
print(f"{'corrida':28s} {'F1 val':>8s} {'F1 eval':>8s} {'acc eval':>9s}")
for n, fv, fe, a in rows:
    print(f"{n:28s} {fv:8.4f} {fe:8.4f} {a:9.4f}")
PY
  echo "Duracion total: $((SECONDS - inicio)) s"
} 2>&1 | tee -a "$LOG"

paso "Terminado. Revise 'git status' y commitee solo la evidencia (corridas/ esta ignorada por git)."
