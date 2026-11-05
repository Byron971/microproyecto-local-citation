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
- `train_haiku`: ejemplos con etiquetas Haiku, **solo train**.
- `train_jurado`: ejemplos con etiquetas del jurado, **solo train**.
- `validation`: ejemplos exclusivamente para elección de configuración, separados por documento/par.
- `test_gold`: ejemplos humanos adjudicados y congelados, **solo evaluación final**.

Registrar la intersección de IDs, documentos y pares entre cada partición; todas deben ser cero. Si A y B tienen tamaños/distribuciones distintos, declarar el factor de confusión y construir además una comparación controlada sobre **intersección de ejemplos** con idéntico presupuesto de entrenamiento, sin descartar la evaluación de corpus completos.

## 4. Diseño comparativo de clasificación — dos factores independientes
**Corrección de alcance A4 y nomenclatura (5-nov-2026):** la propuesta exige entrenar clasificadores basados en **SciBERT y SPECTER** con **ambas entradas A/B** (cuatro combinaciones: SciBERT-A/B, SPECTER-A/B). Las **entradas A/B** se definen por el contenido suministrado, **NO** por la procedencia de las etiquetas. Haiku/jurado es un factor distinto. SPECTER es otro encoder base, no una tercera entrada ni un sinónimo de etiquetas.

**Factor 0: arquitectura de encoder**
- **SciBERT** con cabeza de clasificación para nueve funciones de cita.
- **SPECTER** con cabeza de clasificación para nueve funciones, versión/tokenizer/pooling/truncamiento documentados. No declarar entrenado o desplegado hasta contar con código, checkpoint y ejecución verificados (#103).
- Comparar con igual Test Gold y política de splits, reportando diferencias de recursos y presupuesto.

**Factor 1: configuración de entrada (A/B de la propuesta)**
- **Entrada A:** contexto de cita + título y abstract del trabajo citado.
- **Entrada B:** contexto de cita + fragmentos Top-3 SciBERT y sección retórica (con especificación de truncamiento y separadores). Para aislar efectos, medir B sin sección, B con sección verdadera y B con sección barajada.
- Mantener el mismo Test Gold humano y, cuando se compare entrada, la misma fuente de entrenamiento.

**Factor 2: fuente de la etiqueta de entrenamiento (nombres explícitos, sin letras A/B)**
- **Etiquetas-Haiku:** entrenar SciBERT sobre el corpus Haiku, con versión, prompt y tamaño reales verificados.
- **Etiquetas-Jurado:** entrenar SciBERT sobre consenso de jueces sin contaminar el Gold ni usar ejemplos vistos por el juez ajustado.
- Alinear por ID el tamaño/distribución para el análisis controlado, o declarar diferencias de muestra y confusores.

**Matriz mínima A4 (obligatoria para cubrir el enunciado, 2 encoders × 2 entradas):**
| Encoder | Entrada A: contexto + título/abstract | Entrada B: contexto + sección/Top-3 |
|---|---|---|
| SciBERT | SciBERT-A | SciBERT-B |
| SPECTER | SPECTER-A | SPECTER-B |

**Experimento adicional independiente:** etiqueta-Haiku vs etiqueta-Jurado para cada configuración en que sean viables datos y cómputo. Idealmente sería una matriz 2 encoders × 2 entradas × 2 procedencias (8 celdas); declarar explícitamente celdas no ejecutadas, sus causas y los confusores. La ablación con/sin sección no sustituye ninguna de las cuatro celdas A4.

Modelos adicionales (QLoRA/open-weight, comerciales) mantienen versiones/prompts explícitos. **No asumir que ninguna comparación ha sido ejecutada ni que sus resultados mejoran.**

Para cada contraste fijar: arquitectura exacta, tokenizer, longitud máxima, truncamiento, semilla(s), epochs, learning rate, batch size, scheduler, weight decay, parada temprana, validación, elección de checkpoint, hardware, dataset manifest y versiones. Completar valores desde implementaciones reales **antes** de usar Gold.

Cada predicción exportará: `example_id`, `model_id`, `model_version`, `experiment_id`, `predicted_label`, `scores_9` si existen, latencia, estado de parseo y referencia al manifiesto del Gold (sin registrar la etiqueta verdadera en salidas accesibles al modelo).

## 5. Métricas y análisis
- Clasificación: Precision, Recall y F1 por clase, macro y micro; accuracy, soporte por clase y matriz de confusión 9×9.
- Reportar distribución real y abstenciones/errores de formato separadamente; nunca eliminar silenciosamente ejemplos fallidos.
- Comparaciones pareadas por `example_id` del **mismo** Gold: (a) entrada A frente a B **dentro de cada encoder**, (b) SciBERT frente a SPECTER con entrada/etiquetas fijas, (c) Haiku frente a jurado con entrada/encoder fijos, y (d) ablaciones de sección. Reportar delta de F1 macro y errores por clase.
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
- [ ] **Cuatro corridas A4 (SciBERT-A/B y SPECTER-A/B)** reproducibles y evaluadas sobre el mismo Gold, o bloqueo trazado (issue #103).
- [ ] Contrastes de entrada A/B, base SciBERT/SPECTER y etiquetas Haiku/jurado desambiguados; no presentar variaciones de fuente de etiquetas como A/B.
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
6. Aprobación del diseño factorial y ablación con sección verdadera/ausente/barajada (issue #128).
7. Disponibilidad de SPECTER, arquitectura de clasificación y presupuesto computacional (issue #103); definir responsable de entrenamiento y criterios de aceptación antes de compararlo.

**Regla de publicación:** no declarar números como resultados finales ni marcar el protocolo como aprobado hasta completar todos los P0.
