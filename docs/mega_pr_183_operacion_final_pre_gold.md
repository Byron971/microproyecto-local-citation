# Mega PR #183 — Cierre técnico reproducible antes del Test Gold

Corte: noviembre de 2026. Base: `main` tras PR #182, commit `da24ec2`. Objetivo: que la ejecución posterior de experimentos sea trazable y no requiera inventar anotaciones ni reescribir la arquitectura. **Preparado no equivale a validado con humanos.**

## 1. Hallazgos corregidos

| Riesgo en main | Corrección |
|---|---|
| `science_preflight.ready_a_b` usaba `all()` sobre un filtro; podía omitir un modelo esperado y devolver true | Requiere los dos IDs exactos y estado verified; añade gate `--strict-all` para cuatro checkpoints y dos snapshots pinned |
| A4 validaba SHA contra el manifiesto pasado por el operador, pero no contra el registro histórico | `verify_historical_identity` verifica ID, encoder, entrada, semilla, ruta de manifiesto archivado y SHA original, rechazando cambios coordinados de pesos/manifiesto |
| Smoke HTTP validaba SciBERT A/B pero no SPECTER A/B | `smoke_tesis.py --cientifico --cuatro-modelos` exige las cuatro rutas reales, nueve clases y SciBERT Top-3 en ambas variantes B |
| Gold de fragmentos admitía el texto `split=test` sin verificar ACL-200 real | Nuevo cotejo contra `contexts.json`, `train.json`, `val.json` y `test.json`, verificando IDs, documentos y SHA del masked_text |
| Existía benchmark de predicciones pero no ejecutor único A4 2×2 ciego | Nuevo CLI `src.evaluation.a4_infer_unlabeled`: plan sin Torch, preflight de originales y cuatro inferencias en modo `--apply` |
| Se comprobaba cantidad de nueve scores, pero no validez numérica | Gate de finitud, intervalo [0,1], suma 1 y latencia válida |

El código no descarga pesos, no modifica DVC, no reentrena ni ejecuta Gold en CI. Las pruebas con adaptadores ficticios se etiquetan como sintéticas.

## 2. Operación paso a paso

### A. Diagnóstico pre-Gold local

```bash
uv sync --locked --group dev
uv run pytest -q tests/test_science_hardening.py tests/test_top3_acl_official.py tests/test_four_arm_smoke.py tests/test_a4_unlabeled_pipeline.py
uv run python scripts/ci/release_readiness.py
```

`release_readiness.py --require-final` debe devolver 1 mientras falten resultados/evidencias auténticas. Esto es un control intencional.

### B. Recuperar los cuatro pesos originales

```bash
uv run python -m src.app.restore_a4 --source /ORIGEN/clasificacion_a4/corridas --all
uv run python -m src.app.restore_a4 --source /ORIGEN/clasificacion_a4/corridas --all --apply
uv run python -m src.app.checkpoint_gate
```

Los cuatro `model.safetensors` no están en Git. No es válido sustituir un checkpoint entrenado por pesos nuevos y llamarlo la misma corrida. Si el original es irrecuperable, se debe registrar la decisión de nuevo entrenamiento y actualizar honestamente la metodología.

### C. Preparar los snapshots de los dos encoders

```bash
uv run python -m src.app.science_preflight \
  --weights /DESTINO/clasificacion_a4/corridas --strict-all
```

Es un preflight **sin red** por defecto. Solo añadir `--download` cuando se autorice explícitamente descargar modelos pinned y haya disco/ancho de banda. El sistema exige SciBERT/SPECTER y SHA histórico de los cuatro pesos. `ready_four_a4` no certifica inferencia, calidad ni Gold humano.

### D. Crear entradas ciegas del Test Gold (sin etiquetas)

Para no fabricar el JSONL a mano, preparar primero un archivo privado `/PRIVADO/ids_test_seleccionados.txt` (un `context_id` por línea; admite comentarios con `#`). Debe congelarse **antes de inferir** y contener únicamente casos realmente elegibles de la partición ACL-200 test. El exportador rechaza los IDs de práctica/calibración/piloto históricos conocidos y falla si falta un citado o la fragmentación V1; **no selecciona arbitrariamente otros casos para reemplazarlos**.

```bash
uv run python -m src.evaluation.a4_export_unlabeled \
  --ids-file /PRIVADO/ids_test_seleccionados.txt \
  --raw-dir /PRIVADO/acl200/raw \
  --ocl-cache /PRIVADO/cache_ocl \
  --output artifacts/a4_privado/test_unlabeled_001.jsonl \
  --manifest artifacts/a4_privado/manifiesto_export_001.json
```

El JSONL resultante carece de etiquetas y proviene de `contexts.json`, `papers.json`, particiones ACL oficiales y la fuente OCL con SHA de cada artículo. El reporte guarda procedencia agregada (no los textos) y advierte `heldout_independence_certified=false`: si existieron usos de esos IDs en tuning/prompts fuera de las listas históricas conocidas, debemos detectarlos y excluirlos antes de llamar al conjunto un verdadero held-out. Los dos archivos nuevos se crean en `artifacts/` y no deben publicarse en Git.

Proporcionar un JSONL **privado** con un objeto por caso y estos campos: `context_id`, `citing_id`, `cited_id`, `split="test"`, `citation_context` con un solo `TARGETCIT`, `context_sha256`, `cited_title`, `cited_abstract` y `chunks`; cada chunk debe contener `chunk_id`, `texto`, `seccion`, `paragraph_indices` y `palabras` para el contraste con el fragmentador V1 histórico. `sha256_ocl_citado` es obligatorio para `--apply` y debe representar los bytes exactos del JSON ACL OCL citado. Se requieren 3 a 500 chunks del **mismo** artículo citado.

`context_sha256` es SHA-256 de los bytes UTF-8 del `masked_text` oficial ACL-200; no de una reconstrucción improvisada. No agregar campos Gold, etiquetas, scores o anotadores: se rechazan. Los IDs/documentos/splits del contexto se cotejan con ACL-200; título y abstract se cotejan con `papers.json` oficial. Antes de inferir también se verifican los bytes SHA de cada artículo ACL OCL y **todos los chunks** se reconstruyen usando el fragmentador V1 histórico (sin sustituirlo por V2). El sistema bloquea cambios de textos, secciones, posiciones, longitud o fragmentos faltantes.

Comando dry-run: **no escribe predicciones ni carga Torch**.

```bash
uv run python -m src.evaluation.a4_infer_unlabeled \
  --inputs /PRIVADO/test_unlabeled.jsonl \
  --raw-dir /PRIVADO/acl200/raw \
  --ocl-cache /PRIVADO/cache_ocl
```

### E. Ejecutar A4 2×2, todavía sin Gold

```bash
uv run python -m src.evaluation.a4_infer_unlabeled \
  --inputs /PRIVADO/test_unlabeled.jsonl \
  --raw-dir /PRIVADO/acl200/raw \
  --ocl-cache /PRIVADO/cache_ocl \
  --checkpoint-root /DESTINO/clasificacion_a4/corridas \
  --output-dir artifacts/a4_predicciones_2x2_001 \
  --apply
```

La ejecución primero bloquea ACL falso, IDs/textos alterados, metadatos `papers.json` inventados, hashes o chunks OCL inconsistentes y checkpoints ausentes. Luego SciBERT recupera Top-3 de TODOS los chunks candidatos del citado, sin cachear heldout; a continuación carga de uno en uno SciBERT-A, SciBERT-B, SPECTER-A y SPECTER-B. La salida privada se crea atómicamente **solo cuando se completan los cuatro**: cuatro archivos `*.jsonl`, `a4_factorial_config.json` y `run_manifest.json` (incluye SHA de `papers.json` y la procedencia OCL contrastada).

Las predicciones llevan `case_id`, `status=ok`, `pred_label`, `pred_index`, ID modelo y latencia. Los reportes incluyen hashes; **no guardan la etiqueta humana ni calculan F1**. No sobrescribir un directorio existente. Todo queda en `artifacts/`, ignorado por Git.

### F. Verificar el demostrador de cuatro modelos reales

```bash
uv run python scripts/ci/smoke_tesis.py \
  --cientifico --cuatro-modelos \
  --salida artifacts/qa_tesis/smoke_cuatro_a4_001.json
```

Requiere backend local con los cuatro modelos y SciBERT Top-3 cargados desde checkpoints auténticos. Si falta un peso, una respuesta contiene BM25 o un encoder equivocado, **falla**. Las pruebas CI de contratos con stubs y el smoke HTTP del baseline son otra cosa.

### G. Evaluación factorial cuando llegue el Test Gold legítimo

El evaluador A4 ya existente consume las cuatro predicciones y el `a4_factorial_config.json` generado:

```bash
uv run python -m src.evaluation.commercial.a4_factorial_benchmark \
  --gold /PRIVADO/test_gold_humano_adjudicado.jsonl \
  --config artifacts/a4_predicciones_2x2_001/a4_factorial_config.json \
  --raw-dir /PRIVADO/acl200/raw \
  --output-dir artifacts/a4_resultados_001 \
  --provisional
```

El modo `--provisional` calcula métricas, contrastes pareados y matrices al contar con casos etiquetados, **sin declarar automáticamente Gold humano certificado**. La certificación requiere evidencia externa de autoría humana, cobertura, doble anotación y adjudicación; no basta con un CSV correcto.

Para el **otro Gold**, relevancia de chunks de Top-3, es obligatorio evaluar TODOS los chunks del citado con dos juicios ciegos por par: Se exige también cotejar el universo completo de fragmentos, sus hashes y secciones contra el artículo OCL fuente mediante `--require-ocl`. Este control verifica procedencia documental, no autenticidad de la revisión humana.

```bash
uv run python -m proyecto_de_grado.src.evaluation.top3_gold_gate \
  --manifest /PRIVADO/universe.json \
  --exclusions /PRIVADO/exclusions.json \
  --judgments /PRIVADO/judgments.csv \
  --adjudications /PRIVADO/adjudications.csv \
  --rankings /PRIVADO/rankings.csv \
  --raw-dir /PRIVADO/acl200/raw --require-official-splits \
  --ocl-cache /PRIVADO/cache_ocl --require-ocl \
  --output /PRIVADO/resumen_top3_001.json
```

## 3. Dependencias reales que el código NO puede eliminar

1. **Cuatro checkpoints auténticos:** los manifiestos históricos están versionados, pero no los bytes de `model.safetensors`. No se ha demostrado inferencia real A4 cuatro brazos en este PR.
2. **Cobertura A4-B:** `proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_entradas.json` registra cobertura de 55,28% train, 53,71% eval-2015 y 54,73% candidatos Gold-v2, por debajo del umbral interno de 60%. V2 de fragmentación ya existe como opt-in; cambiarlo ahora implica nuevo experimento/reentrenamiento, no corrección silenciosa.
3. **Balance de nueve clases:** la propuesta requiere ≥2.000 citas por clase y al menos 15% de dataset validado por humanos. No queda demostrado por tener un total 18.000 sin distribución verificada y sin la evidencia de validación.
4. **Equipo humano:** operativamente somos usuario y asistente. La IA NO representa un segundo anotador humano. Si el programa exige dos humanos independientes, será necesario conseguir humanos externos o una excepción metodológica aprobada. El código jamás afirma lo contrario.
5. **Relevancia de fragmentos:** ACL-200 da positivos por artículo, no Gold por chunk. Sin relevancia ciega completa no hay Recall@3/MRR@3 legítimos.
6. **Infraestructura y comercial:** Terraform validate no equivale a HTTPS AWS desplegado; las llamadas API pagas y métricas de costos deben autorizarse y medirse.
7. **Artículo final:** requiere fuentes IEEE verificadas, formato (≤12 páginas) y conclusiones derivadas de resultados reales. El borrador metodológico ya existe.

## 4. Entregables y aceptación del PR

- Código para preflight A4 cuatro brazos, validación autenticada del modelo y smoke HTTP opt-in.
- Validador ACL-200 oficial para Gold Top-3 y suite de regresiones adversariales sintéticas.
- Ejecutor local reproducible de cuatro brazos con modo seguro sin modelos y salidas atómicas con SHA.
- CI verde para tests, Docker CPU SciBERT base y aplicación React/API baseline.
- Ningún Gold humano, token, checkpoint pesado, AWS apply/deploy, resultados inventados o informe final falso.

| Fase final | Instrumento ya disponible | Insumo externo imprescindible |
|---|---|---|
| Modelos A4 | `restore_a4`, `science_preflight --strict-all`, `a4_infer_unlabeled --apply` | Pesos originales y dos snapshots |
| Gold nueve funciones | `gold_freeze_audit`, benchmark factorial | Anotación/adjudicación humana auténtica y 15% |
| Gold relevancia Top-3 | `top3_gold_gate --require-official-splits` | Juicios ciegos de TODOS los chunks |
| Resultados A4 2×2 | `a4_factorial_benchmark` y manifiestos SHA | Gold, predicciones reales y corpus elegible |
| Prototipo | React, FastAPI, smoke cuatro modelos | Host científico con checkpoints restaurados |
| Documento y sustentación | Borrador y matriz de rúbricas | Resultados, evidencia y revisión académica final |

No asignamos tareas a antiguos integrantes. Esta preparación técnica sirve para continuar con el equipo operativo real (usuario + IA) sin falsear requisitos que necesariamente requieren personas externas.
