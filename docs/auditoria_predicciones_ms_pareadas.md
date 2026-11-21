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
