# Matriz de cierre para entrega del 23 de noviembre de 2026

**Corte:** 21-nov-2026. **Propósito:** distinguir evidencias listas, verificaciones técnicas y entregables dependientes del equipo de datos. El documento NO reemplaza acuerdos con el docente ni asigna responsables de manera unilateral.

**Semáforo:** LISTO = evidencia reproducida y auditada en el alcance indicado; POR VALIDAR = hay artefactos pero falta comprobar requisitos; PENDIENTE EQUIPO = entrega/certificación no acreditada; EXCLUSIÓN = no se afirma como completado para esta entrega.

| ID | Producto para entrega | Estado | Responsable funcional (no asignación nominal) | Evidencia disponible / falta | Criterio mínimo de cierre al 23 |
| --- | --- | --- | --- | --- | --- |
| T1 | Recomendación Top-3 BM25/SciBERT | **LISTO con límites** | Integración/evaluación | `docs/resultados_top3_recalculados_1005_entrega23.md`, scripts y hashes | 30 consultas, 1005 pares, 25 elegibles; evaluación reconstruible desde originales privados; anotar sesgos |
| T2 | Clasificación de 9 funciones M/S | **LISTO provisional** | Integración/evaluación | `docs/resultados_ms_pareados_local_20261121.md`, predicciones originales locales | 1530 casos pareados, matrices y métricas reproducidas; Gold **no certificado** |
| T3 | Consistencia del corpus Top-3 y rankings | **LISTO dentro del corpus** | Integración/evaluación | Auditor `scripts/auditar_cobertura_top3_1005.py`, ejecución local: 1005/1005; BM25 y SciBERT 90/90 | Mantener JSON y hashes privados, no confundir con artículo OCL íntegro |
| T4 | API, interfaz y software ejecutable | **POR VALIDAR cierre de entrega** | Integración/software | CI del commit `39bae905` 9/9 workflows con éxito; demo real M/S ya verificada en clon limpio en un caso | Smoke local de endpoints, dependencias, evidencia de ejecución, manual actualizado |
| T5 | Dataset final de 9 clases, N y distribución | **PENDIENTE EQUIPO** | Liderazgo de datos / responsable del dataset, por confirmar | `proyecto_de_grado/docs/cierre_integrado_2026_11.md` registra 18k de jurado y déficit de varias clases respecto a objetivo 2k/clase; no constituye dataset final certificado | Entregar CSV/JSON definitivo, fuentes, N, frecuencias, versionado, hashes, reglas de filtrado |
| T6 | Test Gold de funciones con revisión humana | **PENDIENTE EQUIPO** | Coordinación de anotadores/adjudicadores, por confirmar | `docs/resultados_auditoria_gold_20261120.md`: 1533, 1531 evaluables, auditoría estructural correcta, `certificacion_humana=no_demostrada` | Hojas originales firmadas o fechadas, doble juicio cuando exigido, discordancias y acta de adjudicación; acuerdo **pre**-consenso y denominadores |
| T7 | Cuota de validación humana del 15% del corpus de funciones | **PENDIENTE EQUIPO / decisión docente** | Dirección académica y coordinación de datos | Propuesta histórica contemplaba 15%; no sustituir con los 1005 juicios Top-3 ni etiquetas automáticas | Acta que fije N final y número mínimo, evidencia de juicios humanos realizados o desviación/limitación ratificada |
| T8 | Split y ausencia de leakage para dataset definitivo | **PENDIENTE EQUIPO** | Responsable de particiones y auditor técnico | Protocolo `docs/protocolo_certificacion_test_gold.md`; verificaciones parciales estructurales | Manifiesto train/val/test + controles de IDs, citante y citado/documentos según protocolo, exclusiones |
| T9 | Evidencias QLoRA / jurado open-weight / experimento A4/104 si se declaran contribuciones | **POR VALIDAR con equipo** | Responsables de experimentación, por confirmar | Existen notebooks, resúmenes y manifiestos en Git; artefactos privados completos no verificados aquí | Versiones de entrada, checkpoint/adapter si permitido, manifiestos, scripts, métricas, hashes. **No afirmar como entregado hasta verificarse** |
| T10 | Documento final de grado en formato exigido | **EN PREPARACIÓN** | Integración de informe + revisión de todo el equipo | `docs/borrador_resultados_discusion_conclusiones_entrega23.md` | Texto completo, objetivos, metodología, resultados actuales 96/909, discusión, referencias, limitaciones y contribución individual |
| T11 | Empaquetado de entrega y evidencia de equipo | **EN PREPARACIÓN** | Coordinación del equipo | PR #201 abierta, fusionable, en borrador; guías existentes | Link a código y rama, evidencia de CI, instrucciones, lista de artefactos privados, decisiones de custodia, aportes de cada integrante |
| T12 | Formalización de alcance y fechas | **PENDIENTE CONFIRMAR** | Coordinación/docente | En `proyecto_de_grado/docs/cierre_integrado_2026_11.md` se mencionan otras fechas antiguas como tentativas. Usuario confirma **23-nov-2026** como fecha de entrega | Contrastar rúbrica y aula; no suponer que la defensa o entregas subsecuentes tienen la misma fecha |

## Distinción crítica entre dos conjuntos humanos

**Top-3:** 1005 juicios binarios de relevancia sobre fragmentos de 30 consultas, A/B consolidados; toda la cobertura *interna del corpus* verificada. No acreditan por sí solos primera anotación ciega independiente y **no cuentan** para la cuota del 15% de **función de cita**.

**Función de cita:** 1533 contextos Gold consolidados, con 1531 evaluables y certificación humana aún no demostrada. Las métricas M/S sobre 1530 casos son **provisionales**. El origen `concordancia` y las etiquetas generadas por Opus no certifican dos anotaciones humanas. La cola de 1484 tareas registrada en auditoría es una instantánea de tareas, no prueba de 1484 errores ni evidencia de que no haya progresos posteriores fuera de Git.

## Entrega mínima robusta si el equipo NO completa validación humana total

1. Entregar software, procedimientos de ejecución, pruebas/CI y evidencia de smoke.
2. Presentar clasificación como **evaluación provisional sobre Gold consolidado no certificado**; nunca renombrarlo Gold final humano.
3. Presentar la evaluación Top-3 como **muestra exploratoria** de 30 consultas (25 elegibles), con exhaustividad respecto del corpus fragmentado y cautela sobre independencia inicial y representatividad.
4. Adjuntar la matriz de pendientes con responsables y desviaciones, sin inventar cumplimiento del tamaño por clase ni del 15%.
5. Solicitar aceptación formal de los límites/alcance al equipo/docente si afectan los criterios de calificación.

## Orden de cierre realista

**21 nov:** publicar esta matriz, confirmar responsables y solicitar materiales de T5–T9; consolidar texto académico de T10.
**22 nov:** recibir/verificar hashes y manifiestos; ejecutar smoke final del clon limpio; revisión cruzada de documento; decidir de forma explícita qué evidencia faltante se reportará como limitación.
**23 nov:** congelar versión y anexos, verificar enlaces/permisos, registrar commit de entrega, presentar según rúbrica.

## Formato para que cada responsable entregue evidencias

Por entregable, comunicar: `responsable`, `archivo(s) y ruta(s)`, `versión/fecha`, `N / casos / clases`, `hash SHA-256`, `split`, `guía o método`, `qué se validó`, `qué sigue pendiente`, `permisos de uso`. Los archivos con datos humanos, textos completos, credenciales o pesos privados no se suben al PR público sin autorización.

## Revisión de CI

En el commit `39bae905bbcc586df0a36a3fe4728a5f5fe340be` se consultaron 9 workflows, todos **completed/success**:
- Corte vertical Top3 de fragmentos
- Benchmark operacional A7 sin Gold
- Smoke fullstack real (sin mocks)
- Desplegar API en AWS
- Smoke de aceptación de tesis (baseline sin Gold)
- Validar aplicación React
- Auditoría trazabilidad Test Gold (sin adjudicar)
- Configuración segura del backend
- Ciencia A-B y Docker CPU (sin Gold ni pesos)

El comando local `python -m pytest` falló inicialmente porque el entorno Windows `.venv-ms` no tenía `pytest` instalado; **no es fallo de tests**. No debe marcarse la ejecución local de la nueva suite como exitosa hasta instalar `pytest` y correrla. Las validaciones CI pueden no incluir los tests Top-3 añadidos recientemente; para certificar esos tests específicos correrlos localmente o agregarlos a workflow.

**No fusionar la PR #201 ni marcarla ready sin revisar el contenido/autorizar la integración.**
