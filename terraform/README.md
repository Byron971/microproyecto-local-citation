# Despliegue del API en ECS Fargate

Terraform administra VPC, dos subredes públicas, security groups, ECS, ALB interno,
API Gateway HTTP API, logs con retención de 14 días, S3 privado y CloudFront. Puede crear roles IAM; no crea bucket de estado ni ECR.
El contenedor usa CPU x86, incluye el modelo y sirve también el tablero.

## Requisitos

- Terraform >= 1.10 y < 2.0 (configuración validada con 1.10.5), AWS CLI, Docker y curl.
- Sesión AWS vigente, por ejemplo `AWS_PROFILE=maia`, región `us-east-1`.
- Cuenta personal: `ecs_role_name = ""` (predeterminado) crea un rol de ejecución
  con permisos ECR/logs y otro de tarea sin permisos AWS adicionales. Quien aplica
  necesita permisos para administrar esos roles y `iam:PassRole`.
- Learner Lab: `ecs_role_name = "LabRole"` reutiliza el rol existente para ejecución
  y tarea, sin crear ni modificar IAM. Debe permitir ECS Tasks, ECR/logs y los
  secretos SSM/KMS configurados; quien aplica necesita poder pasarlo a ECS.
- Si ya existe `terraform.tfvars`, cambia `ecs_role_name` según la cuenta. No es
  necesario borrar el estado ni reinicializar el backend por cambiar los roles.
- Confirmar permisos del lab para VPC Link, ALB, ECS y SSM. Comprobar
  separadamente si los servicios continúan al cerrar la sesión del lab.

## Despliegue desde cero

Sigue los [pasos del README principal](../README.md#despliegue-en-aws-con-terraform).
`make init` prepara bucket/ECR y ejecuta `terraform init` con el backend S3.
Después de publicar la imagen con `make login`, `make build` y `make push`:

```sh
terraform -chdir=terraform plan
terraform -chdir=terraform apply
make publish-frontend
terraform -chdir=terraform output -raw frontend_url
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

## Un único estado para API y UI

El directorio `terraform/` administra toda la infraestructura. La URL del API
para el build se obtiene de sus outputs; CORS incluye automáticamente CloudFront.
`api_url` es el API y `frontend_url` es la aplicación React. `apply` crea recursos;
`make publish-frontend` compila y publica el contenido de la UI.

Si solo desplegaste el API, conserva su backend y ejecuta `plan`/`apply`: se
agregan los recursos web manteniendo las direcciones de los recursos existentes.
Si llegaste a aplicar el antiguo stack `terraform/frontend/`, sus recursos deben
transferirse al estado principal antes de aplicar esta versión. Conserva una
copia de ambos estados y evita que dos estados administren los mismos recursos;
no borres el estado anterior ni intentes crearlos de nuevo.

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
- CloudFront se agrega automáticamente a CORS; `cors_allowed_origins` permite
  añadir otros orígenes. El frontend se publica en S3 y accede directamente al API.
- `app_environment` permite configuración y `app_secrets` ARN de parámetros SSM
  existentes. No guardar valores secretos en Terraform. APP_ENV y APP_HOST se
  fijan a production y 0.0.0.0. El API actual todavía no consume estas variables.
- Si Terraform crea los roles, concede al rol de ejecución `ssm:GetParameters`
  solo sobre `app_secrets`. Para claves KMS propias, indica `secrets_kms_key_arns`
  y permite el acceso del rol en la política de la clave. Los roles existentes
  conservan sus permisos; Terraform no los amplía.
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

- **deploy-api.yml:** en PR comprueba el build sin credenciales. Al integrar
  cambios del API en `main`, publica la imagen con el SHA corto, actualiza SSM y
  aplica Terraform. Después comprueba la revisión de ECS, el tablero, el estado
  del modelo y una recomendación. Si falla, intenta restaurar el tag anterior en
  SSM; revisar ECS y ejecutar un plan antes de reintentar.
- **terraform.yml:** comprueba formato y validez sin credenciales. En PRs del
  mismo repositorio publica el plan como comentario si la sesión está vigente;
  sin credenciales o desde forks se omite el plan. Los errores reales del plan
  fallan el job. En `main`, aplica y comprueba el despliegue.

Ambos permiten ejecución manual desde **Actions → Run workflow**, seleccionando
`main`. Comparten `deploy-aws` y no cancelan el despliegue en curso. La comprobación
HTTP se omite si `desired_count=0`. Los runners usan los valores versionados;
no leen tu archivo local `terraform.tfvars`. Configura la variable de repositorio
`ECS_ROLE_NAME=LabRole` para el lab; vacía u omitida crea los roles en la cuenta
personal.

Configura una regla de protección de `main` que exija PR revisado. El diseño usa
secrets temporales de Learner Lab y omite OIDC y environments; esta diferencia
respecto al requisito original de #137 debe quedar aceptada por el equipo.
La ejecución real en GitHub/AWS y la prueba de rollback siguen pendientes; la
validación local no demuestra que el laboratorio permita todos los servicios.

## Apagar y eliminar

Definir `desired_count=0` en tfvars y ejecutar `terraform -chdir=terraform apply` detiene las tareas;
la URL deja de servir el API y otros recursos pueden seguir generando cargos.
Para eliminar toda la infraestructura, vacía primero el bucket web:

```sh
FRONTEND_BUCKET=$(terraform -chdir=terraform output -raw frontend_bucket)
aws s3 rm "s3://$FRONTEND_BUCKET" --recursive
terraform -chdir=terraform destroy
```

Los roles creados por Terraform se eliminan; el rol existente se conserva.
Bucket, historial del estado, imágenes ECR y tag SSM sobreviven al destroy.
Su eliminación es independiente: borrar el bucket elimina el estado y borrar
ECR elimina las imágenes necesarias para redeploy y rollback. No eliminarlos
antes de terminar el destroy.

Referencias IAM: [rol de ejecución ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html)
y [rol de tarea ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html).
