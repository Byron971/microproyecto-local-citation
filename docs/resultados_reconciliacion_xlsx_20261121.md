# Reconciliación de cinco XLSX de anotación humana — 21 de noviembre de 2026

**Estado:** salida agregada de `scripts/reconciliar_gold_xlsx.py` ejecutado localmente en `ms-clon-limpio` sobre los cinco Excel de `microproyecto-local-citation-actualizado`, suministrada por el ejecutor. **No** se han publicado las anotaciones, textos, justificaciones ni la cola privada. El programa analiza celdas con `openpyxl(data_only=True)` y determina completitud por contenido, no por la columna calculada `Estado`.

## Resultados globales

- Universo cruzado: **1533** `context_id` del Gold; sin IDs extra en ninguno de los cinco libros.
- Dos anotaciones completas y concordantes con la etiqueta consolidada: **48** (3.13% del universo).
- Dos anotaciones completas en desacuerdo: **33** (2.15%).
- Al menos una anotación incompleta: **1452** (94.72%).
- Pares completos observables: **81**; acuerdo bruto 48/81 = **59.26%**. No es κ, α ni una validación de calidad semántica.
- El reporte no encontró ninguna categoría `doble_acuerdo_difiere_gold` ni `asignacion_incompleta_o_duplicada`.

| Anotador | Asignados | Completos según campos | Estado Excel COMPLETO |
| --- | ---: | ---: | ---: |
| Arias | 616 | 615 | 616 |
| Caicedo | 614 | 47 | 48 |
| Duque | 613 | 19 | 19 |
| Pinzon | 612 | 0 | 0 |
| Zambrana | 611 | 202 | 201 |

**Desglose por procedencia actual del Gold:**

| Fuente | Dos completas y concuerdan Gold | Dos completas en desacuerdo | Incompletas |
| --- | ---: | ---: | ---: |
| concordancia | 48 | 0 | 138 |
| discrepancia_opus | 0 | 33 | 24 |
| una_anotacion | 0 | 0 | 820 |
| solo_opus | 0 | 0 | 470 |
| **Total** | **48** | **33** | **1452** |

Los 48 acuerdos son **candidatos** a revisión de certificación; requieren comprobación de independencia y criterio de anotación. Los 33 desacuerdos requieren adjudicación humana. Los 470 casos `solo_opus` carecen de dos anotaciones humanas completas y no se deben presentar como Gold certificado.

## Huellas de los cinco XLSX inspeccionados

| Anotador | SHA-256 |
| --- | --- |
| Arias | `3fcc7e69ff32aaea464991390d598ab822711e70467c90ffc68ac4a6ca690b31` |
| Caicedo | `dbae3c3288928b7347993e89f3a01806426ad74a7bf764610a5d4275e7e216` |
| Duque | `6976f8b34d13a034aa0e0e491dd757ab054109bf6b5775b35d745395d43d5c04` |
| Pinzon | `1eb34a5f39782d6e8c9dc345770521dba18d1daf5fbdf093809066af8550104f` |
| Zambrana | `3c7c4e6b52e78f01b994acc7e5d1a89b86f83b614f705e0fd4d63d9327aec6ce` |

## Limitaciones y próximo control

1. `COMPLETO` en Excel no es garantía: Arias y Caicedo reportan una unidad más que los campos satisfacen; Zambrana una menos. Revisar los casos concretos de discrepancia sin publicar datos privados.
2. El reporte solo certifica campos diligenciados, no independencia, anotación ciega o validez semántica.
3. La cola local de 1484 casos (generada a partir de fuentes consolidadas) y la reconciliación por celdas no son la misma medida: la conciliación encuentra 1452 sin dos respuestas completas, **33** con discrepancia y **48** con acuerdo. No se deben restar 1452 de 1484 como si fueran nuevos progresos realizados.
4. Conservar la cola privada `artifacts/reconciliacion_gold_v3_PRIVADA.csv` en el equipo; no subirla a Git.
5. Solicitar segunda revisión independiente y adjudicar discrepancias, luego calcular acuerdo κ/α sobre parejas elegibles y congelar nueva versión Gold con split sin leakage.
6. El F1 final de nueve funciones permanece **no calculable de forma defendible** sobre el consolidado actual. El Gold de funciones no basta para medir Recall@3 sin etiquetas de relevancia de fragmentos.

**Comprobación de código:** el workflow `Auditoria trazabilidad Test Gold (sin adjudicar)` del commit `a843ddb86` terminó con `success` en GitHub Actions. Esto valida el código y los casos sintéticos, pero no ejecutó los cinco Excel del computador del investigador.
