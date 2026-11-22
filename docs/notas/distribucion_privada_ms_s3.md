# Distribución privada de SciBERT y M/S en S3

Fecha de preparación: 21 de noviembre de 2026.

## Ubicación y contenido

Bucket: `citas-api-models-646941583111-us-east-1`, región `us-east-1`.

Release: `ms-scibert-b8ee47317c29afbc`.

Manifiesto remoto publicado y verificado:

```text
s3://citas-api-models-646941583111-us-east-1/releases/ms-scibert-b8ee47317c29afbc/release.json
```

El inventario versionable está en [config/ms_release.json](../../config/ms_release.json): 10 archivos, 1.761.587.556 bytes. Incluye pesos M/S, sus dos manifiestos de entrenamiento y los seis archivos de la revisión SciBERT verificada. No incluye predicciones Gold, anotaciones, solicitudes ni respuestas de prueba.

Las claves bajo el prefijo de release conservan las rutas relativas al repositorio. Los symlinks locales del snapshot Hugging Face se suben como contenido de archivo. La revisión de SciBERT no cambia.

## Protecciones y permisos

- Cuatro controles de bloqueo público activos; política reportada por S3 como `IsPublic: false`.
- Cifrado AES-256 y versionado S3 activos; ACL deshabilitadas mediante BucketOwnerEnforced.
- Política que rechaza acceso sin TLS.
- Rol `citas-api-ecs-task` con `s3:GetObject` limitado a `releases/*`; sin permiso nuevo de listado, escritura ni acceso al bucket de frontend.
- Simulación IAM: GetObject permitido, PutObject denegado implícitamente para una clave de release.
- Terraform protege el bucket con `prevent_destroy`. El versionado permite recuperar versiones; no se habilitó S3 Object Lock.

La infraestructura está en [terraform/model_storage.tf](../../terraform/model_storage.tf), activada por defecto mediante `scientific_models_enabled`. El despliegue inicial utilizó un plan dirigido a estos siete recursos nuevos para no modificar API, dominios ni infraestructura ajena al almacenamiento. Usar Terraform 1.14.8, como los workflows del repositorio; la instalación global 1.4.7 no es compatible con la configuración actual.

## Transferencia y comprobación

El inventario se construyó verificando los checkpoints contra `docs/manifiesto_distribucion_ms.json` y SciBERT contra el manifiesto A1. Cada entrada registra tamaño y SHA-256. La herramienta local de transferencia está en `artifacts/ms_distribution/transferir.py`; sus logs y manifiesto quedan en esa carpeta excluida de Git.

La transferencia evita reemplazar objetos existentes con tamaño o hash declarados diferentes y publica `release.json` después de los archivos. El identificador deriva del inventario de contenidos. El control de escritura del publicador no sustituye la comprobación de SHA-256 después de descargar.

El script versionable para próximas ejecuciones es [scripts/publicar_modelos_ms.py](../../scripts/publicar_modelos_ms.py). Usa el inventario de `config/ms_release.json` y AWS CLI instalado:

```bash
python scripts/publicar_modelos_ms.py upload --profile josezambrana
python scripts/publicar_modelos_ms.py verify --profile josezambrana
```

El perfil es un argumento local; no se incluyen claves en el código. `verify` descarga los objetos de uno en uno a almacenamiento temporal y comprueba sus SHA-256; no instala los archivos en las rutas de inferencia. El aprovisionador `scripts/iniciar_ciencia.py`, incorporado a `Dockerfile.ms`, restaura los archivos antes de iniciar FastAPI.

### Control manual con AWS CLI y reanudación por partes

El script [scripts/subir_modelos_ms_awscli.sh](../../scripts/subir_modelos_ms_awscli.sh) usa AWS CLI para todas las operaciones S3; requiere Bash, jq y Python 3.9 o posterior para los checksums. Se comprobó sintaxis Bash y equivalencia del manifiesto; no se ejecutó una segunda subida en paralelo a la activa.

Antes de tomar control manual, detener solo los procesos automáticos de esta tarea:

```bash
pkill -TERM -f 'python artifacts/ms_distribution/continuar_publicacion\.py'
pkill -TERM -f 'python artifacts/ms_distribution/reanudar\.py'
pkill -TERM -f 'python artifacts/ms_distribution/verificar_al_terminar\.py'
```

Desde la raíz, para publicar o reanudar:

```bash
export AWS_PROFILE=josezambrana
export AWS_REGION=us-east-1
bash scripts/subir_modelos_ms_awscli.sh
```

El script reutiliza objetos completos con metadatos coincidentes y partes de 8 MiB cuyos tamaño, ETag/MD5 y CRC32 coincidan con el archivo local. Incluye CRC32 por parte al cerrar la subida. Ctrl+C deja las partes remotas; ejecutar de nuevo el mismo comando reanuda. Si hay múltiples uploads para una clave, falla para exigir revisión en lugar de elegir uno arbitrariamente. No ejecutar simultáneamente con otro publicador de la misma release.

Tras el mensaje PUBLICACIÓN COMPLETA:

```bash
python scripts/publicar_modelos_ms.py verify --profile josezambrana
```

El flujo manual se sigue por la salida de esos comandos. Si se detuvo el monitor automático, `estado_publicacion.json` deja de actualizarse y no representa el resultado manual. `aws s3 cp` y `aws s3 sync` por sí solos no recuperan las partes de una ejecución interrumpida; el script utiliza `list-multipart-uploads`, `list-parts`, `upload-part` y `complete-multipart-upload` para hacerlo.

Estado actual: **publicación y verificación completadas**. El reporte final registra
`completado`, `verificado: true`, el 22 de noviembre de 2026 a las 00:25:21 UTC
(21 de noviembre, 20:25 en Bolivia). Los diez objetos se descargaron y verificaron
por tamaño y SHA256; el log termina con `RELEASE OK` y la URI de `release.json`.

Evidencia local: `artifacts/ms_distribution/estado_publicacion.json` y
`artifacts/ms_distribution/verificacion.log`. El orquestador que terminó el flujo
es `continuar_publicacion.py`; ya no se requiere continuar la subida.

## Pendiente del despliegue científico

El arranque con release fijada, descarga temporal y validación está implementado en
`Dockerfile.ms` y `scripts/iniciar_ciencia.py`. Se probaron inventario remoto real,
caché completa y recuperación real de un archivo pequeño desde S3. La imagen ya está desplegada en ECS; disponibilidad e inferencia por HTTPS
se comprobaron con datos sintéticos.
Ver [contenedor científico](contenedor_cientifico_ms.md).
