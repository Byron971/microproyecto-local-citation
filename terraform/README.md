# Despliegue del API en ECS Fargate

Terraform administra VPC, dos subredes públicas, security groups, ECS, Cloud Map,
API Gateway HTTP API y logs con retención de 14 días. No crea IAM, bucket ni ECR.
El contenedor usa CPU x86, incluye el modelo y sirve también el tablero.

## Requisitos

- Terraform >= 1.10 y < 2.0 (configuración validada con 1.10.5), AWS CLI, Docker y curl.
- Sesión AWS vigente, por ejemplo `AWS_PROFILE=maia`, región `us-east-1`.
- Rol existente `LabRole` con confianza para ECS Tasks y permisos para ECR,
  CloudWatch Logs y, si se utilizan, los secretos SSM/KMS. Quien aplica debe
  poder pasar ese rol a ECS. Terraform no modifica sus permisos.
- Confirmar permisos del lab para VPC Link, Cloud Map, ECS y SSM. Comprobar
  separadamente si los servicios continúan al cerrar la sesión del lab.

## Despliegue desde cero

Sigue los [pasos del README principal](../README.md#despliegue-en-aws-con-terraform).
`make init` prepara bucket/ECR y ejecuta `terraform init` con el backend S3.
Después de publicar la imagen con `make login`, `make build` y `make push`:

```sh
terraform -chdir=terraform plan
terraform -chdir=terraform apply
terraform -chdir=terraform output -raw api_url
```

El bucket y ECR existentes no se modifican: comprobar su configuración antes de
usarlos. Terraform consulta ECR y el tag SSM `/<project_name>/api/image_tag`,
creado por `make push`; no administra esos recursos.

`TF_STATE_BUCKET`, `TF_STATE_KEY` y `AWS_REGION` configuran el backend al ejecutar
`make init`. Si cambias proyecto, región o repositorio, usa los mismos valores en
el Makefile y `terraform.tfvars`, también para los comandos directos de Terraform.
No versionar tfvars, planes, estado ni credenciales. Conservar el lockfile en Git.

## Configuración

- Inicio: `task_cpu=512`, `task_memory=1024`, una tarea. Validación de las
  combinaciones CPU/memoria permitidas por Fargate.
- Salud: `/api/estado`, startPeriod 120 s y gracia 180 s. Cambiar a
  `/api/salud/lista` cuando exista. El health check usa Python de la imagen.
- El puerto 8000 solo admite tráfico desde VPC Link. La IP pública permite
  salida a ECR/logs; no permite entrada directa desde internet.
- El circuit breaker activa rollback. En el primer despliegue no existe una
  revisión previa sana a la que volver. Comprobar en ECS que la
  revisión estable sea la esperada; estabilidad por sí sola no prueba éxito.
- `use_fargate_spot=true` reduce costo con riesgo de interrupción.
- `app_environment` permite configuración y `app_secrets` ARN de parámetros SSM
  existentes. No guardar valores secretos en Terraform. APP_ENV y APP_HOST se
  fijan a production y 0.0.0.0. El API actual todavía no consume estas variables.
- Dominio opcional: definir `custom_domain_name` y `certificate_arn` (ACM en la
  misma región). Crear DNS por separado con el destino del output
  `custom_domain_target`. No se administra Route 53.
- Modelos futuros: ajustar CPU, memoria y tiempos de salud. Incorporar pesos en
  build y usar PyTorch CPU. API Gateway limita la integración a 30 segundos.
- El corpus Top-3 no está incluido: sus rutas pueden responder 503.

## Verificación después del despliegue

Abrir la URL pública y comprobar `/api/estado` y `/`. Verificar también
`/static/top3.html` y una petición válida a `/api/recomendar`. Cuando se integre
el script de smoke del API, sustituir estas comprobaciones por ese script.
Registrar URL, latencia externa de recomendaciones, CPU/memoria observadas y
costo estimado para el issue #116. La estimación del diseño es USD 23/mes para
0.5 vCPU/1 GB; no es una medición ni una cotización actualizada.

Antes de dar por cumplido el rollback, probar una revisión no saludable y
comprobar recuperación de la revisión anterior. Una subida fallida puede dejar
SSM apuntando a la imagen defectuosa aunque ECS vuelva a la anterior: restaurar
el tag anterior en SSM y ejecutar apply antes de otro cambio de infraestructura.

## GitHub Actions (siguiente etapa)

Los workflows todavía no se incluyen en esta implementación de Terraform.
Necesitarán los secrets AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY y
AWS_SESSION_TOKEN para Learner Lab. Las credenciales temporales deben renovarse
tanto localmente como en CI. El diseño omite OIDC y environments por las
restricciones del lab; es una desviación del requisito original del issue #137.
Los despliegues deben limitarse a main, con PR revisado y concurrencia deploy-aws.

## Apagar y eliminar

Definir `desired_count=0` en tfvars y ejecutar `terraform -chdir=terraform apply` detiene las tareas;
la URL deja de servir el API y otros recursos pueden seguir generando cargos.
Para eliminar la infraestructura del servicio:

```sh
terraform -chdir=terraform destroy
```

Bucket, historial del estado, imágenes ECR y tag SSM sobreviven al destroy.
Su eliminación es independiente: borrar el bucket elimina el estado y borrar
ECR elimina las imágenes necesarias para redeploy y rollback. No eliminarlos
antes de terminar el destroy.
