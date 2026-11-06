# Cierre técnico de integración PR #89–#92 — John, issue #111

Fecha de corte: 5 de noviembre de 2026. **Auditoría, no certificación de Gold humano ni benchmark final.** Este documento reemplaza las afirmaciones históricas del issue #111 que decían que esos PR aún estaban abiertos.

## 1. Integraciones confirmadas

| PR | Estado actual | Qué hay disponible en main | Límite que debe reportarse |
|---|---|---|---|
| [#89](https://github.com/Byron971/microproyecto-local-citation/pull/89) | Fusionado | Auditoría de procedencia de jurado y lotes ACL | No asegura que la anotación humana de las hojas privadas haya concluido |
| [#90](https://github.com/Byron971/microproyecto-local-citation/pull/90) | Fusionado | Corte vertical Top-3 **BM25** y rutas de demo | BM25 es baseline, no encoder SciBERT denso ni función de cita integrada |
| [#91](https://github.com/Byron971/microproyecto-local-citation/pull/91) | Fusionado | Jurado de tres modelos de pesos abiertos, muestreo de 1.533 casos test + 20 calibración; archivos de trabajo en Drive | La asignación doble de las hojas no demuestra por sí sola dos juicios humanos concluidos |
| [#92](https://github.com/Byron971/microproyecto-local-citation/pull/92) | Fusionado | Entrenamiento QLoRA, **2.700 preetiquetas automáticas Haiku** y CSV de **2.700 anotaciones** de 2014/2015 | Los dos grupos de 2.700 son distintos; 2014 es validación, 2015 es test candidato; verificar procedencia humana |
| [#142](https://github.com/Byron971/microproyecto-local-citation/pull/142) | Fusionado | Auditoría sin cambios al CSV, clasificaciones, año y 5 exclusiones históricas | Integridad CSV correcta no equivale a Gold certificado |

Las ramas PR #89–#92 **sí están fusionadas**; no volver a abrir una tarea de merge para ellas. Los temas P0 de los issues #95, #98–#100 y #103 siguen siendo científicos, no bloqueos de GitHub merge.

## 2. Reconciliación reproducible de los dos Gold candidatos

Código: `src/evaluation/commercial/gold_manifest_reconcile.py`. Compara los IDs del manifiesto de PR #91 con los IDs de los CSV realmente versionados por PR #92, sin pedir nuevas anotaciones ni modificar las existentes.

| Dato | Cantidad |
|---|---:|
| Test Gold propuesto PR #91 (tandas 519 + 441 + 573) | 1.533 IDs únicos de 2015 |
| Calibración propuesta PR #91 | 20 IDs de 2014 |
| Archivo diligenciado PR #92 | 2.700 IDs: 1.321 (2014), 1.379 (2015) |
| Test PR #91 que también figura en el CSV PR #92 | **832** |
| Test PR #91 sin anotación en el CSV PR #92 | **701** |
| Registros PR #92 de 2015 fuera de la selección Test PR #91 | **547** |
| Coincidencias de calibración PR #91 en anotaciones PR #92 | **13 de 20** |
| Intersección de Test PR #91 con etiquetas Haiku de entrenamiento PR #92 | **0** |
| Intersección de anotaciones PR #92 con Haiku de entrenamiento PR #92 | **0** |
| Excluidos históricos presentes en test PR #91 | **0** |
| Excluidos históricos dentro del CSV PR #92 (2014/2015) | **1 + 4** |
| Candidatos PR #92 de 2015 luego de exclusiones históricas | **1.375** |

**Por tanda del PR #91:** 313 de 519 coincidencias con el CSV PR #92 en la primera, 239 de 441 en la segunda y 280 de 573 en la tercera. Total 832. Esto **mide coincidencia de IDs, no evidencia de doble anotación**.

**Interpretación crítica:** PR #91 y PR #92 representan dos propuestas de selección diferentes. Un caso presente en ambos no debe tratarse automáticamente como anotado por dos personas distintas: el CSV PR #92 no incluye un identificador del revisor. Los 701 ausentes del CSV PR #92 podrían contar con hojas humanas **privadas en Drive**; esta auditoría no las inspeccionó y por eso no se declaran pendientes de reanotación. Los 547 exclusivos de PR #92 tampoco deben sustituir unilateralmente los 701 del PR #91. No mezclar ambos conjuntos para inflar denominadores.

El conjunto histórico de 2.700 **Haiku** se usó para entrenar QLoRA y es diferente por ID de los 2.700 del CSV de anotaciones. Que los IDs sean disjuntos reduce riesgo, pero no certifica ausencia de filtración por texto literal, documento, prompts o selección de modelos: corroborar el manifiesto y splits.

## 3. Evidencia de jurado y balance ya incorporada

`proyecto_de_grado/docs/auditoria_jurado_v3.md` informa 18.000 casos juzgados, 5.227 unanimidad, 9.349 acuerdo 2/3 y 3.424 sin consenso. Después se excluyen 51 consenso ambiguo/no evaluable. Según `proyecto_de_grado/docs/dataset_funciones_v1.md`, **seis clases** no alcanzan el objetivo de 2.000 ejemplos; en particular *Identification of the Originator* (32) y *Further Reading* (153). Estas son cifras documentadas por los artefactos del equipo; **no son nuevas corridas del presente script**.

El PR #134, a cargo de Caicedo, permanece abierto y trata cobertura, viabilidad y respuesta a Haydemar. No generar una segunda curación de datos para John ni cerrar esa actividad sin revisión.

## 4. Cómo reproducir esta auditoría

```bash
uv sync --group dev
uv run python -m src.evaluation.commercial.gold_manifest_reconcile \
  --output-dir artifacts/conciliacion_test_gold
uv run pytest -q tests/test_gold_manifest_reconcile.py
```

El script lee solo archivos versionados en el repo:
- `proyecto_de_grado/anotacion/test_gold_v2/manifiesto_ids.csv` del PR #91;
- `proyecto_de_grado/anotacion/test_gold/TEST_GOLD_2700_ANOTADO.csv` del PR #92;
- `proyecto_de_grado/anotacion/test_gold/TEST_GOLD_2700_MANIFIESTO.csv` del PR #92;
- `notebooks/qlora-training/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv` del PR #92;
- listas de exclusión del proyecto.

Genera `resumen_conciliacion_gold.json` **con totales, solapes y SHA-256 de las cuatro entradas**. No exporta citas, etiquetas individuales, IDs privados ni nombres de anotadores. CI lo incorpora como artefacto para revisión del equipo.

## 5. Decisiones aún necesarias (owners y bloqueo real)

1. **José + Caicedo (#98/#99/#100):** entregar al equipo (en área restringida) las hojas originales de los 1.533, su estado, revisiones efectivamente independientes, acuerdo y adjudicación; cotejar sus IDs contra estos manifiestos. **No pedir reanotar** los 701 por el mero hecho de no aparecer en PR #92.
2. **John (#100/#109/#110):** fijar un único manifiesto **solo test de 2015** con IDs y hashes tras la decisión de equipo; separar validación 2014, abstenciones y 5 exclusiones; exigir Gold firmado antes del benchmark final.
3. **Caicedo (#125 y PR #134):** reconciliar denominador del dataset final/15 % humano con cobertura y balance real; no confundir *18.000 citaciones candidatas* con *dataset final 14.525 etiquetas válidas documentadas*.
4. **Duque (#102/#103):** aislar Gold de entrenamiento y selección de SciBERT/SPECTER; ejecutar matriz A4 (SciBERT-A/B, SPECTER-A/B) cuando los pesos estén verificados.
5. **Gabriel (#108/#114):** reflejar decisiones y amenazas a validez en el artículo final sin anticipar F1 ni métricas humanas no certificadas.

### Puertas de cierre
- **Issue #111 (auditoría de integración):** evidencia de integraciones y discrepancias **documentada y automatizada**; pendiente revisar esta conciliación y aceptar responsable/decisión de manifiesto canónico. No afirmar que Gold se congeló.
- **Issue #100 (Gold final):** sigue abierto hasta prueba documental humana y manifiesto firmado.
- **Issue #110 (benchmark):** permanece provisional hasta Gold adjudicado; no entrenar/tunear contra el test.

Los PR #89–#92 ya están en main. La tarea ahora es **decidir el Gold científico**, no volver a fusionar código ni duplicar anotaciones.
