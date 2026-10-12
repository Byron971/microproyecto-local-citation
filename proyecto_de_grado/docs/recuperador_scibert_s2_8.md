# S2.8 — Recuperación local de fragmentos Top-3 con SciBERT

**Estado:** implementación experimental offline para solo `train`. No es un sistema Gold ni una medición de relevancia científica. Se incorpora como archivos nuevos y no modifica el MVP, S2.6, los PR abiertos ni el `uv.lock`.

## Entradas y restricciones

- Fuente: `proyecto_de_grado/artifacts/enriquecimiento_s2_4/v6_expansion_20261011/candidatos_train_enriquecidos.jsonl` (67 casos seleccionados, según corrida local).
- Cada caso contiene `id`, `split=train`, `cited_id`, `citation_context`, `cited_chunks`; los fragmentos proceden del **artículo citado**, no de la colección global.
- Se rechazan `val/test`, IDs repetidos, textos vacíos, marcadores `TARGETCIT` inconsistentes, relevancias ya adjudicadas y cambios de chunks entre consultas de un mismo artículo.
- Los resultados contienen IDs de fragmentos, posiciones, similitudes, puntajes BM25 y tiempos. **No se exportan textos completos** al reporte.
- SciBERT es un modelo de lenguaje científico, **no un bi-encoder específicamente entrenado para recuperar evidencia**. La comparación es un baseline exploratorio.

## Entorno y dependencias

El repositorio tiene `requires-python >=3.14`, por lo que la inferencia GPU se realiza en el entorno independiente Python 3.12 existente en Windows:

```powershell
$py = "$env:USERPROFILE\.venvs\scibert-top3\Scripts\python.exe"
& $py -c "import torch, transformers; print(torch.__version__, transformers.__version__)"
```

Ejemplo de entorno probado manualmente: PyTorch `2.12.0+cu130`, Transformers `4.57.6`, NVIDIA RTX 5060 Laptop. El modelo `allenai/scibert_scivocab_uncased` ya se descargó en la caché de Hugging Face.

## Ejecución paso a paso desde la raíz del repositorio

Primero, ejecutar tests **sin GPU ni red** con el entorno original Python 3.14:

```powershell
uv run --group research --group dev pytest -q proyecto_de_grado/tests/test_scibert_top3_s2_8.py
```

Validar estructura de las 67 consultas sin cargar el modelo:

```powershell
$entrada = "proyecto_de_grado/artifacts/enriquecimiento_s2_4/v6_expansion_20261011/candidatos_train_enriquecidos.jsonl"
& $py -m proyecto_de_grado.src.retrieval.scibert_top3_s2_8 --input $entrada --solo-validar
```

Primer ensayo controlado con solo **dos contextos**:

```powershell
& $py -m proyecto_de_grado.src.retrieval.scibert_top3_s2_8 --input $entrada --limit 2 --device cuda --batch-size 4 --max-length 512 --out "proyecto_de_grado/artifacts/scibert_s2_8/ensayo_2_casos.json"
```

Si el ensayo se ejecuta correctamente, correr los 67 casos:

```powershell
& $py -m proyecto_de_grado.src.retrieval.scibert_top3_s2_8 --input $entrada --device cuda --batch-size 4 --max-length 512 --out "proyecto_de_grado/artifacts/scibert_s2_8/comparacion_v6_67.json"
```

La primera ejecución completa puede tardar según GPU, longitud de textos y cantidad de ventanas. El script vectoriza cada artículo **una sola vez** durante la corrida y registra el número de textos y ventanas procesados. A diferencia del truncamiento de 256/512 tokens, aquí los textos largos se procesan por ventanas **contiguas sin descartar tokens**, combinando sus vectores por promedio ponderado y luego normalizando; esto es una decisión experimental y no elimina los efectos de fronteras entre ventanas.

## Salidas y límites

- `tipo=comparacion_tecnica_train_s2_8_no_gold`.
- Para cada contexto: IDs de los tres primeros fragmentos SciBERT, ranking BM25 del mismo contexto y mismos chunks, puntajes y tiempos por consulta (sin contabilizar la primera vectorización del artículo en el tiempo SciBERT por consulta).
- Resumen: cantidad de casos, artículos, chunks únicos, coincidencias entre Top-3, frecuencia de mismo Top-1, abstenciones BM25, tiempo total, ventanas procesadas y `metricas_gold_calculadas=false`.
- Los puntajes coseno y BM25 **no son probabilidades**, y el solapamiento entre sus rankings **no demuestra relevancia**. No reportar Hit@3, Recall@3, MRR@3 ni superioridad metodológica hasta tener relevancias exhaustivas y adjudicadas.
- El fichero de informe se escribe solo si no existe. Si cambia el código, corpus o modelo, usar un nombre nuevo para conservar la evidencia histórica. Las entradas provienen del corpus v6 de `train`, no deben incluirse en un futuro Test Gold como muestras ciegas.
- El reporte consigna la versión/revisión solicitada del modelo y, cuando Hugging Face la proporciona, su commit resuelto; antes de experimentos finales fijar explícitamente la revisión del modelo y congelar entornos.
- No añadir textos de ACL OCL ni `.jsonl`/artefactos generados al commit.
