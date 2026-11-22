# Despliegue de la API científica M/S en AWS

## Arquitectura

API Gateway conserva el dominio `api.proyectocitas-grupo19.click` y el VPC Link
existentes. El ALB interno dirige exclusivamente `/api/analisis-cita-ms` y
`/api/analisis-cita-ms/estado` al nuevo servicio ECS `citas-api-science`.
El resto de las rutas conserva el servicio estándar `citas-api`.

El nuevo servicio usa una imagen Linux x86_64 fijada por digest en SSM
`/citas-api/science/image_uri`, rol de tarea existente con GetObject a releases
privadas y descarga validada antes del arranque. Readiness: `/health/ready`.
La ruta pública de estado añade release, revisión de código y modelos cargados;
la aceptación exige además POST real.

Capacidad final: una tarea Fargate de **2 vCPU y 6 GiB**, dos hilos de cómputo,
600 segundos de gracia ECS y 300 de startPeriod de contenedor. Se validó inicialmente
con 4 vCPU/8 GiB (4.813 s) y se redujo tras medir el margen disponible. La configuración
final respondió en **8.533 s** con 46 fragmentos sintéticos. Es una medición de ese
caso, no garantía de latencia para todas las entradas ni una prueba de carga sostenida.

API Gateway mantiene 30 segundos y React usa 32 segundos de timeout de transporte.
Una segunda inferencia concurrente recibe 429 y Retry-After 5 sin quedar en cola:
prueba pública, 200 en 8.462 s y 429 en 0.773 s. La primera sigue hasta completar.
La aplicación estándar preservó tarea `citas-api:1` y POST `/api/recomendar` 200.

Cómputo final aproximado: **US$0.10763/h, US$78.57/730 h**, según tarifas Linux/x86
us-east-1 (vCPU 0.04048/h y GiB 0.004445/h). Excluye IPv4, registros, S3, ECR y tráfico.
Fuente: https://aws.amazon.com/fargate/pricing/. No se añadió un ALB ni NAT Gateway.
La tarea permanece encendida hasta que se cambie `scientific_desired_count`; no se apaga por inactividad.

## Configuración versionable

- `Dockerfile.ms`: servicio científico separado de los contenedores estándar/A4.
- `terraform/scientific_api.tf`: grupo de logs, target group, regla ALB, tarea y servicio.
- `scripts/ci/deploy-science.sh`: despliegue dirigido, rechazo de cambios ajenos,
  espera de estabilidad, comprobación de revisión y POST público sintético.
- `.github/workflows/deploy-scientific-api.yml`: validación de imagen y despliegue
  manual desde main; utiliza los secretos AWS ya empleados por el workflow estándar.

La imagen debe publicarse primero. El despliegue exige URI `@sha256:...`, nunca
un tag mutable. Las revisiones ECS anteriores se conservan mediante skip_destroy
para poder restaurarlas. El workflow deberá incorporarse al repositorio para
estar disponible en GitHub; preparar el archivo local no lo publica.

## Ejecución y comprobación

Con sesión AWS del entorno correcto, Terraform 1.14.8 inicializado y la imagen
ya publicada:

```bash
export AWS_PROFILE=josezambrana
export AWS_REGION=us-east-1
export SCIENCE_IMAGE_URI='REPOSITORIO@sha256:DIGEST_REAL'
export TERRAFORM_BIN=/tmp/citas-terraform-1.14.8/terraform
bash scripts/ci/deploy-science.sh
```

Para aceptación reproducible con el caso sintético inventado para este despliegue:

```bash
python scripts/probar_api_cientifica.py \
  --url https://api.proyectocitas-grupo19.click \
  --estado-path /api/analisis-cita-ms/estado \
  --solicitud tests/fixtures/ms_sintetico_solicitud.json \
  --referencia tests/fixtures/ms_sintetico_referencia.json \
  --salida artifacts/ms_deploy/aceptacion_publica_sintetica.json
```

La prueba compara Top-3, clases y nueve probabilidades con tolerancia 0.005.
Los textos son sintéticos y la referencia procede de inferencia local con los
checkpoints verificados. Demuestra concordancia numérica; no mide calidad científica.
Comprobar también `/api/estado`, una recomendación estándar real, preflight CORS
y rechazo de una segunda inferencia simultánea. Los casos TRAIN no se añaden a la imagen.

## Rollback

Antes de cada actualización, guardar tarea ECS e imagen SSM anteriores. El script
restaura el puntero SSM y solicita la revisión ECS previa si falla una actualización;
comprobar después estabilidad y un POST real. El circuit breaker de ECS también
puede restaurar un despliegue anterior sano. No confundir `services-stable` con
aceptación: comprobar que la revisión activa sea la solicitada.

En la primera publicación no existe una revisión científica anterior. Si falla,
reducir `citas-api-science` a cero y retirar su regla ALB mediante un plan revisado
con `scientific_api_enabled=false`; conservar logs antes de destruir recursos.
La API estándar no cambia. Para apagar temporalmente el cómputo sin destruirlo,
usar `scientific_desired_count=0` en la configuración de Terraform, teniendo en
cuenta que las rutas científicas no estarán disponibles.

## Publicación verificada — 21 de noviembre de 2026

- SPA: https://proyectocitas-grupo19.click/analisis-ms.
- Estado científico: https://api.proyectocitas-grupo19.click/api/analisis-cita-ms/estado.
- Servicio `citas-api-science`, revisión de tarea `citas-api-science:2`, una tarea sana.
- Imagen ECR: `646941583111.dkr.ecr.us-east-1.amazonaws.com/citas-api@sha256:c54511531fefb7f2a4dbd607548523e068a17c9439bc069a2be59713d7de17fe`.
- Código: `199c457f6b5cd46f952bfd06f7b8f2515d32e62262bd6cef574e026616899f10`.
- Modelos: `ms-scibert-b8ee47317c29afbc`, SciBERT `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`.
- Plan inicial revisado: cinco altas, ningún cambio ni destrucción de recursos existentes.
- Ajuste de capacidad: únicamente revisión de tarea y servicio científicos; revisión 1 conservada.
- React compilado con base API del dominio personalizado, 29 pruebas unitarias aprobadas; assets antiguos conservados y HTML anterior guardado. Bundle `/assets/index-DutapOOx.js`.
- Preflight CORS 204 desde origen SPA; POST de recomendación estándar 200.
- Navegador real: ejemplo ilustrativo ejecutado desde React, Top-3 y nueve probabilidades M/S visibles.

La subida local de la imagen se detuvo por lentitud. Se compiló en CodeBuild dentro
de AWS con un ZIP de 39 KB construido mediante lista explícita de archivos. El
proyecto, rol y todas las versiones de ese ZIP temporal fueron retirados; la imagen
ECR permanece y el grupo de logs tiene retención de siete días. El workflow futuro
utiliza GitHub Actions; su archivo todavía debe incorporarse al repositorio remoto.

La revisión automática rechazó enviar el caso TRAIN privado al dominio público
porque no había autorización específica para transmitir ese material. No se envió
ese archivo. La aceptación pública se completó mediante datos sintéticos inventados
y su referencia local, permitidos por la revisión automática.

Evidencia local excluida de Git:

- `artifacts/ms_deploy/despliegue_final.json` y `deployment.json`.
- `artifacts/ms_deploy/aceptacion_publica_final.json`.
- `artifacts/ms_deploy/concurrencia_publica_sintetica.json`.
- `artifacts/ms_deploy/rollback_before.json` y `frontend_before_index.html`.
- `artifacts/ms_deploy/web_ms_resultados.png`.

La pantalla publicada permite análisis manual. La selección automática de artículos
recomendados, recuperación de su texto completo y armado de sus fragmentos siguen
pendientes de la entrega 2.


## Actualización: flujo integrado por artículo

El servicio vigente es `citas-api-science:3`, con 2 vCPU/6 GiB y la misma release
de pesos. Imagen: `sha256:121315286820ddff1753f839062303dba48dd98dff6a60aef82fab6465839cd5`.
Código: `7676eef942b45ae8ed0c58d8a402aef9115b1677cc1a97b629d205dc6b9f27d5`.
Se añadieron las rutas `/api/analisis-cita-ms/disponibilidad` y
`/api/analisis-cita-ms/articulo`; el ALB dirige el prefijo científico al servicio.
La SPA publicada usa `index-BY5us5AN.js`. Los índices previos de la SPA y
evidencias están en `artifacts/ms_integration/`; las revisiones científicas
1 y 2 siguen disponibles para rollback. El ZIP de CodeBuild, el proyecto y
el rol temporal de esta compilación fueron retirados. Logs conservados siete días.

El primer intento de actualización se detuvo antes del apply por usar una carpeta
Terraform sin backend inicializado; el script restauró el puntero SSM. El segundo
utilizó el backend existente y completó el despliegue y las pruebas públicas.

Véase [guía del flujo integrado](flujo_integrado_ms.md) para operación, corpus
inicial de 22 artículos, pruebas y limitaciones. El workflow local ahora también
comprueba el recorrido integrado, pero sigue pendiente publicarlo en GitHub.
