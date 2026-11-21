# Reproducción local de las métricas pareadas M/S — 21 de noviembre de 2026

**Origen:** ejecución de `scripts/evaluar_predicciones_ms_pareadas.py` realizada por el investigador en el clon independiente, usando `M/pred_gold.jsonl` con `--campo-m pred_ph` y `S/pred_gold.jsonl` con `--campo-s pred`. Datos de salida comunicados por terminal y contrastados con los agregados históricos `proyecto_de_grado/docs/evidencias_experimentos_10/gold_metricas.csv`. Los archivos JSONL de predicciones se mantienen **privados y fuera del repositorio**.

## Comparación emparejada (provisional)

| Medida | M | S |
| --- | ---: | ---: |
| n evaluables emparejados | 1530 | 1530 |
| Accuracy | 0.685621 | 0.725490 |
| Macro-F1 (nueve clases) | 0.551217 | 0.604604 |
| Weighted-F1 | 0.672334 | 0.715024 |

Diferencia S−M: macro-F1 **+0.053387** y accuracy **+0.039869**; predicciones distintas en **397** de los 1530 IDs emparejados (25.95 %). Estas diferencias son descriptivas, sin contraste estadístico pareado ejecutado.

## Cobertura y huellas locales

- Universo evaluable según `test_gold_final.csv`: **1531**.
- Predicciones individuales M: **1532**; S: **1532**.
- Pares de predicciones disponibles para evaluación: **1530**.
- Casos evaluables solo M: **0**; solo S: **0**; sin predicción de ninguno: **1**.
- Las predicciones individuales de los modelos y la salida detallada quedan en `artifacts/` o en el repositorio original; no subirlas a Git.
- SHA256 M: `aa2e3cf42785e0b93dabdba4c22d53b4528f481156159e7bcbb8d933304b526e`
- SHA256 S: `9da79f35277f8efa8ca61d9dca41da7fdac547c9e41a90f2d7e2bc659a32b77a`
- SHA256 Gold (Windows CRLF): `eea8a4d3f5d53f2693259c1624544a0e38ab21f0a39303a6f25e8b4bebe93603`.

## Evidencia adicional encontrada para recuperación Top-3

El investigador encontró localmente `proyecto_de_grado/artifacts/top3_test_preparacion/evaluacion_modelos_reservada/resultados_humanos_revision_independiente/evaluacion_top3_humana_revision_independiente.json`. Su estructura superior contiene: `estado`, `metodologia`, `cohen_kappa_post_revision`, `acuerdo_post_revision`, `cohen_kappa_primera_pasada`, `etiquetas`, `metrica_denominador`, `resultados`, `diferencias_SciBERT_menos_BM25`, `comparacion_consulta_a_consulta`, `hashes`, `limitaciones`.

**Pendiente:** leer el resumen agregado de los resultados Top-3, comprobar denominadores y metodología; el nombre del archivo no certifica validez independiente.

## Límites de interpretación

Los resultados reproducen las métricas históricas frente al consolidado de etiquetas provisional, pero no validan la independencia de anotadores ni la validez semántica del Gold. El registro de una predicción en un JSONL no es, por sí solo, prueba de un nuevo ciclo de inferencia: aquí se **recalcularon métricas** desde predicciones existentes. Se necesita comprobar el ID evaluable no cubierto y determinar si las dos predicciones adicionales corresponden a casos no evaluables.
