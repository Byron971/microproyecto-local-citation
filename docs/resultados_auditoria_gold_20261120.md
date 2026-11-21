# Corte de trazabilidad de Test Gold — ejecución en GitHub Actions

**Evidencia:** [Auditoria trazabilidad Test Gold (sin adjudicar), ejecución 44865105469](https://github.com/Byron971/microproyecto-local-citation/actions/runs/44865105469), sobre commit `57b3af0e0a401aaf04e54c55f6a89871b46c7802`.

El auditor `scripts/auditar_certificacion_gold.py` terminó con
`integridad_consolidacion: true`, `errores: []` y
`certificacion_humana: no_demostrada`.

| Medida | Valor |
| --- | ---: |
| Contextos consolidados | 1533 |
| Evaluables | 1531 |
| No evaluables | 2 |
| Concordancia | 186 |
| Anotación única | 820 |
| Discrepancia resuelta con Opus | 57 |
| Solo Opus | 470 |
| Anotación única con al menos un estado PENDIENTE | 818 |
| Discrepancias donde Opus no coincide con ningún humano | 11 |

**Precaución:** 186 concordancias indican coincidencia de etiqueta
en la consolidación, no necesariamente dos formularios completamente
diligenciados. El auditor encontró, dentro de esa procedencia:
`Estado_A=COMPLETO` en 150, `INCOMPLETO` en 36;
`Estado_B=COMPLETO` en 82, `INCOMPLETO` en 104.
Estos son conteos por columna, no la intersección de parejas completas.

## Distribución nominal del archivo consolidado

| Etiqueta | Cantidad |
| --- | ---: |
| Background | 430 |
| Application | 333 |
| Comparison | 282 |
| Evidence | 228 |
| Gap | 102 |
| Improvement / Modification | 67 |
| Basis | 47 |
| Further Reading | 27 |
| Identification of the Originator | 15 |
| No evaluable | 2 |

La distribución **no** se debe utilizar todavía para afirmar
representatividad o ausencia de sesgos de anotación.

## Integridad de los cinco CSV cotejados

| Archivo | SHA-256 |
| --- | --- |
| `test_gold_final.csv` | `80e4d9a6a72bd36913548bef897ad8212178797e181bb7893f7be2aad66b83c7` |
| `concordancias.csv` | `f628fc32a474ba3eb53042dd6b50a03a6ef28f0e17f4b2fcd1e2dae38035bb82` |
| `una_anotacion.csv` | `e9f9410b3ba58bfbaa40d8fc8022ab47997e7c21b99b1077857f1235514fab17` |
| `discrepancia_opus.csv` | `eb00262e1d749da7382415bfdd705375d21c741d3792a9c8c9f6f5c6552ba596` |
| `anotado_opus.csv` | `78bccf9855adc71bbfc9c8871d4f1ddbd17d415689130d23ae888c0c027a6988` |

**Estado de certificación:** bloqueado por revisión humana pendiente.
`scripts/generar_cola_certificacion_gold.py` permite producir una
cola de tareas *local y privada* sin textos, sin etiquetas adjudicadas y
sin modificar la fuente. La ruta propuesta `artifacts/cola_gold_privada.csv`
está ignorada por Git. Las hojas locales de anotadores pueden contener
avances más recientes que este corte versionado: deben auditarse de
forma separada antes de dar cualquier pendiente por definitivo.

**Alcance:** verificación de unicidad de identificadores, procedencia,
etiqueta/evaluabilidad y hashes; no implica evaluación de validez
semántica, acuerdo interanotador, fragmentos relevantes, partición
sin leakage o F1 definitivo.
