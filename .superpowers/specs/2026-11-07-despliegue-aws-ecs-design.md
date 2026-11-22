# PRD: despliegue del API en AWS (ECS + API Gateway + Terraform)

Issues: [#137](https://github.com/Byron971/microproyecto-local-citation/issues/137)
(IaC y GitHub Actions) y la parte de URL pública de
[#116](https://github.com/Byron971/microproyecto-local-citation/issues/116).
Responsable: José.

## 0. Estado al 2026-11-08

**Implementación disponible; verificación real pendiente.**

- Rama publicada: `feature/despliegue-aws-ecs-137`.
- `af1e061`: infraestructura Terraform, Makefile y guía de despliegue.
- `803ce66`: workflows, sesión AWS compartida, controles de despliegue y pruebas.
- Este plan es un archivo local sin seguimiento en Git; no está incluido en
  esos commits ni en el push. No se ha creado un PR desde el asistente.

**Comprobado:**

- Terraform: `fmt -check` y `validate` con 1.10.5.
- Workflows: `actionlint`; scripts shell: `shellcheck`.
- Cuatro pruebas locales sin AWS: restauración del tag ante fallo de plan,
  apply o rollback, despliegue correcto y reintentos de la comprobación HTTP.
- Registro aportado por el usuario: `make init` completó la inicialización
  del backend y del proveedor; `make build` construyó la imagen.

**Pendiente para dar por terminado #137 y la parte de #116:**

- [ ] Publicar la imagen en ECR con credenciales vigentes y completar apply.
- [ ] Comprobar en AWS salud, tablero, recomendaciones y revisión/tag de ECS.
- [ ] Configurar secrets del repositorio y ejecutar ambos workflows en GitHub.
- [ ] Verificar comentarios del plan, omisión sin credenciales y rechazo de
      despliegues desde ramas distintas de `main`.
- [ ] Confirmar protección de `main` y registrar la aceptación de la desviación
      respecto a OIDC y environments del requisito original.
- [ ] Probar rollback real desde una revisión sana y comprobar la URL.
- [ ] Confirmar comportamiento al cerrar la sesión de Learner Lab.
- [ ] Registrar URL pública, CPU/memoria, latencia externa y costo estimado.
- [ ] Verificar dominio opcional, redimensionamiento e idempotencia en AWS.

La validación local no demuestra que la cuenta permita todos los recursos ni
que el servicio ya esté desplegado. El último push de imagen compartido falló
por una denegación `voc-cancel-cred`; se indicó renovar la sesión y ejecutar
`make login` antes de repetir `make push`, sin confirmar todavía su resolución.

## 1. Intención

El objetivo es publicar el API (FastAPI, `src/app/main.py`) y el tablero en
ECS Fargate mediante una URL pública. La guía anterior de EC2 fue reemplazada
por el flujo con Terraform; la disponibilidad en AWS sigue pendiente de verificar.

- **Criterio de "desplegado":** la URL responde.
- **Tablero incluido:** el contenedor del API también sirve el tablero (`/`,
  `/static`, `/static/top3.html`), así que con desplegar ese contenedor la
  interfaz también queda en línea.

Es un proyecto académico, así que se prioriza que sea **simple, barato y
reproducible** antes que robusto como un sistema de producción.

El #137 pide OIDC y entornos protegidos. El equipo decidió **no usar ninguno de
los dos**: no se crea el proveedor OIDC ni un environment de GitHub. El README
deja escrita la justificación (§5.6).

## 2. Objetivos

1. Un directorio `terraform/` que crea y gestiona la infraestructura del
   servicio. El bucket del estado y ECR se preparan con `make init` y quedan
   fuera del estado de Terraform.
2. El API corre en **ECS Fargate**, con **API Gateway** al frente y la URL por
   defecto de API Gateway como URL pública.
3. La infraestructura queda preparada para un **dominio personalizado**, pero
   desactivada por ahora.
4. `terraform apply` se puede ejecutar **localmente** y **desde GitHub
   Actions** cuando cambia el código de Terraform.
5. Un workflow de GitHub que **construye y publica la imagen en ECR y la
   despliega en ECS** cuando cambia el código del API.
6. **El modelo corre dentro del mismo contenedor del API.** No hay servicio de
   inferencia aparte (ni SageMaker, ni Lambda, ni un segundo contenedor). La
   infraestructura debe permitir que el modelo crezca, por ejemplo de TF-IDF a
   SciBERT/SPECTER, cambiando solo variables de tamaño.

## 3. Fuera de alcance

- **Crear el bucket del estado y el repositorio ECR desde Terraform.** Los
  crea `make init` con AWS CLI (§4.1), y Terraform solo los usa.
- **OIDC entre GitHub y AWS.** No se crea el proveedor ni los roles para
  GitHub. CI usa credenciales guardadas como secrets (§5.6).
- Environments de GitHub y aprobaciones manuales de despliegue.
- Varios entornos (dev/staging/prod): hay uno solo.
- Alta disponibilidad, autoescalado y varias tareas.
- Activar el dominio personalizado (solo se deja preparado).
- GPU. Toda la inferencia corre en CPU.
- **Integrar en el código los modelos densos (SciBERT/SPECTER, #103) y la
  clasificación de 9 funciones (#107).**
  - Este despliegue sirve lo que hay en `main`: el wheel `modelo-citas`
    (TF-IDF + reordenador lineal) y Top-3 con BM25.
  - Cuando esos modelos se integren al API, entran en la misma imagen y el
    mismo contenedor. Desde la infraestructura solo se suben las variables de
    tamaño (§5.7).
- Desplegar el contenedor nginx (`dashboard`) de `docker-compose.yml`, porque
  el API ya sirve el tablero.
- Autenticación de usuarios del API y WAF.

## 4. Restricciones y contexto

### 4.1 Cuenta AWS y estado de Terraform

- **Cuenta:** la del perfil `maia` (`211125443585`), en la región
  `us-east-1`, la misma del bucket del wheel del modelo.
  - Las credenciales de ese perfil asumen el rol `voclabs`, que es el de
    **AWS Academy Learner Lab**. Por eso Terraform **no crea roles IAM**: usa
    uno que ya existe en la cuenta (§5.2) y que se pasa por variable.
  - Si el despliegue se mueve a otra cuenta, basta con cambiar las
    credenciales y esa variable.
- Nada del código asume un account ID fijo: se obtiene con
  `data "aws_caller_identity"`.
- **Bucket del estado:** `maia2026-grupo19`, con versionado, cifrado SSE-S3 y
  bloqueo de acceso público.
  - Terraform no lo crea ni lo gestiona; solo lo usa como backend.
  - Key del estado: `citas-api/terraform.tfstate`.
- **Repositorio ECR:** `citas-api`, con *scan on push* y una lifecycle policy
  que conserva las últimas 5 imágenes. Terraform lo lee con
  `data "aws_ecr_repository"`.
- **`make init`** crea el bucket y el repositorio si no existen, y no toca
  nada si ya están (es idempotente para esos recursos). Después ejecuta
  `terraform init` para preparar el proveedor y el backend S3.
  No verifica ni corrige la configuración de recursos existentes: antes del
  despliegue se comprueban región, versionado, cifrado y bloqueo público del
  bucket, y escaneo y lifecycle policy de ECR. Un error de permisos no debe
  interpretarse como confirmación de que un recurso no existe.
- El bucket y ECR sobreviven a `terraform destroy`. El README debe explicar
  que su limpieza es independiente y que borrar el bucket elimina el estado
  y borrar ECR elimina las imágenes disponibles para despliegue y rollback.

### 4.2 Costo

Se minimiza el costo fijo:

- sin NAT Gateway,
- sin ALB,
- una sola tarea Fargate,
- logs con retención corta.

El equipo no necesita aprobar el costo, solo conocer un aproximado.

**Estimado del diseño del 2026-11-07, sin actualización de tarifas ni
medición de facturación** (us-east-1, 730 h, precios on-demand de Fargate x86:
USD 0.04048 por vCPU-hora y USD 0.004445 por GB-hora):

| Concepto | TF-IDF + BM25 (0.5 vCPU / 1 GB) | Modelo mediano (1 vCPU / 2 GB) | SciBERT/SPECTER en CPU (2 vCPU / 4 GB) |
| --- | --- | --- | --- |
| Fargate | ~USD 18 | ~USD 36 | ~USD 72 |
| IPv4 pública de la tarea | ~USD 3.6 | ~USD 3.6 | ~USD 3.6 |
| API Gateway HTTP API (USD 1 por millón de peticiones) | < USD 1 | < USD 1 | < USD 1 |
| ECR (imagen actual de 2.35 GB; ~3–4 GB con PyTorch, se conservan 5) | ~USD 1 | ~USD 1.5 | ~USD 2 |
| CloudWatch Logs, Cloud Map, S3 del estado, SSM | < USD 1 | < USD 1 | < USD 1 |
| **Total aproximado** | **~USD 23** | **~USD 42** | **~USD 79** |

- VPC Link (HTTP API), VPC, subredes e Internet Gateway no tienen costo.
- La transferencia de datos de salida es despreciable con tráfico académico.
- *Opción para bajar el costo un ~70 %:* Fargate Spot (variable
  `use_fargate_spot`, apagada por defecto). La tarea puede ser interrumpida y
  reemplazada, con un par de minutos sin servicio, así que no conviene durante
  la franja de evaluación.
- En Learner Lab este costo se descuenta del crédito del lab.

### 4.3 Base de código

- **Base de implementación:** `main` en `45ec752`; el trabajo continúa en
  `feature/despliegue-aws-ecs-137`. Antes de integrar, revisar cambios recientes
  de `main` y compatibilidad con los PRs #130/#131.
  - El checkout implementado usa `/api/estado` como health check.
  - Si se integra `/api/salud/lista`, cambiar `health_check_path` explícitamente;
    no hay detección automática de rutas.
  - CI tiene su comprobación en `scripts/ci/smoke-api.py`: verifica `/`,
    `/static/top3.html`, modelo listo y recomendaciones. Revisar su compatibilidad
    con `scripts/smoke_despliegue.py` cuando se integre ese trabajo.
- **Modelo a desplegar (revisado el 2026-11-07):** el wheel `modelo-citas`
  **0.2.0** (TF-IDF + reordenador lineal). No hay una versión más nueva
  publicada.
  - SciBERT/SPECTER solo existen como experimentación (PRs #147 y #144).
  - El clasificador de 9 funciones (#103) todavía no tiene modelo publicado.
  - Cuando aparezca una versión nueva del wheel, desplegarla es subir la URL en
    `pyproject.toml`/`uv.lock` y hacer merge. El workflow se encarga del resto.
- **Dockerfile:** el que ya existe (Python 3.14, `uvicorn` en el puerto 8000).
  El wheel del modelo se descarga de un bucket S3 público, así que el build no
  necesita credenciales.
- **Makefile:** ya existe en la raíz del repo con estos targets:
  - `make init` prepara bucket/ECR e inicializa Terraform (§4.1);
  - `make login` verifica las credenciales y hace login en ECR;
  - `make build` construye para `linux/amd64` con el SHA corto como tag;
  - `make push` sube la imagen a ECR y escribe el tag en SSM.

  Se toman `AWS_PROFILE`, `AWS_REGION`, `ECR_REPOSITORY` (por defecto
  `citas-api`), `TF_STATE_BUCKET` (por defecto `maia2026-grupo19`) e
  `IMAGE_TAG` del entorno. También admite `PROJECT_NAME`, `TF_STATE_KEY` y
  `TERRAFORM`. El flujo local se describe en §5.5.
- **Corpus Top-3:** el archivo de `/api/top3-corpus/*`
  (`proyecto_de_grado/artifacts/top3_s2/casos_train.json`) no está versionado,
  así que en el despliegue esas rutas devuelven 503.
  - `POST /api/top3-fragmentos`, con fragmentos enviados por formulario, no
    depende de él.
  - Incluir el corpus queda fuera de este trabajo.
- **Mediciones de la imagen actual** (2026-11-07, `citas-api:0.2.0-amd64`,
  emulada en Apple Silicon):
  - imagen de **2.35 GB**;
  - `/api/estado` responde 200 a los **~81 s** del arranque. Con emulación es
    más lento; en Fargate x86 nativo se espera menos;
  - memoria de **~415 MiB** en reposo y **~435 MiB** después de varias
    recomendaciones, sin OOM;
  - `POST /api/recomendar` tarda **0.07–0.23 s** en local;
  - `/` responde 200.

  Con esto, **0.5 vCPU / 1 GB alcanza** con margen. El health check necesita
  un `startPeriod` de al menos 120 s, y la gracia del servicio al menos 180 s.
- **Commits:** se siguen las reglas de `CLAUDE.md` (una frase corta, sin
  atribución a Claude).

## 5. Decisiones

### 5.1 Decididas con el equipo

- ECS como plataforma del API, con API Gateway al frente.
- URL por defecto de API Gateway por ahora. El dominio personalizado queda
  para después.
- Terraform en `terraform/`, ejecutable en local y en CI. CI aplica cuando
  cambia el código de Terraform.
- Workflow que publica la imagen y despliega cuando cambia el código del API.
- Sin OIDC, sin environment de GitHub y sin aprobaciones manuales.
- El bucket del estado (`maia2026-grupo19`) y el repositorio ECR los crea
  `make init`, no Terraform.
- El modelo corre en el mismo contenedor del API.
- `make login`, `make build` y `make push` en un Makefile.

### 5.2 Arquitectura implementada (pendiente de validar en AWS)

```
Internet ──► API Gateway HTTP API (stage $default)
                 │  VPC Link
                 ▼
            Cloud Map (registro SRV del servicio)
                 │
                 ▼
     ECS Fargate (1 tarea, subred pública, IP pública)
                 │  egress a ECR / CloudWatch / SSM por internet
                 ▼
          CloudWatch Logs (retención 14 días)
```

- **Red:** una VPC propia con dos subredes públicas en dos AZ, un Internet
  Gateway y sin NAT. La tarea tiene IP pública para poder bajar la imagen y
  escribir logs.
- **ECR:** el repositorio `citas-api` que crea `make init`. Terraform solo lo
  lee con `data "aws_ecr_repository"`.
- **ECS:** un cluster, una *task definition* Fargate (`linux/amd64`) y un
  servicio con `desired_count = 1`.
  - Tamaño inicial: 0.5 vCPU / 1 GB, en las variables `task_cpu` y
    `task_memory`. Está confirmado por la medición de ~435 MiB (§4.3). El #116
    pide además documentar la latencia y la memoria en Fargate.
  - El servicio usa `health_check_grace_period_seconds` de al menos 180.
  - Health check del contenedor con un `startPeriod` de al menos 120 s, contra
    la ruta configurable `health_check_path`, por defecto `/api/estado`.
  - Despliegue con `deployment_circuit_breaker` y rollback activado, para que
    una imagen rota no deje el servicio caído.
- **Seguridad de red:** el security group de la tarea solo acepta el puerto
  8000 desde el security group del VPC Link. La tarea no queda expuesta
  directamente a internet.
- **API Gateway:** una HTTP API con las rutas `ANY /` y `ANY /{proxy+}`,
  integradas por VPC Link al servicio de Cloud Map. Stage `$default` con
  auto-deploy, para que no haya prefijo de stage que rompa las rutas
  `/static`.
  - Access logs a CloudWatch.
  - Throttling por defecto razonable, por ejemplo 20 rps con ráfagas de 40,
    para limitar el costo si alguien abusa de la URL.
  - El límite de 30 s de integración de API Gateway alcanza para los backends
    actuales, que responden en milisegundos.
- **IAM: Terraform no crea roles.**
  - El *execution role* y el *task role* de ECS son un rol que ya existe,
    referenciado con `data "aws_iam_role"`. Su nombre va en la variable
    `ecs_role_name`, que por defecto es `LabRole`, el rol de Learner Lab.
  - Es el mismo patrón que el proyecto `202611-grupo23-proyecto` del curso de
    nube.
- **Secretos y configuración:** las variables de runtime van como
  `environment` en la *task definition*. Hoy el API no necesita secretos.
  - Queda listo el mecanismo: una variable `app_secrets` (mapa nombre → ARN de
    un parámetro SSM `SecureString`) que se inyecta como `secrets` en el
    contenedor.
  - Nunca se escriben valores secretos en el código de Terraform ni en
    `tfvars` versionados.
- **Dominio personalizado:** variables `custom_domain_name` (vacía por
  defecto) y `certificate_arn`. Con `count` condicionado, se crean el
  `aws_apigatewayv2_domain_name` y el `api_mapping` solo si están definidas.
  Route 53 queda fuera por ahora.
- **Outputs:** `api_url`, `ecr_repository_url`, `cluster_name`,
  `service_name`, `task_definition_arn` y `custom_domain_target`.

### 5.3 Un solo stack en `terraform/`

Sin OIDC, y con el bucket y el ECR creados por `make init`, no hace falta un
stack de bootstrap. Todo vive en `terraform/`.

- **Backend S3** sobre el bucket existente `maia2026-grupo19`, con la key
  `citas-api/terraform.tfstate`, la región `us-east-1` y **bloqueo nativo de
  S3** (`use_lockfile = true`, Terraform ≥ 1.10), sin DynamoDB.
  - Los `apply` locales y los de CI comparten el mismo estado, y el bloqueo
    evita que choquen.
  - El backend es parcial: `make init` pasa `TF_STATE_BUCKET` y
    `AWS_REGION` con `-backend-config`, manteniendo la key indicada y
    `use_lockfile = true`. CI usa esos mismos valores. Así, sobrescribir las
    variables de `make init` no deja Terraform apuntando al bucket anterior.
  - Makefile exporta región, proyecto y repositorio como `TF_VAR_*` a sus
    subprocesos. Al ejecutar Terraform directamente, usar valores coherentes
    en `terraform.tfvars`: esas exportaciones no modifican la terminal padre.
    CI usa los defaults versionados; no lee el tfvars local. Cambiar nombres o
    región requiere alinear Makefile, variables y ambos workflows.
- `terraform.tfvars` está ignorado por git y se versiona un
  `terraform.tfvars.example`.
- **Primer despliegue:** configurar credenciales o perfil, copiar
  `terraform.tfvars.example`, ejecutar `make init`, `make login`, `make build`
  y `make push`, en ese orden. Después ejecutar `terraform -chdir=terraform plan`
  y `terraform -chdir=terraform apply`. No hace falta `-target`.
- **Versiones:** Terraform `>= 1.10.0, < 2.0.0`; provider AWS `5.100.0` con
  lockfile versionado. CI fija Terraform `1.14.8`. Se amplió la restricción
  inicial de 1.10.x para aceptar la instalación 1.14.8 del usuario.

### 5.4 Tag de imagen como fuente única de verdad

Para que un `terraform apply` no revierta una imagen recién desplegada:

1. Cada despliegue del API construye la imagen, la etiqueta con el **SHA
   corto del commit** y la sube a ECR.
2. Solo si la publicación terminó correctamente, escribe ese tag en el
   parámetro SSM `/<project_name>/api/image_tag` (por defecto
   `/citas-api/api/image_tag`), de tipo `String`, con
   `aws ssm put-parameter --overwrite`. El parámetro lo mantienen Makefile y
   CI; Terraform solo lo consulta, no lo crea ni lo gestiona.
3. Terraform lee el tag con `data "aws_ssm_parameter"` y arma la imagen de la
   *task definition* con él. Al cambiar el tag cambia la revisión, y ECS
   despliega la tarea nueva.

Cualquier `apply` usa el tag registrado en SSM. En CI, si falla el despliegue
del API y existía un tag anterior, se intenta restaurarlo. Esto no ejecuta un
rollback de Terraform: hay que revisar ECS y el siguiente plan. En el primer
despliegue no hay una revisión sana anterior a la que volver.

### 5.5 Despliegue local

El README contiene notas breves y bloques de comandos, sin guía de EC2 ni
secciones separadas de preparación de herramientas o credenciales.

- `make init`: prepara bucket/ECR y ejecuta `terraform init`; reemplaza el
  nombre anterior `make tf-init`.
- `make login`, `make build`, `make push`: autentican Docker, construyen para
  amd64 y publican imagen/tag.
- Se usan comandos directos: `terraform -chdir=terraform plan`, `apply`,
  `output -raw api_url` y `destroy`.
- `make deploy` permanece como atajo para login → build → push → apply, con
  inicialización previa. No espera estabilidad ni ejecuta smoke local.
- Los wrappers `tf-plan` y `tf-apply` permanecen disponibles, pero no son el
  flujo recomendado en el README.
- Se retiraron `make wait` y `make smoke`; las verificaciones automáticas se
  realizan en CI mediante scripts, sin targets equivalentes en Makefile.

### 5.6 Workflows de GitHub

Reglas comunes a los dos workflows:

- **Autenticación:** usan `aws-actions/configure-aws-credentials` con los
  secrets `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN`
  (este último es opcional y solo hace falta con credenciales temporales).
  - No se usa OIDC ni se crean roles para GitHub.
  - La acción compartida `.github/actions/aws-session/action.yml` configura
    la sesión y la comprueba con `aws sts get-caller-identity`. Si las credenciales
    faltan o vencieron, el workflow falla con un mensaje claro: "actualiza los
    secrets AWS_* del repositorio".
  - En Learner Lab las credenciales vencen con cada sesión, así que hay que
    renovarlas en GitHub antes de un despliegue desde CI. El camino local
    también requiere credenciales vigentes, pero no necesita copiarlas a
    GitHub.
- **Recursos base:** antes de habilitar despliegues en CI se ejecuta
  `make init` localmente y se completa el primer despliegue. Los workflows
  consumen bucket y ECR existentes; no ejecutan `make init`.
- **Quién configura:** los secrets los carga en GitHub alguien con permisos
  sobre el repo, y el README documenta cómo.
- **Justificación frente al #137:** sin OIDC, la defensa es que las
  credenciales son de corta duración (sesión de Learner Lab) y viven solo
  como secrets cifrados, nunca en el código. Así queda escrito en el README.
- **Protección:** no se usan environments de GitHub. Los jobs que aplican o
  publican solo corren en push a `main` o con `workflow_dispatch` sobre
  `main`. La regla de PR revisado debe configurarse en GitHub; el YAML no la
  crea ni demuestra que esté activa.
- **Concurrencia:** comparten un `concurrency` group (`deploy-aws`, sin
  cancelar el que está en curso), para no ejecutar dos `apply` a la vez.

**`deploy-api.yml`**, para los cambios en el código del API:

- **Disparadores:** push a `main` con cambios en `src/app/**`,
  `src/config.py`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, `uv.lock` o
  `data/processed/dashboard_insights.json`, además de `Makefile`,
  `scripts/ci/**`, la acción de sesión AWS y el propio workflow. También
  permite `workflow_dispatch`.
- **En PRs con esos mismos paths:** solo construye la imagen, sin
  credenciales y sin publicarla, para detectar errores de build.
- **En `main`:** construye, sube la imagen a ECR con el SHA, actualiza SSM,
  corre `terraform apply`, espera la estabilidad del servicio y hace el smoke
  test contra la URL pública.
- Usa caché de capas de Docker (`cache-from`/`cache-to` de GitHub Actions).
- `scripts/ci/deploy-api.sh` guarda el tag anterior, actualiza SSM, ejecuta
  plan/apply e intenta restaurar el tag anterior si falla.
- `scripts/ci/verify-deployment.sh` espera estabilidad y compara la revisión
  de ECS con la esperada para detectar rollback. Luego ejecuta el smoke HTTP;
  si `desired_count=0`, omite las peticiones HTTP.

**`terraform.yml`**, para los cambios en la infraestructura:

- **Disparadores:** cambios en `terraform/**`, scripts CI, su prueba, la
  acción de sesión AWS y el propio workflow; también `workflow_dispatch`.
- **En PRs:**
  - Siempre: `terraform fmt -check`, `init -backend=false`, `validate` y las
    cuatro pruebas de `tests/test_ci_deployment.py`, sin credenciales AWS.
  - Si los secrets están disponibles y vigentes, también corre `plan` y lo
    publica como comentario del PR.
  - En PRs internos sin sesión válida, el plan se omite con un aviso. Desde
    forks, el job del plan se omite. Un fallo real del plan, después de validar
    las credenciales, hace fallar el job.
- **En push a `main`:** guarda el plan, aplica ese mismo archivo y verifica
  el despliegue con los scripts de CI.

### 5.7 El modelo dentro del contenedor

- El modelo se carga en el mismo proceso de FastAPI al arrancar, como ya hace
  el wheel `modelo-citas`. No se agrega ningún servicio de inferencia.
- Los pesos del modelo **van dentro de la imagen** o se instalan como
  dependencia al construirla, siguiendo el patrón del wheel en S3. *Mi
  decisión:* no se descargan al arrancar, porque eso alarga el arranque y hace
  depender cada reinicio de una red externa.
- Para que el modelo pueda crecer sin rediseño:
  - el tamaño de la tarea depende solo de `task_cpu` y `task_memory` (la
    tabla de §4.2 da los costos);
  - `health_check_grace_period_seconds` y el `startPeriod` del health check
    son variables;
  - si se usa PyTorch, debe ser la variante solo CPU, para que la imagen no
    pese ~8 GB con CUDA.
- **Límite de API Gateway:** una petición no puede tardar más de 30 s. Si la
  inferencia se acerca a ese límite, hay que optimizar el modelo o subir la
  CPU. No se cambia la arquitectura.

## 6. Criterios de aceptación

1. Con las credenciales del perfil `maia` y el bucket `maia2026-grupo19`,
   siguiendo los comandos del README (init → login → build → push → plan →
   apply), se llega a una
   `api_url` que:
   - responde 200 en `GET /api/estado` (y en `GET /api/salud/lista` si ya
     existe),
   - sirve el tablero en `GET /`,
   - devuelve recomendaciones en `POST /api/recomendar`.
2. Con los secrets vigentes, un cambio en `src/app/` mergeado a `main` publica
   sin intervención manual una imagen con el SHA del commit, y la tarea de ECS
   corre con ese tag.
3. Después del punto 2, `terraform -chdir=terraform plan` sin cambios sale con el plan
   vacío.
4. Un PR que toca `terraform/` muestra `fmt`, `validate` y, si hay
   credenciales, el plan como comentario. Al mergearlo, se aplican los
   cambios.
5. Con los secrets vencidos o ausentes, los workflows fallan, o en PRs se
   saltan el plan, con un mensaje que dice qué hacer.
6. Una imagen que no arranca hace que el circuit breaker vuelva a la revisión
   anterior, y la URL sigue respondiendo.
7. Al definir `custom_domain_name` y `certificate_arn`, se crean el dominio y
   el mapeo. Sin ellas no se crea nada relacionado con el dominio.
8. Terraform no crea NAT Gateway, ALB, roles IAM, proveedor OIDC, el bucket
   del estado ni el repositorio ECR.
9. `make init` se puede correr dos veces seguidas sin errores, y la segunda
   vez no cambia los recursos base. La inicialización de Terraform puede
   actualizar su caché local. Se comprueba además que los recursos tengan la
   configuración requerida; su mera existencia no demuestra esa configuración.
10. Cambiar `task_cpu`/`task_memory` y aplicar redimensiona la tarea sin
    tocar ningún otro recurso.
11. Queda documentado, para el #116: la URL pública, la memoria y CPU
    observadas en Fargate, la latencia de `/api/recomendar` medida desde fuera
    de AWS y el costo mensual estimado.

## 7. A criterio del builder

- La estructura interna de los archivos `.tf` y si usar módulos propios o
  `terraform-aws-modules`. Se prefiere poco código y legible.
- Los nombres de los recursos, con el prefijo `var.project_name` (por defecto
  `citas-api`).
- Versiones ya elegidas: rango de Terraform ≥ 1.10 y < 2.0, CI en 1.14.8
  y provider AWS 5.100.0.
- El formato del comentario del plan y la acción que se use para publicarlo.
- Los nombres exactos de los targets nuevos del Makefile, siempre que se
  conserven `login`, `build` y `push`.

## 8. Riesgos

- **Learner Lab:**
  - Hay que confirmar que la cuenta permite crear un VPC Link de API Gateway
    v2, un namespace de Cloud Map, ECS Fargate y parámetros SSM, y pasar
    `LabRole` a ECS. Si VPC Link o Cloud Map fallan, el plan B es un ALB
    público con API Gateway apuntando a él (cuesta ~USD 16 más al mes).
  - No está claro si el servicio sigue corriendo cuando se cierra la sesión
    del lab. Si se detiene, la URL deja de responder hasta la próxima sesión.
    Esto se verifica al principio y se documenta. Si la URL tiene que estar
    en línea siempre, el despliegue debe ir a otra cuenta.
- **Credenciales vencidas en CI:** si son temporales, cada despliegue desde
  GitHub requiere renovar los secrets. El camino local es el de respaldo.
- **Memoria del contenedor:** si el modelo no cabe en la memoria asignada, la
  tarea se reinicia en bucle (OOM). Hay que medirlo antes de cada cambio de
  modelo. Con SciBERT/SPECTER se esperan 2–4 GB y un arranque más largo.
- **Tamaño de la imagen:** con 2.35 GB hoy, y más con PyTorch, el primer
  arranque de cada tarea tarda en bajar la imagen, y los builds en CI son
  lentos sin caché.
- **Arquitectura de la imagen:** si se construye en Apple Silicon sin
  `--platform linux/amd64`, falla en Fargate (x86_64). Con emulación el build
  es lento (unos 10 minutos), así que el camino normal es que lo construya CI.
- **Costo fijo:** el throttling limita peticiones, pero no reduce las horas
  de Fargate ni el costo de la IP pública. Para apagar el
  servicio basta con `desired_count = 0` (variable) o `terraform destroy`, y
  el README documenta las dos opciones.
- **Rama `main` sin protección:** sin environment, la única barrera antes de
  desplegar es que a `main` se llegue por PR revisado. Hay que confirmar que
  la regla de protección de rama esté activa.
