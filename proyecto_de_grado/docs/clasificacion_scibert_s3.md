# S3 — C2: función de cita con evidencia SciBERT Top-3

## Alcance

Incremento experimental del proyecto de grado. Reutiliza el prompt C1 histórico (`PROMPT_ETIQUETA_DIRECTA`) y añade hasta tres fragmentos del **artículo citado**, recuperados en S2.8. No modifica el preetiquetado previo ni los datos de ACL-200. Las etiquetas de Qwen son **predicciones automáticas no validadas**, no Gold.

La variante C2 implementada es: contexto TARGETCIT + título y resumen del artículo citado + tres fragmentos SciBERT. No suministra metadatos de sección; C3 queda separado para evitar la confusión entre C2 y C3.

## Controles de integridad

1. El SHA-256 del JSONL v6 debe coincidir exactamente con `sha256_entrada` del informe SciBERT.
2. Los ID de contextos deben coincidir en ambos archivos, sin faltantes ni duplicados, y `split` debe ser `train`.
3. El artículo `cited_id` debe coincidir por consulta.
4. Cada `chunk_id` Top-3 debe existir dentro de los fragmentos de ese artículo; no se admiten fragmentos ajenos ni IDs duplicados.
5. La similitud coseno debe ser finita. Los valores no se interpretan como probabilidades.
6. El historial se separa de C1 y es reanudable; se identifica mediante una huella que contempla el código, prompt, modelo, corpus e informe S2.8.
7. Las respuestas inválidas quedan registradas como `parse_error` sin asignar etiquetas arbitrarias. También se conservan los errores de proveedor, tiempos y trazas de fragmentos.

## Pruebas y ejecución

Con PowerShell desde la raíz del repositorio (entorno habitual del proyecto, no el entorno Python de SciBERT):

```powershell
uv run --group research --group dev pytest -q proyecto_de_grado/tests/test_clasificar_scibert_s3.py

$entrada = 'proyecto_de_grado/artifacts/enriquecimiento_s2_4/v6_expansion_20261011/candidatos_train_enriquecidos.jsonl'
$informe = 'proyecto_de_grado/artifacts/scibert_s2_8/experimento_67_casos.json'
$salida = 'proyecto_de_grado/artifacts/clasificacion_s3/piloto_c2_scibert_v6'

uv run --group research --group dev python -m proyecto_de_grado.src.data.clasificar_scibert_s3 --input $entrada --retrieval $informe --out $salida --limit 10 --solo-validar

uv run --group research --group dev python -m proyecto_de_grado.src.data.clasificar_scibert_s3 --input $entrada --retrieval $informe --out $salida --model qwen3:4b-instruct --base-url http://localhost:11434/v1 --limit 2
```

Repetir con `--limit 10` para completar los diez primeros casos pareados; los dos anteriores se omitirán por reanudación. Los artefactos quedan en `artifacts/` y **no deben incluirse en Git**.

## Interpretación

Comparar C1 y C2 mediante tasa de respuestas válidas, desacuerdo entre etiquetas y tiempos en **los mismos ID**. El cambio de predicción no equivale a una mejora. Ni la exactitud, ni F1 Macro, ni el valor de evidencia top-3 pueden establecerse sin referencias humanas Gold independientes. No emplear val/test en la experimentación actual.
