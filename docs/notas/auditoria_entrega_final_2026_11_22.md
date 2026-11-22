# Auditoría de entrega final — 22 de noviembre de 2026

## Dictamen

Cumplimiento parcial. Hay una API científica operativa y evidencia experimental útil, pero los informes entregables no reflejan el estado actual. No es defendible afirmar que todo está listo para máxima calificación. Esta auditoría no asigna una nota: identifica evidencia, carencias y acciones frente a las rúbricas oficiales.

Se revisaron los ocho documentos de instrucciones en `docs/proyecto_final/`, los dos informes en `docs/proyecto_final/informe final/`, la propuesta `docs/propuesta/0102_propuesta_proyecto_pln.md`, resultados posteriores y evidencia de la API pública. Los ocho archivos de instrucciones ya contienen texto; queda resuelta la limitación inicial de archivos vacíos.

## Qué se exige y qué significa para el flujo

La propuesta define dos tareas: recuperar fragmentos dentro del artículo citado y clasificar la función retórica de la cita. SciBERT Top-3 y los modelos M/S responden a esas tareas. No se encontró una obligación de sustituir la búsqueda global de artículos por SciBERT base. Una búsqueda global nueva tampoco queda validada por tener funcionando `/api/analisis-cita-ms`.

Flujo coherente: introducir contexto de cita, identificar el artículo citado, comprobar disponibilidad de su texto, recuperar Top-3 con sus secciones y mostrar las predicciones M/S con sus nueve probabilidades. Si no hay texto preparado, la interfaz debe explicarlo. El buscador de catálogo puede ayudar a identificar el artículo, pero su calidad se evalúa separadamente.

La propuesta también compromete datos balanceados de al menos 2.000 ejemplos por clase, revisión humana del 15 %, comparación con un modelo comercial y variantes experimentales. Su cumplimiento no queda demostrado por desplegar M/S. Hay que justificar y declarar los cambios de alcance, incluido arXiv → ACL y las variantes que finalmente se entregan.

## Evidencia y límites

- Prueba pública con solicitud sintética: inferencia correcta, tres fragmentos y nueve probabilidades por cada modelo, 8,869 s en esa solicitud. No representa una distribución de latencia ni una evaluación de calidad científica.
- Estado público: modelos cargados, release `ms-scibert-b8ee47317c29afbc`.
- Consulta de disponibilidad: 22 de 38 identificadores tienen texto preparado; 16 no. El corpus local ampliado no debe describirse como ya desplegado.
- El catálogo público conserva `tfidf_reranker_v1` como recomendador predeterminado. Esto no invalida por sí mismo la tarea científica de analizar una cita dentro de un artículo.
- Evidencia directa guardada en `artifacts/auditoria_entrega_20261122/`: `estado_publico.json`, `inferencia_publica.json`, `cobertura_publica.json`.
- Las cifras experimentales siguientes provienen de informes locales existentes; no se recalcularon desde todos los datos originales durante esta auditoría. La experiencia visual completa no se volvió a ejecutar en esta pasada.

## Artículo: rúbrica independiente de 100 puntos

| Criterio oficial | Peso | Situación y acción |
|---|---:|---|
| Problema | 10 | Existe; precisar usuario, entrada, salida y alcance final de las dos tareas. |
| Estado del arte | 10 | Hay referencias, pero falta comparación crítica y actualización bibliográfica justificada. |
| Metodología | 30 | Buena trazabilidad histórica; falta explicar el pipeline M/S actual, selección, datos, arquitectura y despliegue. |
| Resultados | 15 | Los informes finales mantienen resultados históricos; incorporar M/S y Top-3 actuales, métricas por clase y figuras. |
| Discusión y contribuciones | 15 | Hay limitaciones honestas; actualizar con BM25 superior en la muestra Top-3 y las restricciones del Gold. |
| Conclusiones y futuro | 10 | Separar logros actuales, pendientes reales y afirmaciones que la evaluación no permite. |
| Estructura y redacción | 10 | Artículo aún marcado Entrega 2; preparar versión final, verificar formato y máximo 12 páginas. |

Los informes revisados tienen corte del 16 de noviembre. El artículo presenta A4 (SciBERT/SPECTER, entradas A/B) y Jurado; esos experimentos no equivalen a los modelos M/S con entrada AB del notebook 10. Deben describirse como experimentos distintos, con sus respectivas particiones y fuentes de etiquetas.

El resumen cuenta aproximadamente 191 palabras frente a las 200–300 requeridas y hay seis palabras clave frente a las 3–5 solicitadas. No hay imágenes incorporadas en esos Markdown: conviene añadir arquitectura, resultados por clase y una figura del flujo. El número de páginas solo se puede verificar al maquetar el documento final. La plantilla IEEE es opcional. El informe de avance tiene su propia rúbrica y límite de ocho páginas; no sustituye el artículo final.

## Integridad de la evaluación

1. **Selección con el test:** el notebook `notebooks/10_modelos_finales_M_S.ipynb` declara seleccionar las mejores corridas según F1-macro del Gold y volver a evaluarlas sobre ese Gold. Revisar el procedimiento real. Si fue así, ese conjunto no es una prueba independiente: declararlo como evaluación exploratoria o usar un conjunto realmente no utilizado para selección. No extender automáticamente este hallazgo a todos los experimentos A4/Jurado.
2. **Gold provisional:** la reconciliación reporta 48 acuerdos, 33 desacuerdos y 1.452 casos incompletos entre 1.533 contextos. No se puede presentar todo el conjunto como validado por humanos ni convertir acuerdo bruto en kappa. No queda acreditada la revisión humana del 15 %.
3. **M/S:** el informe pareado usa 1.530 ejemplos: M macro-F1 0,551217; S 0,604604. Son resultados útiles, con las limitaciones anteriores. No prueban superioridad estadísticamente significativa ni independencia del test.
4. **Top-3:** usar la versión recalculada de 1.005 pares, 96 positivos y 909 negativos: 30 consultas, 25 evaluables y cinco sin positivos excluidas. BM25 Hit@3 0,84 / Recall@3 0,515051 / MRR@3 0,666667; SciBERT 0,52 / 0,211414 / 0,433333. No mezclar con la versión anterior de 99 positivos. La exhaustividad se refiere al corpus de chunks exportado, no necesariamente a todo el artículo original. Declarar el límite de muestreo y anotación.
5. **Conclusión defendible:** SciBERT no supera a BM25 en esta muestra Top-3. Presentar ese resultado con claridad mejora la validez del trabajo; cambiar silenciosamente la narrativa para sostener una superioridad inexistente la debilita.

Fuentes: `docs/resultados_ms_pareados_local_20261121.md`, `docs/resultados_reconciliacion_xlsx_20261121.md`, `docs/resultados_top3_recalculados_1005_entrega23.md`. Hay texto de apoyo en `docs/borrador_resultados_discusion_conclusiones_entrega23.md`.

## Despliegue: otra rúbrica independiente de 100 puntos

| Criterio oficial | Peso | Situación y acción |
|---|---:|---|
| Funcionamiento | 35 | API pública funcional con prueba sintética; fijar release, probar el recorrido completo y documentar cobertura y casos sin texto. |
| README | 15 | Alinear instrucciones con la versión entregada y verificar reproducción desde un entorno limpio. |
| Parametrización | 15 | Consolidar variables, configuración, carga de modelos, permisos y requisitos; comprobar que no dependa de archivos locales omitidos. |
| Usabilidad | 35 | Dar acceso claro al análisis científico sin exigir JSON, con ejemplo, identificación del artículo, disponibilidad y resultados comprensibles. Falta repetir la validación visual completa. |

La rúbrica pide además un documento breve Word/PDF con nombre del proyecto, integrantes, enlace al repositorio, enlace a la aplicación y credenciales si hacen falta. Mantener acceso al momento de evaluación. Los pesos grandes pueden alojarse externamente, pero se necesitan instrucciones claras de acceso y carga. S3 privado no obliga a publicar pesos ni secretos.

Documentar tamaño de los modelos, hardware, tiempo de inferencia y reproducción/despliegue. El benchmark local de `docs/A7_benchmark_operativo_consolidado_20261120.md` y la latencia pública medida tienen condiciones distintas; no deben fusionarse ni presentarse como mediciones de costo AWS.

### Riesgo del código local frente a producción

Durante el trabajo anterior introduje una extensión experimental de búsqueda global SciBERT que aún no se ha publicado. Actualmente `Dockerfile.ms` exige `config/search_release.json`, que no está presente, y `science_main.py` carga ese índice al iniciar. También hay cambios locales del frontend hacia rutas nuevas. Por tanto, el árbol local no es todavía una reproducción fiel del servicio público y requiere aislar esa extensión o completar su configuración antes de congelar la entrega. La búsqueda experimental tuvo resultados poco pertinentes y no tiene justificación para reemplazar el flujo científico requerido. No se modificó ni desplegó esa extensión como parte de esta auditoría.

## Sustentación

La instrucción oficial asigna 15 minutos de exposición y cinco de preguntas. Rúbrica: claridad problema/solución 30 %, resultados y demo 25 %, diseño/coherencia 20 %, comunicación 15 %, tiempo 10 %. Todos los integrantes deben participar; acordar roles y ensayar al menos dos veces. Preparar un ejemplo público con texto disponible, un caso sin cobertura y respuestas sobre Gold, selección de modelos y por qué BM25 supera SciBERT en la muestra. No se auditó aquí una presentación terminada ni el desempeño oral.

## Lista de seguimiento por prioridad

- [ ] **P0 — Congelar una versión reproducible:** separar la búsqueda global experimental, resolver dependencias ausentes, validar instalación/build, registrar commit y release realmente desplegados. Conservar los cambios ajenos a esta tarea.
- [ ] **P0 — Acordar afirmaciones científicas:** resolver/documentar selección con Gold, estado de validación humana y desviaciones de la propuesta. No llamar certificado o independiente a lo que no lo es.
- [ ] **P1 — Actualizar el artículo:** método M/S, evaluación Top-3 vigente, arquitectura, resultados por clase, discusión crítica y conclusiones actuales. Mantener A4/Jurado como antecedentes separados.
- [ ] **P1 — Preparar entrega formal:** resumen y palabras clave conformes, referencias críticas, PDF de máximo 12 páginas, documento breve de acceso y enlaces verificados.
- [ ] **P1 — Verificar el recorrido de usuario:** contexto → artículo citado → Top-3/sección → M/S; mensajes sin cobertura y ejemplo listo. Registrar demo y prueba pública de la versión final.
- [ ] **P1 — Completar README y configuración:** instalación desde cero, acceso a pesos, recursos, ejemplos, variables y despliegue sin secretos.
- [ ] **P2 — Preparar defensa:** diapositivas, reparto de participación y dos ensayos de 15 minutos más preguntas.

Los pesos de las tres rúbricas no se suman entre sí. El siguiente paso con mayor valor es cerrar la metodología y la versión entregable antes de reescribir conclusiones o publicar cambios adicionales.
