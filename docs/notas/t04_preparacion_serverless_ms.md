# T04 — Preparación de la prueba SageMaker Serverless

Estado: EN CURSO. Preparación local validada; prueba AWS y decisión de viabilidad
pendientes. No se han publicado artefactos ni creado/modificado recursos AWS.

## Preparado

- Imagen separada Dockerfile.serverless-ms; no modifica el comando del servicio
  ECS actual. Soporta `serve`, puerto 8080, GET/POST /ping y POST /invocations.
- Reutiliza contratos y funciones existentes M/S y por artículo. Un solo worker,
  sin búsqueda global, sin descarga dinámica ni credenciales dentro del contenedor.
- Empaquetador local de la allowlist de config/ms_release.json. Verifica tamaños y
  hashes antes de empaquetar y al arrancar. Incluye diez archivos y release.json;
  no incluye etiquetas, Gold, resultados precalculados ni credenciales.
- Bundle 1.640.458.673 bytes comprimidos y 1.761.587.556 bytes de artefactos.
  SHA-256 b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f.
- Comprobador scripts/probar_serverless_ms.py: usa /invocations local o un endpoint
  ya existente. Hasta seis llamadas seriales, sin reintentos automáticos y con
  parada al primer error; no crea recursos ni imprime textos de entrada.
- Terraform aislado en terraform/serverless_ms_probe, sin backend remoto ni estado
  compartido con producción. Proveedor 5.100.0 como el proyecto; validate aprobado.
  No se ejecutaron plan/apply, porque aún falta publicar y fijar el digest ECR real.

## Evidencia local

Ocho pruebas de integridad, adapter y bootstrap aprobadas. Builds AMD64 y ARM64
aprobados. Imagen AMD64 preparada para publicar:
sha256:52921583040c44b07f400085d1c2655d7a29c58ab9ad323c22204ada881511ec
(ID local, NO digest de registro ECR).

AMD64 se ejecutó emulado sobre Docker ARM64 y no alcanzó readiness en 180 segundos
de observación; no hubo OOM. Esa prueba fue detenida. La emulación y el montaje
local impiden atribuir ese resultado a SageMaker.

La variante ARM64 nativa cargó el bundle de solo lectura con límite de 6 GiB,
sin swap adicional, dos CPU y sin credenciales. /ping respondió 200. Las cinco
inferencias locales pasaron:

- Sintética inicial: 11,882 s; repetida: 13,786 s. Top-3, clases y nueve puntuaciones
  M/S coinciden con la referencia con tolerancia 0,005.
- Artículo público W05-0821: 15,950 s, 16,191 s y 15,325 s. Identidad y textos
  cotejados con el corpus; M Background, S Application.
- Muestra de memoria del contenedor: aproximadamente 3,2 GiB de 6 GiB; no es un
  máximo CloudWatch ni garantía para documentos largos. VmHWM del proceso al final:
  2.077.308 kB. No hubo OOM.

Estas observaciones NO miden frío/caliente ni rendimiento en AWS. Los contenedores
temporales fueron detenidos; se conservan imagen y bundle locales para la prueba.

## Lecturas AWS y propuesta revisable

Cuenta del proyecto 646941583111, us-east-1. Consultas de lectura: sin endpoints
SageMaker y sin roles cuya confianza incluya sagemaker.amazonaws.com. Cuotas de
cuenta devueltas: 300 endpoints serverless y concurrencia total 10. No confundir
estas cuotas con las predeterminadas o ejemplos de documentación.

AWS Pricing GetProducts devolvió 6 GB a US$0,00012/s, tarifa efectiva 1-nov-2026.
Propuesta: un endpoint nuevo de 6144 MB, concurrencia máxima 1, sin provisioned
concurrency, máximo seis invocaciones, presupuesto total propuesto US$1. Este
presupuesto NO es un tope de facturación automático. Mantener ECS implica que sus
cargos continúan. Incluir S3/ECR/logs/datos/carga y limpiar recursos de la prueba.

Requiere publicar imagen y bundle en ECR/S3 privados existentes, crear rol/política
limitados, logs con retención de tres días, modelo, configuración y endpoint nuevos.
El procedimiento y limpieza exactos están en terraform/serverless_ms_probe/README.md.
No toca ECS, rutas, dominio ni release actual.

## Aceptación pendiente

Ejecutar en AWS tras autorizar recursos nuevos; medir descarga/readiness, memoria,
errores, primera llamada y repetidas. Consultar OverheadLatency y logs para
identificar frío, sin llamar «fría» a una petición solo por ser la primera.
Registrar costo y decisión viable/no viable/evidencia insuficiente. Comprobar
artículo largo y el presupuesto del cliente/proxy, que actualmente vence antes
que el límite de inferencia SageMaker. No cerrar T04 con esta preparación local.

Fuentes oficiales consultadas:
- https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints-invoke.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints-monitoring.html
- https://aws.amazon.com/sagemaker/ai/pricing/

## Publicación desde EC2 verificada el 22 de noviembre de 2026

Se publicaron las imágenes M/S y Serverless AMD64 en el ECR aislado de T04.
Los diez archivos originales se recuperaron directamente de S3 en EC2, con
tamaños y SHA256 comprobados. El paquete de 1.640.458.673 bytes coincide con
el local: b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f.

Terraform ejecutado en EC2 publicó el paquete en experiments/t04-ms-serverless/
<sha256>/model.tar.gz del bucket privado de modelos. Se verificó el SHA256
leyendo de nuevo todos los bytes desde S3. El estado propio del objeto está en
terraform/t04-ms-artifact/terraform.tfstate del mismo bucket; el módulo del
endpoint solo consulta el objeto como dato. Ver terraform/model_artifact/README.md.

No se creó aún un endpoint ni se realizaron inferencias en SageMaker. T04 sigue
en curso: publicar los artefactos no acredita latencia, memoria ni arranque en
Serverless. La siguiente validación debe usar el digest Serverless ya publicado,
el objeto verificado y un plan que conserve ECS.

## Intento real en SageMaker: pendiente de cuota de memoria

AWS rechazó inicialmente el manifiesto OCI. Se publicó una variante Docker V2
usando la traducción de ECR, con idénticos hashes de configuración y capas.
Digest compatible: sha256:f2c7c71692f3e3063dda146a4a0692f338c32eb5ee507399a3b8520207bbf72c.
SageMaker registró correctamente el modelo y la configuración de 6144 MB.
CreateEndpoint fue rechazado con ResourceLimitExceeded: cuota de memoria
3072 MB, solicitud 6144 MB en us-east-1. No se creó el endpoint ni se ejecutaron
inferencias. Esta cuota no figura en la lista de Service Quotas. La API de
Support devolvió SubscriptionRequiredException; el usuario abrirá el caso manual.

T04 sigue pendiente: no hay medidas de carga, memoria o latencia en SageMaker
y no se ha decidido la viabilidad técnica. ECS se conserva. Imágenes, bundle,
modelo, configuración, rol y logs de prueba quedan preparados para reintentar
tras la aprobación; no hay endpoint activo de esta prueba.
