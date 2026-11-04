# Protocolo experimental unificado — Proyecto de grado (borrador para revisión)

Responsable técnico: John Byron Arias Sanz  
Fecha: 2026-11-04  
Estado: **PROPUESTA / NO APROBADO**. No usar para afirmar resultados finales.

## 1. Propósito y alcance
Hacer comparables y reproducibles las evaluaciones de clasificación de nueve funciones de cita y recuperación local Top-3. Separar estrictamente los resultados históricos del microproyecto de los resultados finales del proyecto de grado.

Las nueve clases, en este orden canónico, son:
1. Background
2. Gap
3. Basis
4. Comparison
5. Application
6. Improvement / Modification
7. Evidence
8. Identification of the Originator
9. Further Reading

Conservar una correspondencia versionada de nombres/IDs, incluido el tratamiento de etiquetas «Ambiguo/No evaluable» como abstenciones, nunca como décima clase.

## 2. Bloqueos previos a la evaluación final (P0)
- [ ] Resolver la incompatibilidad entre los manifiestos Gold planteados en PR #91 y #92; publicar **un único manifiesto** con identificadores y hashes inmutables.
- [ ] Confirmar, con los archivos y sus hashes, la procedencia de 18.000 casos, los ejemplos Haiku (aprox. 2.642/2.700, cifra por conciliar), las etiquetas del jurado y el gold humano.
- [ ] Verificar aislamiento de train, validation y test por **documento citante y par citante–citado**, no solo por identificador de fila ni año inferido del ID.
- [ ] Concluir doble anotación independiente y adjudicación; registrar criterios, desacuerdos, kappa/alpha y porcentaje humano real sobre el dataset final.
- [ ] No tratar los 20 ejemplos históricos de `annotations/citation_function/test_gold.jsonl` como test final.
- [ ] Verificar que todo dato Gold esté excluido del entrenamiento, selección de prompts, elección de jueces y ajuste de hiperparámetros.
- [ ] Completar balance o documentar explícitamente desviaciones frente al objetivo de 2.000 casos por clase; no sobremuestrear para simular cobertura real.

## 3. Registro canónico de datos
Antes de cada corrida registrar en un manifiesto: `dataset_id`, ruta/URI, SHA-256, tamaño, esquema de columnas, número total, conteo por clase, IDs excluidos, fecha de congelamiento, responsable y política de acceso. El Test Gold definitivo debe tener etiqueta adjudicada sin exponerla a los modelos.

Separar explícitamente:
- `train_A`: ejemplos con etiquetas Haiku, **solo train**.
- `train_B`: ejemplos con etiquetas del jurado, **solo train**.
- `validation`: ejemplos exclusivamente para elección de configuración, separados por documento/par.
- `test_gold`: ejemplos humanos adjudicados y congelados, **solo evaluación final**.

Registrar la intersección de IDs, documentos y pares entre cada partición; todas deben ser cero. Si A y B tienen tamaños/distribuciones distintos, declarar el factor de confusión y construir además una comparación controlada sobre **intersección de ejemplos** con idéntico presupuesto de entrenamiento, sin descartar la evaluación de corpus completos.

## 4. Diseño comparativo de clasificación
Hipótesis: cambiar la fuente de etiquetas de Haiku a jurado puede modificar el desempeño; **no asumir dirección positiva**.

Variantes mínimas:
- A: SciBERT fine-tuned con etiquetas Haiku.
- B: SciBERT fine-tuned con etiquetas del jurado.
- Baselines y modelos adicionales (QLoRA/open-weight, comerciales) únicamente con su modelo, prompt y configuración versionados.

Para A/B fijar: arquitectura exacta, tokenizer, longitud máxima, estrategia de truncamiento, semilla(s), epochs, learning rate, batch size, scheduler, weight decay, parada temprana, conjunto de validación, criterio de selección del checkpoint, hardware y versión de librerías. Estos valores **no están definidos por este documento**: se completan desde el código y se aprueban **antes** de consultar el Gold.

Cada predicción exportará: `example_id`, `model_id`, `model_version`, `experiment_id`, `predicted_label`, `scores_9` si existen, latencia, estado de parseo y referencia al manifiesto del Gold (sin registrar la etiqueta verdadera en salidas accesibles al modelo).

## 5. Métricas y análisis
- Clasificación: Precision, Recall y F1 por clase, macro y micro; accuracy, soporte por clase y matriz de confusión 9×9.
- Reportar distribución real y abstenciones/errores de formato separadamente; nunca eliminar silenciosamente ejemplos fallidos.
- Comparación A/B pareada por `example_id` del **mismo** Gold, reportando delta de F1 macro y errores por categoría.
- Si el tamaño lo permite, intervalos de confianza por bootstrap pareado con semilla fija; indicar unidad de remuestreo (preferentemente documento para respetar dependencias).
- No derivar certeza estadística de una sola corrida; si se hacen varias semillas, publicar dispersión.

## 6. Recuperación Top-3
Distinguir recuperación léxica BM25 (baseline) de embeddings densos SciBERT (objetivo). Mantener idénticos corpus de candidatos, reglas de chunking, contextos consulta y particiones.

- Chunks: máximo dos párrafos y 300 palabras, sin romper oraciones; conservar `cited_paper_id`, `chunk_id`, posición y sección retórica.
- Evaluar Recall@3 y MRR@3 (y, si es aplicable, nDCG@3) **solo cuando haya relevancia de chunks validada**.
- Sin anotaciones de relevancia a nivel de chunk, reportar ejemplos cualitativos sin afirmar calidad cuantitativa de recuperación.

## 7. Costos, latencia y estabilidad
Medir latencia por ejemplo con condiciones de hardware/concurrencia y tamaño de muestra documentados. Para API comerciales: contabilizar tokens y precio de tarifa correspondiente a la fecha; para modelos locales: duración, infraestructura y supuestos de costo. Reportar tasa de fallos y respuestas no parseables.

## 8. Reproducibilidad y evidencias de aceptación
- [ ] Manifiesto Gold único firmado/versionado y aprobado por equipo.
- [ ] Prueba automatizada anti-leakage por ID/documento/par con resultado verificable.
- [ ] Configs y semillas versionadas, artefactos y datasets con hash.
- [ ] Dos corridas A/B reproducibles y resultados en formato comparable.
- [ ] Reporte de métricas por clase y matrices; trazabilidad a predicciones individuales.
- [ ] Baseline BM25 separado del método SciBERT Top-3.
- [ ] Documento de amenazas a validez: desbalance, sesgo de anotación, contaminación, diferentes tamaños de train, selección adaptativa de prompts e infraestructura.

## 9. Dependencias existentes
Consultar issue #111 (auditoría técnica 4 nov), PR #89–#92 (todavía no tratados como fusionados en esta propuesta), y los issues del proyecto #93–#110. La integración en la rama `main` está condicionada a resolver las contradicciones de Gold y comprobar CI.

## 10. Decisiones pendientes del equipo
1. Nombre/ubicación del manifiesto Gold canónico y definición de cobertura humana.
2. Tamaño y procedencia exactos del conjunto A (2.642 vs. 2.700) y B.
3. Composición del conjunto de entrenamiento controlado y validación.
4. Parámetros de entrenamiento recuperados de las implementaciones reales.
5. Disponibilidad y protocolo de relevancia a nivel de chunk para evaluar Top-3.

**Regla de publicación:** no declarar números como resultados finales ni marcar el protocolo como aprobado hasta completar todos los P0.
