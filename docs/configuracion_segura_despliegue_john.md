# John — Configuración segura del servicio (issue #118)

Fecha: 2026-11-04. Estado: implementación sometida a revisión, no equivale a despliegue público verificado.

## Alcance real (no declarar modelos no integrados)
El backend de `src/app/main.py` sirve:
- `/api/recomendar`: artefacto `modelo-citas` empaquetado con TF-IDF + reordenador lineal, CPU.
- `/api/top3-fragmentos`: BM25 léxico; no calcula función de cita.
- `/api/top3-corpus/*`: casos TRAIN del artefacto local S2.2, si se proporciona. Por defecto puede devolver HTTP 503 al no existir el corpus.
- `/api/estado`: disponibilidad del modelo y nombres públicos de backends/entorno, sin secretos/rutas.

**SciBERT Top-3 y el clasificador de nueve funciones de cita NO están integrados al backend de producción**; `APP_RECOMMENDER_BACKEND=scibert`, `APP_TOP3_BACKEND=scibert` o `APP_MODEL_DEVICE=cuda` se rechazan en arranque. Esta política previene una demo que anuncie modelos aún no conectados. La integración real corresponde a #102 #103 #107 #116.

## Opciones centralizadas (servicio actual)

| Variable | Por defecto | Uso validado |
|---|---|---|
| `APP_ENV` | `development` | Identificación de entorno: `development`, `test`, `production`; **no** es control de acceso |
| `APP_HOST` | `127.0.0.1` | IP/interfaz de `uv run tablero`; Docker aplica `0.0.0.0` dentro de su red |
| `APP_PORT` | `8000` | Puerto de `uv run tablero` (1–65535). En Compose se conserva `8000` como puerto interno |
| `APP_LOG_LEVEL` | `info` | Logging de Uvicorn: critical/error/warning/info/debug |
| `APP_RECOMMENDER_BACKEND` | `packaged_tfidf_linear` | Comprueba que el backend realmente exista |
| `APP_TOP3_BACKEND` | `bm25_lexical` | Comprueba que el recuperador esté implementado |
| `APP_MODEL_DEVICE` | `cpu` | CPU del modelo actual; GPU no implementada en la API |
| `APP_INSIGHTS_PATH` | `data/processed/dashboard_insights.json` | Ruta leída en startup para tablero |
| `TOP3_CORPUS_PATH` | `proyecto_de_grado/artifacts/top3_s2/casos_train.json` | Ruta opcional del artefacto TRAIN para endpoint Top-3; solo se lee, nunca descarga |

Las rutas relativas se resuelven contra la raíz del proyecto (no el directorio desde el que se lanzó el proceso), y las rutas absolutas explícitas son responsabilidad de quien despliega. No incluir claves en nombres de archivos ni imprimir rutas de secretos.

### Proveedores de experimentación, separados de la API

`OPENAI_MODEL`, `GEMINI_MODEL`, `COHERE_MODEL`, `OPENWEIGHT_MODEL` y `OPENWEIGHT_BASE_URL` ya estaban respaldados por clientes LLM. Las claves se obtienen únicamente del entorno: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `COHERE_API_KEY`, `OPENWEIGHT_API_KEY`. **No están habilitados como endpoints de la aplicación web**.

Se agregó `CITATION_PROVIDER_TIMEOUT_SECONDS` (por defecto 60 s; se validan 1–600), aplicado efectivamente al SDK HTTP de los cuatro proveedores, sin cambiar la estrategia de reintentos del orquestador. `OPENWEIGHT_BASE_URL` se valida como URL HTTP(S) sin usuario, contraseña, query ni fragmento. Una URL con HTTP sin TLS en red pública puede exponer tráfico: utilizar HTTPS o red privada autorizada.

## Desarrollo local

```bash
uv sync --group dev
uv run tablero
```

Para cambiar host/puerto sin editar código:

```bash
export APP_ENV=development
export APP_HOST=127.0.0.1
export APP_PORT=8123
export APP_LOG_LEVEL=warning
uv run tablero
```

PowerShell:

```powershell
$env:APP_ENV = "development"
$env:APP_PORT = "8123"
$env:APP_LOG_LEVEL = "warning"
uv run tablero
```

**Importante:** `uv run tablero` usa estas opciones; un comando manual `uvicorn src.app.main:app --port 9000` usa los argumentos explícitos de Uvicorn, no `APP_PORT`. El arranque valida las variables en el ciclo de vida del servicio.

## Docker Compose

```bash
docker compose --env-file config/runtime.env.example config --quiet
docker compose --env-file config/runtime.env.example up --build
```

Por defecto, el puerto publicado de la API y dashboard solo escucha en `127.0.0.1`, aunque dentro del contenedor la API escuche en `0.0.0.0:8000` para que Nginx alcance `api:8000`.

Variables de publicación de Compose (distintas del puerto interno `APP_PORT`):
- `API_BIND_HOST` (127.0.0.1), `API_PUBLISHED_PORT` (8000)
- `DASHBOARD_BIND_HOST` (127.0.0.1), `DASHBOARD_PUBLISHED_PORT` (8080)

Al preparar despliegue público, publicar por un proxy con HTTPS y controles adecuados; cambiar deliberadamente `DASHBOARD_BIND_HOST` si la plataforma necesita ingress externo. **No exponer el puerto de API sin necesidad.** Ni estas opciones ni `APP_ENV=production` garantizan por sí solas autenticación, cifrado, firewall, disponibilidad o seguridad de red.

### Datos de corpus en Docker
El `.dockerignore` excluye `artifacts/` y `data/raw/`; el artefacto S2.2 NO llega en la imagen. Si se quiere usar `/api/top3-corpus`, montar un archivo TRAIN aprobado como volumen de solo lectura y apuntar `TOP3_CORPUS_PATH` a su ruta dentro del contenedor. No incluir Test Gold, llaves ni corpus sensibles en una imagen pública. Si está ausente, se informa error 503, nunca se inventan casos.

### Protección de secretos
El `.dockerignore` ahora excluye `.env`, `.env.*`, `*.pem`, `*.ppk` y `*.key`, evitando que `COPY . .` los incluya por accidente. No almacenar claves en `runtime.env.example`, `citation_eval.env.example`, PR, capturas o logs. Para producción usar mecanismos de secretos y permisos de la plataforma.

## Pruebas y aceptación de #118

Pruebas nuevas:
- `tests/test_app_settings.py`: defaults, entorno, host/puerto/log, rutas, backends no implementados, no exposición de claves, arranque anticipado, `uv run tablero`.
- `tests/test_provider_settings.py`: valores inválidos, URL open-weight, timeout real del constructor de SDK en cuatro proveedores (mocks, sin gastos ni llamadas).
- `.github/workflows/configuracion-app.yml`: regresa pruebas de API/Top-3, proveedores, sintaxis Python, `docker compose config` sin iniciar contenedores.

Ejecutar local:

```bash
uv run pytest -q tests/test_app_settings.py tests/test_provider_settings.py
docker compose --env-file config/runtime.env.example config --quiet
```

Criterios aún pendientes, sin afirmar completitud total:
1. Validar build Docker real, endpoint /api/estado y regresiones de interfaz en un entorno externo (issue #116/#119).
2. Integrar SciBERT Top-3/clasificador de nueve funciones como inferencia verificada (issues #102/#103/#107).
3. Medir tiempos, consumo de CPU/GPU y error de proveedor bajo infraestructura real; no confundir mock con disponibilidad de servidor.
4. Actualizar README general una vez que Gabriel cierre la integración de documentación #117.
5. Confirmar CI en último SHA de este PR, luego revisión cruzada; no fusionar por éxito parcial.

## Relación con rúbrica
#118 cubre parametrización (15/100) de la rúbrica de **despliegue**, no del informe de avance de 8 páginas ni del artículo de 12 páginas. La puntuación efectiva requiere evidencia operativa, validada por evaluadores.
