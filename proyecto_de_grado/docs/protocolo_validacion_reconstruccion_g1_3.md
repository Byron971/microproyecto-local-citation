# G1.3 — Protocolo de validación humana de reconstrucciones de cita

**Estado:** protocolo operativo inicial, pendiente de revisión humana sobre casos reales.  
**Fuentes:** `data/raw/contexts.json`, `data/raw/papers.json`, ACL OCL local (`cache_ocl`), `proyecto_de_grado/src/data/reconstruir_oraciones.py`.  
**Alcance:** verificación de oración, fuente y posición de `TARGETCIT`. **No** asigna la función retórica de las nueve clases.

## Objetivo

Comprobar que una oración reconstruida corresponde a la cita objetivo específica del contexto ACL-200. Se mantienen por separado:
1. El contexto original enmascarado de ACL-200, inmutable.
2. La oración original extraída de ACL OCL, con texto y posición de `cite_span`.
3. La oración candidata derivada de ACL OCL, con exactamente un `TARGETCIT`.
4. La decisión humana, motivo, identidad del revisor y fecha.

Una coincidencia alta en texto o un título similar en bibliografía **no** demuestra por sí sola identidad de la cita.

## Evidencias mínimas a mostrar al revisor

- `context_id`, split comprobado, `citing_id`, `cited_id`; identidad de artículos ACL OCL.
- `masked_text` inmutable y el párrafo del citante con sección e índice.
- `BIBREF` candidata, título bibliográfico y `cite_span` exacto (`ref_id`, `start`, `end`).
- Oración OCL antes de enmascarar; oración propuesta con `TARGETCIT`.
- Referencias cercanas para descartar atribución de `OTHERCIT` a `TARGETCIT`.

## Criterios de aceptación por humanos

**Aprobar** solo cuando el revisor compruebe todo lo siguiente:

- La cita es a **ese** artículo `cited_id`, no solo un título parecido.
- La posición de `TARGETCIT` coincide con el `cite_span` relevante y con la cita original, no con otra referencia de la misma oración.
- La oración incluye la unidad sintáctica correcta de la cita, conserva el texto sustantivo del citante y tiene puntuación coherente.
- En los paréntesis se sustituye **solo la cita objetivo**; otras citas se conservan o, cuando no se pueden localizar inequívocamente, se rechaza la propuesta automática.
- El texto reconstruido mantiene `TARGETCIT` exactamente una vez y registra la procedencia y decisión.

**Rechazar** cuando la bibliografía no corresponde al citado o el contexto esté localizado en un párrafo erróneo. **Corregir** solo si la identidad está confirmada y la diferencia es solucionable sin adivinar; registrar versión anterior y nueva. **Pendiente** cuando el material no permite adjudicar el vínculo.

Para grupos como `(OTHERCIT; TARGETCIT; OTHERCIT)` no se permite convertir todo el grupo en `(TARGETCIT)`. Requieren inspeccionar referencias y posiciones de manera individual; pueden permanecer pendientes.

## Primera tanda G1.2: cinco casos usados para desarrollo

| ID | Split | Estado automático | Próxima revisión |
| --- | --- | --- | --- |
| `P14-1048_P12-1007_0` | val | reconstruccion_candidata_revision_humana | Comprobar cita Feng & Hirst 2012, oración y paréntesis |
| `W09-0704_E89-1009_0` | train | reconstruccion_candidata_revision_humana | Comprobar cita Evans & Gazdar 1989, oración y paréntesis |
| `P14-1048_P12-1007_2` | val | revision_manual | Desambiguar grupo de citas en Experiments |
| `D15-1288_P09-2086_0` | test | revision_manual | Desambiguar grupo que incluye Watanabe et al. 2009 |
| `W15-2710_P11-1082_0` | test | revision_manual | Desambiguar grupo que incluye Rahman & Ng 2011 |

Estas **dos propuestas y tres abstenciones** son resultados de desarrollo; ninguna propuesta está validada por humanos. Los cinco IDs ya fueron registrados en `proyecto_de_grado/anotacion/ids_excluir_test_gold.txt`, de modo que no podrán formar parte del nuevo Test Gold independiente. La unión actual con el piloto histórico contiene **94 IDs**. No se debe reportar "40 % de cobertura" como resultado poblacional: los casos fueron elegidos por su estado previo de alineación.

## Registro y proceso

La plantilla `proyecto_de_grado/anotacion/plantilla_revision_reconstruccion_g1_3.csv` deja decisiones intencionalmente vacías; **no se deben rellenar automáticamente**.

Por caso, anotar `decision` (aprobar/rechazar/corregir/pendiente), `revisor`, `fecha_utc`, `identidad_citada_confirmada`, `span_target_confirmado`, `oracion_corregida` y `justificacion`. Registrar cambios sobre una copia de trabajo, sin alterar ACL-200 ni la caché.

Las decisiones finales requieren al menos una revisión humana documentada. Para casos con incertidumbre o desacuerdo, pedir segunda revisión y adjudicación; conservar ambas versiones. Las revisiones humanas de reconstrucción **no se cuentan automáticamente** dentro del 15 % de validación humana de funciones de cita: son tareas diferentes.

## Puerta de salida G1.3

- Las dos reconstrucciones candidatas revisadas por una persona, con aceptación o rechazo y justificación.
- Los tres casos ambiguos triados como pendiente, corregido o rechazado con evidencia; nunca adjudicados en automático.
- Registro verificable y reproducible, enlazado a `context_id`, `BIBREF` y offsets.
- Solo después diseñar G1.4: manejo seguro de grupos de citas y evaluación en muestra independiente (sin contaminar Test Gold).
