# Resultados experimentales provisionales M/S y recuperación Top-3

**Propósito:** aprovechar evidencias versionadas sin pedir nueva adjudicación manual. Este informe no declara Test Gold certificado ni nuevas métricas calculadas desde predicciones individuales. Verificación adicional: `python scripts/auditar_metricas_provisionales.py`.

## Clasificación retórica M/S

Fuente: `proyecto_de_grado/docs/evidencias_experimentos_10/gold_metricas.csv`.

| Modelo | Subconjunto histórico | n cubiertos | Macro-F1 | Accuracy |
|---|---|---:|---:|---:|
| M | `todo_cob` | 1530 | 0.551217 | 0.685621 |
| S | `todo_cob` | 1530 | 0.604604 | 0.725490 |
| M | `humano_cob` | 1060 | 0.557651 | 0.688679 |
| S | `humano_cob` | 1060 | 0.601488 | 0.703774 |
| M | `concordancia_cob` | 186 | 0.733462 | 0.801075 |
| S | `concordancia_cob` | 186 | 0.736739 | 0.806452 |

Diferencias descriptivas S menos M en macro-F1:
`todo_cob` = +0.053387; `humano_cob` = +0.043838;
`concordancia_cob` = +0.003276.
No se prueba significación estadística ni superioridad generalizable con solo agregados.

### Denominadores

El Gold consolidado posee 1533 filas, 1531 evaluables y dos no evaluables.
Las fuentes son: concordancia 186, una anotación 820,
discrepancia Opus 57 y solo Opus 470.
Aun si las etiquetas Gold son internamente consistentes,
la categoría de origen **no es garantía de validación humana independiente**.

- `todo_cob`: 1530 de 1531 evaluables (1 no cubierto).
- `humano_cob`: 1060 de 1061 evaluables de fuentes con participación
  humana (1 no cubierto; `concordancia` + `una_anotacion` +
  `discrepancia_opus`). La etiqueta puede seguir siendo provisional.
- `concordancia_cob`: 186 de 186 filas etiquetadas por
  concordancia, pero las hojas XLSX reconciliadas muestran solo
  **48 con dos anotaciones completas** según el criterio de
  diligenciamiento de campos. Así que el F1 sobre 186 no debe
  titularse F1 de 186 casos completamente certificados.

Falta auditar por `context_id` cuáles son los casos excluidos (1 caso por subconjunto, que podría ser el mismo)
y confirmar que M/S comparten los mismos IDs, no solamente el mismo n.
Los archivos agregados actuales por sí solos no lo prueban.

## Recuperación local Top-3 SciBERT vs BM25

Fuente: `proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/resumen.json`.

- Es una comparación técnica de **TRAIN sin Gold de relevancia**.
- 603 contextos, 89 artículos citados, 2574 chunks distintos.
- Cero violaciones de integridad reportadas por el experimento.
- Intersección promedio entre los Top-3: 0.812604 chunks,
  solape normalizado 0.270868 y mismo Top-1 en 19.07 % de consultas.
- Esos valores no miden precisión, Recall@3, MRR@3 ni nDCG@3;
  esos indicadores requieren relevancia anotada de fragmentos.

## Interpretación científica defendible

En este corte histórico, S registra mayor macro-F1 y accuracy
que M en las tres agregaciones publicadas, con diferencias
de magnitud distinta según procedencia. Es una **comparación
descriptiva condicionada al conjunto consolidado**; no es la
estimación final de generalización frente a un Gold certificado.

El contraste de recuperadores indica que las dos estrategias
seleccionan grupos de párrafos diferentes; no establece cuál
recupera evidencia más relevante. La demostración real sobre un
caso TRAIN, ejecutada exitosamente desde clon independiente,
prueba funcionamiento reproducible, no calidad de recomendación.

## Camino crítico sin solicitar anotación manual nueva

1. Ejecutar el auditor de agregados y conservar los hashes del CSV
   de métricas, Gold consolidado y `resumen.json`.
2. Reconstruir del historial los IDs de los casos evaluables
   no cubiertos y las predicciones M/S existentes, sin mirar el
   Gold para seleccionar hiperparámetros.
3. Si existen predicciones individuales emparejadas, calcular
   tablas por clase, cobertura y contraste pareado; de lo contrario,
   explicitar que solo hay agregados históricos.
4. Mantener como pendiente separado la certificación humana;
   no usar LLMs para reemplazarla silenciosamente.

**Límite:** ninguna de estas tareas exige que el investigador
adjudique a mano cientos de citas para terminar el reporte de
resultados provisionales.
