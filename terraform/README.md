# Despliegue del API en ECS Fargate

Terraform administra VPC, dos subredes públicas, security groups, ECS, ALB interno,
API Gateway HTTP API, logs con retención de 14 días, y ahora el hosting web privado
(S3 + CloudFront). No crea IAM, bucket del estado ni ECR.
El contenedor usa CPU x86, incluye el modelo y sirve también el tablero.

## Requisitos

- Terraform >= 1.10 y < 2.0 (configuración validada con 1.10.5), AWS CLI, Docker y curl.
- Sesión AWS vigente, por ejemplo `AWS_PROFILE=maia`, región `us-east-1`.
- Rol existente `LabRole` con confianza para ECS Tasks y permisos para ECR,
  CloudWatch Logs y, si se utilizan, los secretos SSM/KMS. Quien aplica debe
  poder pasar ese rol a ECS. Terraform no modifica sus permisos.
- Confirmar permisos del lab para VPC Link, ALB, ECS y SSM. Comprobar
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
CI permite que init agregue checksums de su plataforma; no usa `-upgrade` y
conserva la versión fijada y la verificación del proveedor.

## Continuar después del error de Cloud Map

Learner Lab rechazó `servicediscovery:CreatePrivateDnsNamespace`. La integración
usa ahora un ALB interno y conserva el VPC Link existente. No ejecutar destroy,
borrar el estado ni volver a crear la imagen por este cambio de infraestructura.
Con credenciales vigentes, desde la raíz:

```sh
export AWS_PROFILE=maia
terraform -chdir=terraform plan
terraform -chdir=terraform apply
```

El plan debe agregar ALB, target group, listener y reglas de seguridad, además
de completar los recursos pendientes. Revisar cualquier reemplazo inesperado
antes de confirmar. El rol necesita permisos de Elastic Load Balancing; esta
configuración aún debe comprobarse en el laboratorio.

## Configuración

- Inicio: `task_cpu=512`, `task_memory=1024`, una tarea. Validación de las
  combinaciones CPU/memoria permitidas por Fargate.
- Salud: `/api/estado`, startPeriod 120 s y gracia 180 s. Cambiar a
  `/api/salud/lista` cuando exista. El health check usa Python de la imagen.
- Flujo: API Gateway → VPC Link → ALB interno (80) → ECS (8000).
  El ALB solo acepta al security group del VPC Link y ECS solo al del ALB.
  La IP pública de la tarea permite salida a ECR/logs; no permite entrada
  directa desde internet. El ALB comprueba la misma ruta de salud del contenedor.
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
costo estimado para el issue #116. La estimación anterior de USD 23/mes para
0.5 vCPU/1 GB excluía el ALB. Ahora se agregan sus horas y consumo LCU;
actualizar la estimación antes de usarla como costo total.

Antes de dar por cumplido el rollback, probar una revisión no saludable y
comprobar recuperación de la revisión anterior. Una subida fallida puede dejar
SSM apuntando a la imagen defectuosa aunque ECS vuelva a la anterior: restaurar
el tag anterior en SSM y ejecutar apply antes de otro cambio de infraestructura.

## GitHub Actions

Primero completa el despliegue local. En GitHub abre **Settings → Secrets and
variables → Actions → New repository secret** y agrega las credenciales vigentes:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` (obligatorio para Learner Lab)

Renueva los tres al cambiar de sesión del lab. No los escribas en el código.
Los workflows usan `us-east-1`, `maia2026-grupo19` y `citas-api`, igual que la
configuración inicial local. Si cambias esos valores, actualiza ambos workflows.

- **deploy-api.yml:** en PR/push valida el build sin credenciales y **no
  publica**. Para publicar desde `main`, usa **Actions → Run workflow** y
  escribe `DEPLOY` en `confirm_deploy`. Valida API y rollback.
- **terraform.yml:** valida formato y configuración sin credenciales. En PR
  puede generar un plan con sesión AWS vigente. **Nunca aplica en push**:
  selecciona `main` y escribe `DEPLOY` en `confirm_apply`.
- **publicar-frontend.yml:** no se ejecuta en push. Solo después de crear los
  recursos web autorizados con un plan/revisión previa, selecciona `main` y
  escribe `PUBLISH`. Usa `make publish-frontend`, que copia primero assets con
  hash, luego HTML, e invalida `/index.html` en CloudFront.

Los trabajos que modifican AWS comparten `deploy-aws` y no cancelan un
despliegue en curso. **No ejecutar** Terraform apply ni publicación sin revisar
costos y permisos de la cuenta. CloudFront y S3 generan cargos; Learner Lab
puede no permitir su creación. La validación `terraform validate` por sí sola
no demuestra disponibilidad pública ni permisos efectivos. La comprobación
HTTP se omite si `desired_count=0`. Los runners usan los valores versionados;
no leen tu archivo local `terraform.tfvars`.

Configura una regla de protección de `main` que exija PR revisado. El diseño usa
secrets temporales de Learner Lab y omite OIDC y environments; esta diferencia
respecto al requisito original de #137 debe quedar aceptada por el equipo.
La ejecución real en GitHub/AWS y la prueba de rollback siguen pendientes; la
validación local no demuestra que el laboratorio permita todos los servicios.

## Publicar el frontend React (requiere autorización explícita)

La infraestructura React añade un bucket S3 **privado** protegido por OAC de
CloudFront, una distribución HTTPS y rutas SPA. La API habilita CORS solo para
el origen CloudFront generado y los orígenes HTTPS locales/externos
declarados explícitamente en `cors_allowed_origins` (por defecto ninguno
adicional). Los outputs nuevos son `frontend_url`, `frontend_bucket`,
`distribution_id` y `api_base_url`.

Antes de aplicar, ejecutar `terraform -chdir=terraform plan` con credenciales
válidas y **revisar los cambios en API Gateway**: hay migración de rutas ANY
a GET/POST mediante bloques `moved`. No perder ni reemplazar el estado S3.
Si el plan propone destruir recursos ajenos o reemplazos inesperados, detenerse
y revisar. Se requiere permiso AWS para CloudFront/S3 y un presupuesto
aprobado.

Una vez exista el stack aprobado, construir y publicar desde el comando
`make publish-frontend` o mediante el workflow manual con `PUBLISH`.
El build inyecta únicamente la URL pública de la API en
`VITE_API_BASE_URL`; **nunca secretos**. Comprobar externamente HTTPS,
recarga en `/fragmentos` y `/datos`, API, CORS y casos de error. La
publicación aún está **pendiente** hasta ejecutar este smoke real.

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

Dominio del frontend: `proyectocitas-grupo19.click`.
Dominio del API: `api.proyectocitas-grupo19.click`.
