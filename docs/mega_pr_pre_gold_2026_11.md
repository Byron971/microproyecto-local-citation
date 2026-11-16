# Mega PR de preparación pre-Gold — auditoría posterior a #180

Corte: 15-nov-2026 (Colombia); base `main` tras #180 (732db4d). Este documento no certifica Gold humano, precisión científica ni despliegue.

## 1. Comparación con los cinco pendientes de Copilot

| Área | Ya disponible en main | Mejora incorporada ahora | Aún bloqueado |
|---|---|---|---|
| Manifiestos, SHA, splits | `validar_splits.py`, `gold_freeze_audit.py`, `gold_manifest_reconcile.py`, `acl200_gold_split_gate.py`, `checkpoint_gate.py` | Gate de Gold de fragmentos independiente + inventario transversal | Reconciliación Gold de nueve funciones y 15% humano |
| API/frontend | CI HTTP real `fullstack-e2e.yml`, `smoke_tesis.py`, React/Vitest/Playwright | Regresión sintética de nuevo protocolo | Pruebas A4 auténticas no equivalen a fixtures |
| SciBERT/A4 | #180: Top-3 SciBERT real CPU, loader A/B, Docker científico | Inventario de cuatro celdas A4 y pesos | Falta restaurar `model.safetensors` originales |
| Método y artículo | `protocolo_experimental_grado_2026_11.md` y artículo borrador | Matriz de experimentos/tabla de resultados pendientes | IEEE, resultados Gold, edición/autoría |
| CI/IaC | Terraform validate, Docker CI, auditoría AWS read-only | CI de gates pre-Gold | Sin despliegue, Cost Explorer ni costo observado |

**Distinción científica obligatoria:** ACL-200 proporciona relevancia de **artículo**, no Gold de **chunk**. El Gold de nueve funciones y el Gold Top-3 son dos conjuntos y protocolos diferentes. Tampoco son equivalentes entrada A/B (forma de entrada) y origen de etiquetas (Haiku/jurado). Véanse issues #100, #103, #127 y #128.

## 2. Cambios concretos de este PR

1. `proyecto_de_grado/src/evaluation/top3_gold_gate.py`: ingesta local privada del universo completo de chunks, dos juicios por par, adjudicación por tercero, controles de fugas declaradas por contexto/citante/par, abstenciones y ranking pareado. Nunca crea etiquetas ni conserva ejemplos Gold en el reporte.
2. `tests/test_top3_gold_gate.py`: pruebas sintéticas de denominadores Hit@3, Recall@3 y MRR@3, exclusión de consultas sin relevantes, rechazando anotaciones solo de Top-3, decisiones no independientes y duplicados.
3. `scripts/ci/release_readiness.py`: inventario de rutas de código, cuatro manifiestos A4 y disponibilidad SHA de pesos si se suministran. Por diseño, jamás marca Gold o servicios AWS como certificados por inspección estática.
4. `.github/workflows/pre-gold-gates.yml`: CI sin credenciales, pesos, Gold humano o ejecución de AWS. Archivo JSON de estado contiene solo metadatos.

No se modifican registros humanos, fuentes ACL-200, DVC, entrenamientos ni Terraform. No se publica infraestructura de pago.

## 3. Protocolo de Gold Top-3 de chunks

**Antes de anotar:** seleccionar muestra verdaderamente held-out, no utilizada en entrenamiento, búsqueda de hiperparámetros, selección de modelos ni prompts; preservar el universo **completo** de chunks del artículo citado, sus hashes y la identidad del contexto. Ocultar a revisores scores y método. Dos evaluaciones por cada par (contexto, chunk), y un tercer adjudicador distinto para desacuerdos o abstenciones. Una consulta sin positivos identificables no se convierte artificialmente en fallo.

Cinco archivos privados, con nombres ejemplares y formatos exactos:

- `universe.json`: objeto con `schema_version=1`, `purpose="heldout_chunk_relevance"`, `used_for_tuning=false` y `cases`, cada uno con `context_id`, `citing_id`, `cited_id`, `split="test"`, `context_sha256` y `chunks`. Cada chunk tiene exactamente `chunk_id`, `text_sha256` y `section`. Registrar TODOS los chunks, no solo Top-3. El manifest no puede contener labels, Gold ni scores.
- `exclusions.json`: `schema_version=1` y ocho listas de cadenas: `train_context_ids`, `validation_context_ids`, `prompt_selection_context_ids`, `ranking_tuning_context_ids`, `train_citing_ids`, `validation_citing_ids`, `train_pairs`, `validation_pairs`. Los pares tienen formato `citante::citado`. Construir estas listas a partir de datos y manifests originales. Una lista vacía sin auditoría no constituye evidencia de independencia.
- `judgments.csv`: encabezados `context_id,chunk_id,annotator_id,relevance`; exactamente dos anotadores primarios **distintos** por cada chunk. `relevance` admite `0`, `1` o `abstain`.
- `adjudications.csv`: `context_id,chunk_id,adjudicator_id,relevance,reason`; una fila para cada desacuerdo/abstención; la relevancia final es binaria y el adjudicador es un tercero distinto.
- `rankings.csv`: `context_id,method,rank,chunk_id`; Top-3 único por consulta y método `bm25` o `scibert`, todos dentro del mismo universo evaluado. El código no usa el ranking como etiqueta.

Comando de evaluación cuando existan archivos humanos reales (los paths son **ilustrativos**, no existentes):

```bash
uv run python -m proyecto_de_grado.src.evaluation.top3_gold_gate \
  --manifest /PRIVADO/universe.json \
  --exclusions /PRIVADO/exclusions.json \
  --judgments /PRIVADO/judgments.csv \
  --adjudications /PRIVADO/adjudications.csv \
  --rankings /PRIVADO/rankings.csv \
  --output /PRIVADO/reportes/top3_agregado_001.json
```

El denominador de Recall@3 es **todos los fragmentos juzgados relevantes del documento citado**, no el número de posiciones Top-3. MRR@3 es 1/(posición del primer relevante) o cero sin hit, promediado sobre consultas evaluables; Hit@3 mide la presencia de al menos uno. Consultas sin relevantes se cuentan separadamente y excluyen de los denominadores; si no hay ninguna evaluable, métricas `null`. La salida solo contiene agregados y SHA de archivos de entrada, **no textos ni juicios individuales**.

El script deja `human_gold_certified=false`, `blindness_certified=false` y `split_independence_certified=false` siempre, porque ningún CSV puede por sí solo demostrar identidad humana, ceguera o que el manifiesto no omitió casos. Requiere acta y verificación privada del equipo. Las etiquetas de Haiku no son humanas.

## 4. Orden de operación y responsabilidades

| Paso | Instrumento/evidencia | Requiere humanos o recursos externos |
|---|---|---|
| Auditoría estructural | `uv run python scripts/ci/release_readiness.py` | No (solo código, manifiestos) |
| Verificación de los cuatro checkpoints | `uv run python -m src.app.checkpoint_gate --base /PESOS_ORIGINALES` | Sí: originales del equipo de entrenamiento |
| Restauración controlada A/B | `uv run python -m src.app.restore_a4 --source /PESOS_ORIGINALES` primero sin `--apply` | Sí |
| Inferencia real SciBERT A/B | `uv run python scripts/ci/smoke_tesis.py --cientifico --salida artifacts/qa_tesis/ciencia_001.json` | Sí: checkpoints y runtime |
| Cuatro celdas A4 SciBERT/SPECTER A/B | `packages/clasificacion-funcion` + manifiestos SHA | Sí: pesos SPECTER y recursos |
| Gold de nueve clases | `gold_freeze_audit.py`, acuerdo, 15%, acta #98–#100 | Sí: anotación y adjudicación humanas |
| Gold de chunks | nuevo gate Top-3, archivos privados #127 | Sí: doble anotación de **todo** el universo |
| Comparación factorial | `a4_factorial_benchmark.py`, controles #103/#128 | Sí: Gold adjudicado común, checkpoints |
| AWS y costos | Auditoría HTTPS/Cost Explorer read-only; luego publicación autorizada | Sí: cuenta, presupuesto, autorización |
| Artículo final | fuente, IEEE, revisión, PDF <=12 páginas | Sí: referencias verificadas y resultados |

**Control de confidencialidad:** No guardar pesos, claves, corpus privado, anotaciones humanas ni reportes individuales de evaluación en Git público. Un informe de preparación con datos sintéticos no es un resultado del proyecto.

## 5. Tablas preformadas para el informe

### A4: 2 × 2 con etiquetas Haiku (no Gold)

| Encoder | Entrada | Checkpoint histórico | Precision/Recall/F1 real en Gold | Estado |
|---|---|---|---|---|
| SciBERT | A | Manifiesto SHA semilla 42 | Pendiente | Pesos por recuperar |
| SciBERT | B | Manifiesto SHA semilla 42 | Pendiente | Pesos por recuperar |
| SPECTER | A | Manifiesto SHA semilla 42 | Pendiente | Pesos por recuperar |
| SPECTER | B | Manifiesto SHA semilla 42 | Pendiente | Pesos por recuperar |

Separar además las comparaciones de fuente de etiquetas Haiku **vs** jurado. Las ablaciones B con/sin sección y sección barajada son otro factor independiente. No usar eval 2015 para seleccionar y posteriormente afirmar independencia: el solapamiento histórico está documentado.

### Top-3 humano

| Método | N consultas evaluables | N sin positivos | Hit@3 | Recall@3 | MRR@3 |
|---|---|---|---|---|---|
| BM25 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| SciBERT | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

### A7 rendimiento/costos

| Modelo | Hardware, concurrencia | Latencia p50/p95 | Tokens o memoria | Costo observado | Errores |
|---|---|---|---|---|---|
| Baseline | Pendiente de corte comparable | Pendiente | Pendiente | Pendiente | Pendiente |
| SciBERT Top-3 | Pendiente en destino | Pendiente | Pendiente | Pendiente | Pendiente |
| A4 A/B | Faltan checkpoints | Pendiente | Pendiente | Pendiente | Pendiente |
| API comercial | Requiere autorización | Pendiente | Pendiente | Pendiente | Pendiente |

## 6. Traza editorial para artículo

Issue #112: artículo científico **máximo 12 páginas**, tamaño carta, márgenes 2,5 cm, Times New Roman 10, sencillo, resumen de 200–300 palabras y 3–5 keywords, citas IEEE numéricas verificadas y declaración de IA. Se exige un verbo principal por objetivo, según observación de Haydemar. Reutilizar `proyecto_de_grado/docs/articulo_metodologia_borrador_sin_gold_2026_11.md` y `docs/matriz_rubricas_100_distribucion_2026_11.md`.

| Rubro rúbrica | Peso | Evidencia que se necesita |
|---|---:|---|
| Problema | 10 | Introducción, brecha y objetivos |
| Estado del arte | 10 | Estudios citados y comparados |
| Metodología | 30 | A1–A7, 2×2, splits, arquitectura |
| Resultados | 15 | Tablas reales, Gold, matrices, Top-3 |
| Discusión | 15 | Sesgos, amenazas, aportes contrastados |
| Conclusiones | 10 | Respuestas sustentadas en resultados |
| Formato | 10 | 12 páginas, IEEE y fuente editable |

## 7. Qué sigue pendiente aunque este Mega PR pase CI

1. Recuperar y autenticar **cuatro** checkpoints A4 (no solo SciBERT A/B) y probar inferencia real por encoder/entrada.
2. Reconciliar los manifiestos de candidatos Gold, verificar splits, cobertura y 15% humano real; preservar independencia de test.
3. Doble anotación y adjudicación del Gold de nueve funciones y del Gold **separado** de fragmentos.
4. Ejecutar experimentos, ablations, comparaciones pareadas y benchmarks; no fabricar métricas.
5. AWS HTTPS/costos sólo bajo autorización, y revisión académica de referencias, tablas, autores y PDF final.

**Criterio de aceptación del PR:** pruebas adversariales sintéticas, código/manifest coherentes, CI verde, documentación revisable, indicadores honestos. NO cierra por sí solo issues #98–#115 ni #127–#128.

```bash
uv sync --locked --group dev
uv run pytest -q tests/test_top3_gold_gate.py tests/test_release_readiness.py
uv run python scripts/ci/release_readiness.py
uv run python scripts/ci/release_readiness.py --require-final
# El último debe devolver 1: la certificación final sigue pendiente.
```
