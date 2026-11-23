# Pasos numerados y espera dentro de resultados

## Solicitud y decisión de diseño

El usuario pide conservar 1. Contexto, 2. Artículo, 3. Clasificador y 4. Resultados, y abrir el paso 4 inmediatamente al pulsar «Ver resultados». La implementación anterior sustituía los números completados por checks y esperaba la respuesta M/S dentro del clasificador. Esas decisiones históricas se sustituyen aquí.

Se conserva el indicador secuencial como lista ordenada: número visible y accesible en todos los estados, check complementario, texto de estado y `aria-current=step`. No se convierte en un conjunto de pestañas. La acción del clasificador se llama «Ver resultados» antes y después del cálculo: si ya existe un análisis completo vigente, vuelve a mostrarlo sin otra solicitud ni espera artificial.

Tras validar entradas y consentimiento, se activa Resultados en el mismo evento que inicia el análisis. Se enfoca su título y aparece una superficie blanca con indicador de actividad, «Calculando los resultados…» y explicación breve. No se muestran porcentajes, tiempos estimados ni fases ficticias: la API M/S calcula recuperación y clasificación conjuntamente. Cuando devuelve el Top-3 en el camino comercial, el estado cambia realmente a espera de OpenAI y permite consultar los fragmentos. El resultado parcial no completa el paso 4.

Patrones aplicados: visibilidad del estado del sistema, respuesta inmediata al cambio de etapa, indicador indeterminado, presentación progresiva del resultado disponible y recuperación de errores conservando entradas. Los mensajes usan `role=status` y `aria-atomic`, sin mover el foco en cada actualización. Al finalizar se enfoca el resultado; ante error se enfoca el aviso. La animación respeta `prefers-reduced-motion`. Referencia de accesibilidad: [W3C, mensajes de estado](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html).

Mientras se calcula, la navegación está bloqueada para evitar cambios y ejecuciones duplicadas. No se añade cancelación que prometa detener el servidor. Un fallo anterior al Top-3 muestra el error en Resultados y ofrece «Volver al clasificador» o «Revisar artículo» si perdió cobertura; no reintenta automáticamente. Un fallo comercial conserva el Top-3 y las salidas existentes. El título de resultados se presenta una sola vez en este recorrido.

Se mantienen paleta, tipografías, contenido científico, selección manual, recorte, consentimiento, endpoints y modelos. Es exclusivamente frontend; no necesita imágenes backend ni cambios de infraestructura. No acredita calidad científica ni completa la familia abierta.

## Verificación local

Build inicial correcto y 41 pruebas unitarias aprobadas. 36 recorridos de carga, etapas, asincronía, cobertura y comercial aprobados con mocks, en escritorio y móvil. Incluyen número persistente, paso 4 activo antes de responder, foco, ausencia de resultados falsos, espera comercial con Top-3, movimiento reducido, retorno a resultados sin repetir cálculo y recuperación ante expiración, 404, 429 y respuesta inválida. Capturas de carga inicial y espera comercial revisadas en ambos tamaños.

Los 56 recorridos adicionales de catálogo, ejemplos, usabilidad, recorrido y pestañas también aprobaron: 92 casos locales distintos en total. Se eliminó el título duplicado de resultados y la regla CSS del mensaje de carga anterior. Evidencia local separada: `artifacts/numbered-results-local/` y `artifacts/numbered-results-regression/`. Las pruebas que ejecutan inferencias reales no se han utilizado; solo se actualizó su selector de botón al nuevo nombre.

## Publicación y checklist

Publicado exclusivamente el frontend del commit `54b0910` con `make publish-frontend`, usando outputs recién actualizados y contrastados desde `make release-status`. El build final TypeScript/Vite aprobó. `make release-confirm` comprobó servicios estables, imágenes conservadas, salud HTTP, corpus y HTML público idéntico al build. SHA256 de `index.html`: `624d4156b0312488a74c0d41637dfcaf1e2a3904ed9682949bf1917ad3ae916b`. API conservada en `citas-api:7`; científico en `citas-api-science:9`. No se construyeron imágenes backend ni se encendió la constructora.

Los 14 recorridos públicos con respuestas API simuladas aprobaron en escritorio/móvil: carga inicial M/S y número persistente, resultados vigentes sin otra solicitud, espera asíncrona y expiración, consentimiento, espera comercial con Top-3, éxito y errores 429/502. Las capturas públicas de carga se revisaron en ambos tamaños. Evidencia separada en `artifacts/numbered-results-public-mocks/`, incluida copia de la confirmación. Estas pruebas aceptan presentación e interacción del bundle público; no son inferencias reales ni acreditan calidad científica. No se repitieron llamadas reales a modelos.

- [x] Números 1–4 conservados junto a sus nombres.
- [x] Validación y consentimiento antes de iniciar el paso 4.
- [x] Espera inmediata, accesible y sin porcentajes inventados.
- [x] Resultados existentes sin nueva inferencia; errores con recuperación.
- [x] Capturas locales de escritorio y móvil revisadas.
- [x] Regresión adicional y build final.
- [x] Publicación frontend y confirmación de HTML, salud y servicios actuales.
- [x] UI pública comprobada con mocks y capturas revisadas.

Estado general: T01–T03 disponibles; T04 pendiente por cuota; T05–T06 suspendidas por QLoRA; T07–T09 disponibles para M/S y comercial, familia abierta suspendida; T10 parcial; T11 conserva aceptación real anterior; T12 migración/retirada pendiente, sin retirar ECS; T13 notas actualizadas y cierre documental final pendiente. El proyecto sigue parcialmente cumplido.
