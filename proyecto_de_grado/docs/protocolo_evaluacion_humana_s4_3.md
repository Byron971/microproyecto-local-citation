# S4.3 — Protocolo de evaluación humana ciega y preparación de muestras

**Proyecto:** Recomendación local de citas y clasificación de funciones de cita.
**Estado:** BORRADOR DE DISEÑO. No hay muestras congeladas, anotaciones humanas ni métricas Gold generadas por este documento.
**Rama prevista:** `feature/s4-auditoria-exploratoria`.
**Dependencias metodológicas:** `proyecto_de_grado/docs/politica_evaluacion_g0.md` (G0.5) y `proyecto_de_grado/docs/protocolo_top3_s2_3.md` (S2.3).

## 1. Propósito y separación de objetivos

Se definen dos tareas diferentes y NO intercambiables:

- **Funciones de cita (clasificación multiclase):** una función principal por contexto `TARGETCIT`, elegida entre las nueve categorías del proyecto, con anotación ciega independiente y posterior adjudicación.
- **Relevancia de recuperación Top-3:** juicio binario de cada `(context_id, chunk_id)` en el artículo citado. Para estimar Recall@3, el conjunto de fragmentos relevantes debe construirse mediante revisión exhaustiva de *todos* los chunks del documento candidato, no solo los Top-3 recuperados.

No contabilizar juicios de relevancia de chunks como ejemplos de función de cita validados.

## 2. Poblaciones y protección del futuro Test Gold

- **Calibración de procedimientos:** casos de `train` ya conocidos o de `val`; nunca presentarlos como una evaluación final independiente.
- **Piloto prospectivo de clasificación (propuesta de factibilidad):** comenzar con hasta **12 contextos nuevos de `val`** que superen las comprobaciones, elegidos sin consultar predicciones C1/C2 y sin seleccionar por etiquetas predichas. La cifra 12 es una propuesta operativa reducida para medir viabilidad, NO una muestra Gold final ni una garantía de representación de nueve clases. Registrar todos los rechazos y el marco de muestreo.
- **Piloto prospectivo de recuperación (propuesta):** hasta **2 consultas nuevas de `val`** para las que el artículo citado sea íntegramente legible y sus chunks estén validados. Solicitar a cada anotador revisar TODOS los chunks por consulta. Si falta texto o hay dudas de alineación, registrar exclusión sin fabricar juicios.
- **Test Gold definitivo:** solamente casos nuevos de `test`, excluyendo cualquier contexto previamente expuesto a selección de prompts/modelos o revisión de desarrollo. **No seleccionar, revelar ni etiquetar ahora** el Test Gold definitivo.

La política G0.5 exige aplicar la **unión** de las listas `proyecto_de_grado/anotacion/ids_excluir_test_gold.txt` y `proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt`, más los identificadores que se expongan posteriormente en entrenamiento, pilotos o calibración. Conservar las listas existentes intactas y generar un manifiesto complementario de exposiciones nuevas. Verificar separación de `citing_id`, pares `(citing_id, cited_id)`, duplicados exactos y posibles casi duplicados entre splits según G0.5. Los citados pueden repetirse entre particiones; registrarlo, no declararlo automáticamente fuga.

**No crear supuestas muestras `val` a partir de los 67 casos actuales: todos son `train`.** La selección efectiva requiere examinar los registros ACL-200 originales, procedencia y elegibilidad; este entregable solo define el protocolo.

## 3. Precondiciones antes de entregar fichas a anotadores

1. Comprobar `split` desde ACL-200 original y conservar `context_id`, `citing_id`, `cited_id`, título, resumen, contexto original y fuente/huella SHA-256.
2. Conservar exactamente un `TARGETCIT`; no suprimir `OTHERCIT`. Marcar como no evaluable un contexto truncado o de cita agrupada que no permita atribución segura; no reconstruir por suposición.
3. Verificar que el artículo citado pertenece al contexto y que hay texto usable cuando se requiera; una correspondencia ACL OCL tentativa NO es una cita reconstruida y validada.
4. Ejecutar controles de duplicados y exclusiones. Registrar cada exclusión con un motivo; no eliminar ejemplos silenciosamente.
5. Congelar previamente listado de IDs, orden de extracción/semilla, SHA-256 de entrada, versión de guía y fechas. Anotar responsable del congelamiento.
6. Elaborar fichas de anotación sin predicciones de Qwen, etiquetas sugeridas, scores, rankings BM25/SciBERT ni fragmentos Top-3 destacados. Los anotadores de relevancia sí ven TODOS los chunks en orden aleatorizado por anotador.
7. La participación de al menos **dos anotadores distintos**, independientes y ciegos, y la capacidad de resolver desacuerdos debe confirmarse antes de iniciar la campaña. La aprobación del tamaño final de Test Gold corresponde al equipo/docente.

## 4. Clasificación: ficha, criterio y proceso

**Unidad:** una cita objetivo `TARGETCIT` por `context_id`.

**Etiquetas oficiales (una función principal):**
1. Background
2. Gap
3. Basis
4. Comparison
5. Application
6. Improvement / Modification
7. Evidence
8. Identification of the Originator
9. Further Reading

**Campos mínimos del juicio:** `context_id`, `primary_label`, `secondary_label` opcional, `annotation_status`, `ambiguity_notes`, `annotation_guide_version`, `annotator_id`, `annotation_date_utc`. La ficha textual asociada debe conservar el contexto original y su procedencia. **No** poner por defecto Background, Basis ni otra etiqueta si la entrada es incierta.

**Proceso recomendado:**

1. Definir/cerrar con el equipo una guía de decisión por categoría y ejemplos de práctica (no del futuro Test Gold).
2. Generar dos copias independientes A y B de los mismos IDs; ocultar las respuestas mutuas y de los sistemas.
3. Cada anotador asigna una función principal o declara un estado `dudoso`/`no_evaluable` con justificación. Las etiquetas secundarias solo documentan ambigüedad.
4. Congelar A y B con fecha y huellas de archivos antes de comparar.
5. Reportar tasa de acuerdo y Cohen kappa (o Krippendorff alfa si se justifica); las etiquetas ambiguas/no evaluables requieren tratamiento explícito en el denominador, no se imputan.
6. Resolver desacuerdos con adjudicación humana rastreable (idealmente tercera persona), manteniendo ambas opiniones originales.
7. No calcular F1 Macro como resultado científico del sistema hasta tener un conjunto de referencia humano apropiado e independiente, predicciones sobre los MISMOS IDs y cobertura clara. Reportar nueve clases, soportes, F1 por clase, matriz de confusión, abstenciones y fallos sin esconder categorías sin soporte.

## 5. Recuperación: juicio de relevancia de fragmentos

- **Unidad:** `(context_id, chunk_id)`; todos los fragmentos del documento citado, no solo los tres devueltos.
- **Relevante = 1:** evidencia directa, método, resultado, antecedente o definición del artículo citado que respalde específicamente la afirmación en torno a `TARGETCIT`.
- **No relevante = 0:** coincidencia de tema o vocabulario sin respaldo concreto.
- **Incierto/no interpretable:** juicio vacío y nota; detener métricas de esa consulta hasta resolver, como establece S2.3.
- Dos evaluadores independientes, mismos pares con órdenes aleatorios diferentes y adjudicación documentada.
- Calcular Hit@3, Recall@3 y MRR@3 **solo** para consultas exhaustivamente adjudicadas con al menos un relevante, y reportar por separado consultas sin relevantes o no evaluables; comparar BM25 y SciBERT en los mismos IDs y universo de chunks.

El sistema de calibración existente `proyecto_de_grado/src/evaluation/top3_humano.py` cubre **dos casos `train` de S2.2** y no debe reutilizarse sin adaptación/validación para nuevas consultas `val` o Test Gold.

## 6. Auditoría y manejo de archivos

Los archivos de esta entrega son **plantillas de columnas sin filas y sin etiquetas**. No han seleccionado ejemplos ni producido juicios.

- `manifiesto_muestra_plantilla.csv`: control de selección, identidad y elegibilidad; rellenar solo cuando se implemente la extracción validada desde ACL-200.
- `anotador_a_plantilla.csv` y `anotador_b_plantilla.csv`: columnas de clasificación humana independientes.
- `adjudicacion_plantilla.csv`: decisiones finales, solo después de congelar A y B.
- `relevancia_chunks_plantilla.csv`: juicio de cada fragmento; separar por anotador y consulta antes de anotar.

Los CSV de trabajo se conservan en `proyecto_de_grado/artifacts/evaluacion_s4/plantillas_s4_3/` (local e ignorado por Git). La identidad o datos privados de anotadores no deben publicarse sin autorización. Solo la **guía metodológica** va a revisión por PR; no subir fichas con respuestas ni texto completo sujeto a restricciones.

## 7. Puertas de aceptación S4.3

- [x] Distinguidas las dos tareas y sus métricas.
- [x] Aclarado el papel de `train`/`val`/`test` y la contaminación histórica.
- [x] Especificada selección piloto orientativa sin etiquetar el nuevo Test Gold.
- [x] Definidos ceguera, doble anotación, adjudicación, incertidumbre y trazabilidad.
- [x] Definida la necesidad de anotación exhaustiva de chunks para Recall@3.
- [ ] Equipo confirma dos anotadores y adjudicador, disponibilidad y calendario.
- [ ] Equipo/docente revisan y aprueban tamaño final Test Gold y meta de validación del 15 %.
- [ ] Se implementa selección reproducible con controles de exclusión y se congela un manifiesto real de `val`.
- [ ] Se efectúa piloto con juicios humanos (no incluido en esta entrega).

## 8. No confundir con requisitos finales

La política G0.5 exige **15 % de validación humana de las funciones sobre el dataset final**, `ceil(0.15*N)`. Por ejemplo, para N=18.000 serían 2.700 revisiones. La presente calibración pequeña **no elimina ni satisface** ese requisito. La cuota de 2.000 ejemplos por clase sigue siendo una meta no demostrada. Cualquier cambio de alcance, tamaño o criterio requiere justificación y acuerdo académico explícito.

**Conclusión provisional:** S4.3 deja un protocolo y formatos reproducibles, pero no constituye una evaluación Gold ni una validación humana ya realizada.
