# S2.3 — Calibración humana ciega y protocolo de evaluación Top-3

**Estado:** implementación inicial para **calibración**, no Test Gold. Complementa S2.2 y no modifica los modelos, la API, el frontend ni las etiquetas de funciones de cita.

## Por qué necesitamos este protocolo

ACL-200 aporta `positive_ids` de **artículos**, no relevancia de **fragmentos**. Que BM25 recupere `p00005-p00005` en primera posición prueba funcionamiento, no que ese párrafo justifique una cita. No existe todavía una referencia humana independiente que permita afirmar Recall@3/MRR@3 de la solución definitiva.

### Etapa A — Calibración sobre dos casos reales de train

Los contextos exportados localmente mediante S2.2 son:

- `D13-1157_P12-1007_0`
- `W13-4005_W08-1111_0`

Se usan **únicamente para validar el procedimiento de anotación y software**, no para comparar modelos como experimento final ni para ampliar el Test Gold. Es posible que personas del equipo ya hayan visto la recuperación BM25 de uno de esos casos; asignar a la calibración, en lo posible, dos evaluadores que no hayan visto los puntajes o ranking.

Desde la raíz del repositorio, una vez actualizado el código de esta rama y presente el artefacto local:

```powershell
python -m proyecto_de_grado.src.evaluation.top3_humano preparar
```

Archivos creados en `proyecto_de_grado/artifacts/top3_s2/anotacion/` (ignorados por Git):

- `anotador_a.csv` — todos los fragmentos, orden aleatorizado con semilla 42
- `anotador_b.csv` — mismos fragmentos, otro orden de filas (semilla 43)
- `adjudicacion_plantilla.csv` — inicialmente vacía; solo es necesario resolver desacuerdos
- `manifiesto.json` — SHA-256 del artefacto de origen, conteos y condiciones

**Ninguna hoja muestra el puesto o puntaje BM25 ni ofrece etiquetas automáticas.** No compartir entre A y B sus respuestas hasta haber congelado ambas hojas. Conservar versiones y responsable de cada una; evitar que alguien compare con la aplicación mientras anota. La opción de inglés del contexto ACL-200 incluye TARGETCIT para distinguir la cita objetivo.

### Juicio humano por fragmento

Los dos anotadores trabajan con la **misma consulta y todos los chunks del artículo citado**. En cada fila completar `relevante_0_1`:

- **1 (relevante)**: el fragmento proporciona evidencia directa, método, resultado, definición o antecedente del **artículo citado** que sustenta específicamente la afirmación o función de `TARGETCIT` en su contexto. Puede haber varios relevantes.
- **0 (no relevante)**: solo comparte vocabulario, se refiere a otro resultado, es demasiado genérico, o no sustenta la afirmación hecha por la cita objetivo.
- **Duda o artículo no interpretable**: dejar en blanco y documentar en `notas` antes de resolver con el equipo. Un blanco **bloquea** el cálculo, nunca se transforma automáticamente en 0.

No confundir `OTHERCIT` con `TARGETCIT`. Si la cita aparece truncada o agrupada y no es posible saber qué parte corresponde a TARGETCIT, registrar la limitación y excluir el caso del ensayo cuantitativo hasta tener una reconstrucción adjudicada. No deducir relevancia de la puntuación BM25 ni del título del artículo por sí solo.

La **unidad de juicio es (context_id, chunk_id)**. Ambos jueces deben evaluar *todos* los chunks de cada documento. Si un artículo tiene 32 chunks, cada anotador realiza 32 juicios. Un pool limitado a los tres recuperados por BM25 **no permite interpretar Recall@3 como exhaustivo**.

### Consenso y adjudicación

Una vez terminadas **por separado** las hojas de A y B, comparar desacuerdos. Los acuerdos se aceptan automáticamente como doble anotación coincidente. Cada desacuerdo se resuelve por revisión explícita (idealmente una tercera persona) y se registra en la fila correspondiente de `adjudicacion_plantilla.csv` escribiendo 0 o 1. Las filas donde hay acuerdo se dejan vacías; si se completan, no deben contradecir el consenso.

**No escribir un resultado automático para rellenar un desacuerdo.** Conservar las hojas firmadas o identificadas por responsable, versión de guía, fecha y las notas cualitativas; el CSV de esta primera versión no sustituye un sistema formal de auditoría de anotadores.

Luego ejecutar:

```powershell
python -m proyecto_de_grado.src.evaluation.top3_humano evaluar
```

El programa **falla sin generar métricas** si falta una anotación, se repite una fila, aparece un ID extraño, hay discrepancias sin adjudicar o se ha modificado el corpus desde que se prepararon las hojas. La evaluación produce `resumen_calibracion.json` con acuerdo observado, κ de Cohen cuando está definido, denominadores, Hit@3, Recall@3 y MRR@3 **solo de calibración**. Un contexto sin ningún fragmento relevante según ambas personas se informa por separado y queda fuera del promedio, no se cuenta como acierto ni cero arbitrario. Los indicadores no se calculan hasta contar con etiquetas humanas reales.

### Métricas y fórmulas

Con `G(q)` como conjunto **exhaustivamente adjudicado** de chunks relevantes de la consulta y `Top3(q)` como ranking de hasta tres chunks del mismo artículo:

- `Hit@3(q) = 1` si `G(q) ∩ Top3(q)` no está vacío; 0 de otro modo.
- `Recall@3(q) = |G(q) ∩ Top3(q)| / |G(q)|`.
- `RR@3(q) = 1 / r` si el primer chunk relevante aparece en posición `r ≤ 3`, o 0 si no aparece.
- `MRR@3` es el promedio de `RR@3` de consultas **elegibles**, con `|G(q)| > 0`.

Siempre publicar `total_casos`, `casos_elegibles`, `casos_sin_relevantes`, `juicios_por_anotador`, `desacuerdos`, acuerdo pre-adjudicación y, si corresponde, κ de Cohen. No extrapolar dos casos a resultados de una población.

## Etapa B — Evaluación científica posterior (aún NO implementada)

Para comparar BM25 con SciBERT se debe construir y congelar un **nuevo corpus de evaluación** con documentos citados válidos, relevancia doble y adjudicada, sin usar IDs de piloto ni Test Gold. Seleccionar muestras de `val` para el desarrollo de modelos y reservar nuevos casos de `test` para la comparación final; definir con el equipo y profesor tamaño objetivo (la política G0 contempla ~100 consultas para Top-3, no 100 casos completados). No reciclar como evaluación ciega los dos casos de `train` ahora expuestos.

Para una comparación justa, evaluar BM25 léxico, BM25 normalizado (stemming/lematización versionados) y SciBERT sobre el **mismo universo de chunks** y particiones, con los mismos IDs, límites y relevancias adjudicadas. Separar consultas excluidas por falta de texto ACL OCL, citas agrupadas irresolubles y casos sin relevante. Reportar cobertura por grupo y posible sesgo de selección.

La validación humana del **15 % del dataset final de funciones de cita** es una obligación distinta de esta anotación de **relevancia de fragmentos**. No sumar los juicios de S2.3 como si fueran funciones de cita validadas.

## Puertas de calidad

1. Script no mezcla `train` con `val`/ `test` ni lee el piloto histórico por defecto.
2. Hojas no contienen resultados o relevancias sugeridas por BM25.
3. Ambas hojas cubren todos los pares de contexto y fragmento, con identificadores reproducibles y SHA-256 del artefacto.
4. Se requiere consenso o adjudicación explícita de diferencias antes de calcular métricas.
5. Las métricas conservan denominador, relevancias múltiples y estados no evaluables.
6. Se ejecutan pruebas unitarias sin acceso a la red, datos DVC ni APIs pagas.
7. Los archivos de anotación y su contenido permanecen **locales** hasta decidir custodia y publicación con los anotadores.

**Pendiente del equipo:** asignar dos revisores humanos distintos para la calibración y un adjudicador. La referencia final de aproximadamente 100 consultas sigue sujeta al protocolo y viabilidad real.
