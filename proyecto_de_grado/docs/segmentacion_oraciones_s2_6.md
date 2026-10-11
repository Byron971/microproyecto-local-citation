# S2.6 — Segmentación conservadora por oraciones para fragmentos ACL OCL

**Proyecto:** Recomendación local de citas y clasificación de su función en artículos académicos
**Rama de desarrollo:** `feature/s2-6-segmentacion-oraciones`
**Base de código auditada:** `a19e3f8d79aa1431b5b7c25af5e3311903c4bc25`
**Fecha del corte:** 2026-10-11
**Estado:** implementación y pruebas locales aprobadas; pendiente revisión por PR, ratificación del equipo y evaluación humana de calidad de las fronteras.

## 1. Motivación

Durante la auditoría S2.5.d de ACL OCL, el artículo `P03-1054` presentó fragmentos de párrafos largos que cumplían los límites de longitud y preservaban el texto, pero cortaban oraciones en lugares inadecuados. Ejemplos de la versión histórica v4:

- `p00016-s000` terminaba en «Splitting», separándolo del inicio del siguiente fragmento («DT tags...»).
- `p00017-s000` terminaba en «and brought the».
- `p00019-s000` terminaba en «and».

Estos cortes podían reducir la coherencia de la evidencia textual recuperada por BM25 o por modelos semánticos. La integridad de caracteres no demuestra calidad lingüística.

## 2. Alcance del cambio

Se añadió un modo experimental y **optativo** de segmentación por oraciones, sin cambiar el modo histórico por defecto de S2.4 y S2.2.

Archivos implicados:

- `proyecto_de_grado/src/data/segmentacion_oraciones_s2_6.py`: identificación heurística conservadora de fronteras y agrupación de oraciones completas.
- `proyecto_de_grado/src/data/exportar_corpus_top3.py`: parámetro `segmentacion_oraciones` en `fragmentar`; los IDs, las secciones y los offsets mantienen trazabilidad.
- `proyecto_de_grado/src/data/preparar_enriquecimiento_s2_4.py`: propagación de la opción y bandera CLI `--segmentacion-oraciones`.
- `proyecto_de_grado/tests/test_segmentacion_oraciones_s2_6.py`: siete pruebas de regresión y seguridad.

Se preservan las restricciones de hasta **300 palabras** y **5.000 caracteres** por chunk. Para párrafos segmentados, los offsets `[start, end)` permiten reconstruir el texto original. Una oración individual que exceda estos límites, o sin frontera fiable, se rechaza con error en el modo nuevo en vez de cortarse arbitrariamente. El algoritmo es heurístico y está diseñado principalmente para prosa científica en inglés.

El modo nuevo solo se activa cuando se solicita `--segmentacion-oraciones`; los experimentos v4 siguen siendo reproducibles con el modo anterior.

## 3. Evidencia de verificación local

Las siguientes cifras proceden de la terminal del equipo durante la ejecución local del 11 de octubre de 2026; no son métricas de relevancia Top-3 ni resultados Gold.

| Verificación | Resultado |
| --- | ---: |
| Pruebas dirigidas S2.6 + regresiones S2.2/S2.4 | 30 aprobadas |
| Batería integral `tests` y `proyecto_de_grado/tests` | **320 aprobadas** |
| Advertencias de dependencias de la batería integral | 160 (avisos de deprecación, sin fallos) |
| Artículos del lote v5 auditados frente a caché original | **11** |
| Chunks auditados | **440** |
| Segmentos con offsets auditados | **28** |
| Pérdidas o duplicaciones detectadas en las comprobaciones programáticas | **0** |

En el piloto específico:

| Artículo | Estado S2.6 | Chunks | Segmentos por oraciones |
| --- | --- | ---: | ---: |
| `P03-1054` | utilizable | 31 | 10 |
| `P98-1013` | utilizable | 22 | 0 |

La comparación de finales de chunks de v4 y v5 muestra cortes más naturales en `p00016-s000`, `p00017-s000` y `p00019-s000` de `P03-1054`. En `P98-1013`, 22 chunks conservaron sus textos sin cambios.

La auditoría programática de v5 comprobó: identidad del artículo, unicidad de `chunk_id` por artículo, textos no vacíos, límites de longitud, equivalencia exacta entre texto original y offsets, y cobertura sin huecos o solapamientos para los párrafos segmentados. Se observaron cero pérdidas o duplicaciones **en el lote examinado**.

## 4. Reproducción

Desde la raíz del repositorio, con las dependencias del proyecto instaladas:

```powershell
uv run --group research --group dev pytest -q proyecto_de_grado/tests/test_segmentacion_oraciones_s2_6.py proyecto_de_grado/tests/test_exportar_corpus_top3.py proyecto_de_grado/tests/test_preparar_enriquecimiento_s2_4.py
uv run --group research --group dev pytest -q tests proyecto_de_grado/tests
```

Para regenerar los candidatos de desarrollo en una carpeta **nueva**, manteniendo intacta v4:

```powershell
uv run --group research --group dev python -m proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 --limit 40 --seed 42 --max-per-cited 4 --segmentacion-oraciones --out proyecto_de_grado/artifacts/enriquecimiento_s2_4/v5_oraciones_20261011
```

El resultado depende de la caché ACL OCL y los datos ACL-200 locales; el directorio `artifacts/` está excluido del repositorio. Los contextos exportados son solamente de **desarrollo/train**, no un Test Gold.

## 5. Límites y riesgos pendientes

1. La detección de oraciones usa heurísticas de puntuación/abreviaturas; las fronteras lingüísticas no han sido adjudicadas exhaustivamente por humanos. Los ejemplos verificados no prueban precisión universal.
2. La validación de offsets y conservación de texto no demuestra relevancia del chunk para la cita objetivo ni garantiza mejoras de Hit@3, Recall@3 o MRR@3.
3. El rechazo de oraciones demasiado largas puede dejar algunos artículos fuera del corpus bajo el modo S2.6; deben contarse y documentarse cuando se amplíe la caché.
4. No se deben fusionar ni reinterpretar las etiquetas externas de MultiCite como parte de esta actividad.
5. Los cambios de fronteras de chunks pueden afectar `chunk_id`, comparabilidad de rankings y juicios humanos. Congelar el segmentador antes de generar cualquier conjunto de evaluación adjudicado.
6. La selección del lote de 40 contextos es de desarrollo y no representativa del corpus completo; las pruebas cuantitativas de modelos quedan pendientes.

## 6. Criterio de cierre y continuación

**Validación de ingeniería completada** en la rama local: pruebas dirigidas e integrales aprobadas; comprobación en artículos reales; diferencias v4/v5 observadas; auditoría de offsets sin errores dentro del lote.

**Pendiente de cierre de repositorio:** revisar cambios, documentar, ejecutar `git diff --cached --check`, crear commit, abrir PR y obtener revisión. No modificar `main` directamente ni versionar documentos ACL OCL completos o archivos generados en `artifacts/`.

**Siguiente etapa científica:** calibración humana ciega de relevancia Top-3 (S2.3), por dos anotadores independientes, usando un corpus congelado y juicios sobre todos los chunks de cada contexto. Mantener separados los experimentos exploratorios train y el futuro conjunto Gold.
