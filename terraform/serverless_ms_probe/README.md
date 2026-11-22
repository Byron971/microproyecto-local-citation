# Prueba aislada T04 — SageMaker Serverless M/S

Preparación local solamente. Este módulo NO se ha aplicado. No comparte backend,
estado ni recursos Terraform con el servicio ECS. No ejecutar apply sin autorizar
la publicación de artefactos y la creación de los recursos nuevos de la prueba.

## Configuración concreta

- Cuenta 646941583111, us-east-1; perfil josezambrana.
- Nombre citas-ms-serverless-t04, 6144 MB, concurrencia máxima 1.
- Sin concurrencia aprovisionada, GPU, VPC, cambios de dominio o integración web.
- Rol exclusivo: GetObject del tarball exacto, lectura del repositorio ECR citas-api
  y escritura en el grupo de logs de la prueba (retención 3 días).
- Usa el bucket privado existente, en un prefijo experimental distinto de releases/.
- El modelo, la configuración y el endpoint son nuevos; ECS sigue atendiendo tráfico.

## Preparación comprobable

Desde la raíz, construir Dockerfile.ms para linux/amd64 con etiqueta
citas-science:t04-amd64 y luego Dockerfile.serverless-ms como
citas-serverless-ms:t04-local. No publicar la variante ARM64 de validación local.

Empaquetar con `PYTHONPATH=. python -m scripts.empaquetar_serverless_ms --output RUTA/model.tar.gz`.
El script verifica todos los SHA-256 de config/ms_release.json; no modifica pesos,
no entrena y no sube datos. El bundle incluye solo los diez archivos permitidos y
release.json, con archivos regulares y metadatos deterministas. El corpus público
preparado está en la imagen, sin anotaciones TRAIN/Gold.

## Después de autorizar la prueba AWS

1. Publicar la imagen AMD64 con una etiqueta nueva t04-serverless-ms en el ECR
   existente. Obtener su digest del registro. El ID Docker local NO es ese digest.
2. Subir el tarball verificado a la clave model_key de main.tf, privado y cifrado
   AES256. Comprobar previamente que la clave no existe; no reemplazar objetos.
   Registrar el VersionId nuevo para poder retirar solo esa versión al limpiar.
3. Ejecutar init en ESTE directorio y generar un plan con image_uri fijada por
   digest ECR. Revisar que solo haya seis creaciones (rol, política inline, logs,
   modelo, configuración, endpoint), sin cambios del servicio actual.
4. Aplicar únicamente el plan revisado de este módulo aislado. Si el endpoint no
   llega a InService, registrar FailureReason y logs; no lanzar inferencias ni
   sustituir automáticamente por instancias permanentes.
5. Desde la raíz ejecutar el comprobador acotado:

   `python scripts/probar_serverless_ms.py --endpoint citas-ms-serverless-t04 --profile josezambrana --region us-east-1 --include-long --output RUTA/reporte_aws.json`

   Máximo seis llamadas, seriales, sin reintentos automáticos; se detiene al primer
   error. Son dos sintéticas, tres del artículo público W05-0821 y una de D15-1167.
   El script verifica referencia sintética y pertenencia de los textos al artículo.
6. Recoger OverheadLatency, ModelLatency, ModelSetupTime, MemoryUtilization y errores
   en CloudWatch para AllTraffic. La primera llamada no demuestra por sí sola frío;
   correlacionar métricas y logs de arranque. Las repetidas tampoco garantizan que
   se reutilice un proceso. No activar provisioned concurrency para esta medición.
7. Registrar memoria, carga, compatibilidad, latencia, costo y decisión. Si 6 GB no
   bastan o la carga/inferencia supera límites, conservar M/S en ECS y documentar
   no viable o evidencia insuficiente, sin declarar una migración realizada.
8. Destruir SOLO los recursos de este módulo con su propio estado. Retirar únicamente
   la etiqueta ECR nueva y la versión S3 recién creada; el bucket tiene versionado,
   por lo que un delete marker no elimina los bytes de versiones anteriores.
   No borrar el bucket, el repositorio, releases/ ni el servicio ECS.

## Límites y costo

AWS documenta hasta 6 GB de RAM, 5 GB de disco temporal e imagen de hasta 10 GB.
Descarga + respuesta /ping deben completarse en 3 minutos; /invocations tiene
límite de 60 segundos y los payloads de 4 MB. El frontend/proxy actual vence antes;
esta prueba usa SageMaker Runtime directamente y no modifica ese límite público.

Tarifa consultada mediante AWS Pricing GetProducts para us-east-1: 6 GB a
US$0,00012/s (efectiva 1-nov-2026). Seis respuestas de 60 s equivalen a US$0,0432
de duración, antes de considerar frío/carga, datos y servicios auxiliares.
Presupuesto total propuesto: US$1 para la prueba, NO un tope automático de AWS.
Incluir S3, ECR y logs, mantener solo la prueba y limpiar al terminar. El costo
actual de ECS continúa y no debe presentarse como ahorro de esta evaluación.

Fuentes oficiales:
- https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints-invoke.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints-monitoring.html
- https://aws.amazon.com/sagemaker/ai/pricing/
