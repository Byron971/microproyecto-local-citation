# Estabilidad M/S y alternativas SageMaker — 23 de noviembre de 2026

## Solicitud y reporte recibido

El usuario consulta mover M/S a SageMaker tras un reporte del equipo: sobre los casos 2–26 de una batería de 50 artículos, nueve éxitos de 17–30 s, seis HTTP 503 próximos a 30 s y diez HTTP 429 inmediatos, con dos segundos entre solicitudes y sin concurrencia intencional. Es información reportada, no una batería reproducida aquí. El usuario estima alrededor de las 11:52 de Bolivia y no dispone del método/cuerpo de las peticiones. Confirmó que AWS todavía no responde al aumento de memoria Serverless y que debemos continuar sin él.

## Comprobaciones actuales de lectura

Perfil josezambrana, cuenta 646941583111, us-east-1. No se ejecutaron inferencias, crearon endpoints, modificaron recursos ni encendió la constructora.

- ECS conserva API `citas-api:7` y científico `citas-api-science:9`, una tarea activa de cada servicio. Salud científica pública: modelos cargados, revisión `e84fd3a`, 19.243 artículos preparados y versión `1f496d7b681b0852d927462f7b24a854189f37535e58d598cc131f435146b55d`.
- Científico: **2 vCPU y 6.144 MB**. En las 24 horas observadas, CloudWatch devolvió máximo de CPU **100 %** y memoria **37,79 %**. Son máximos observados por las métricas del servicio, no máximos instantáneos del proceso ni garantía contra picos.
- HTTP API y configuración efectiva: integración **30.000 ms**, tasa 20 solicitudes/s y ráfaga 40. [AWS fija el máximo de HTTP API en 30 segundos, sin aumento](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html). No confundir con cambios permitidos a algunas REST APIs.
- ALB: `TargetResponseTime` máximo **40,8721 s**; se observaron varios intervalos con respuestas superiores a 30 s. No hubo datos positivos de `HTTPCode_ELB_503_Count`; `HTTPCode_Target_5XX_Count` sumó un evento en esa ventana.
- API Gateway registró 15 POST 503 en 24 horas; no identifica la URL concreta porque su formato actual conserva la ruta comodín, no el path, ni incluye duración. El servicio científico no registró POST de artículo 503 en el agregado consultado; sí 16 respuestas 429 de análisis. No se encontraron filas del patrón de errores de ejecución en esos logs. La consulta de tareas detenidas no devolvió tareas; no acredita ausencia histórica de reinicios fuera de su retención.
- Hubo **65 POST de artículo con resultado 200**, correspondientes al camino síncrono. También se contaron **19 POST 202 y 19 GET finales 200** en el camino de trabajos. Esos contadores no son una prueba de concurrencia o de que toda la batería del equipo usara un modo concreto.
- Se encontró el patrón especialmente entre **10:54 y 11:08 de Bolivia**: después de solicitudes que terminaron en 503 en el gateway, aparecen 429 cada ~2,3 s y luego un 200 del servicio. Ejemplo de correlación temporal: solicitud registrada por gateway 10:58:49, 429 desde 10:59:21 y respuesta científica 200 a las 10:59:29. Sin ID compartido entre ambos registros, la asociación es temporal; no se atribuye de forma concluyente a la batería reportada alrededor de las 11:52.

Evidencia agregada y sin textos/IPs: `artifacts/stability-review-2026-11-23/readonly-summary.json`, `followup-summary.json` y `verified-settings.json`. Los IDs internos de filas de logs se eliminaron del informe.

## Diagnóstico y acción inmediata

La evidencia respalda como hipótesis principal el **uso del camino síncrono por encima del límite del gateway**. Un timeout del cliente/proxy no detiene automáticamente la inferencia. Por tanto, una batería secuencial desde el punto de vista del cliente puede solaparse con el cálculo que sigue activo y recibir 429 por el bloqueo compartido con M/S y sugerencias. No parece justificar aumentar el rate limit general ni la memoria solo por estos datos.

La web ya envía `asincrono: true`, recibe `trabajo_id` y consulta GET hasta finalizar. El endpoint mantiene `asincrono: false` como predeterminado por compatibilidad; un cliente directo que omita el campo sigue siendo síncrono. No se cambió ese contrato público ni se añadieron reintentos.

Se corrigió **`scripts/probar_flujo_integrado_ms.py`**, usado por `make release-check`: todavía esperaba el resultado completo en un POST. Ahora envía una sola admisión asíncrona, exige 202, conserva el ID, consulta solo ese trabajo y espera hasta 180 s. Cada petición tiene su propio límite de transporte. Un 429/503, una respuesta inválida o la expiración detienen la comprobación sin repetir ni cancelar la inferencia. Se conservan las verificaciones de artículo, textos Top-3 y puntuaciones. Esto corrige el comprobador del repositorio, no demuestra que el equipo utilizara ese mismo script.

Para una batería externa, el protocolo es:

```text
POST /api/analisis-cita-ms/articulo
{"paper_id":"W05-0821","contexto":"Earlier work TARGETCIT proposed a method.","asincrono":true}

202 -> consultar GET /api/analisis-cita-ms/articulo/{trabajo_id}
202 -> seguir consultando el mismo trabajo
200 -> guardar resultado; solo entonces iniciar el siguiente caso
429/503/410/timeout -> detener y registrar; no enviar otro POST automáticamente
```

La espera asíncrona actual evita mantener abierta la petición HTTP durante el cálculo, **no añade una cola**. Solo admite una inferencia científica activa; sugerencias y otros usuarios pueden ocupar el mismo bloqueo. Los trabajos actuales viven en memoria, tienen capacidad ocho y expiran 120 s después de terminar. No se debe aumentar réplicas sin resolver dónde se consultan esos trabajos. Tampoco basta aumentar vCPU: la imagen actual fija `OMP_NUM_THREADS=2` y `MKL_NUM_THREADS=2`; se debe medir el efecto de cualquier ajuste de recursos e hilos, sin modificar pesos.

## SageMaker sin esperar la cuota Serverless

No existe actualmente un endpoint SageMaker activo. El modelo y configuración de T04 siguen preparados a 6.144 MB y concurrencia uno. El rechazo anterior fue 3.072 frente a 6.144 MB; Service Quotas no expone ese límite de memoria y el usuario confirma que el caso sigue sin respuesta. No se reintentó CreateEndpoint ni se bajó memoria sin probarla. [Serverless admite hasta 6 GB](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html) y [limita inferencia a 60 s](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints-invoke.html); sigue necesitando resolver el presupuesto del cliente/proxy.

**Sí hay una alternativa independiente del aumento Serverless:** endpoints con instancias CPU. Las cuotas consultadas para `ml.c5.xlarge` y `ml.m5.xlarge` en endpoint usage son 30 cada una. Es cuota disponible, no una instancia desplegada ni una validación de rendimiento/capacidad regional.

Para lotes y esperas superiores al límite HTTP, la recomendación es evaluar un **piloto aislado de SageMaker Asynchronous Inference**. [AWS proporciona cola, entrada/salida en S3 y procesamiento asíncrono](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html). Reutilizar M/S y SciBERT existentes, sin entrenar ni cambiar pesos. Propuesta técnica aún no aplicada:

1. Terraform separado de producción, una instancia CPU de las familias con cuota, máximo una invocación activa por instancia. Fijar imagen y artefactos; no reutilizar sin revisar la imagen T04 anterior como si incluyera el corpus y contratos actuales.
2. Adaptar y verificar `/invocations` para devolver el resultado final. La cola SageMaker gestiona la asincronía: no devolver un token de los trabajos en memoria de ECS desde dentro de la invocación.
3. Integrar API pública y almacenamiento/estado del trabajo para conservar artículo confirmado, Top-3, clasificación y espera frontend. Prever ciclo de vida de los objetos de entrada/salida S3. Una réplica nueva no puede recuperar el estado que solo exista en otra memoria.
4. Comprobar arranque, memoria, latencia, cola, fallos, resultados y costo con pocos casos normales/largos antes de repetir la batería completa. Fijar presupuesto y política de escalado; el escalado a cero puede añadir espera y requiere configuración explícita, no ocurre por declarar asíncrono.
5. Conservar ECS y la reversión hasta aceptar el piloto. No dirigir tráfico ni retirar recursos actuales durante esta investigación.

SageMaker Real-Time CPU también tiene cuota de hosting disponible, pero no elimina el límite del gateway ni añade por sí solo la cola que interesa para este patrón de carga. La viabilidad de cualquiera de las alternativas sigue pendiente de prueba e integración; T04 Serverless no se marca completa.

## Verificación del cambio y checklist

Once pruebas locales de trabajos y comprobador aprobadas con dobles HTTP/modelo, incluida espera simulada de 41 segundos y un único POST, sin nuevas solicitudes de inferencia en GET. La prueba adicional de concurrencia del runtime se omitió porque este entorno no tiene PyTorch. No se descargaron dependencias ni ejecutaron modelos. No hay una nueva aceptación pública del comprobador corregido ni una batería de 50 ejecutada por esta revisión.

- [x] Estado, cuotas disponibles, gateway, métricas y logs consultados actualmente.
- [x] Hipótesis separada de hechos; procedencia exacta de la batería sin confirmar.
- [x] Comprobador heredado actualizado a trabajos; pruebas locales aprobadas.
- [ ] Identificar el cliente/cuerpo exacto usado por el equipo y repetir pocos casos con el protocolo correcto.
- [ ] Preparar, presupuestar y aceptar piloto SageMaker CPU asíncrono antes de migrar.
- [ ] Resolver cuota si se retoma específicamente Serverless.

Estado general conservado: familia abierta/QLoRA suspendida, T04 Serverless pendiente, T10 parcial, T12 migración/retirada pendiente; ECS sigue sirviendo y no se modifica infraestructura. Las notas se actualizan sin declarar cerrado el proyecto ni validación científica nueva.
