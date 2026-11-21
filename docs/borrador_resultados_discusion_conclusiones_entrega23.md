# Consolidado de metodología y resultados — corte de entrega 23-nov-2026

**Estado:** borrador técnico para integrar en documento académico. No declara una evaluación humana certificada ni aprobación del jurado. Esta versión se basa en resultados verificables del clon del investigador y los archivos privados documentados; los datos sensibles y checkpoints no están incorporados al repositorio.

## 1. Alcance del trabajo

Se implementó un prototipo para dos tareas relacionadas, pero evaluadas de forma separada:

1. **Recomendación local de citas:** dada una cita objetivo dentro del contexto de un artículo citante, ordenar fragmentos (`chunks`) del artículo citado y devolver hasta tres candidatos. Se compararon el recuperador léxico BM25 y la representación densa SciBERT.
2. **Clasificación de función de cita:** asignar una de nueve categorías funcionales a cada contexto. Se contrastaron dos modelos M y S del experimento 10, manteniendo su configuración histórica de predicción (M con `pred_ph`; S con `pred`).

No se debe inferir de esta evaluación que la mejora de una de las tareas garantiza mejora de la otra: las muestras, referencias y métricas son diferentes.

## 2. Material y procedimientos

### 2.1. Clasificación de nueve funciones

El conjunto consolidado `test_gold_final.csv` contiene 1533 registros, de los cuales 1531 figuran evaluables. Las dos exportaciones privadas `experimentos_10/{M,S}/pred_gold.jsonl` contienen 1532 predicciones cada una. El cruce por `context_id` permitió puntuar **1530 registros evaluables emparejados**; un evaluable carece de predicción M y S. Se utilizaron las nueve categorías del proyecto y se computaron accuracy, macro-F1, weighted-F1, matrices de confusión y desacuerdos M/S mediante `scripts/evaluar_predicciones_ms_pareadas.py`.

La reproducción corresponde al cálculo de métricas a partir de **predicciones históricas existentes**; no implica una nueva inferencia ni reentrenamiento. El Gold consolidado no tiene certificación humana completa; la presencia de la etiqueta de fuente `concordancia` no equivale a acreditar dos formularios humanos completos.

### 2.2. Recuperación de fragmentos Top-3

Se utilizaron 30 contextos asociados a artículos citados, fragmentados en 1005 pares `(context_id,chunk_id)`, con 14 a 138 fragmentos por consulta. Los Excel A/B completados fueron consolidados en 1005 etiquetas binarias: **96 relevantes** y **909 no relevantes**. Las versiones A/B consolidadas coinciden; esto no demuestra independencia ciega de una primera pasada.

BM25 y SciBERT devolvieron tres fragmentos por consulta. Una auditoría automatizada verificó **30/30 consultas, 1005/1005 pares etiquetados y 180/180 fragmentos Top-3 válidos**: cero faltantes, duplicados o IDs extraños en los rankings. Estos controles certifican **exhaustividad respecto del corpus fragmentado exportado**, no preservación integral del artículo original OCL ni pertinencia semántica de todas las etiquetas.

De las 30 consultas, 25 contenían al menos un fragmento relevante y se incluyeron en los promedios de Hit@3, Recall@3 y MRR@3. Cinco sin positivos se reportan excluidas, sin asignarles artificialmente cero. Las métricas se calcularon nuevamente desde los archivos privados mediante `scripts/recalcular_top3_etiquetas_finales.py`.

Definiciones por consulta elegible:
- `Hit@3`: 1 si Top-3 contiene al menos un fragmento marcado relevante; 0 en caso contrario.
- `Recall@3`: fracción de todos los fragmentos relevantes del corpus de esa consulta presentes entre los tres recuperados.
- `RR@3`: inverso de la posición del primer relevante dentro de Top-3, o 0 si no existe; `MRR@3` es la media.

## 3. Resultados

### 3.1. Clasificación M/S

| Indicador (n = 1530) | Modelo M | Modelo S |
| --- | ---: | ---: |
| Accuracy | 0.685621 | **0.725490** |
| Macro-F1, 9 clases | 0.551217 | **0.604604** |
| Weighted-F1 | 0.672334 | **0.715024** |

La diferencia observada S menos M fue **+0.053387** en macro-F1 y **+0.039869** en accuracy. Ambos clasificadores discreparon en **397 de los 1530 casos** (25.95%). Las métricas coinciden con los agregados históricos registrados en `proyecto_de_grado/docs/evidencias_experimentos_10/gold_metricas.csv`. El resultado es **provisional**, pues compara con el Gold consolidado aún no certificado. No se ha documentado aquí prueba de significación pareada para M/S.

### 3.2. Recuperación Top-3 (n = 25 consultas elegibles)

| Métrica | BM25 | SciBERT | BM25 − SciBERT |
| --- | ---: | ---: | ---: |
| Hit@3 | **0.840000** | 0.520000 | +0.320000 |
| Recall@3 | **0.515051** | 0.211414 | +0.303636 |
| MRR@3 | **0.666667** | 0.433333 | +0.233333 |

| Métrica | Consultas mejores con BM25 | Mejores con SciBERT | Empates |
| --- | ---: | ---: | ---: |
| Hit@3 | 8 | 0 | 17 |
| Recall@3 | 15 | 0 | 10 |
| MRR@3 | 10 | 3 | 12 |

El informe anterior, correspondiente a **99 positivos / 906 negativos**, reportaba otros valores (por ejemplo MRR@3 BM25 0.686667); no mezclarlo con los **96 positivos / 909 negativos** del corte actual. Las pruebas exactas de signos sobre los conteos actuales, si se reportan, son exploratorias y condicionadas a la independencia entre consultas; no sustituyen intervalos de confianza ajustados por artículo ni el control de sesgo de selección.

## 4. Discusión preliminar

- En la clasificación provisional de nueve funciones, S presentó mayor macro-F1 que M. No puede interpretarse como ventaja definitiva antes de concluir la auditoría humana del Gold.
- En la submuestra de recuperación, BM25 recuperó fragmentos relevantes con más frecuencia que SciBERT según las etiquetas consolidadas. Este resultado **cuestiona la premisa de que una representación densa preentrenada sea necesariamente superior** en recuperación local; no identifica por sí mismo la causa del rendimiento observado.
- El solape de Top-3 entre recuperadores del experimento técnico TRAIN (603 consultas, solape medio ≈ 0.270868) mide diferencia de rankings, **no** relevancia. No se combina numéricamente con los 25 casos del test fragmentado.
- La doble tarea exige informar por separado la calidad de recuperación y la de clasificación, ya que sus conjuntos de evaluación no son directamente comparables.

## 5. Limitaciones y amenazas a la validez

1. **Proveniencia humana:** el acuerdo total de A y B sobre archivos consolidados no permite afirmar anotación inicial ciega independiente, y κ=1 posterior a revisión no es κ inicial.
2. **Clasificación:** el Gold v3 está consolidado pero no plenamente certificado por revisión humana; los 1530 emparejados representan una cobertura evaluable casi completa, no validación humana plena.
3. **Selección Top-3:** las 30 consultas constituyen una muestra filtrada, no necesariamente representativa de ACL-200 TEST; cinco consultas sin positivos quedaron excluidas de las medias.
4. **Exhaustividad acotada:** se auditaron todos los 1005 fragmentos del corpus fragmentado, sin demostrar que la extracción y fragmentación cubran todo texto disponible del documento OCL de origen.
5. **Independencia documental:** revisar por separado los cruces train/val/test y si varias consultas comparten documentos antes de inferencia estadística poblacional.
6. **Configuración comparativa:** las métricas reproducen predicciones/rankings históricos; no se ha ejecutado aquí un reentrenamiento o estudio completo de robustez y calibración.

## 6. Conclusiones del corte

El prototipo dispone de evidencia reproducible de ambos módulos: **clasificación M/S sobre 1530 casos evaluables emparejados**, y **recuperación BM25/SciBERT sobre 25 consultas elegibles con 1005 pares anotados** en 30 consultas totales. El experimento de recuperación tiene cobertura exhaustiva dentro del corpus exportado. En los conjuntos considerados, S obtuvo mejores métricas de clasificación y BM25 obtuvo mejores métricas de recuperación. Los resultados se consideran provisionales/exploratorios en su inferencia científica hasta completar las verificaciones humanas y documentales pendientes.

## 7. Evidencia auditable y reproducibilidad

- `docs/resultados_ms_pareados_local_20261121.md` y `scripts/evaluar_predicciones_ms_pareadas.py`.
- `docs/resultados_top3_recalculados_1005_entrega23.md`, `scripts/recalcular_top3_etiquetas_finales.py` y `scripts/auditar_cobertura_top3_1005.py`.
- SHA-256 del corpus Top-3: `383475458ecb1d124a8367199e2c66f367e99b480cde4fd9622c420147a427f1`.
- SHA-256 de las etiquetas consolidadas: `e695bd86f481b0784906b47a1de0baec40a9a5063597ea779f388df6dfd07064`.
- SHA-256 BM25: `25d32d3e560e62f5ee92a8b05a6e81cd99697f3f528fa92b4387f225723f9a0d`.
- SHA-256 SciBERT: `762b02d5f03d4a5e449edc48a49d85219731b145f0b7d75700598d054ac40222`.
- Las anotaciones y checkpoints son privados y se mantienen fuera de Git, conforme a las restricciones de custodia.

**Pendientes de edición académica:** incorporar referencias bibliográficas verificadas y la definición institucional exacta de entregables, figuras, tabla de clases, cronograma cumplido y aportes del equipo. No inventar bibliografía ni validaciones no realizadas.
