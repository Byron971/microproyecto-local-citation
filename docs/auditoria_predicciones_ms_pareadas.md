# Auditoría de predicciones individuales M/S: estado y reproducción

## Estado del inventario

- Los agregados del experimento 10 se encuentran en
  `proyecto_de_grado/docs/evidencias_experimentos_10/gold_metricas.csv`.
  Son métricas existentes, no predicciones individuales reproducidas.
- La carpeta `proyecto_de_grado/docs/evidencias_experimentos_10/` en
  GitHub contiene solamente `gold_metricas.csv`: **no incluye**
  archivos JSONL de predicciones por `context_id` de esos
  checkpoints M/S.
- GitHub sí conserva `predicciones_gold_v2.jsonl` de experimentos
  anteriores A4 (por ejemplo `scibert_A_2026`), pero el manifiesto
  de esos experimentos indica `data_use: provisional_only` y
  `estado: provisional_etiquetas_haiku_no_gold_humano`.
  **No deben etiquetarse erróneamente** como predicciones de los
  checkpoints originales del experimento 10 o del runtime M/S.
- Los manifiestos de experimentos 104 y 104b incluyen agregados
  estadísticos, no prueban la existencia de predicciones M/S 10
  individuales accesibles en la rama.

## Herramienta añadida

`scripts/evaluar_predicciones_ms_pareadas.py` toma **dos JSONL**
de predicciones individuales exportados de los modelos M y S,
con campos `context_id` (o `case_id`) y `pred_label`
(o `clase`). Exige IDs únicos y nueve etiquetas válidas.
Realiza la intersección por contexto, cruza el archivo
`test_gold_final.csv` sin modificarlo y calcula:

- Matrices de confusión 9×9 y F1 por clase; macro-F1 y weighted-F1
  incluyendo clases sin soporte.
- Cobertura por `context_id` y conteos de predicciones no pareadas.
- Tablas separadas por procedencia del Gold.
- Desacuerdos entre M y S, deltas descriptivos de macro-F1.
- Hashes SHA-256 de los tres insumos.
- Resumen sin textos ni IDs; no escribe datos de predicción
  en GitHub ni nuevas etiquetas Gold.

No hay un resultado numérico nuevo hasta que los
archivos **efectivamente correspondientes a M/S** sean localizados
y cotejados con los checkpoints originales.

## Búsqueda local sugerida (no altera datos)

Desde `ms-clon-limpio`, buscar posibles predicciones
en la carpeta original, omitiendo `node_modules` y entornos:

```powershell
$original = "C:\Users\juan sanz\Downloads\IAandes\microproyecto-local-citation-actualizado"
Get-ChildItem (Join-Path $original "proyecto_de_grado") -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -in ".jsonl", ".csv", ".parquet" -and $_.Name -match "(predic|logit|inferencia)" } |
  Select-Object FullName, Length, LastWriteTime |
  Format-List
```

No ejecutar el evaluador con los archivos A4 antiguos
simplemente para llenar tablas del experimento 10.
Si no hay predicciones exportadas, requerimos generación de
predicciones individuales desde los checkpoints sobre
casos autorizados con sus respectivas condiciones de entrada,
sin recurrir a etiquetas Gold durante la inferencia.

**Limitaciones:** la herramienta no demuestra que cada archivo
provenga del checkpoint declarado; esa procedencia requiere
manifiesto de ejecución separado. Las métricas calculadas sobre
el consolidado se etiquetarán como provisionales mientras
la certificación humana siga pendiente.


## Hallazgo posterior: artefactos locales exactos del notebook 10

La búsqueda local reportó dos ficheros de predicciones previamente
no incluidos en el árbol versionado:

- `proyecto_de_grado/artifacts/experimentos_10/M/pred_gold.jsonl`
- `proyecto_de_grado/artifacts/experimentos_10/S/pred_gold.jsonl`

El código fuente del notebook `notebooks/10_modelos_finales_M_S.ipynb`
escribe filas con `context_id`, `pred` (índice sin PH),
`pred_ph` (índice con PH) y `probs`. En el CSV histórico
`gold_metricas.csv`, M tiene `ph=True` y S `ph=False`.
Por ello, **si se confirma la procedencia de ambos ficheros**,
la comparación debe leer índice `pred_ph` en M y `pred` en S.
El script acepta ahora los selectores
`--campo-m pred_ph --campo-s pred` y rechaza índices fuera
de 0..8.

Ejemplo local, desde `ms-clon-limpio`, usando el mismo Gold
consolidado solo para puntuar la predicción ya emitida:

```powershell
$original = "C:\Users\juan sanz\Downloads\IAandes\microproyecto-local-citation-actualizado"
$artefactos = Join-Path $original "proyecto_de_grado\artifacts\experimentos_10"
.\.venv-ms\Scripts\python.exe scripts/evaluar_predicciones_ms_pareadas.py --pred-m "$artefactos\M\pred_gold.jsonl" --pred-s "$artefactos\S\pred_gold.jsonl" --campo-m pred_ph --campo-s pred --salida artifacts\resultados_ms_pareados_local.json
```

La salida guardada en `artifacts/` es local e ignorada por Git.
Este análisis **no** vuelve a entrenar ni hacer inferencia: coteja
predicciones históricas con etiquetas consolidadas. El Gold no debe
emplearse para optimizar los checkpoints o escoger hiperparámetros.
Antes de describir la comparación como reproducida deben comprobarse
los `context_id` y SHA-256 de ambos archivos.

También existe evidencia local de Top-3 bajo
`proyecto_de_grado/artifacts/top3_test_preparacion/evaluacion_modelos_reservada/`,
incluyendo `comparacion_rankings_sin_gold.csv` y
`resultados_humanos_revision_independiente/evaluacion_top3_humana_revision_independiente.json`.
Su contenido y esquema **aún no se han inspeccionado**; el nombre
del archivo no prueba anotación humana certificada ni permite afirmar
Recall@3.
