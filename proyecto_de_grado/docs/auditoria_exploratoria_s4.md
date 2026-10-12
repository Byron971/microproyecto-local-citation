# S4.1 — Auditoría experimental de clasificadores C1/C2 (solo train)

## Objetivo

Verificar de forma reproducible que las predicciones Qwen C1 (contexto+título+resumen) y C2 (C1+SciBERT Top-3) provienen de los mismos casos de entrenamiento, y caracterizar su concentración en `Basis`, cambios por contexto y composición por artículo citado. El análisis es solo descriptivo: **no calcula ni simula F1, precisión, recall o métricas Gold**.

## Fuentes utilizadas

- Política `proyecto_de_grado/docs/politica_evaluacion_g0.md` (G0.5, borrador operativo pendiente de ratificación).
- `proyecto_de_grado/docs/protocolo_top3_s2_3.md`.
- `proyecto_de_grado/docs/informe_s3_c1_c2.md`.
- Resultados locales v6 de S2.8 y S3 (no se añaden a Git).

## Controles

- Identidad exacta de contextos en corpus, C1, C2 y recuperación; solo `train` y `TARGETCIT` único.
- Huella SHA-256 del corpus contra S2.8 y contra ambos resúmenes S3.
- Huella del informe S2.8 contra el resumen de C2.
- Mismo identificador del modelo Qwen, fingerprints de ejecución correctos y etiqueta única en la taxonomía de nueve funciones.
- Evidencia C2: IDs, orden, artículo citado, hash del texto y similitud compatibles con el informe SciBERT.
- Denominador de casos válidos y estados erróneos registrados separadamente.
- Cálculo de cambios y frecuencias por artículo citado para detectar concentración documental.

## Salida

El script produce, bajo una carpeta nueva de `proyecto_de_grado/artifacts/`:

- `auditoria_s4.json`: resultados estructurados, huellas de archivos y desagregación por artículo.
- `transiciones_s4.csv`: 1 fila por predicción discordante, sin reproducir texto del corpus.
- `resumen_s4.md`: resumen reproducible para incorporar al informe, no Gold.

No sobrescribe archivos existentes. No consulta Ollama, no carga GPU ni realiza anotaciones humanas.

## Interpretación y siguientes etapas

La predominancia de `Basis` podría estar relacionada con selección documental, prevalencia real, prompt o sesgos de Qwen. Esta auditoría no distingue por sí sola entre esas explicaciones, ni convierte un desacuerdo en evidencia de mejora.

La política G0.5 plantea F1 Macro sobre un **nuevo Test Gold independiente** y relevancias de fragmentos anotadas exhaustivamente para medir Hit@3/Recall@3/MRR@3. El conjunto histórico usado para selección de prompts no constituye un test válido. El requisito de revisión humana de al menos 15 % del dataset final es separado del tamaño del Test Gold; cualquier cambio de alcance necesita ratificación académica.

Se recomienda no comenzar otra corrida masiva ni editar prompts a partir de un subconjunto de discrepancias antes de definir la evaluación controlada. S4.2 puede preparar el paquete ciego de una muestra pequeña de desarrollo, mientras la decisión sobre su ejecución humana queda pendiente del equipo.
