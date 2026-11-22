# Prueba aislada T04: SageMaker Serverless M/S

Estado real: modelo y configuración registrados; endpoint rechazado por cuota
de memoria de la cuenta (3072 MB frente a los 6144 MB solicitados). No hay
endpoint activo ni inferencias ejecutadas. T04 sigue pendiente, no se ha
decidido viabilidad técnica ni migración. El usuario abrirá el caso de soporte.

La imagen OCI inicial fue rechazada. La variante Docker V2, con idénticas capas
y configuración, fue aceptada al registrar el modelo. Ver comandos
builder-compatible y builder-compatible-result en make/image-builder.mk.

## Recursos y estado

- Cuenta 646941583111, us-east-1, perfil josezambrana.
- Endpoint previsto citas-ms-serverless-t04, 6144 MB, concurrencia máxima 1.
- Sin capacidad aprovisionada ni integración pública. ECS conserva su tarea y capacidad.
- Repositorio ECR propio de T04; imágenes publicadas desde EC2.
- Paquete S3 gestionado por terraform/model_artifact, con estado propio en S3.
  Este módulo solo consulta el paquete como dato.
- Este módulo usa estado local separado del despliegue de producción. Conservarlo.
- Rol, política, grupo de logs (retención 3 días), modelo y configuración preparados.

## Reanudar después de confirmar la cuota de 6144 MB

```sh
make ms-serverless-enable AWS_PROFILE=josezambrana
make ms-serverless-plan AWS_PROFILE=josezambrana
make ms-serverless-apply AWS_PROFILE=josezambrana
make ms-serverless-observe AWS_PROFILE=josezambrana
```

Enable verifica digest Docker V2, arquitectura y versión/metadata del paquete.
Aplicar solo planes validados por el guard de alcance. Cuando el endpoint esté
InService, ejecutar ms-serverless-test: máximo seis solicitudes seriales, sin
reintentos automáticos y con contador persistente. Recoger métricas y logs.

El primer request no demuestra arranque frío: correlacionar OverheadLatency y
ModelSetupTime. MemoryUtilization se consulta en /aws/sagemaker/Endpoints.
Las latencias de cliente incluyen red y no constituyen benchmark estadístico.

## Retiro

ms-serverless-destroy-plan y ms-serverless-destroy retiran TODO este estado,
incluido el ECR temporal y sus imágenes. No usarlos para retirar solo el endpoint
si deben conservarse las imágenes publicadas. El paquete y su estado S3 pertenecen
a otro módulo y no se eliminan mediante este estado. No tocar ECS, bucket ni releases/.

AWS limita descarga y /ping a tres minutos; /invocations a sesenta segundos y
payloads a 4 MB. El presupuesto operativo previsto es US$1 para la prueba,
no un límite duro de facturación AWS. No crear capacidad permanente como sustitución.
