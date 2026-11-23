# PRD — Integración del flujo científico de citas

**Fecha:** 22 de noviembre de 2026  
**Estado:** enfoque y secuencia de trabajo acordados; especificación para implementación. Las tareas pendientes no se consideran implementadas ni desplegadas.  
**Alcance:** aplicación web, API, modelos existentes y operación del despliegue.  
**Restricción:** no entrenar modelos nuevos. Reutilizar componentes y contratos existentes siempre que sea compatible.
**Decisión de producto:** mostrar únicamente el demostrador solicitado. Retirar de la interfaz pública el buscador global y las pantallas heredadas ajenas al flujo científico.

**Actualización solicitada por el usuario, 22/11/2026:** el paso «Artículo» incorpora sugerencias relacionadas con el contexto, limitadas al corpus preparado y con selección explícita. Esta decisión sustituye la restricción anterior de filtro exclusivamente literal; no habilita otra página de búsqueda global. Véase [decisión y comprobaciones](../notas/selector_articulos_relacionados.md).

**Ampliación posterior solicitada por el usuario:** la búsqueda del paso 2 abarca los 19.776 artículos del índice existente. La selección sigue siendo manual; el análisis Top-3 requiere texto preparado (19.243 artículos preparados; despliegue y recorridos de muestra verificados públicamente). Esta decisión sustituye la restricción de búsqueda limitada al corpus preparado. Estado y evidencia: [ampliación del catálogo](../notas/busqueda_catalogo_completo_paso2.md).

**Cobertura y simplificación posteriores:** se recortan documentos al límite existente (100 fragmentos y 56.000 caracteres de artículo/metadatos), indicando el alcance retenido. Sin artículo por defecto; sugerencias automáticas al entrar al paso 2 y confirmación manual. Implementación, preparación y aceptación: [ampliación de cobertura](../notas/ampliacion_cobertura_corpus.md).

## Plan de ejecución acordado

1. **Rediseñar la página principal** con un único recorrido: contexto de cita → artículo citado → clasificador → Top-3 y función predicha. El mockup ASCII de §13 define la organización.
2. **Retirar las funcionalidades ajenas al alcance**, incluidos buscador global, paneles heredados y páginas experimentales separadas; conservar evidencias y componentes reutilizables.
3. **Mantener temporalmente M/S en el despliegue actual de AWS**, estabilizando la versión local y preservando una reversión funcional.
4. **Probar SciBERT y M/S en SageMaker Serverless Inference**, verificando memoria, compatibilidad, latencia en frío/caliente y costo por uso.
5. **Recuperar Qwen 7B y su adaptador QLoRA**, y probarlos en SageMaker Asynchronous Inference con GPU y escalado a cero; comprobar cuotas y activación desde cero.
6. **Adaptar API y frontend para las tres familias**, reutilizando contratos compatibles e incorporando trabajos/estado cuando la ejecución sea asíncrona. Preparar el contrato comercial en esta etapa.
7. **Conectar el proveedor comercial** reutilizando los clientes existentes y validar sus respuestas reales.
8. **Verificar el flujo completo desde la web pública**, incluidos errores, falta de cobertura, tiempos de espera y mediciones por familia.
9. **Migrar los modelos y retirar recursos anteriores solo tras validar funcionamiento y costos**, con versión identificada, reversión y documentación actualizada.

Esta es la secuencia principal del PRD. Las tablas de tareas la detallan, sin constituir planes alternativos. Probar SageMaker no implica aprobar todavía una migración; no se garantiza ahorro. Recuperar artefactos y consultar cuotas puede adelantarse mientras se trabaja en la interfaz. La estabilización técnica se realiza antes de publicar cambios de UI.

## 1. Problema y resultado esperado

Un investigador necesita comprender qué fragmentos de un artículo citado se relacionan con su contexto de cita y qué función retórica cumple la referencia. Buscar un artículo relacionado por título/resumen no resuelve por sí solo esta necesidad.

La aplicación debe permitir ingresar un contexto académico en inglés, identificar el artículo citado, recuperar sus tres fragmentos más relacionados con SciBERT y clasificar la cita con una de las tres familias previstas: encoder ajustado, modelo abierto de 1–8B o modelo comercial. Los resultados deben ser legibles, trazables y accesibles desde la web pública.

**Resultado de producto:** un tercero puede completar ese recorrido sin preparar JSON, conocer rutas internas ni ejecutar notebooks.

## 2. Fuentes y relación con la evaluación

- [Definición del problema y solución](../propuesta/0102_propuesta_proyecto_pln.md): descripción, objetivos, A1–A7 y sección 5 del demostrador.
- [Rúbrica de despliegue](../proyecto_final/07%20Entregable%20y%20criterios%20de%20evaluación.md): funcionamiento 35 %, README 15 %, parametrización 15 %, usabilidad 35 %.
- [Revisión de modelos existentes](../notas/revision_modelos_abiertos_2026_11_22.md).
- Evidencia del equipo en `tmp/texto_whatsapp.txt`: 3-nov selección QLoRA/Qwen/Llama; 17-nov publicación y ejecución local del adaptador; 21-nov anuncio de resultados comerciales. Son declaraciones y referencias históricas, no comprobación actual del servicio remoto.

Este PRD mejora el cumplimiento funcional del demostrador. No certifica metas de datos, revisión humana, independencia del test o comparaciones científicas. La implementación no debe presentarse como resolución de esas limitaciones.

## 3. Situación actual y evidencia

| Componente | Confirmado | Pendiente |
|---|---|---|
| Recuperación SciBERT y clasificadores M/S | API científica y prueba pública de inferencia; componentes React de resultados. | Flujo principal directo, revisión visual final y versión reproducible. |
| Modelos M/S | Dos encoders SciBERT ajustados, aproximadamente 110 millones de parámetros cada uno. | Explicar identidad/entrada, sin confundirlos con LLM de 7–8B. |
| Qwen 2.5 7B y Llama 3.1 8B | Notebooks, metadatos y 18.000 predicciones únicas de cada juez v3. | Servicio para nuevas entradas e integración web. |
| Qwen 7B ajustado con QLoRA | Código de entrenamiento/inferencia; WhatsApp registra publicación y ejecución del adaptador. | Recuperar adaptador y verificar carga, integridad y configuración. |
| Proveedores comerciales y abiertos | Clientes reutilizables en `src/evaluation/commercial/`. | Configuración operativa, adaptador de producto y verificación real. |
| Artículos citados | Consulta de disponibilidad y análisis por ID; existe un buscador global heredado. | Retirar el buscador global del producto y seleccionar explícitamente el artículo citado. |
| Código local de búsqueda global SciBERT | Experimento existente, no necesario para el flujo requerido. | Aislarlo: actualmente introduce una dependencia de arranque/manifiesto ausente. |

El 22-nov se verificaron 22 artículos con texto disponible entre 38 IDs consultados. No utilizar esta muestra como tamaño universal del catálogo. La disponibilidad debe consultarse al servicio.

## 4. Alcance y prioridades

### Entrega A: recorrido científico estable con M/S

Corregir dependencias locales, hacer accesible el análisis por artículo, mejorar presentación y estados, validar el despliegue y documentar uso. Es una entrega incremental útil, pero no cubre por sí sola las tres familias.

### Entrega B: selección de tres familias

Conectar un modelo abierto existente y un proveedor comercial existente. Mostrar M y S como variantes del encoder. Solo declarar el demostrador completo respecto a selección de familias cuando las tres puedan ejecutar inferencia real desde la web pública.

No forma parte del producto público: búsqueda global de artículos, rankings TF-IDF, paneles heredados de datos/desempeño/negativos ni páginas separadas de experimentos A/B o carga manual de candidatos/JSON. Se conservan código, notebooks y evidencia que ayuden a reproducir los experimentos; no se exponen como funcionalidades del demostrador. Tampoco se incluyen entrenamientos nuevos, rediseño visual integral, corrección retrospectiva de etiquetas, cierre del Gold o reescritura completa del artículo. La recuperación de cualquier PDF/URL no está especificada como requisito y no se incorpora en este cierre.

### Pantallas que se conservan o retiran

| Elemento actual | Decisión | Motivo |
|---|---|---|
| `/` — Recomendar / Encuentra referencias | Sustituir por el análisis científico. | El objetivo es recuperar fragmentos del citado, no recomendar artículos del catálogo. |
| `/datos`, `/modelo`, `/negativos` | Retirar navegación y rutas públicas de esas vistas. | Paneles del microproyecto, ajenos al demostrador solicitado. |
| `/fragmentos`, `/funcion`, `/funcion-b` | Retirar como páginas independientes; reutilizar componentes útiles dentro del flujo único. | Las tareas requeridas se presentan integradas y con los modelos finales. |
| `/analisis-ms` — formulario manual/JSON | Sustituir por el flujo normal o redirigir al inicio científico. | No exigir al usuario construir candidatos ni conocer el formato interno. |
| Ayuda de funciones, fuentes, estado y errores | Conservar dentro del flujo. | Necesarios para usar e interpretar la solución. |
| Selector de artículo citado | Conservar como entrada: filtro por título/ID y sugerencias opcionales del catálogo completo, con cobertura comprobada al seleccionar. | El Top-3 debe recuperarse dentro de un documento identificado. |

Quitar significa eliminar del recorrido y de las rutas de producto; no basta con ocultar enlaces y dejar accesibles páginas viejas. Usar redirecciones pertinentes o una página de ruta inexistente. No borrar automáticamente APIs o artefactos usados por evaluación/notebooks: su retiro se decide por dependencias, sin convertirlos en parte de la interfaz.

## 5. Recorrido de usuario

1. Abrir la aplicación; la página principal es «Analizar una cita».
2. Pegar contexto en inglés y marcar la cita objetivo con una acción sencilla. Internamente se utiliza TARGETCIT exactamente una vez.
3. Identificar explícitamente el artículo citado por ID de ACL o seleccionarlo del catálogo completo por título e ID. Puede filtrarse la lista por título/ID; al entrar a la etapa se solicitan sugerencias según el contexto usando SciBERT existente. Las sugerencias abarcan el catálogo completo; no identifican automáticamente la referencia ni garantizan texto preparado para Top-3. Los ejemplos precargan únicamente el contexto; ningún artículo queda confirmado por defecto. Mostrar título y enlace para confirmar la selección.
4. Consultar si existe texto preparado. Si no existe, explicar la limitación y mantener lo ingresado; permitir corregir el identificador o seleccionar otro artículo preparado. No sustituir silenciosamente la referencia ni ofrecer JSON como salida normal.
5. Elegir «Encoder SciBERT — M», «Encoder SciBERT — S», «Modelo abierto — [identidad verificada]» o «Modelo comercial — [identidad verificada]». Agrupar M/S en la misma familia. Mostrar opciones no configuradas como no disponibles con motivo.
6. Pulsar «Ver resultados» en el clasificador: tras validar entradas y consentimiento, abrir inmediatamente el paso 4 y mostrar la espera del análisis. Mantener visibles los números 1–4; anunciar estado, evitar duplicados y ofrecer recuperación ante error. Si ya existe un análisis completo vigente, mostrarlo sin repetir inferencia.
7. Ver artículo, Top-3 ordenado, secciones y fuentes; después, función de cita predicha y puntuaciones disponibles del clasificador elegido. Permitir cambiar de clasificador conservando la misma entrada.

La selección de M o S puede filtrar la respuesta conjunta actual: no afirmar que el servidor ejecuta únicamente uno. Una comparación simultánea de todos los proveedores es opcional y queda fuera del mínimo, para controlar costo y latencia.

## 6. Requisitos funcionales y aceptación

| ID | Requisito | Criterio de aceptación |
|---|---|---|
| RF01 | Acceso directo al análisis científico. | Se completa el caso feliz sin usar el ranking de artículos ni pegar JSON. |
| RF02 | Identificar el artículo citado dentro del catálogo completo y comprobar cobertura. | Filtro literal por título/ID y sugerencias opcionales por contexto sobre los 19.776 artículos, con SciBERT existente; título, resumen y fuente confirmables; selección explícita antes de recuperar fragmentos. Sin buscador global separado ni TF-IDF. |
| RF03 | Validar contexto y marca. | Vacío, múltiples marcas y exceso de longitud producen instrucciones concretas antes de inferir; límites consistentes con backend. |
| RF04 | Mostrar cobertura. | Artículo no preparado no dispara inferencia ni presenta resultados ficticios. Fallo de consulta no se confunde con falta de texto. |
| RF05 | Recuperar únicamente dentro del artículo elegido. | La respuesta identifica el mismo artículo y muestra tres fragmentos distintos con sección, o informa que no se puede completar el análisis. |
| RF06 | Ejecutar encoder existente. | M/S conservan contrato, nueve categorías y correspondencia con sus checkpoints. |
| RF07 | Ejecutar un abierto de 1–8B. | Una entrada nueva produce respuesta real de un modelo identificado; no se responde con las etiquetas precalculadas. |
| RF08 | Ejecutar un comercial. | Llamada desde backend con credenciales privadas; salida validada y manejo de errores del proveedor. |
| RF09 | Selección honesta de modelo. | Familias, modelo y perfil de entrada visibles; opciones indisponibles no se ofrecen como operativas. |
| RF10 | Presentación comprensible. | Clase y explicación breve; nueve funciones consultables; probabilidades solo cuando existen. Ambiguo/No evaluable se presentan como abstención, sin forzar una clase. |
| RF11 | Estados y errores. | Carga, ocupado, timeout y salida inválida recuperables; cambiar contexto/artículo descarta resultados obsoletos. |
| RF12 | Información técnica secundaria. | Tokens, perfiles internos y versiones quedan en detalles; fuentes y advertencias útiles permanecen visibles. |
| RF14 | Retirar funcionalidades fuera del alcance. | No hay buscador global ni acceso por rutas antiguas a paneles/experimentos; inicio y navegación presentan solo el flujo requerido. |
| RF13 | Ejemplos públicos. | Al menos un ejemplo compatible con el corpus desplegado completa el flujo; no se envían datos privados TRAIN/Gold a servicios externos como prueba. |

No presentar similitud coseno ni softmax como probabilidad de una cita correcta. Los fragmentos recuperados son candidatos relacionados, no una verificación automática de la afirmación. Si los proveedores usan entradas distintas, mostrar esa diferencia; no llamar a sus salidas una comparación científica controlada.

## 7. Reutilización de API y extensión mínima

| Endpoint existente | Función |
|---|---|
| `POST /api/analisis-cita-ms/disponibilidad` | Cobertura por IDs, máximo 20 por solicitud. |
| `POST /api/analisis-cita-ms/articulo` | Camino principal por ID: obtiene metadatos/candidatos y devuelve Top-3 + M/S. |
| `POST /api/analisis-cita-ms` | Contrato interno reutilizable; no exponer formulario JSON/candidatos en el producto público. |
| `GET /api/analisis-cita-ms/estado` | Estado técnico, complementado por POST real en validación. |
| `GET /api/modelos` y `POST /api/recomendar` | Fuera del recorrido público. No consumirlos desde la nueva interfaz; conservarlos solo si otras herramientas los necesitan. |

Para un selector de artículos preparados se puede generar una lista pública de metadatos mínimos desde el manifiesto del corpus y verificar disponibilidad al seleccionar. Versionarla con la misma entrega del corpus; no extraer ni publicar anotaciones privadas. Si el corpus cambia de forma independiente y esto no es viable, una consulta de documentos disponibles sería una extensión adicional por justificar.

**Límite de reutilización:** los endpoints M/S actuales no ejecutan Qwen ni comerciales. No basta con añadir opciones al frontend. Se requiere una pequeña extensión backend para despachar estos proveedores, sin alterar las respuestas M/S existentes.

**Contrato propuesto, aún no implementado:** añadir `GET /api/analisis-cita-ms/clasificadores` para identidades, familia, disponibilidad, perfil y capacidades; añadir `POST /api/analisis-cita-ms/clasificar` para ejecutar el proveedor sobre contexto y artículo identificados. Mantener estas rutas bajo el prefijo científico para reutilizar su enrutamiento, verificando las reglas reales del despliegue. Si se decide extender un endpoint existente en vez de añadir rutas, hacerlo con campos opcionales y pruebas de compatibilidad equivalentes.

La operación propuesta de clasificación obtiene metadatos desde el corpus del servidor; recibe un identificador permitido de clasificador, no una URL de proveedor arbitraria. Devuelve identidad y perfil efectivos, clase o abstención, puntuaciones opcionales, latencia de clasificación y metadatos de uso si el proveedor los ofrece. No acepta etiquetas ni probabilidades enviadas por el navegador como resultados del modelo.

Para reducir cambios, reutilizar la respuesta M/S para Top-3 y sus variantes; al elegir abierto/comercial, ejecutar la clasificación adicional sobre el mismo artículo/contexto. Advertir que ese camino calcula M/S aunque se visualice otro proveedor y medir su latencia total. Optimizar para evitar ese cálculo solo si el presupuesto de tiempo lo exige; no introducir esa refactorización como requisito inicial.

## 8. Modelos, protocolos y decisiones pendientes

- **Abierto preferido para recuperar:** Qwen2.5-7B + adaptador QLoRA ya compartido, sujeto a verificación. Ubicación comunicada: `datos y resultados/qlora_18000/qlora_citas_adapter_v1/` en SharePoint/OneDrive. No se verificó acceso remoto actual.
- **Alternativa sin entrenamiento:** Qwen2.5-7B-Instruct usado como juez v3. Elegirlo solo documentando que es distinto del ajustado.
- **Destino de inferencia:** confirmar servicio existente o aprovisionar destino compatible. El notebook usa CUDA/bf16 o cuantización; el contenedor CPU M/S actual no queda acreditado para alojar Qwen. No modificar infraestructura con costos nuevos sin concretar primero destino y recursos.
- **Comercial:** reutilizar un proveedor ya evaluado por el equipo, una vez revisados sus artefactos, acceso y configuración. No elegir un modelo por nombre histórico sin comprobar disponibilidad.
- **Protocolos:** los jueces v3 puntúan letras con tres rotaciones sobre contexto/título/abstract; el cliente OpenAI-compatible genera texto. No son equivalentes automáticamente. Si se usa JSON generado, asignar un perfil nuevo y no atribuirle las métricas v3.
- **Abstenciones:** los jueces manejan 11 opciones, M/S nueve. Mantener las dos opciones adicionales como estados explícitos y las nueve funciones como taxonomía principal.
- **Puntuaciones:** no fabricar una distribución de nueve valores a partir de una sola clase; mostrar «no disponible» cuando corresponda.

## 9. Requisitos operativos

- Credenciales solo en backend y configuración segura del despliegue; no incluir claves ni direcciones sensibles en respuestas o logs.
- Configurar lista de modelos permitidos, destino abierto, proveedor comercial, timeouts y límites de concurrencia. Reutilizar configuración existente donde aplique.
- Mostrar antes de ejecutar un proveedor externo que el texto será procesado por ese proveedor.
- Establecer límites de solicitudes para la URL pública antes de habilitar consumo comercial; una solicitud de usuario no debe disparar evaluaciones masivas ni reintentos ilimitados.
- Medir el tiempo total del recorrido y alinear timeouts del navegador, proxy y proveedor. La configuración actual del cliente ronda 32 s y la de evaluación puede llegar a 60 s: no conectarlas sin ajustar y probar el presupuesto. Si no cabe, simplificar la ejecución o definir un flujo asíncrono como cambio adicional explícito.
- Un fallo del proveedor externo no debe impedir iniciar M/S ni ocultar resultados ya calculados.
- Validar artefactos y revisión del modelo, registrar release y permitir volver a la versión previa. Mantener pesos privados con instrucciones de acceso autorizadas.

## 10. Backlog de implementación y seguimiento

Todas las tareas quedan pendientes de aceptación. La existencia de componentes previos no equivale a tarea terminada.

| ID | Paso acordado | Tarea | Dependencia de cierre | Evidencia de aceptación |
|---|---|---|---|---|
| T01 | 1–3 | Aislar búsqueda global experimental y recuperar build/arranque M/S reproducible, manteniendo el servicio público actual. | — | Build y arranque sin manifiesto ausente; contratos existentes pasan. |
| T02 | 1–2 | Implementar página principal según ASCII, identificación de artículo y marca de cita; retirar buscador y rutas heredadas. | T01 antes de publicar | Flujo único sin JSON ni ranking; rutas antiguas redirigen o no existen. |
| T03 | 1–2 | Incorporar disponibilidad, ejemplos públicos y resultados comprensibles reutilizando componentes. | T02 | Casos preparado/no preparado/error correctos; referencia y contexto conservados. |
| T04 | 4 | Empaquetar recuperador/M/S y probar SageMaker Serverless CPU. | T01 | Memoria, carga, compatibilidad y latencias medidas; decisión viable/no viable documentada. |
| T05 | 5 | Recuperar QLoRA, base/tokenizador/revisiones y verificar una entrada sintética. | Acceso a artefactos | Hashes y salida real. Si falta adaptador, decisión explícita sobre Qwen base; no sustitución silenciosa. |
| T06 | 5 | Probar Qwen + adaptador en SageMaker Asynchronous GPU y mínimo cero. | T05, región y cuota disponibles | Arranque desde cero, inferencia, apagado, latencias y costo observados. |
| T07 | 6 | Implementar catálogo de clasificadores, despacho, respuesta normalizada y trabajo/consulta de estado asíncronos. | T06 para validar QLoRA real; contrato puede prepararse antes | Compatibilidad M/S, abstenciones, aislamiento de errores y recuperación de resultados. |
| T08 | 6 | Integrar selector de familias y estados de espera/resultados en frontend. | T03 y T07 | Cambio de modelo sin resultados obsoletos; entrada preservada; ejecución elegida identificada. |
| T09 | 7 | Conectar un comercial existente, fijar perfil y validar parseo/configuración. | T07 y acceso al proveedor | Inferencia real acotada; identidad efectiva y puntuaciones solo si disponibles. |
| T10 | 4–8 | Configurar IAM, S3/ECR, secretos, retención, concurrencia, máximos de escala, alertas y presupuesto de tiempo/costo. | Antes de exponer cada nuevo servicio | Acceso privado, sin secretos en navegador/logs y consumo acotado. |
| T11 | 8 | Ejecutar pruebas relevantes y recorrido visual/publicación controlada de las tres familias. | T02–T03, T06–T10 | Casos reales públicos/sintéticos, errores y cobertura; versión y tiempos registrados. |
| T12 | 9 | Decidir migración M/S con evidencia y retirar recursos sustituidos tras comprobar dependencias. | T04, T10–T11 y alternativa validada | Comparación de costo total, reversión y comprobación de servicio posterior al cambio. |
| T13 | 9 | Actualizar README y documento de acceso con configuración, ejemplos, recursos y limitaciones. | Release final identificada | Documentación alineada con versión pública y reproducción verificable. |

La Entrega A de §4 permite publicar primero el recorrido M/S estable (T01–T03 y sus comprobaciones), describiéndolo como M/S únicamente. La entrega de tres familias requiere T05–T11. Si la prueba Serverless no es viable, se conserva M/S actual y se registra la razón; no bloquear innecesariamente las otras familias ni considerar esa migración completada. No se asignan responsables ni fechas sin coordinación del equipo.

## 11. Validación y definición de terminado

Comprobar que no quedan rutas ni enlaces al buscador global o paneles heredados; que las sugerencias del paso 2 pertenecen al catálogo versionado y no seleccionan automáticamente; que se comprueba texto preparado antes de analizar; y que el inicio muestra únicamente el flujo científico. Pruebas de contrato M/S sin regresiones; pruebas de adaptadores con respuestas válidas/inválidas y abstenciones; UI de disponibilidad, selector y resultados obsoletos; comprobación de red de que las credenciales no salen al navegador. Las pruebas de red reales utilizan casos sintéticos o públicos, con consumo acotado.

**Entrega completa de este PRD:** desde la URL pública un usuario identifica un artículo con texto disponible, obtiene su Top-3 y ejecuta un clasificador real de cada familia; las opciones no disponibles se identifican correctamente; los fallos no rompen el servicio; release y documentación coinciden con lo desplegado. Registrar latencia observada por familia sin convertir una solicitud en benchmark estadístico.

## 12. Resumen en palabras sencillas

Los modelos principales ya existen. Falta hacer que la web los ofrezca y utilice de verdad: recuperar el QLoRA, disponer de dónde ejecutarlo, conectar un comercial y presentar todo en un flujo sencillo. La parte de M/S y Top-3 se reutiliza. El trabajo principal es integración, interfaz, configuración y comprobación del despliegue; la incertidumbre mayor es el acceso y destino de ejecución del modelo abierto.

## 13. Mockup ASCII de la página principal

Este esquema define organización y contenido, no una página adicional. En móvil se apilan los mismos bloques. Las alternativas de entrada son un único selector de referencia, no otro recorrido de recomendación.

```text
+--------------------------------------------------------------------+
| Análisis de citas académicas                               [Ayuda]  |
| Identifica fragmentos relacionados y la función de una cita.         |
+--------------------------------------------------------------------+
| 1. CONTEXTO DE LA CITA                                              |
| Pega un párrafo académico en inglés.                                |
| +----------------------------------------------------------------+ |
| | Previous research [Smith, 2020] introduced ...                   | |
| |                                                                | |
| +----------------------------------------------------------------+ |
| Selecciona la referencia en el texto y pulsa: [Marcar cita]          |
| Cita objetivo: [Smith, 2020]                         [Usar ejemplo]  |
|                                                                    |
| 2. ARTÍCULO CITADO                                                 |
| [Seleccionar artículo preparado por título o ID                  v] |
| Artículo seleccionado: Título completo · ACL ID                     |
| [Abrir publicación]       Texto preparado: disponible               |
|                                                                    |
| 3. CLASIFICADOR                                                    |
| Familia: [Encoder ajustado / Modelo abierto / Modelo comercial   v] |
| Modelo:  [Nombre de la variante disponible                       v] |
| Ayuda breve: qué información utiliza el clasificador.               |
| Si es externo: el texto se procesará mediante [proveedor].          |
|                                                    [Analizar cita] |
+--------------------------------------------------------------------+
| RESULTADOS — aparecen después del análisis                         |
| Artículo: título · referencia objetivo · clasificador elegido       |
|                                                                    |
| FRAGMENTOS RELACIONADOS DEL ARTÍCULO CITADO                          |
| 1. [Sección]  Texto del fragmento...                 [Ver fuente]    |
| 2. [Sección]  Texto del fragmento...                 [Ver fuente]    |
| 3. [Sección]  Texto del fragmento...                 [Ver fuente]    |
| Son candidatos relacionados; no prueban por sí solos la afirmación. |
|                                                                    |
| FUNCIÓN DE LA CITA                                                 |
| Application — utiliza un método sin modificarlo.                    |
| [Distribución de puntuaciones, si el modelo la ofrece]              |
| [Qué significan las nueve funciones]     [Detalles del análisis v]  |
+--------------------------------------------------------------------+
```

Estados del mismo formulario: campo inválido junto a su entrada; artículo sin texto con explicación; proveedor no disponible con motivo; progreso de recuperación/clasificación; fallo de clasificación que conserva Top-3 cuando ya fue recuperado. No incluir gráficos históricos, controles de ranking o enlaces a los paneles retirados.

## 14. Diseño de API: separar recuperación y clasificación

La recuperación SciBERT es común a las tres familias; la elección cambia el clasificador, no el artículo ni el significado del Top-3. No cargar un recuperador distinto por cada proveedor sin necesidad.

Arquitectura de producto:

```text
Web: contexto + referencia + clasificador
                  |
                  v
API de la aplicación: valida, obtiene artículo y controla solicitudes
                  |
                  +--> SciBERT: recuperación Top-3 del artículo
                  |
                  +--> Clasificador elegido
                         |-- SciBERT M/S (pesos propios)
                         |-- Qwen 7B / Qwen + adaptador QLoRA
                         `-- API comercial
                  |
                  v
Respuesta normalizada: Top-3 + función/abstención + metadatos
```

Mantener endpoints M/S existentes para compatibilidad y verificaciones. Para el recorrido unificado, preferir ampliar de forma compatible el análisis por artículo con un identificador opcional de clasificador, manteniendo el comportamiento antiguo cuando no se envía. Si normalizar la respuesta modifica el contrato anterior, utilizar un endpoint unificado nuevo en lugar de romper clientes. Resolver esta elección al implementar con pruebas de contrato; no diseñar una API por familia visible al navegador.

El objetivo final es ejecutar solo el clasificador seleccionado. El atajo descrito en §7 —ejecutar M/S para obtener Top-3 antes del externo— es transitorio: se admite únicamente si las mediciones permiten cumplir el presupuesto de latencia/costo. Extraer la recuperación común del servicio existente no requiere entrenar modelos. No cambiar silenciosamente la entrada histórica de cada clasificador para incluir fragmentos que no usaba; informar su perfil.

## 15. Plan de despliegue AWS con costo por uso

**Preferencia explícita:** utilizar servicios AWS para alojar los modelos propios, buscando evitar instancias de inferencia permanentemente encendidas. Se reemplaza la comparación previa con proveedores externos.

### Opciones según la familia

| Componente | Candidato AWS | Condición y límite |
|---|---|---|
| Recuperación SciBERT y M/S | SageMaker Serverless Inference bajo demanda | CPU, hasta 6 GB de RAM; verificar memoria total, carga desde S3 y latencia. No tiene GPU. No activar concurrencia aprovisionada para la evaluación de costo bajo demanda. |
| Qwen 7B + adaptador QLoRA | SageMaker Asynchronous Inference con GPU y mínimo cero | Compatible en principio con contenedor propio, sujeto a empaquetado y prueba; requiere autoscaling correcto para despertar desde cero. Cobra capacidad mientras está aprovisionada, no una tarifa fija por consulta. |
| Modelo comercial | API del proveedor seleccionado, llamada desde backend AWS | No alojar pesos comerciales. Bedrock puede considerarse si existe un modelo disponible adecuado y se verifican contrato/acceso; no se asume que aloje automáticamente nuestros checkpoints. |

No se necesita desplegar Qwen y Llama a la vez para cubrir la familia abierta. Un endpoint que sirve Qwen base no sustituye al adaptador QLoRA propio.

### Precisión de costos

SageMaker Serverless bajo demanda factura duración de cómputo y datos procesados según su tarifa; almacenamiento y otros servicios se consideran aparte. Es el candidato más cercano a pago por ejecución para los encoders pequeños. No se confirma su adecuación hasta medir el conjunto recuperador + M/S en el límite de memoria.

SageMaker Asynchronous puede reducir a cero instancias sin solicitudes. Usa facturación de instancias mientras están aprovisionadas: incluir arranque, carga y ventanas de escalado/inactividad; no prometer costo exclusivamente por segundos del forward del modelo. Es una alternativa GPU para QLoRA con uso intermitente, con arranque en frío y cola.

Costo total = inferencia CPU/GPU + almacenamiento S3/ECR + observabilidad y transferencias aplicables + API comercial + infraestructura AWS conservada. Migrar modelos sin retirar recursos anteriores no elimina sus cargos.

### Arquitectura de ejecución propuesta

La web utiliza la API propia como fachada. Para tareas que no terminan dentro del timeout HTTP, la API crea un trabajo, devuelve identificador y permite consultar estado/resultado. La aplicación muestra «Preparando modelo» o «Procesando» y conserva entradas/resultados. El navegador no accede directamente a pesos ni a URLs S3 privadas.

Este contrato asíncrono es una extensión de API necesaria si se elige la modalidad asíncrona para QLoRA, no un cambio de la tarea del usuario. La ejecución síncrona M/S existente se conserva para compatibilidad. Los payloads y resultados de trabajos se guardan en S3 privado con permisos mínimos y política de retención definida.

### Seguimiento de despliegue

Las tareas T04–T07 y T10–T13 de §10 son el único seguimiento de infraestructura: prueba CPU Serverless, recuperación QLoRA, prueba GPU asíncrona, API de trabajos, configuración segura, validación y migración/retirada. No se mantiene una segunda lista D01–D07 para evitar duplicar estados.

La decisión es provisional hasta pruebas y cuotas; este PRD no inicia recursos ni garantiza ahorro. Mantener el despliegue actual mientras se valida la alternativa. Para sustentación, medir por separado servicio frío y caliente; cualquier precalentamiento tiene costo y debe explicarse.

Fuentes oficiales consultadas el 22-nov-2026:

- [SageMaker Serverless Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html): memoria hasta 6 GB y exclusión de GPU.
- [SageMaker Asynchronous Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html): cola y escalado a cero.
- [Precios SageMaker AI](https://aws.amazon.com/sagemaker/ai/pricing/): comprobar tarifas por modalidad, región y recurso al presupuestar.


La espera de análisis largos conserva un solo inicio de inferencia y consulta su resultado transitorio, evitando el límite HTTP de 30 segundos. Los errores no provocan reintentos automáticos ni pérdida del contexto; esta integración no cambia modelos, pesos ni la confirmación manual. Véase el cierre de [cobertura y aceptación](../notas/ampliacion_cobertura_corpus.md).


**Organización de resultados solicitada posteriormente:** la sección «Función predicha de la cita» presenta tres pestañas locales: Puntuación (activa al abrir), Detalles del análisis y Ayuda (definiciones de las nueve funciones). Los detalles comerciales se incluyen en la segunda; el Top-3 permanece fuera de estas pestañas. No cambia el recorrido de cuatro etapas ni las inferencias. Véase [pestañas de resultados](../notas/pestanas_funcion_predicha.md).

**Refinamiento de los detalles:** resumen del método y clasificador, tabla de fragmentos con sección y similitud, alcance del recorte cuando existe y metadatos técnicos plegados. Se conserva el proveedor comercial identificable y el enlace a cada fragmento. Véase [diseño y comprobaciones](../notas/diseno_detalles_analisis.md).

**Numeración y espera en resultados:** los números de las cuatro etapas se conservan al completarlas; la espera se presenta dentro de Resultados desde el inicio del cálculo. Véase [decisión y comprobaciones](../notas/pasos_numerados_carga_resultados.md).
