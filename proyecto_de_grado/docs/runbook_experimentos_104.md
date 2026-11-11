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
