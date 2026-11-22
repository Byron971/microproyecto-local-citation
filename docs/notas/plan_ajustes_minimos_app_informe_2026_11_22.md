# Plan de ajustes mínimos: aplicación e informe final

Fecha: 22 de noviembre de 2026. Estado: análisis y tareas propuestas; este documento no implica que los cambios estén implementados o desplegados.

## Corrección tras revisión exhaustiva de notebooks

El proyecto sí tiene implementación y predicciones de Qwen 7B y Llama 8B, además de código QLoRA. La segunda familia existe como desarrollo; falta verificar su servicio de inferencia e integrarla en la web. Los clientes de proveedores abiertos y comerciales también existen para evaluación. Ver `revision_modelos_abiertos_2026_11_22.md`. Las menciones posteriores a opciones pendientes se refieren a integración, no a inexistencia de modelos.

## Decisión de alcance

Reutilizar SciBERT y los checkpoints M/S disponibles, sin entrenamiento nuevo. Reutilizar los contratos actuales de análisis por artículo y de análisis manual. Priorizar un recorrido de análisis de cita accesible desde la navegación principal. Conservar la búsqueda de artículos como ayuda para seleccionar la referencia, sin hacerla un requisito para ejecutar el análisis.

La base normativa es `docs/propuesta/0102_propuesta_proyecto_pln.md` (descripción, objetivos, A1–A7 y demostrador), junto con las rúbricas oficiales 06 y 07 en `docs/proyecto_final/`. Las precisiones de `proyecto_de_grado/docs/informe_avance/borrador_ajustes_informe_avance.md` son antecedentes documentados; sus decisiones marcadas pendientes no se consideran aprobaciones.

No es necesario entrenar un buscador global nuevo ni restaurar los cuatro checkpoints A4 para que el demostrador ejecute el flujo M/S. Eso tampoco reemplaza los experimentos comparativos de la propuesta ni permite declarar sus metas cumplidas.

## Flujo mínimo recomendado

1. Entrada principal «Analizar una cita»: contexto académico en inglés y artículo citado.
2. Identificación mediante ID de ACL, selección desde un resultado del catálogo o ejemplo público comprobado. No adivinar automáticamente cuál es la referencia objetivo cuando hay varias.
3. Marcación sencilla de la cita objetivo; convertir internamente la selección en TARGETCIT, sin exigir conocimiento previo de esa sintaxis.
4. Comprobación de disponibilidad de texto completo antes de inferir. Si no existe, mantener la entrada y explicar el límite; ofrecer otro artículo o la entrada manual avanzada. No presentar como análisis completo un resultado sin fragmentos.
5. Un botón de análisis ejecuta recuperación SciBERT y clasificación M/S.
6. Mostrar artículo y fuente, los tres fragmentos ordenados con sección, clase principal por modelo y distribución de las nueve puntuaciones. Explicar desacuerdos y que softmax no mide probabilidad de acierto ni prueba el respaldo de una afirmación.

El Top-3 corresponde a cada artículo analizado. No hace falta ejecutar inferencia de todos los artículos recomendados automáticamente: agrega latencia y consumo sin ser requisito. Permitir analizar cada resultado bajo demanda.

## Endpoints reutilizables

| Contrato actual | Uso previsto | Cambio de API necesario |
|---|---|---|
| `POST /api/analisis-cita-ms/disponibilidad` con `paper_ids` | Comprobar cobertura antes de inferir; máximo 20 IDs por solicitud. | Ninguno. |
| `POST /api/analisis-cita-ms/articulo` con `paper_id`, `contexto` | Camino principal: el servidor obtiene título, abstract y candidatos del corpus preparado. | Ninguno. |
| `POST /api/analisis-cita-ms` con contexto, título, abstract y candidatos | Camino manual avanzado ya existente. Los candidatos deben pertenecer al mismo artículo. | Ninguno para el flujo mínimo. |
| `GET /api/analisis-cita-ms/estado` | Informar disponibilidad del servicio; comprobar después con POST real. | Ninguno. |
| `GET /api/modelos`, `POST /api/recomendar` | Búsqueda auxiliar del catálogo mediante el servicio estándar. | Restaurar su uso en el cliente si fue sustituido por rutas experimentales. |

No se propone un endpoint nuevo. Una lista estática versionada de ejemplos públicos puede bastar para el demostrador; no se debe simular que lista todo el corpus. La cobertura debe provenir del endpoint de disponibilidad, no de un contador fijo. Las rutas locales de búsqueda global experimental no se asumen publicadas.

## Tareas de aplicación y criterios de aceptación

| ID | Prioridad | Cambio concreto | Aceptación | Rúbrica |
|---|---|---|---|---|
| A1 | P0 | Separar la extensión experimental de búsqueda global del arranque y del cliente principal; eliminar la dependencia obligatoria del manifiesto ausente. Preservar el trabajo como experimento aislado. | Servicio M/S inicia sin índice global; build reproducible; catálogo estándar y análisis M/S siguen funcionando. | Funcionamiento 35; parametrización 15. |
| A2 | P1 | Añadir un acceso principal al análisis científico y un formulario simple de ID/contexto, reutilizando `ArticleAnalysis`. Mantener la pantalla JSON como avanzada. | Una cita con artículo conocido puede analizarse sin pasar por el ranking de búsqueda ni pegar JSON. | Usabilidad 35; problema/solución. |
| A3 | P1 | Integrar selección desde el buscador y ejemplos públicos compatibles con el corpus desplegado. | Desde un resultado se conserva contexto e ID; al menos un ejemplo público ejecuta la inferencia completa. | Funcionamiento y demo. |
| A4 | P1 | Resolver estados de disponibilidad, entrada inválida, servicio ocupado, error y cambio de artículo/contexto. | No se mezclan resultados anteriores con entradas nuevas; sin texto se explica la limitación; no se envían solicitudes duplicadas. | Funcionamiento y usabilidad. |
| A5 | P1 | Simplificar resultados con etiquetas legibles y ayuda breve para nueve funciones; conservar Top-3, secciones, fuentes y barras actuales. Mover tokens, perfiles, hashes y ajuste PH a detalle técnico. | Un usuario entiende qué se recuperó y qué clasifica cada modelo sin interpretar códigos internos. | Usabilidad 35. |
| A6 | P1 | Identificar M/S a partir de sus manifiestos y ofrecer «ver M / ver S / comparar» si resulta útil. Ambos se calculan ya en el backend. | La selección se describe como visualización/comparación; no se finge ejecución selectiva ni tres familias de modelos. | Transparencia funcional. |
| A7 | P1 | Validar contratos, casos de UI y recorrido público final; actualizar README y documento de acceso. | Pruebas relevantes pasan, POST público real y recorrido visual completos, versión/release registrados, instrucciones verificables. | README 15; funcionamiento 35; usabilidad 35. |

Componentes reutilizables: `frontend/src/components/ArticleAnalysis.tsx`, `ScientificResults.tsx`, `Results.tsx`; navegación `frontend/src/App.tsx`; cliente `frontend/src/api.ts`; contratos en `src/app/ms_router.py`. Hay que revisar efectos al cambiar de artículo y no solo el caso feliz.

La ampliación del corpus es opcional para el cierre mínimo. Si se publica el corpus local ampliado, validar sus límites y coherencia con el protocolo de entrenamiento antes de cambiarlo. La cobertura actual limitada debe comunicarse incluso si el servicio funciona.

## Lo que este alcance no resuelve

- La propuesta pide encoder ajustado, modelo abierto y modelo comercial seleccionables. M/S no son esas tres familias. Registrar esta diferencia como alcance parcial; no crear botones que llamen al mismo modelo bajo nombres diferentes.
- Si ya existe una API operativa para otra familia, podría integrarse después de verificar modelo, contrato, acceso y costo. No se confirmó esa disponibilidad en esta revisión y no debe convertirse en dependencia del cierre mínimo.
- No se acreditan por una mejora de interfaz las cuotas de datos, la revisión humana del 15 %, el acuerdo interanotador ni un test independiente.
- No puede afirmarse que Top-3 mejora la clasificación solo porque ambos pasos se ejecuten. Hace falta la comparación controlada con/sin fragmentos; reutilizar resultados existentes si tienen un protocolo comparable, o reconocer que esa hipótesis permanece abierta.

## Informe: modificaciones estrictamente necesarias

Trabajar sobre el artículo existente en `docs/proyecto_final/informe final/Articulo cientifico - Grupo 19 - Entrega 2 - REVISION 2.md`. Conservar resultados históricos, fuentes, advertencias y autorías pendientes de validación. No reemplazar cifras A4 por M/S dentro de la misma tabla: son experimentos distintos.

| Parte actual | Ajuste mínimo |
|---|---|
| Cabecera, corte, resumen y palabras clave | Fecha/release solo tras verificar; añadir alcance M/S actual; 200–300 palabras y 3–5 palabras clave. No convertirlo en afirmación de superioridad. |
| Introducción | Un párrafo de alcance: recuperación dentro del citado + clasificación; búsqueda global auxiliar. Explicitar los objetivos que se cumplen parcialmente. |
| §3.4–3.5 Método y despliegue | Añadir una subsección breve M/S con arquitectura e entrada verificadas en manifiestos, selección y limitaciones del Gold, y una figura del flujo real. Sustituir el estado antiguo de AWS por evidencia fechada. |
| §4 Resultados | Añadir tabla separada M/S y tabla Top-3 vigente, con tamaño de muestra, fuente y límites. Agregar medición operativa identificada como solicitud única o benchmark, según corresponda. |
| §5 Discusión | Explicar BM25 superior en la muestra, validación humana incompleta, selección con Gold si se confirma y cobertura limitada. Distinguir ejecución correcta de calidad científica. |
| §6 Conclusiones | Quitar pendientes que ya se resolvieron para M/S, mantener los que siguen vigentes en A4. No proponer reentrenar A4 como requisito del cierre si el alcance final es desplegar M/S. |
| Anexos y materiales | Enlaces de aplicación/API/repositorio y release verificable; desplazar detalle largo de restauración/hashes a anexo externo para respetar 12 páginas. |

No se propone reescribir íntegramente el estado del arte ni el informe de avance para esta intervención mínima. El estado del arte conserva riesgo en sus 10 puntos: mejorar brevemente la síntesis crítica usando las referencias ya verificadas, sin inventar bibliografía. No trasladar todos los detalles de ingeniería al artículo: concentrarlos en README.

Fuentes actuales de resultados: `docs/resultados_ms_pareados_local_20261121.md`, `docs/resultados_top3_recalculados_1005_entrega23.md`, `docs/resultados_reconciliacion_xlsx_20261121.md` y `docs/A7_benchmark_operativo_consolidado_20261120.md`. Antes de trasladarlas, cotejar sus condiciones y procedencia; no etiquetar automáticamente sus conjuntos como Gold certificado. La documentación pública de ejecución del 22 de noviembre está en `artifacts/auditoria_entrega_20261122/`.

## Orden de ejecución y cierre

- [ ] A1: versión científica reproducible sin dependencia de búsqueda experimental.
- [ ] A2–A4: entrada directa, selección de artículo, disponibilidad e inferencia con endpoints existentes.
- [ ] A5–A6: presentación comprensible y comparación honesta de modelos disponibles.
- [ ] A7: comprobaciones locales y públicas de la versión que se entregará.
- [ ] Cambios quirúrgicos del artículo con métricas y metodología cotejadas.
- [ ] Maquetación y verificación de máximo 12 páginas; documento breve de acceso y README alineados.

No se asigna una nota estimada ni se promete cumplimiento total. La estrategia reduce cambios y mejora criterios de alto peso —funcionamiento/usabilidad y metodología/resultados/discusión— sin ocultar las diferencias con la propuesta original.
