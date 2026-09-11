# Manual de instalación

Procedimiento verificado sobre un **clon limpio** de `main` en Windows 11, sin credenciales de AWS. Cada comando de este documento se ejecutó realmente y los tiempos son los medidos; no son estimaciones.

## Requisitos previos

| Herramienta | Versión verificada | Para qué |
|---|---|---|
| Git | 2.40 | Clonar el repositorio |
| [uv](https://docs.astral.sh/uv/) | 0.12.7 | Entorno y dependencias. Administra Python por su cuenta |
| Docker Desktop | 29.6 | Solo para la ejecución en contenedores (opcional) |

No hace falta instalar Python: `uv` descarga la versión que el proyecto declara.

**No se requieren credenciales de AWS.** El remoto de datos por omisión es `publico`, servido por HTTPS y de solo lectura.

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

## 2. Instalar uv

Linux o macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 3. Crear el entorno e instalar dependencias

```bash
uv sync
```

*Tiempo medido: 30 s.* Crea `.venv` con la versión de Python declarada en `pyproject.toml`.

## 4. Descargar los datos versionados

```bash
uv run dvc pull
```

*Tiempo medido: 41 s.* Recupera 11 archivos **sin pedir credenciales**:

| Carpeta | Contenido | Tamaño |
|---|---|---|
| `data/raw/` | `contexts.json`, `papers.json`, `train.json`, `val.json`, `test.json` | 67.374.876 bytes |
| `data/processed/` | `train_pairs.json`, `val_pairs.json`, `test_pairs.json`, `train_tfidf_top100.json` | 50.247.436 bytes |

Para comprobar el estado:

```bash
uv run dvc status
```

> **Advertencia.** `dvc status -c` no prueba que los datos se puedan recuperar: contra un remoto sin permisos de lectura llega a informar *«Cache and remote are in sync»*. Solo un `dvc pull` completo lo demuestra.

## 5. Ejecutar las pruebas

```bash
uv run pytest
```

*Tiempo medido: 113 s — 96 pruebas.*

---

## 6. Entrenar y publicar el modelo

El paquete `model-package` **no incluye un modelo entrenado**: la carpeta `modelo_citas/trained/` viaja vacía a propósito, porque el artefacto pesa 49 MB. Hay que generarlo antes de levantar la API.

```bash
uv pip install -e model-package
uv run --no-sync python -m modelo_citas.train_pipeline --data-dir data/raw
```

*Tiempo medido: 76 s.* Genera `modelo-citas-output0.1.0.pkl` (49.308.404 bytes) **dentro del entorno virtual**, que es donde `modelo_citas.predict` lo busca.

> **No anteponer `PYTHONPATH=model-package` al comando de entrenamiento.** `TRAINED_MODEL_DIR` se deriva de la ubicación del módulo importado: con esa variable, Python carga `modelo_citas` desde el árbol de fuentes y el artefacto se guarda ahí, mientras que la API lo lee desde el entorno virtual. El síntoma aparece más tarde, al pedir una predicción:
>
> ```
> FileNotFoundError: No se encontró el modelo entrenado en
> .venv/Lib/site-packages/modelo_citas/trained/modelo-citas-output0.1.0.pkl
> ```
>
> Si ya ocurrió, se arregla con `uv sync --reinstall-package modelo-citas`, que copia el artefacto al entorno. Un `uv sync` normal no basta: detecta que el paquete no cambió de versión y no lo vuelve a copiar.

Para confirmar que quedó bien:

```bash
uv run --no-sync python -c "from modelo_citas.predict import make_prediction; print(make_prediction(context='neural machine translation with attention', top_k=3)['predictions'][0]['titulo'])"
```

Debe imprimir `Effective Approaches to Attention-based Neural Machine Translation`.

---

## 7. Levantar la API y el tablero

```bash
uv run --no-sync uvicorn src.app.main:app --host 127.0.0.1 --port 8000
```

*Tiempo medido hasta responder: 6 s.* Después, abrir <http://127.0.0.1:8000>.

La primera vez el backend construye `data/processed/dashboard_insights.json` a partir de los datos; en los arranques siguientes lo reutiliza.

Para comprobar que sirve el modelo correcto:

```bash
curl http://127.0.0.1:8000/api/estado
```

Debe responder `"modelo": "TF-IDF + reordenador lineal"` junto con los coeficientes aprendidos. Si dijera solo `"TF-IDF + similitud coseno"`, estaría sirviendo la línea base y no el modelo supervisado.

### Endpoints

| Ruta | Método | Descripción |
|---|---|---|
| `/` | GET | Tablero web |
| `/api/estado` | GET | Modelo cargado, tamaño del corpus y coeficientes |
| `/api/recomendar` | POST | `{"contexto": "...", "top_k": 10}` devuelve el ranking |
| `/api/insights` | GET | Indicadores del análisis exploratorio |
| `/api/ejemplo` | GET | Un contexto de ejemplo para probar |

---

## 8. Ejecución con contenedores

```bash
docker compose up --build
```

Levanta dos servicios:

| Contenedor | Puerto del host | Contenido |
|---|---|---|
| `microproyecto-citas-api` | 8000 | FastAPI con el paquete `modelo-citas` |
| `microproyecto-citas-dashboard` | 8080 | Nginx sirviendo el tablero |

El tablero queda en <http://localhost:8080>. Nginx redirige `/api/*` hacia `http://api:8000` por la red interna de Compose, de modo que **no hay que exponer la IP de la máquina**.

El `Dockerfile` hace por su cuenta el `dvc pull -r publico` y el entrenamiento del modelo, así que no hay que ejecutar el paso 6 antes: el primer build tarda varios minutos.

---

## Solución de problemas

**`uv : The term 'uv' is not recognized`** — `uv` no quedó en el `PATH`. Cerrar y volver a abrir la terminal después de instalarlo.

**`FileNotFoundError: No se encontró el modelo entrenado`** — falta `uv sync --reinstall-package modelo-citas` después de entrenar (ver paso 6).

**`[Errno 10048] only one usage of each socket address`** — el puerto ya está ocupado por otro proceso. Elegir otro con `--port`, o liberar el que está en uso. En Windows: `Get-NetTCPConnection -LocalPort 8000 -State Listen`.

**`request returned 500 Internal Server Error ... /_ping`** — Docker Desktop está abierto pero su motor no arrancó. Reiniciar Docker Desktop por completo.

**`ExpiredToken` o `InvalidClientTokenId` en AWS** — solo afecta a quien publique datos con `dvc push`. Para instalar y ejecutar el proyecto no se necesitan credenciales.

---

## Variables de entorno

| Variable | Por omisión | Efecto |
|---|---|---|
| `MLFLOW_TRACKING_URI` | sin definir | Servidor de MLflow para registrar experimentos. Sin ella se usa SQLite local (`mlflow.db`). No es necesaria para la API ni para el tablero |
| `PYTHONPATH` | sin definir | **Dejarla sin definir.** Apuntarla a `model-package` hace que el entrenamiento guarde el modelo en el árbol de fuentes en vez del entorno virtual, y la API no lo encuentra (ver paso 6) |
