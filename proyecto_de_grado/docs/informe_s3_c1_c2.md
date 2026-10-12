# S3 — Comparación exploratoria de clasificación de funciones de cita (C1 frente a C2)

## 1. Objetivo

Examinar, en un lote piloto de 67 contextos de cita del conjunto de entrenamiento, cómo varían las etiquetas automáticas de función de cita cuando el modelo Qwen incorpora fragmentos del artículo citado recuperados por SciBERT Top-3. Este estudio mide comportamiento y concordancia entre configuraciones; **no evalúa exactitud frente a una referencia humana (Gold)**.

## 2. Configuraciones

- **C1:** Qwen (`qwen3:4b-instruct`) con el contexto de cita, el título y el resumen del artículo citado, sin fragmentos Top-3 adicionales. Se conserva la nomenclatura histórica del código, cuyo parámetro es `--evidence none`.
- **C2:** mismo modelo y tarea de etiqueta directa, enriquecidos con los tres fragmentos del artículo citado seleccionados mediante `allenai/scibert_scivocab_uncased` (SciBERT Top-3).
- **Datos:** 67 contextos emparejados por `id`, procedentes del corpus v6 de *train*. Cada registro recibe una etiqueta entre las nueve categorías de la taxonomía del proyecto.
- **Control de identidad:** la auditoría cotejó los identificadores de los 67 registros, la pertenencia al mismo corpus y el estado `ok` de ambas respuestas. La inferencia y los rankings se conservan como artefactos separados.

## 3. Resultados

Se procesaron correctamente **67/67** registros en C1 y **67/67** registros en C2. Hubo **55 coincidencias** de etiqueta (**82,1 %**) y **12 discrepancias** (**17,9 %**).

### 3.1 Distribución de etiquetas

| Función de cita | C1 | C2 |
|---|---:|---:|
| Background | 6 | 5 |
| Gap | 3 | 2 |
| Basis | 54 | 56 |
| Comparison | 0 | 0 |
| Application | 3 | 4 |
| Improvement / Modification | 1 | 0 |
| Evidence | 0 | 0 |
| Identification of the Originator | 0 | 0 |
| Further Reading | 0 | 0 |
| **Total** | **67** | **67** |

La categoría **Basis** concentra **54/67 (80,6 %)** en C1 y **56/67 (83,6 %)** en C2. Por tanto, el predominio de esta categoría precede a la incorporación de los fragmentos SciBERT.

### 3.2 Transiciones observadas

| Transición C1 → C2 | Casos |
|---|---:|
| Background → Basis | 4 |
| Basis → Background | 3 |
| Basis → Application | 2 |
| Gap → Basis | 1 |
| Improvement / Modification → Basis | 1 |
| Application → Basis | 1 |
| **Total** | **12** |

El número neto de predicciones Basis aumenta en dos, pero las transiciones ocurren en ambas direcciones. Por ello, la diferencia de frecuencias no sustituye al análisis pareado.

## 4. Interpretación y límites

La incorporación de evidencia Top-3 está asociada con cambios de etiqueta en 12 de 67 casos. La concordancia observada indica **estabilidad relativa entre configuraciones**, no rendimiento de clasificación. Ni los cambios ni las coincidencias permiten determinar cuál etiqueta es correcta.

La concentración en Basis podría depender de la composición de la muestra, el contenido del prompt, las definiciones de las categorías o el comportamiento del modelo. **No se dispone todavía de evidencia que permita aislar estas causas**. La muestra es pequeña, se limita a *train* y puede incluir contextos relacionados entre sí, por lo que no corresponde extrapolar estos porcentajes a la población de citas académicas.

No se informan exactitud, F1, macro-F1, precisión o recall de las funciones de cita: faltan etiquetas Gold independientes. Tampoco se atribuye una mejora a SciBERT sin evaluación de relevancia de los fragmentos recuperados.

## 5. Auditoría cualitativa trazable

Se exportaron los **12 casos discordantes** a:

`proyecto_de_grado/artifacts/clasificacion_s3/auditoria_transiciones_c1_c2.csv`

El archivo conserva `context_id`, `cited_id`, predicciones C1/C2, contexto de cita y `chunk_id`/texto de los Top-3 de SciBERT. Su finalidad es inspeccionar la evidencia y detectar patrones; **no constituye una campaña de anotación humana ni un conjunto Gold**.

## 6. Reproducibilidad y próximos pasos

- Conservar por separado los archivos de predicciones C1 y C2 y el informe de SciBERT, con huellas de contenido y versiones del modelo/prompt.
- Ejecutar los tests unitarios de S3 y toda la batería de regresión del repositorio antes del commit.
- Realizar una revisión cualitativa puntual de los 12 casos discordantes y registrar observaciones, sin adjudicar automáticamente una etiqueta como verdadera.
- Documentar el predominio de Basis como limitación abierta y diseñar después una evaluación Gold de alcance factible para el tiempo del proyecto.
- No incorporar los artefactos locales al commit salvo que se adopte explícitamente un mecanismo de versionamiento de datos y se verifique que no contienen material restringido.

**Estado:** resultados exploratorios de S3 listos para informe; las pruebas integrales y el Pull Request se verificarán por separado.
