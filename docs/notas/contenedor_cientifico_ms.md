# Contenedor científico M/S

Servicio independiente de la API estándar. `Dockerfile.ms` contiene el servicio M/S;
`Dockerfile.science` conserva el flujo histórico A4 y sus comprobaciones de CI. Usa Python 3.12, Torch CPU 2.6.0,
Transformers 5.21.0 y la release fijada en `config/ms_release.json`.
No instala el proyecto principal, que actualmente exige Python 3.14.
Reutiliza directamente el código de recuperación densa validado. La base está
fijada por digest y las dependencias transitivas por versiones exactas en
`requirements/science-constraints.txt`; la construcción ejecuta `pip check`.

## Arranque en AWS

1. Construir para la arquitectura de ECS: `docker build --platform linux/amd64 -f Dockerfile.ms -t citas-ms:local .`.
2. Asignar el rol de tarea con `s3:GetObject` sobre la release. No añadir claves a la imagen.
3. Reservar un volumen escribible en `/models`, propiedad del UID/GID 10001, y definir `AWS_REGION=us-east-1`.
4. El proceso compara el inventario remoto con el fijado en la imagen; descarga archivos temporales, comprueba tamaño y SHA256 y los publica mediante renombrado. Reutiliza únicamente archivos locales que vuelvan a pasar ambas verificaciones.
5. Configura `HF_HOME` y `MS_ARTIFACTS_DIR`, activa modo offline e inicia un único worker. FastAPI carga SciBERT y M/S antes de completar el arranque. Un error impide servir solicitudes.
6. Comprobar `/health/ready`, luego ejecutar un POST real. El GET `/api/analisis-cita-ms/estado` conserva su significado de presencia de archivos; no sustituye el POST.

`MS_SCIBERT_MANIFEST` permite cambiar la ruta al manifiesto SciBERT. `MS_CORS_ORIGINS`
acepta orígenes separados por comas; por defecto solo admite la SPA pública.
`OMP_NUM_THREADS` y `MKL_NUM_THREADS` valen 2 por defecto, pendientes del dimensionamiento.
El healthcheck tiene 300 segundos de gracia inicial; ECS/ALB deben configurarse
según la medición real del arranque en AWS, que incluye descarga inicial de 1.76 GB.

## Validación

Pruebas del aprovisionamiento:

```bash
.venv-ms/bin/python -m unittest tests/test_bootstrap_ciencia.py
```

Con el servicio iniciado y los archivos de prueba locales (no incorporarlos a la imagen):

```bash
python scripts/probar_api_cientifica.py \
  --url http://127.0.0.1:8012 \
  --solicitud artifacts/ms_local/solicitud_real_ms.json \
  --referencia artifacts/ms_local/respuesta_real_ms.json \
  --salida artifacts/ms_local/reporte_contenedor.json
```

Comprueba readiness, Top-3 exacto, clase M/S, nueve probabilidades, suma unitaria
y tolerancia absoluta de 0.005 frente al caso del equipo.

La imagen copia solo código, inventarios y configuración autorizados. El contexto
excluye entornos, ZIP, checkpoints, cachés y materiales privados. No contiene
credenciales ni corpus Gold. Cambiar de release exige reconstruir la imagen con
el nuevo inventario fijado; la configuración externa no sustituye los hashes.

## Pendientes de despliegue

Dimensionar CPU/memoria y tiempos; integrar construcción/publicación en CI;
dirigir únicamente las rutas científicas al nuevo servicio y conservar las rutas
estándar; comprobar POST desde el dominio público y React. Ninguno de estos
cambios de infraestructura se aplica mediante la construcción local.

## Evidencia de aceptación local — 21 de noviembre de 2026

- Tres pruebas del aprovisionamiento aprobadas y tres pruebas existentes de la API M/S aprobadas.
- S3 real: inventario remoto idéntico al fijado, diez archivos de caché local verificados y recuperación de un manifiesto pequeño ausente mediante descarga temporal, tamaño/SHA256 y renombrado.
- La verificación independiente de descarga de los diez objetos S3 terminó con `RELEASE OK` y `verificado: true` a las 00:25:21 UTC del 22 de noviembre (20:25 del día 21 en Bolivia).
- Ambas imágenes Linux construidas; `pip check` aprobado y versiones transitivas fijadas.
- Linux ARM nativo: arranque completo con consulta S3 y caché montada en lectura, carga de SciBERT y M/S, readiness 200 y POST 200 del caso completo de 46 candidatos. Tiempo final: **23.598 segundos**, con límite de 2 CPU y 4 GiB; consumo observado durante la primera prueba, aproximadamente 3.25 GiB (no es una medición de pico).
- Top-3: `p00011-p00012`, `p00002-p00003`, `p00065-p00065`. M: Evidence, 0.458718. S: Background, 0.866312. Nueve probabilidades por modelo; clases y fragmentos coinciden con la referencia y todas las probabilidades están dentro de la tolerancia absoluta 0.005.
- Linux x86_64 emulado sobre este Mac ARM: construcción, inventario S3, verificación de caché, carga de modelos y readiness 200 aprobados. El POST completo agotó 300 segundos sin OOM; no se validó equivalencia de esa respuesta. La latencia x86_64 debe comprobarse en ECS nativo. La emulación no sirve para estimar rendimiento de producción.

Imágenes finales:

| Arquitectura | Etiqueta local | ID |
|---|---|---|
| Linux x86_64 | `citas-ms:local` | `sha256:b6c4138be866cf10c2a9ff1f45b3f3e8a28b6287eb996ae2cb7eddcee4eca828` |
| Linux ARM64 | `citas-ms:native` | `sha256:623f33fa20cbeb0ce13c85ba902d48c1bbe9ab2765bd46bad30aec40ea39421a` |

Evidencia local (excluida de Git):

- `artifacts/ms_local/reporte_contenedor_linux_arm64.json`.
- `artifacts/ms_local/requirements_contenedor_linux_amd64.txt`.
- `artifacts/ms_local/contenedor_final_arranque.log`.

La prueba local montó credenciales AWS solo para lectura y usó el UID del usuario
local para leer esos archivos. La imagen configura UID/GID 10001; ECS debe usar
el rol de tarea y un volumen con permisos para ese usuario. No incorpora claves.

El POST nativo de 23.6 segundos deja margen limitado frente a los 30 segundos de
API Gateway. Antes de publicar: medir en ECS, ensayar concurrencia y decidir los
tiempos y el comportamiento del servicio ocupado. No extrapolar esta medición
local a producción ni mantener el dimensionamiento estándar de 1 GiB.

## Validación posterior en AWS

La aceptación x86_64 nativa en ECS pasó con el caso sintético público de 46
fragmentos y referencia local: Top-3, clases y nueve probabilidades concordantes,
8.533 s con 2 vCPU/6 GiB. El caso TRAIN privado no se transmitió. Ver
[despliegue y rollback](despliegue_cientifico_aws.md). El digest de producción
es el de la imagen compilada en AWS, registrado en esa guía y en SSM; las
imágenes locales anteriores permanecen como evidencia de la preparación.

## T01 — aislamiento local de búsqueda global (22-nov-2026)

El servicio científico carga por defecto corpus, recuperador y M/S, sin índice de
búsqueda global. El bootstrap descarga solo la release M/S y el Dockerfile no
requiere `config/search_release.json`. Se conservan los endpoints experimentales:
sin índice responden como no disponibles, sin sustituir resultados.

Para recuperar el experimento de búsqueda global de forma explícita, definir
`MS_ENABLE_GLOBAL_SEARCH=1`, proporcionar el manifiesto mediante
`MS_SEARCH_MANIFEST` (por defecto `/app/config/search_release.json`) y el índice
en `MS_SEARCH_DIR`. El manifiesto experimental no está incluido en la imagen.
No activar esta opción para el recorrido por artículo del PRD.

Validación local: arranque real offline con pesos existentes, readiness 200 y
POST sintético M/S 200 con Top-3 y puntuaciones coincidentes con la referencia
(tolerancia 0,005). Pruebas de arranque, bootstrap, corpus, concurrencia y búsqueda;
contrato M/S de la aplicación estándar comprobado por separado en su entorno.
Todos los orígenes COPY existen. El build Docker completo quedó pendiente por
un timeout DNS contra auth.docker.io al resolver la imagen base fijada; no es
una validación de build superada. No se publicó imagen ni se modificó AWS.

### Cierre de validación local T01

Tras recuperarse la conexión a Docker Hub, el build terminó correctamente:
`citas-science:t01-local`, imagen
`sha256:48db7a716fdd19a9b342dee7bd33b66880177f1d8546b7a72fbdc6fa3abfc43a`
(ARM64). Se arrancó esa imagen con bind mounts de solo lectura de los pesos y
la caché SciBERT locales, sobrescribiendo el comando para ejecutar Uvicorn sin
descargas S3 ni credenciales AWS. `/health/ready` respondió 200 con `listo: true`.
El POST sintético pasó `scripts/probar_api_cientifica.py`: 11,282 s, Top-3
`classifier`, `neural`, `citations`; M Comparison (0,975675), S Background
(0,421516). Las nueve puntuaciones por modelo coinciden con la referencia con
tolerancia 0,005. Se comprobó además que `search_release.json` no existe en la
imagen y la búsqueda global está desactivada. Contenedor temporal detenido al
terminar. T01 aceptada localmente; esta prueba no acredita build Linux AMD64,
bootstrap S3 real ni despliegue AWS, que permanecen fuera de esta validación.
