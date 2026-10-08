# G0.5 — Política de evaluación, anotación humana y separación de datos

**Proyecto:** Recomendación local de citas y clasificación de su función.
**Fecha:** 2026-10-08.
**Versión:** 0.1, borrador operativo del equipo.
**Estado:** Pendiente de revisión del equipo y de ratificaciones académicas especificadas abajo. No autoriza inferencias masivas ni evaluación final.

## 1. Fuentes y alcance

Esta política desarrolla las observaciones R4, R5 y R6 documentadas en `proyecto_de_grado/docs/matriz_correcciones_haydemar.md`. Aplica al clasificador de nueve funciones y a la evaluación complementaria de recuperación Top-3 de **fragmentos**. No confundir estas métricas con la recomendación de **artículos** del MVP.

ACL-200 es la fuente de identidad de contextos, pares, `TARGETCIT` y splits originales. ACL OCL es una fuente complementaria de texto completo, párrafos, secciones y bibliografía; disponibilidad del JSON no equivale a reconstrucción validada de la cita.

## 2. Decisiones adoptadas operativamente

### D1. Validación humana mínima: 15 % del dataset final

- Para `N` ejemplos distintos admitidos en el dataset final, deben existir al menos `ceil(0.15*N)` ejemplos con función **examinada y confirmada o corregida por humanos**. Si N=18.000, corresponden 2.700 ejemplos.
- Una etiqueta automática sin revisión humana no cuenta. Los casos de práctica/calibración descartados del corpus final tampoco se cuentan.
- Registrar ID, split, clase, fecha, anotador, versión de guía, origen de la propuesta, resultado de revisión y adjudicación, si aplica; reportar cobertura por clase y partición.
- **El 15 % validado no implica que el Test Gold tenga 2.700 ejemplos**, ni que todos los ejemplos validados deban tener doble anotación. El tamaño y el diseño del Test Gold se definirán aparte.
- Mantener la meta original de 2.000 ejemplos por clase como **objetivo aún no demostrado**. No afirmar cuotas logradas sin datos verificados. Si cambia el tamaño final, recalcular el 15 %.

### D2. Clasificación multiclase, etiqueta principal única

Categorías oficiales en el orden usado por el código:
1. Background
2. Gap
3. Basis
4. Comparison
5. Application
6. Improvement / Modification
7. Evidence
8. Identification of the Originator
9. Further Reading

Para cada contexto hay una sola `primary_label` confirmada como objetivo principal. Se puede registrar `secondary_label` opcional y `ambiguity_notes` para análisis humano, pero la función secundaria no interviene como etiqueta adicional en el F1 multiclase. Una salida inválida, un empate o un desacuerdo no adjudicado **no** se convierte automáticamente en Background ni en otra clase.

Ambas decisiones son acuerdos operativos actuales; consignar cualquier ratificación exigida por el profesor.

## 3. Contrato mínimo de los registros

Conservar `context_id`, `citing_id`, `cited_id`, `split` comprobado en los archivos originales, `citation_context_original` con **exactamente un TARGETCIT**, `cited_title` y `cited_abstract` si existe. No eliminar TARGETCIT/OTHERCIT de los datos usados para clasificar o anotar.

Para etiquetas: `primary_label` y `secondary_label` opcional, `label_source` (automática/humana independiente/humana adjudicada), `annotation_status`, guía/versiones, anotador o modelo, fecha y evidencia. Las predicciones automáticas no sobrescriben etiquetas humanas; sus puntajes **no son probabilidades calibradas**. Versionar fuente y transformación. Una coincidencia tentativa de la cita en ACL OCL se marca como candidata, nunca validada automáticamente.

## 4. Particiones, exclusiones y prevención de fugas

Conservar inicialmente los splits temporales originales de ACL-200 por año del **citante**: train 2009–2013 (30.390); val 2014 (9.381); test 2015 (9.585).

Controles obligatorios antes de generar un nuevo Test Gold y antes de entrenar:
- Contexto en un solo split, `citing_id` ausente en otros splits de la comparación principal y pares `(citing_id, cited_id)` sin duplicación entre splits.
- Detectar duplicados exactos y candidatos a casi duplicados textuales (registrar investigación, no borrar en silencio).
- Los artículos **citados** pueden repetirse entre splits: se observaron 1.338 entre train/test. Esto **no constituye automáticamente fuga**; reportar y analizar rendimiento sobre citados vistos/no vistos.
- Aplicar la unión trazable de exclusiones de práctica/calibración con las de pilotos utilizados en ajuste de modelos o prompts.
- No mezclar ejemplos adicionales extraídos de ACL OCL sin asignación explícita de partición, deduplicación y documentación de procedencia.
- Congelar manifiesto e identificadores de train, val y Test Gold antes de ajuste final. Las etiquetas Gold finales no se usarán para elegir modelos, prompts, parámetros ni umbrales.

### Hallazgo de contaminación del piloto histórico

`annotations/citation_function/test_gold.jsonl` tiene **20 ejemplos** cuyos `input` no conserva TARGETCIT; comparten IDs con `provisional_test_gold.jsonl` y ya fueron usados para elegir/comparar prompts y modelos. **El nombre del archivo no lo convierte en Test Gold independiente**.

Se verificó que solo 8 de los 20 están en la lista previa `proyecto_de_grado/anotacion/ids_excluir_test_gold.txt` (77 IDs). Los otros 12 deben excluirse del **nuevo test final**. Mantener la lista original sin sobrescribirla y añadir el manifiesto separado `proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt` con los 20. Las pruebas de G0.6 utilizarán **la unión**. Corregir el texto de un caso antiguo no borra su uso previo en selección.

Los 20 casos siguen disponibles como ejemplos **históricos/de desarrollo**, no como muestra final independiente.

## 5. Anotación humana y Test Gold nuevo

- Congelar la guía, calibrar anotadores con ejemplos **fuera** del nuevo Test Gold y registrar una función principal por TARGETCIT.
- El Test Gold final debe construirse con **nuevos contextos elegibles del split test**, seleccionados antes de mirar sus etiquetas definitivas y excluyendo los casos ya usados en desarrollo.
- Doble anotación **ciega e independiente** de todos los casos nuevos del Test Gold y adjudicación trazable de desacuerdos. Para los demás ejemplos validados por humanos, definir y reportar qué proporción tendrá anotación doble.
- Calcular acuerdo previo a adjudicación (tasa de acuerdo, Cohen κ y/o α de Krippendorff) y errores por categoría. El objetivo α ≥ 0,70 que figura en un borrador es una **meta preliminar**, no un resultado demostrado.
- Los no adjudicados quedan registrados como ambiguos y no se usan como verdad del test final.
- **Tamaño del Test Gold por determinar y ratificar**. El antiguo borrador sugirió 450; la adopción del 15 % no aprueba esa cifra ni obliga a asignar los 2.700 al test.
- Documentar muestreo, distribución por clase, estrategias de enriquecimiento para clases raras y sesgo respecto a frecuencias naturales. Una prueba balanceada no representa necesariamente la población original.
- Una vez sellado el conjunto humano, custodiar las etiquetas de manera controlada y no consultarlas para ajustar el sistema.

## 6. Evaluación multiclase

**Métrica principal:** F1 Macro sobre las nueve clases, junto con precisión, recall y F1 por clase, soportes, exactitud y matriz de confusión. Indicar qué clases están ausentes: un piloto con cinco clases no valida calidad sobre nueve.

Reportar **cobertura**, errores de proveedor/formato, abstenciones y casos ambiguos por separado. No retirar respuestas fallidas del denominador sin informar. Para ablaciones, utilizar los **mismos contextos**; si faltan chunks o documentos, informar cobertura y métricas en la intersección comparable.

## 7. Evaluación de recuperación Top-3

ACL-200 da `positive_ids` a nivel de **artículos**, no relevancia de **fragmentos**. Para Recall@3 y MRR@3 se requiere referencia humana de `chunk_id` relevantes para cada contexto. El plan actual contempla un conjunto curado de aproximadamente 100 consultas, con anotación independiente y adjudicación; no confundir un pool incompleto de candidatos con verdad exhaustiva.

Para consultas con al menos un fragmento relevante conocido, definir:
- `Hit@3(q)`: 1 si aparece algún relevante entre los tres primeros; 0 en otro caso.
- `Recall@3(q) = |Top3(q) ∩ G(q)| / |G(q)|`.
- `RR@3(q) = 1/r` si el primer fragmento relevante está en la posición `r∈{1,2,3}`, 0 si ninguno aparece.

Promediar por consulta elegible; informar consultas sin relevancia conocida/juicios incompletos, denominador y límites de interpretación. Evaluar adicionalmente el efecto del Top-3 sobre el F1 de clasificación mediante configuraciones: C0 contexto; C1 contexto+título/resumen; C2 Top-3; C3 C2+sección **del citado**; C3-control con secciones permutadas. No confundir sección del citado y sección del citante.

## 8. Puertas de aceptación y tareas siguientes

**Para aceptar G0.5:** decisiones D1/D2 reflejadas en documento y guía, piloto histórico aislado, política de nuevo gold y doble anotación definida, tamaño de test y aprobaciones pendientes explícitos, métricas/denominadores documentados.

**G0.6 debe implementar pruebas automáticas:** conservación TARGETCIT, etiquetas válidas, unión de ambas listas de exclusión, pertenencia a splits verificable desde ACL-200, cruces de citantes/pares, duplicados, rechazo de Gold usado en desarrollo, empates/abstenciones, huellas de ejecución y workflow CI que vigile `proyecto_de_grado/`.

No iniciar todavía entrenamiento definitivo, pre-etiquetado masivo, nuevos experimentos sobre el test histórico ni fusión con `main`.

## 9. Decisiones abiertas

- D3: número y reparto de anotadores, calendario y protocolo de revisión humana fuera del Gold.
- D4: tamaño/composición final del nuevo Test Gold y ratificación académica.
- D5: método validado de alineación citante-ACL OCL y cobertura real del corpus.
- D6: criterio de análisis adicionales para `cited_id` vistos/no vistos y ejemplos externos.

**Referencias en el repositorio:** `proyecto_de_grado/docs/matriz_correcciones_haydemar.md`, `proyecto_de_grado/src/data/preparar_preetiquetado.py`, `src/evaluation/commercial/orchestrate.py`, `annotations/citation_function/test_gold.jsonl`, `proyecto_de_grado/anotacion/ids_excluir_test_gold.txt`.
