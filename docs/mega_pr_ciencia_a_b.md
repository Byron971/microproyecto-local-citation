# Mega PR #180 · Ingeniería SciBERT / A4 A-B / Docker / AWS

Estado: componentes de código y contratos listos para revisión; las verificaciones pesadas y de facturación se realizan únicamente en equipos autorizados. No se consideran cumplidas por CI ligero. Sin anotaciones ni Test Gold humano.

## Qué implementa

| Requisito | Código | Evidencia aún necesaria |
|---|---|---|
| Recuperación A4 | src/app/restore_a4.py y registro SHA del proyecto | Archivos model.safetensors originales |
| Snapshot SciBERT | src/app/science_preflight.py y manifest A1/A4 | Caché HuggingFace auténtico, importación Torch real |
| Entrada B | SciBERT Top-3 → perfil_seccion original → ClasificadorCLS | Inferencia con checkpoint B autenticado |
| Caché | LRU por documento+hash+versión, límites de artículos/bytes y lock | Memoria pico y rendimiento bajo carga |
| Imagen | Dockerfile.science y docker-compose.science.yml | Build e inicio científico auténtico |
| AWS | scripts/ci/audit_https_aws.py read-only | HTTPS público, permisos, facturación Cost Explorer |

## 1. Recuperar los checkpoints A4 auténticos

En el equipo original localizar proyecto_de_grado/artifacts/clasificacion_a4/corridas.
No descargar checkpoints arbitrarios ni generar archivos simulados: cada peso
debe coincidir byte a byte con los manifiestos históricos.

- SciBERT-A: 0656fceb422632195a9ec35a8dab7e2482041c033451ea3442a5bdcd4a7a6fbd
- SciBERT-B: 238b4035d7680d810488290eccc50c8cd977639e392df96b1bc10d91f3955902
- SPECTER-A: 43243a929880203fa3eb75882163874452fbceaf6662cfb25a709a9c4e016606
- SPECTER-B: aa2b293f11ca6b0028896d374f9553d97a274a85d18dd986a8b5b69948622597

El script de restauración comprueba SHA de fuente y manifiesto histórico. Por defecto
restaura SciBERT A/B; con --all incluye SPECTER. El dry-run no copia nada.

~~~bash
uv run python -m src.app.restore_a4 --source /RUTA/ORIGINAL/clasificacion_a4/corridas
uv run python -m src.app.restore_a4 --source /RUTA/ORIGINAL/clasificacion_a4/corridas --apply

# Inventario que NO certifica todos los modelos si hay alguno ausente:
uv run python -m src.app.checkpoint_gate --permitir-faltantes
~~~

No subir pesos a Git. El destino por defecto es gitignored. El script falla
si faltan bytes, hay symlinks o SHA difieren, y nunca sobrescribe archivos alterados.
Si no aparecen los archivos originales, la recuperación sigue bloqueada.

## 2. Instalar y verificar el snapshot SciBERT fijado

Identidad: allenai/scibert_scivocab_uncased, revisión exacta
24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1.

A1 y A4 exigen el mismo hash del manifiesto:
d64d1ac222fa40fb65d148ab4b87ca24b5063d4d54dc2317f280e8c50d671e7a.

Descarga explícita en entorno científico del proyecto con internet autorizado:

~~~bash
uv sync --project packages/clasificacion-funcion --locked --group modelo
uv run --project packages/clasificacion-funcion --group modelo \
  python -m clasificacion_funcion.descarga_modelo --encoder scibert
~~~

No equivale a cargar Torch en FastAPI. Después ejecutar la validación del
snapshot y de los pesos reales desde un intérprete que pueda importar los
paquetes científicos y la raíz del proyecto:

~~~bash
uv run python -m src.app.science_preflight
uv run python -m src.app.science_preflight --strict
~~~

El primer comando puede informar faltantes y salir sin error; SOLO el segundo
exige snapshot y A/B originales. La imagen Docker CPU permite un entorno
separado del uv.lock ligero de FastAPI. El grupo modelo histórico usa el
índice PyTorch CUDA, por lo que no confundir instalación CUDA con CPU.

## 3. Corpus de desarrollo TRAIN, no Gold

~~~bash
uv run python -m proyecto_de_grado.src.data.exportar_corpus_top3 --limite 5
uv run python -m src.app.corpus_preflight \
  --archivo proyecto_de_grado/artifacts/top3_s2/casos_train.json
~~~

El preflight exige procedencia TRAIN y no acepta etiquetas adjudicadas.
Nunca subir documentos ACL OCL ni datos privados a la imagen o al repositorio.

## 4. Construir la imagen científica CPU

La imagen ligera permanece intacta; el nuevo Dockerfile.science instala
PyTorch CPU, Transformers, Safetensors y tres paquetes científicos. No
descarga los modelos durante las peticiones. Usa un usuario no privilegiado,
HF offline y tres montajes de solo lectura. Reservar 4 vCPU/12 GiB y almacenamiento
suficiente para la imagen.

~~~bash
export SCIENCE_HF_CACHE_HOST_PATH="$HOME/.cache/huggingface"
export SCIENCE_A4_RUNS_HOST_PATH="$(pwd)/proyecto_de_grado/artifacts/clasificacion_a4/corridas"
export TOP3_CORPUS_HOST_PATH="$(pwd)/proyecto_de_grado/artifacts/top3_s2/casos_train.json"

docker compose -f docker-compose.yml -f docker-compose.science.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.science.yml build api
docker compose -f docker-compose.yml -f docker-compose.science.yml up api
~~~

Asegurar que el UID 10001 pueda LEER los montajes. El caché HuggingFace
puede estar en otro directorio, según HF_HOME en el equipo de descarga.
El build pesado NO se ejecuta en CI ligero y no ha sido validado en este
entorno contra los pesos originales. No afirmar que existe imagen científica
operativa sin observar la compilación y la carga real.

## 5. E2E científico sin mocks, cuándo estén disponibles los pesos

Rutas: POST /api/top3-scibert, POST /api/clasificar-cita (A),
POST /api/clasificar-cita-b (B), GET /api/clasificar-cita-b/corpus/{context_id}
y GET /api/capacidades. El flujo B usa los EXACTOS tres fragmentos del
citado y clasificacion_funcion.dominio.construir_segmentos con perfiles de
sección generados por auditoria_corpus.dominio.perfil_seccion.

~~~bash
uv run python scripts/ci/smoke_tesis.py --cientifico \
  --salida artifacts/qa_tesis/cientifico_cpu_001.json
~~~

El smoke científico falla expresamente si no cargaron ambos checkpoints y
SciBERT o si se sustituye indebidamente por BM25. No confundir el smoke
baseline real CI con una ejecución del modelo pesado. UI en /fragmentos,
/funcion y /funcion-b.

La caché SciBERT es temporal, en memoria, solo para corpus TRAIN y nunca
retiene consultas manuales. Incluye SHA del documento, chunk IDs/textos,
modelo/revisión y configuración. Límites: APP_SCIBERT_CACHE_PAPERS=8,
APP_SCIBERT_CACHE_MAX_MB=64, APP_SCIENCE_MAX_CHUNKS=500 y
APP_SCIENCE_MAX_CHARACTERS=600000 (todos configurables). Se serializa la
inferencia por worker para limitar picos simultáneos. Es necesario medir
RAM, CPU y latencia P50/P95 en el equipo destino.

## 6. Despliegue HTTPS y costos reales AWS (solo lectura)

Este PR NO ejecuta terraform apply ni despliegue. Se deben revisar permisos,
Terraform plan, costos y tamaño de ECS/Fargate antes de autorizar cualquier
publicación del contenedor pesado. Con URL API Gateway y CloudFront REALES:

~~~bash
uv run python scripts/ci/audit_https_aws.py \
  --api-url https://TU_API_GATEWAY \
  --frontend-url https://TU_CLOUDFRONT \
  --output artifacts/auditorias/https_001.json
~~~

Con credenciales AWS CLI autorizadas, Cost Explorer habilitado y la etiqueta
de asignación de costos Project activada:

~~~bash
uv run python scripts/ci/audit_https_aws.py \
  --aws-cost --project-tag citas-api \
  --start 2026-11-01 --end 2026-11-16 \
  --output artifacts/auditorias/costos_001.json
~~~

Requiere sts:GetCallerIdentity y ce:GetCostAndUsage. El reporte contiene
costo atribuido por etiqueta y servicio; **no** es factura completa y puede
haber recursos sin etiqueta, rezagos u otros cargos. Cuando no hay datos,
reporta sin datos atribuibles en vez de inventar USD 0.

Para verificar ciencia real externamente ejecutar adicionalmente el smoke
con --cientifico --url https://API_REAL --permitir-remoto después de
publicación autorizada.

## 7. Qué prueba CI y qué sigue pendiente

La nueva suite Ciencia A-B y Docker CPU ejecuta contratos de A/B, SHA y
restauración sintéticos, caché, protección de TRAIN, seguridad AWS,
validación Compose. React verifica los flujos visuales. Los workflows
baseline hacen llamadas HTTP reales, sin modelos científicos pesados.
Pasar estas suites no certifica inferencia SciBERT/A4 con Torch.

Evidencia pendiente para declarar el sistema científico operativo:
1. Checkpoints originales SciBERT-A/B verificados.
2. Snapshot SciBERT coincidente con manifiestos A1/A4.
3. Docker build CPU completado y digest identificado.
4. Smoke científico SIN mocks con A+B cargados.
5. Medición de memoria y latencias reales en máquina destino.
6. HTTPS público funcionando y Cost Explorer por periodo/cuenta autorizada.

Hasta disponer de los seis puntos, indicar solamente:
**integración implementada y CI de contratos verde; inferencia pesada,
despliegue y facturación no verificados**.
