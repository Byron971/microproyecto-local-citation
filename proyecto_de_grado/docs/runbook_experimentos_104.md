# Runbook — experimentos SciBERT/SPECTER (issue #104)

> **Todo es provisional** hasta evaluar contra el Test Gold humano. Las métricas son contra la
> validación fija V (`val`), `dev_haiku` y `ref_gpt`; las etiquetas no son humanas.

## Qué hace
`notebooks/04_experimentos_scibert_104.ipynb` orquesta (la lógica está en
`clasificacion_funcion.{seleccion_datos,experimento_104,registro_mlflow}`): datos limpios →
TF-IDF → SciBERT-A en D1–D6 → variantes de pérdida → SPECTER → semillas → smoke test →
manifiesto. Todo queda en MLflow, experimento `clasificacion-funcion-104`.

## Regla anti-fuga
Se excluyen los citantes de **2014 y 2015** (todo `val` y `test` de `data/raw`: el Test Gold
mezcla 1.299 casos de 2014 y 1.379 de 2015), el manifiesto v2, TG2700, taller y piloto, más los
citantes y textos de esos casos. `verificar_fugas` falla cerrado y el resultado queda en
`manifiesto_datos.json`.

## Insumos (no versionados; sha256 en `evidencias_experimentos_104/manifiesto_datos.json`)
- `local_workflows/qlora_18000_preds_v2.jsonl` y `local_workflows/subconjuntos_qlora/*_qlora_v2_preds.jsonl`
- `v3_Jueces/jurado_18000_v3.csv`, `v3_Jueces/referencia_gpt_200.jsonl`
- `local_workflows/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv`, `local_workflows/qlora_split_v2.json`
- `data/raw/*.json`; encoders SciBERT y SPECTER ya descargados (sin red de noche).

## Instalación
```bash
cd packages/clasificacion-funcion
uv sync --group modelo --group experimentos
uv run python -m ipykernel install --user --name clasificacion-funcion
```

## Prueba en seco (~2 min)
Con `DRY = True` en la celda de parámetros (64 casos, 1 época; usa el experimento
`clasificacion-funcion-104-dry` y carpetas `*_dry`, que se pueden borrar):
```bash
cd notebooks
uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --output-dir /tmp --output dry.ipynb 04_experimentos_scibert_104.ipynb
```

## Corrida nocturna (~5 h)
Poner `DRY = False` y lanzar:
```bash
cd notebooks
nohup uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --inplace --ExecutePreprocessor.timeout=-1 04_experimentos_scibert_104.ipynb > ../noche_104.log 2>&1 &
```
- `HORAS_MAX` (def. 7) omite las fases restantes.
- Cada run va en try/except: queda FAILED en MLflow y el notebook sigue (ver `FALLAS`).
- **Reanudable**: se salta todo run FINISHED con el mismo tag `config_sha`. Si se corta, relanzar igual.

## Resultados
- MLflow: `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db` (desde la raíz).
- Checkpoints (~440 MB c/u): `proyecto_de_grado/artifacts/experimentos_104/corridas/<run>/` (ignorado por git; MLflow guarda ruta y sha).
- Evidencias: `proyecto_de_grado/docs/evidencias_experimentos_104/` — `manifiesto_datos.json`,
  `auditoria_fuentes.json`, `smoke_inferencia.json`, `manifiesto_experimentos.csv/json`.
- Los 18 runs de #103 se registran sin reentrenar con `registro_mlflow.registrar_corridas_a4`.

## Fases opcionales
- **7 (entrada B)** y **8 (D7 Sonnet)** quedan registradas como omitidas mientras no existan
  `artifacts/experimentos_104/entrada_b/` ni `artifacts/anotacion_sonnet/etiquetas_sonnet.csv`.

## Pendiente tras la corrida
La interpretación breve de resultados que pide el issue se escribe después, con los números reales.

---

# Parte 2: pista Sonnet, grilla de hiperparámetros, épocas y arreglo de la pérdida

Notebook `notebooks/05_experimentos_104_part2.ipynb` (orquestador; el 04 queda como registro de la Parte 1).
Mismo experimento MLflow, así que los runs de la Parte 1 con la misma configuración se reanudan.

## Pistas de etiquetas
- **Pista M («mixta»)**: entrenamiento D1–D6 (QLoRA, jurado, Haiku); V con la mejor etiqueta disponible.
- **Pista S («sonnet»)**: entrenamiento D7 `sonnet` (todas las citas de D1 con etiqueta Sonnet), D8 `sonnet_alta`
  (solo confianza Alta) y D9 `sonnet_cap` (tope por clase, Alta primero); V con etiquetas Sonnet (`v_sonnet`, las mismas citas).
- Dentro de una pista, early stopping y elección usan **su** `val`. **`val` no es comparable entre pistas**: todo run
  también se evalúa en `val_mixta`, `val_sonnet`, `dev_haiku` y `ref_gpt`. La comparación final espera al Test Gold.
- Las etiquetas Sonnet se consolidan en `proyecto_de_grado/anotacion/sonnet/etiquetas_sonnet.csv`
  (`scripts/anotar_sonnet.py consolidar`; el notebook lo hace en la fase 0).

## Runs de la Parte 1 inválidos
`preparar_ejemplos` descartaba `objetivo` y `peso`, así que `scibert-A-natural-kd-s42` y
`scibert-A-natural-ponderado-s42` fueron copias del run duro. Ya está corregido; la fase 0 los marca
(`registro_mlflow.invalidar`: tag `invalido=<motivo>` + KILLED) junto con `tfidf-lr-d1` (se re-corre para tener los
conjuntos nuevos). No se reanudan y se excluyen de las tablas.

## Fases
| Fase | Qué corre |
|---|---|
| 0 | Datos (D1–D9, V, V_sonnet), fugas = 0, manifiesto, invalidar los 3 runs |
| 1 | Re-evaluar 10 checkpoints de la Parte 1 en `val_mixta`/`val_sonnet` (`ex.reevaluar_checkpoint`, sin reentrenar) |
| 2 | Pista M: TF-IDF, `kd` y `ponderado` sobre `natural` (s42) |
| 3 | Pista S: TF-IDF y SciBERT en D7, D8, D9 (s42) |
| 4 | Grilla por pista sobre su mejor configuración: lr {1e-5, 3e-5, 5e-5} × épocas {4, 10}, paciencia 3 (alterna pistas) |
| 5 | Semillas 1234 y 2026 de la mejor configuración de cada pista |
| 6 | SPECTER con la mejor configuración de cada pista |
| 7 | Smoke test de inferencia de los 2 ganadores |
| 8 | Tablas por pista, media ± std entre semillas, bootstrap pareado, `resumen_part2.csv` y manifiesto |

Regla de elección: dentro de una pista, mayor macro-F1 en su propia `val`. Micro-lote (8) y `max_len` (512) no cambian
en la grilla; ante `OutOfMemoryError` se reintenta una vez con micro-lote 4 y acumulación 4. El pico de memoria queda
en MLflow (`gpu_mem_pico_gb`).

## Comandos
Primero `DRY = True` en la celda de parámetros (experimento `-dry`, 64 casos, 1 época):
```bash
cd notebooks && uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --output-dir /tmp --output dry_part2.ipynb 05_experimentos_104_part2.ipynb
```
Luego `DRY = False` y la noche (`HORAS_MAX = 10`):
```bash
cd notebooks
nohup uv run --project ../packages/clasificacion-funcion jupyter nbconvert --to notebook --execute \
  --inplace --ExecutePreprocessor.timeout=-1 05_experimentos_104_part2.ipynb > ../part2_104.log 2>&1 &
```
Vigilar `nvidia-smi` en el primer run. Disco: ~25 checkpoints nuevos × 440 MB ≈ 11 GB.

> **Entorno**: `mlflow.db` fue migrado con mlflow 3.18 (`local_workflows/.venv`); el entorno del paquete fija 3.15.1 y
> **no puede abrir esa base** («out-of-date database schema»). Antes de lanzar, alinear versiones (p. ej. subir `mlflow`
> en el grupo `experimentos`) o ejecutar con el entorno con el que se corrió la Parte 1. No migrar la base sin respaldo.
