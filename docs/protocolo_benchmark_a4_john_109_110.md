# John — Protocolo A4/A6 para evaluación conjunta de SciBERT y SPECTER

**Issue #109:** protocolo único, cinco factores de validez, métricas y líneas base.  
**Issue #110:** tabla y contrastes pareados reproducibles sobre el Gold común.  
**Estado: herramienta de evaluación PROVISIONAL. No hay métricas de modelos ejecutados ni Gold humano certificado.**

## 1. Alcance científico exacto

La propuesta A4 exige dos **encoders de clasificación** (SciBERT y SPECTER) con dos **formas de construir la entrada**. La procedencia de etiquetas Haiku/Jurado constituye **otro factor**, no equivale a A/B.

| Celda A4 | Modelo base | Información de entrada | Etiquetas de entrenamiento |
|---|---|---|---|
| SciBERT-A | SciBERT | Contexto + título/abstract citado | Fuente fijada (Haiku o Jurado) |
| SciBERT-B | SciBERT | Contexto + Top-3 + sección retórica | Misma fuente e IDs que SciBERT-A |
| SPECTER-A | SPECTER | Contexto + título/abstract citado | Misma fuente e IDs de A4 |
| SPECTER-B | SPECTER | Contexto + Top-3 + sección retórica | Misma fuente e IDs de A4 |

Se requiere **una matriz completa de cuatro corridas por fuente de etiquetas**. Si se dispone de matrices Haiku y Jurado serán ocho corridas, pero no se inventa ninguna ejecución. El comparador acepta sus predicciones existentes y no entrena modelos ni descarga pesos. Exige que las cuatro corridas de la misma fuente declaren **iguales hashes del conjunto de IDs y etiquetas de entrenamiento**; los hashes de la definición de entrada A deben ser iguales entre encoders, igual para B, aunque el checkpoint y tokenizer sean distintos. La coincidencia de los hashes declarados se debe **cotejar contra artefactos reales**.

**Contrastes controlados:**
1. Dentro de SciBERT: B frente a A, mismo train y test.
2. Dentro de SPECTER: B frente a A, mismo train y test.
3. Encoder: SPECTER frente a SciBERT con entrada A.
4. Encoder: SPECTER frente a SciBERT con entrada B.

Si hay ambas fuentes: contrastar etiquetas-Jurado frente a etiquetas-Haiku únicamente donde **los IDs del entrenamiento sean iguales**. Si difieren, el programa omite esos deltas causales y registra una advertencia: métricas descriptivas separadas no prueban que el cambio se deba a las etiquetas.

Los encoders SciBERT y SPECTER clasifican funciones de cita (9 clases). No confundir con un recuperador de fragmentos SciBERT Top-3; **BM25 continúa como baseline léxico** de recuperación y no cuenta como método denso por sí solo.

## 2. Política de Gold: fail-closed

La evaluación final de tesis está **bloqueada por diseño**. Se permite solo `--provisional` y se exige `--raw-dir` con corpus ACL-200 para comprobar que todos los ejemplos pertenecen a test. Aplica `inspect_gold` para excluir casos de calibración/práctica y evitar que los 20 ejemplos históricos usados para selección de prompts se presenten como prueba nueva.

Los 2.700 CSV ya anotados **no equivalen a un Gold humano final indiviso**: 1.321 son candidatos de validación 2014 y 1.379 de test 2015, con 4 exclusiones históricas de test. En paralelo, PR #91 propone 1.533 test 2015; el PR #143 documenta 832 coincidencias, 701 casos solo PR #91 y 547 solo PR #92. El equipo aún debe escoger y firmar **un solo manifiesto canónico de test**, conciliar la evidencia humana y verificar leakage a nivel de documentos.

Aun si el script devuelve exit code 0:
- `status = PROVISIONAL_NO_CERTIFICADO`;
- `test_gold_certified = false`;
- `ready_for_final_article = false`.

**Una simulación que pasa tests no implica haber entrenado SciBERT/SPECTER ni verificado resultados.**

## 3. Contrato de predicciones

Crear un directorio de trabajo local o en almacenamiento autorizado con un archivo JSONL por variante, que contenga para **cada caso idéntico** `case_id`, `status: "ok"`, `pred_label` (o `pred_index`, índices 0–8). No incluir ejemplos ausentes, duplicados, abstenciones ni casos extra: se **rechazan** para evitar sesgo de eliminación de predicciones difíciles. Las predicciones pueden incluir metadatos adicionales, pero el evaluador **no los necesita para leer etiquetas Gold de los modelos**.

Ejemplo de fila ficticia:
```json
{"case_id":"C-001","status":"ok","pred_label":"Application"}
```

El Gold, guardado **por separado** y nunca pasado a los modelos, usa `id`, `input` (con una marca `TARGETCIT`), `gold` (una de nueve clases), `citing_id` y `cited_id`. Su contenido debe ser aprobado por el equipo. Ejemplo ficticio:
```json
{"id":"C-001","input":"We apply TARGETCIT in our work.","gold":"Application","citing_id":"P15-001","cited_id":"P12-002"}
```

## 4. Manifiesto A4 (ejemplo NO ejecutable con placeholders)

Crear `config_a4.json` con formato:
```json
{
  "schema_version": "a4_factorial_v1",
  "data_use": "provisional_only",
  "variants": [
    {
      "name": "scibert_a",
      "encoder": "SciBERT",
      "input": "A",
      "training_labels": "Haiku",
      "predictions": "scibert_a.jsonl",
      "checkpoint_sha256": "<HASH_REAL_64_HEX>",
      "train_ids_sha256": "<HASH_REAL_64_HEX>",
      "train_labels_sha256": "<HASH_REAL_64_HEX>",
      "input_spec_sha256": "<HASH_ESPECIFICACION_A_64_HEX>"
    }
  ]
}
```
Repetir con `scibert_b`, `specter_a`, `specter_b`, con los campos correspondientes. Los cuatro deben figurar en el mismo archivo, no solo la variante del ejemplo. Los hashes deben generarse de los artefactos reales, **no copiar un placeholder ni un hash de ejemplo**. Los archivos de predicciones deben estar dentro del directorio del manifiesto o en subdirectorios, no en rutas externas o `../`. Los checkpoints no se descargan ni verifican por sí solos mediante este script: la revisión del PR científico de Carlos Duque valida su procedencia.

Ejecutar (una vez aprobado el dataset de desarrollo para pruebas, sin exponer el test final):
```bash
uv sync --group dev
uv run python -m src.evaluation.commercial.a4_factorial_benchmark \
  --gold /ruta_autorizada/gold_candidato.jsonl \
  --config /ruta_autorizada/experimentos/config_a4.json \
  --raw-dir data/raw \
  --output-dir artifacts/benchmark_a4_provisional \
  --provisional --bootstrap-draws 1000 --seed 42
```

Salida: `a4_factorial_provisional.json` (métricas de nueve clases, matriz 9×9, comparaciones y advertencias agregadas; huellas de archivos) y `a4_model_scores.csv` para tabla del artículo. **La prueba sintética solo valida funcionamiento.** No publicar el reporte de un Test Gold real hasta confirmar permisos, confidencialidad y reglas del curso.

## 5. Métricas y justificación

- Reportar precisión, recall y **F1 por cada una de las nueve funciones**, macro-F1 calculado sobre **las nueve clases fijas**, micro-F1 y accuracy, soportes y matrices 9×9. Si una clase no aparece en un conjunto reducido, su F1 se trata como cero en la métrica macro de nueve clases, no se elimina del denominador.
- Reportar `n_same_gold` idéntico en todas las corridas; las comparaciones entre predicciones son **pareadas por ID** y muestran diferencia de macro-F1, accuracy, y recuento A-solo correcta/B-solo correcta/ambas correctas/ambas incorrectas. Errores por clase son agregados, sin copiar textos.
- `--bootstrap-draws >=100` produce intervalos percentiles exploratorios del delta macro-F1 re-muestreando por **documento citante (`citing_id`)**, para respetar dependencia de citas dentro del mismo artículo. Exige al menos dos documentos; no afirmar significancia con una sola semilla o con corpus desbalanceado.
- Para reportar latencia, tokens, RAM, GPU o costos, usar mediciones reales con hardware/concurrencia/fecha y coste documentados. Este comparador **no genera benchmark de rendimiento del sistema**, solo desempeño predictivo a partir de etiquetas ya calculadas.
- Para **baselines**, recuperar y documentar en un apartado separado la regla mayoritaria aprendida **solo de train**, y baselines recuperadores BM25 frente a SciBERT Top-3 sobre un Gold de chunks validado. No elegir la clase mayoritaria mirando el Test Gold; tampoco usar BM25 como clasificación de función de cita.

## 6. Verificaciones y responsabilidades

```bash
uv run pytest -q tests/test_a4_factorial_benchmark.py tests/test_paired_benchmark.py
```

| Responsable | Evidencia necesaria |
|---|---|
| Carlos Duque (#103/#102) | Cuatro archivos de predicción A4 por fuente disponible; checkpoint/versiones y hashes reales, mismo split y trazabilidad de train; abstenciones/errores reportados |
| John (#109/#110) | Validar manifiesto, exactitud de nueve clases, igualdad de ejemplos/factores, tabla y matrices, documentación de metodología, no hacer tuning del test |
| José y Caicedo (#98/#99/#100/#125) | Gold test canónico, notas de revisión humana/adjudicación, partición ACL-200, IDs exclusivos y solapados entre PR #91/#92 |
| Gabriel (#108/#112) | Redacción y evidencia en el artículo, declaración de IA, limitaciones, ningún número simulado como real |

**No cerrar #110** por CI sintético: faltan corridas reales SciBERT/SPECTER y Gold final firmado. Se puede integrar la infraestructura de comparación una vez que pase CI y revisión técnica.
