# Recomendación Local de Citas Académicas

Cuando alguien escribe un artículo académico, necesita constantemente citar otros trabajos que respalden lo que está afirmando. Encontrar el artículo correcto entre miles de publicaciones es lento: hay que recordar qué se ha leído, buscar por palabras clave y revisar uno por uno si de verdad aplica a esa idea puntual.

Este proyecto es un prototipo que automatiza esa búsqueda: a partir del fragmento de texto que la persona está escribiendo, sugiere una lista ordenada de los artículos más probables para citar en ese punto, como un asistente que lee el contexto y recomienda las referencias más relevantes. Es un trabajo experimental para la materia Proyecto: Desarrollo de Soluciones, que prueba distintas formas de hacer esa recomendación para encontrar la que da mejores resultados.

Datos de origen: [Local-Citation-Recommendation](https://github.com/nianlonggu/Local-Citation-Recommendation).

## Quickstart

Requisitos: `git` y `uv` (Python lo administra `uv`, no hace falta instalarlo aparte).

```Shell
# 1. Clonar
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation

# 2. Instalar uv (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell): powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 3. Crear el entorno e instalar dependencias
uv sync

# 4. Descargar los datos versionados (remoto público de solo lectura)
uv run dvc pull

# 5. Verificar que todo funciona
uv run pytest

# 6. Entrenar el modelo del paquete e instalarlo con el artefacto dentro
uv run tox -c model-package -e train
uv sync --reinstall-package modelo-citas

# 7. Levantar el tablero
uv run tablero   # http://127.0.0.1:8000
```

El paso 6 es obligatorio antes de usar el tablero: el artefacto entrenado viaja dentro del wheel de `modelo-citas` y no se versiona en Git (ver [Paquete del modelo](#paquete-del-modelo-modelo-citas)).

Si el paso 4 falla o no se tiene acceso al remoto DVC, ver [Datos](#datos) para la alternativa manual.

## Estructura del proyecto

```text
src/                  código fuente (datos, features, modelos, entrenamiento, evaluación, tracking)
src/app/              tablero y backend FastAPI que consumen el paquete del modelo
model-package/        librería instalable `modelo-citas` con el modelo entrenado
notebooks/            análisis exploratorio
tests/                pruebas automatizadas (pytest)
config/model.yaml     hiperparámetros del reordenador supervisado
data/raw/, data/processed/   datos versionados con DVC (no van en Git)
reportes/             informes del curso
pyproject.toml, uv.lock   dependencias y entorno reproducible
```

## Uso

### Pruebas

```Shell
uv run pytest              # dentro del entorno del proyecto
uv run tox                 # además, en un entorno aislado
uv run tox -e smoke-model  # subconjunto rápido del modelo supervisado
```

### Análisis exploratorio

```Shell
uv run jupyter notebook notebooks/01_exploracion_datos.ipynb
```

### Línea base: TF-IDF + similitud coseno

Representa artículos y contextos como vectores TF-IDF y ordena por similitud coseno. No aprende de los datos etiquetados; es el piso de comparación para cualquier modelo supervisado.

```Shell
uv run python -m src.training.run_tfidf_baseline
uv run python -m src.training.run_tfidf_baseline --k 5 --limit 200  # opciones útiles
```

Referencia (validación, K=10): Recall\@10 = 0,2541, MRR\@10 = 0,1249.

### Modelo supervisado: reordenador lineal

Reordena el Top-N de TF-IDF con un `Pipeline` (`StandardScaler` + `LogisticRegression`) sobre cinco features de similitud y longitud. Los hiperparámetros están en [`config/model.yaml`](config/model.yaml), incluida la estrategia de negativos (`random` o `hard`).

```Shell
uv run python -m src.training.run_linear_reranker train
uv run python -m src.training.run_linear_reranker evaluate --model artifacts/<run_id>/model.joblib --split val
```

Cada corrida entrena en `train`, evalúa en `val` y guarda modelo + configuración + métricas en `artifacts/<run_id>/`. Usar `--split test` solo tras elegir configuración con validación. Esta es la vía de experimentación, con seguimiento en MLflow; el modelo que sirve el tablero se construye con el [paquete](#paquete-del-modelo-modelo-citas).

### Seguimiento de experimentos con MLflow

Todos los entrenamientos se registran vía `src/tracking/mlflow_setup.py` — no llamar a `mlflow` directamente desde scripts nuevos, para que los runs sigan siendo comparables. Se guardan en SQLite local (`mlflow.db`, ignorado por Git); para un servidor compartido basta con definir `MLFLOW_TRACKING_URI`.

```Shell
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Abrir <http://localhost:5000> para comparar runs.

### Paquete del modelo (`modelo-citas`)

El modelo se distribuye como librería instalable en [`model-package/`](model-package/). El wheel incluye el modelo entrenado y los metadatos de los artículos, así que instalarlo basta para predecir: no hace falta el dataset ni el repositorio.

```python
from modelo_citas import make_prediction

resultado = make_prediction(
    context="Recent work on neural machine translation with attention",
    top_k=5,
)
print(resultado["predictions"])
```

`make_prediction` devuelve `{"predictions": [...], "version": ..., "errors": None}`. Cada recomendación trae `posicion`, `paper_id`, `titulo`, `resumen`, `similitud` (probabilidad del reordenador) y `similitud_tfidf` (coseno del recuperador). `load_model()` carga el artefacto en memoria de forma explícita —útil al arrancar un servidor— y `describe()` devuelve la ficha técnica del modelo servido.

```Shell
uv run tox -c model-package -e train   # entrena y guarda modelo_citas/trained/modelo-citas-output<VERSION>.pkl
uv run tox -c model-package            # pruebas del paquete
uv run tox -c model-package -e build   # wheel en model-package/dist/
```

El artefacto `.pkl` no se versiona en Git: se regenera con `tox -e train` y se instala con `uv sync --reinstall-package modelo-citas`, que reconstruye el wheel con el modelo dentro. La versión vive en `model-package/modelo_citas/VERSION` y da nombre al artefacto, así que al subirla hay que reentrenar antes de construir el wheel.

Para comprobar que el wheel es autocontenido, instalarlo en un entorno limpio fuera del repositorio:

```Shell
uv run tox -c model-package -e build
pip install model-package/dist/modelo_citas-<VERSION>-py3-none-any.whl
python -c "from modelo_citas import make_prediction; print(make_prediction(context='neural machine translation attention', top_k=5))"
```

### Tablero del prototipo

`src/app/` sirve las recomendaciones del paquete `modelo-citas`: un backend FastAPI y un frontend que además muestra el estudio de datos (EDA), el desempeño del modelo y el diagnóstico de negativos.

```Shell
uv run python -m src.app.insights   # opcional: precalcula el EDA (~1 min); si se omite, se calcula en el primer arranque
uv run tablero                      # http://127.0.0.1:8000
```

También expone una API propia (`POST /api/recomendar`, `GET /api/insights`, `GET /api/ejemplo`, `GET /api/estado`), documentada en `http://127.0.0.1:8000/docs`.

## Datos

Los datos no se versionan en Git por su tamaño; se gestionan con DVC (`data/raw.dvc`, `data/processed.dvc`).

```Shell
uv run dvc pull              # descargar (remoto "publico", solo lectura, sin credenciales)
uv run dvc push -r <remoto>  # publicar (requiere un remoto propio con permiso de escritura)
uv run dvc status            # ver estado; un "in sync" no garantiza que el pull funcione
```

Los remotos `s3://` en `.dvc/config` pertenecen a cuentas AWS Academy aisladas entre sí: cada integrante escribe en la suya y `publico` es el único legible por todos. Las credenciales expiran al detener el Learner Lab (verificar con `aws sts get-caller-identity` antes de un push).

> El remoto `publico` es el remoto DVC predeterminado y de solo lectura para el equipo. Contiene tanto `data/raw` como `data/processed`, por lo que una clonación limpia puede recuperar todos los datos mediante `uv run dvc pull` sin credenciales adicionales.

### Remoto por SSH (`ssh-team`)

Además de los remotos S3 hay uno por SSH sobre la instancia compartida del equipo, con los datos completos (`data/raw` y `data/processed`). Requiere la llave privada del equipo (`maia_team`, pedirla a quien la generó) y configurar su ruta localmente — no se versiona en Git porque cada quien la guarda en un lugar distinto:

```Shell
uv run dvc remote modify --local ssh-team keyfile /ruta/a/maia_team
uv run dvc pull -r ssh-team
uv run dvc push -r ssh-team
```

`data/processed/` se deriva de `data/raw/` de forma determinista, por lo que puede regenerarse sin ningún remoto:

```Shell
uv run python -m src.data.make_processed
uv run python -m src.training.export_top100
```

### Alternativa manual (sin DVC)

```Shell
git clone https://github.com/nianlonggu/Local-Citation-Recommendation.git
cp Local-Citation-Recommendation/data/custom/* data/raw/
```

`data/raw/` debe quedar con `contexts.json`, `papers.json`, `train.json`, `val.json` y `test.json`.

## Dependencias

El proyecto usa `uv`; `pyproject.toml` declara las dependencias y `uv.lock` fija las versiones resueltas (ambos se versionan en Git y no se editan a mano).

```Shell
uv add <paquete>       # agregar
uv remove <paquete>    # quitar
uv sync                # instalar/actualizar el entorno tras un pull
uv lock                # re-resolver el lockfile
```

`modelo-citas` se resuelve desde la carpeta local `model-package/` mediante `[tool.uv.sources]`; sus propias dependencias se declaran en `model-package/requirements/requirements.txt`.

`requirements.txt` es un artefacto congelado para herramientas que aún esperan ese formato; se regenera, nunca se edita a mano:

```Shell
uv export --locked --no-dev --format requirements.txt --no-hashes --output-file requirements.txt
```

## Tecnologías

Python · uv · Git · DVC (Amazon S3) · scikit-learn · pandas · MLflow · FastAPI · setuptools · Jupyter · pytest / tox
