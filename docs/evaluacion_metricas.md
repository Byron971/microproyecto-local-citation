# Pipeline de evaluación y métricas — issue #42

Este módulo consolida la evaluación comparable de los modelos de clasificación de función de cita sobre el mismo Test Gold.

## Entrada

El pipeline consume el archivo results.jsonl generado por src/evaluation/commercial/cli.py. Cada registro conserva caso, proveedor, modelo, prompt, respuesta cruda, respuesta parseada, latencia, tokens, costo opcional, reintentos, estado y etiqueta gold.

La clasificación usa las nueve categorías definidas para el proyecto:

1. Background
2. Gap
3. Basis
4. Comparison
5. Application
6. Improvement / Modification
7. Evidence
8. Identification of the Originator
9. Further Reading

La etiqueta gold puede expresarse como nombre de categoría o índice 0 a 8. También se admite un vector de nueve valores con máximo único para facilitar integración con otros artefactos.

## Métricas

Por cada combinación prompt + proveedor + modelo se calculan Precision Macro, Recall Macro, F1 Macro, Precision Micro, Recall Micro, F1 Micro, Accuracy, cobertura de clasificación, tasa de errores de formato, tasa de errores del proveedor, latencia promedio, reintentos promedio, tokens de entrada y salida, y costo estimado total cuando el runner recibió pricing explícito.

Si un caso tiene varias repeticiones, primero se promedian sus vectores válidos y luego se toma argmax. De esta manera, las repeticiones de estabilidad no inflan artificialmente el tamaño del Test Gold.

Los errores de proveedor no se contabilizan como errores de formato. Las respuestas no parseables tampoco se fuerzan a una clase inventada: reducen la cobertura y se registran aparte. Precision, Recall y F1 se calculan únicamente sobre casos con etiqueta gold y predicción válida.

## Matrices de confusión

Las matrices siempre usan las nueve categorías y mantienen el orden definido en la propuesta. Esto permite comparar modelos y prompts aunque un subconjunto particular no contenga observaciones de todas las clases.

## Ejecución

Ejecutar:

python -m src.evaluation.commercial.metrics --results artifacts/commercial_eval/results.jsonl --output-dir artifacts/commercial_eval/metrics

Se generan tres tipos de artefacto:

- evaluation_summary.csv: tabla consolidada por modelo y prompt.
- predictions.csv: predicción final por caso y vector promedio.
- confusion_matrices: una matriz CSV por combinación modelo y prompt.

## Criterio para la entrega del 20 de septiembre

El pipeline queda listo para recibir resultados comerciales y resultados de otros modelos adaptados al mismo contrato. No inventa métricas cuando gold es null; en ese escenario reporta únicamente información operacional. Precision, Recall y F1 deben reportarse después de contar con un Test Gold realmente validado.
