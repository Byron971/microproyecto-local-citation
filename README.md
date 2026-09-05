# Recomendación Local de Citas Académicas

Microproyecto desarrollado para la materia Proyecto: Desarrollo de Soluciones.

## Descripción

El proyecto busca desarrollar un prototipo de recomendación local de citas académicas mediante técnicas de aprendizaje automático.

El sistema recibe como entrada un contexto textual académico en inglés y busca generar un ranking de artículos candidatos potencialmente relevantes para ser citados.

Actualmente, el proyecto incluye versionamiento de datos con DVC, análisis exploratorio del conjunto de datos, una línea base TF-IDF evaluada y registrada en MLflow, y un tablero web que sirve ese modelo junto con los resultados del estudio de los datos.

## Fuente de datos

El proyecto utiliza como fuente principal el conjunto de datos disponible en:

[Local Citation Recommendation](https://github.com/nianlonggu/Local-Citation-Recommendation)

Los datos incluyen contextos locales de cita, información de artículos académicos y particiones para entrenamiento, validación y prueba.

Los archivos utilizados son:

- `contexts.json`
- `papers.json`
- `train.json`
- `val.json`
- `test.json`

## Estructura del proyecto

- `data/`: metadatos y versionamiento de datos mediante DVC.
- `data/raw/`: datos originales utilizados por el proyecto.
- `data/processed/`: espacio destinado a datos procesados.
- `notebooks/`: análisis exploratorio y experimentación.
- `src/`: código fuente del proyecto.
- `src/app/`: tablero y backend que sirven el modelo real.
- `reportes/`: informes y soportes del proyecto.
- `pyproject.toml`: configuración del proyecto y declaración de dependencias.
- `uv.lock`: versiones resueltas de las dependencias para garantizar reproducibilidad.

## Gestión de dependencias

El proyecto utiliza `uv` como gestor principal del entorno y las dependencias.

La fuente principal de dependencias es:

```text
pyproject.toml
```

Las versiones resueltas se almacenan en:

```text
uv.lock
```

El archivo `uv.lock` debe mantenerse versionado en Git para que todos los integrantes del equipo trabajen con el mismo entorno reproducible.

Las dependencias no deben modificarse manualmente en `uv.lock`.

## Instalación y ejecución local

### Requisitos previos

- Git
- `uv`

Python no necesita instalarse o administrarse manualmente para el flujo habitual del proyecto, ya que `uv` puede gestionar el entorno Python utilizado por el proyecto.

### 1. Clonar el repositorio

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

### 2. Instalar uv

#### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Después de la instalación, abrir una nueva terminal y verificar:

```powershell
uv --version
```

#### Linux / macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verificar la instalación:

```bash
uv --version
```

### 3. Crear y sincronizar el entorno

Desde la raíz del repositorio ejecutar:

```bash
uv sync
```

Este comando:

- lee las dependencias declaradas en `pyproject.toml`;
- utiliza las versiones registradas en `uv.lock`;
- crea o actualiza el entorno virtual `.venv`;
- instala las dependencias necesarias.

No es necesario ejecutar manualmente `pip install` ni activar `.venv` para utilizar los comandos del proyecto.

## Manejo de dependencias

### Agregar una dependencia

Por ejemplo:

```bash
uv add mlflow
```

`uv` actualizará automáticamente:

```text
pyproject.toml
uv.lock
```

### Eliminar una dependencia

```bash
uv remove nombre-del-paquete
```

### Actualizar el entorno

Después de obtener cambios del repositorio:

```bash
uv sync
```

### Actualizar el lockfile

Cuando sea necesario resolver nuevamente las dependencias:

```bash
uv lock
```

## requirements.txt

`pyproject.toml` y `uv.lock` son las fuentes oficiales para la gestión de dependencias del proyecto.

El archivo `requirements.txt` se conserva en el repositorio como un artefacto congelado de compatibilidad para herramientas de despliegue o servicios que todavía esperan este formato.

No debe editarse manualmente ni generarse mediante `pip freeze`.

Después de agregar, eliminar o actualizar dependencias con `uv`, debe regenerarse ejecutando:

```bash
uv export --locked --no-dev --format requirements.txt --no-hashes --output-file requirements.txt
```

## Obtener los datos

Los archivos de datos no se almacenan directamente en Git debido a su tamaño.

El proyecto utiliza DVC para mantener el versionamiento de los datos mediante:

```text
data/raw.dvc
```

### Obtener los datos desde la fuente original

Clonar el repositorio:

```bash
git clone https://github.com/nianlonggu/Local-Citation-Recommendation.git
```

Los archivos requeridos se encuentran en:

```text
Local-Citation-Recommendation/data/custom/
```

Deben copiarse hacia:

```text
data/raw/
```

#### Linux / macOS

```bash
cp Local-Citation-Recommendation/data/custom/* data/raw/
```

#### Windows (PowerShell)

```powershell
Copy-Item ".\Local-Citation-Recommendation\data\custom\*" ".\data\raw\" -Force
```

Al finalizar, `data/raw/` debe contener:

```text
contexts.json
papers.json
train.json
val.json
test.json
```

## Uso de DVC

Los datos están versionados mediante DVC.

El archivo:

```text
data/raw.dvc
```

contiene la referencia a la versión de los datos utilizada por el proyecto.

### Descargar los datos versionados

El remoto por defecto es `publico`, un bucket S3 expuesto por HTTPS y de **solo lectura**. No requiere credenciales de AWS, así que basta con:

```bash
uv run dvc pull
```

### Publicar datos nuevos

Como el remoto por defecto es de solo lectura, un `dvc push` debe indicar explícitamente un remoto sobre el que se tenga permiso de escritura:

```bash
uv run dvc push -r caicedo
```

Los remotos `s3://` declarados en `.dvc/config` pertenecen a cuentas distintas de AWS Academy. **Esas cuentas están aisladas entre sí**, de modo que ningún integrante puede leer el bucket de otro: cada quien escribe en el suyo, y `publico` es el único legible por todos.

Las credenciales de AWS Academy son temporales y caducan al detenerse el Learner Lab. Antes de un `dvc push`, conviene comprobarlas:

```bash
aws sts get-caller-identity
```

Para verificar el estado de los datos:

```bash
uv run dvc status
```

> **Advertencia.** `dvc status -c` no sirve como prueba de que los datos se puedan recuperar: sobre un bucket sin ningún permiso de lectura llega a reportar *«Cache and remote are in sync»*. Solo un `dvc pull` completo lo demuestra.

### Regenerar los datos procesados sin descargarlos

Todo el contenido de `data/processed/` se deriva de `data/raw/` de forma determinista, por lo que puede reconstruirse sin acceder a ningún remoto:

```bash
uv run python -m src.data.make_processed        # pares supervisados
uv run python -m src.training.export_top100     # Top-100 de candidatos TF-IDF
```

El resultado es idéntico byte a byte al versionado: al regenerarlo se obtiene el mismo hash que registra `data/processed.dvc` (`c345a8e4…`, 4 archivos, 50 247 436 bytes). Esto hace que el proyecto siga siendo reproducible aunque un remoto deje de estar disponible, algo esperable porque las cuentas de AWS Academy se desactivan al terminar el curso.

## Ejecutar el análisis exploratorio

Para iniciar Jupyter:

```bash
uv run jupyter notebook notebooks/
```

Abrir:

```text
notebooks/01_exploracion_datos.ipynb
```

El notebook contiene el análisis exploratorio inicial del conjunto de datos, incluyendo características de los textos, particiones y análisis de similitud entre contextos y artículos citados.

## Seguimiento de experimentos con MLflow

Todos los entrenamientos se registran en MLflow para poder comparar modelos con evidencia y no de memoria. La configuración está centralizada en `src/tracking/mlflow_setup.py`: **no se debe llamar a `mlflow` directamente desde los scripts de entrenamiento**, porque la comparación entre modelos solo funciona si todos los runs comparten experimento y nombres de métricas.

### Dónde se guardan los runs

Por defecto se usa una base **SQLite local** (`mlflow.db` en la raíz del repositorio) y una carpeta `mlartifacts/` para los archivos. Ambas están ignoradas por Git, así que cada integrante acumula sus propios runs sin ensuciar el historial.

> MLflow 3.x dejó el backend de archivos (`./mlruns`) en modo mantenimiento y lanza una excepción si se usa, por eso el proyecto usa SQLite.

Si más adelante se levanta un servidor compartido, basta con definir la variable de entorno `MLFLOW_TRACKING_URI`; el módulo la respeta sin cambiar código.

### Convención de nombres

| Elemento | Convención | Ejemplo |
|---|---|---|
| Experimento | Uno solo para todo el proyecto: `recomendacion-local-citas` | — |
| Run | `modelo[-variante]-YYYYmmdd-HHMMSS` (UTC) | `tfidf-bigramas-20260901-143512` |
| Etiquetas | `modelo` y `variante` | `modelo=tfidf` |
| Métricas | `recall_at_k` y `mrr`; el valor de K va como parámetro `k` | — |

Se usa **un solo experimento** para que la línea base y los modelos supervisados aparezcan en la misma tabla y se puedan ordenar por métrica.

### Cómo registrar un entrenamiento

```python
from src.evaluation.ranking_metrics import mean_reciprocal_rank, recall_at_k
from src.tracking.mlflow_setup import configure_mlflow, log_ranking_metrics, start_run

configure_mlflow()  # una vez al inicio del script

with start_run("tfidf", params={"max_features": 5000}):
    # ... entrenar y generar el ranking ...
    log_ranking_metrics(
        recall_at_k=recall_at_k(ranked_ids, relevant_ids, k=10),
        mrr=mean_reciprocal_rank(rankings),
        k=10,
    )
```

### Consultar los resultados

Para abrir la interfaz web de MLflow:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Y visitar [http://localhost:5000](http://localhost:5000). Ahí se pueden comparar runs lado a lado, ordenar por `recall_at_k` o `mrr`, y filtrar por la etiqueta `modelo`.

## Línea base: TF-IDF con similitud coseno

La línea base representa cada artículo (título + resumen) y cada contexto de cita como vectores TF-IDF, y ordena los artículos por similitud coseno con el contexto. No aprende de los ejemplos etiquetados: solo mide coincidencia léxica. Sirve como piso de comparación —  cualquier modelo supervisado debe superarla para justificarse.

Para ejecutarla y registrar el run en MLflow:

```bash
python -m src.training.run_tfidf_baseline
```

Opciones útiles:

```bash
# Evaluar con otra profundidad de ranking
python -m src.training.run_tfidf_baseline --k 5

# Prueba rápida sobre las primeras 200 consultas
python -m src.training.run_tfidf_baseline --limit 200

# Evaluar sobre la partición de prueba
python -m src.training.run_tfidf_baseline --split test
```

### Resultados de referencia

Sobre las 9.381 consultas de validación, contra los 19.776 artículos candidatos:

| Métrica | Valor |
|---|---|
| Recall@10 | 0,2541 |
| MRR@10 | 0,1249 |

Es decir, sin ningún entrenamiento, el artículo correcto aparece entre los 10 primeros en aproximadamente 1 de cada 4 consultas. La evaluación completa toma unos 20 segundos.

Ambas métricas se calculan **truncadas a K**, como es convención en recuperación de información: el ranking se corta en las K primeras posiciones antes de evaluarlas. Por eso su valor depende de `--k`, y el `k` empleado queda registrado como parámetro de cada run de MLflow. Al comparar corridas entre sí, hay que asegurarse de que usen el mismo K.

## Tablero del prototipo

La carpeta `src/app/` contiene el tablero del proyecto: un backend en FastAPI que **sirve el modelo real** y un frontend que muestra, además de las recomendaciones, la información obtenida en el estudio de los datos.

### 1. Precalcular la información del tablero

El tablero muestra el análisis exploratorio, la evaluación del modelo y el diagnóstico de negativos. Calcular todo eso tarda alrededor de un minuto —  sobre todo el conteo de bigramas en los 63.768 contextos—  así que se hace una sola vez y el resultado queda en `data/processed/dashboard_insights.json`:

```bash
uv run python -m src.app.insights
```

Si el archivo ya existe, el comando no hace nada. Para rehacerlo tras cambiar los datos o el modelo:

```bash
uv run python -m src.app.insights --force
```

Este paso es opcional: si el archivo no está, el backend lo calcula al arrancar y lo guarda. Precalcularlo solo evita esa espera en el primer arranque.

### 2. Levantar el tablero

```bash
uv run tablero
```

Equivale a:

```bash
uv run python -m uvicorn src.app.main:app --host 127.0.0.1 --port 8000
```

El arranque tarda unos segundos porque ajusta el TF-IDF sobre el corpus. Cuando la consola escribe `Backend listo`, abrir:

```text
http://127.0.0.1:8000
```

### 3. Probar el tablero

El panel izquierdo recibe un contexto académico en inglés y devuelve los artículos más pertinentes, con su título, su resumen y la similitud calculada.

El botón **«Usar un ejemplo real»** trae un contexto auténtico del corpus. Como se conoce la cita que le correspondía, el tablero marca con `✓` si el modelo la encontró e indica en qué posición quedó. Conviene tener presente el Recall@10 de 0,2541: el artículo correcto aparece entre los diez primeros en aproximadamente una de cada cuatro consultas.

Las tres pestañas inferiores muestran:

| Pestaña | Contenido |
|---|---|
| Estudio de los datos | Tamaños y particiones, nueve comprobaciones de calidad, longitudes de los textos, términos y bigramas frecuentes, señal léxica y artículos más citados. |
| Desempeño del modelo | Recall@K y MRR@K para K entre 1 y 100, con la lectura de por qué el margen está en el reordenamiento. |
| Diagnóstico de negativos | Similitud media y AUC de las tres poblaciones, con la explicación de por qué el muestreo aleatorio produce una tarea artificialmente fácil. |

La pestaña de diagnóstico de negativos necesita los pares supervisados de `data/processed/`. Si faltan, el tablero muestra un aviso en esa pestaña y el resto sigue funcionando.

### API

El backend expone además una API que puede usarse sin el frontend:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/estado` | Indica si el modelo está listo y con qué parámetros se cargó. |
| `POST` | `/api/recomendar` | Recibe `{"contexto": "...", "top_k": 10}` y devuelve el ranking. |
| `GET` | `/api/insights` | Toda la información que dibuja el tablero. |
| `GET` | `/api/ejemplo` | Un contexto real del corpus con su cita correcta. |

Ejemplo:

```bash
curl -X POST http://127.0.0.1:8000/api/recomendar \
  -H "Content-Type: application/json" \
  -d '{"contexto": "Recent work on neural machine translation has shown that attention mechanisms improve alignment quality.", "top_k": 5}'
```

La documentación interactiva de FastAPI queda en `http://127.0.0.1:8000/docs`.

## Dependencias principales

Actualmente el proyecto incluye como dependencias principales:

- DVC con soporte para Amazon S3
- Jupyter
- IPykernel
- Matplotlib
- Pandas 2.3.3
- Seaborn
- Scikit-learn 1.9.0
- FastAPI
- MLflow 3.15.1

Estas dependencias se declaran en `pyproject.toml` y sus versiones resueltas se registran en `uv.lock`.

Las herramientas utilizadas únicamente durante el desarrollo y las pruebas, como `pytest`, se gestionan mediante el grupo de dependencias de desarrollo de `uv` y no se incluyen en el `requirements.txt` exportado para compatibilidad y despliegue.

Para instalar también las dependencias de desarrollo se utiliza:

```bash
uv sync
```

Para ejecutar las pruebas:

```bash
uv run pytest
```

## Tecnologías

Utilizadas o configuradas durante el desarrollo:

- Python
- uv
- Git
- GitHub
- DVC
- Amazon S3
- Jupyter
- Pandas
- Matplotlib
- Seaborn
- Scikit-learn
- FastAPI
- MLflow
- pytest

Tecnologías contempladas para etapas posteriores:

- Docker

## Estado actual

Actualmente se encuentran implementados:

- estructura inicial del repositorio;
- control de versiones con Git;
- gestión reproducible de dependencias con `uv`;
- versionamiento de datos con DVC;
- obtención y almacenamiento local del dataset;
- análisis exploratorio inicial de los datos;
- notebook reproducible de exploración;
- seguimiento de experimentos preparado con MLflow;
- estructura inicial de pruebas automatizadas con pytest;
- línea base TF-IDF evaluada sobre validación y registrada en MLflow;
- diagnóstico del muestreo de negativos;
- exportación de los Top-100 candidatos como insumo del reordenador;
- tablero web que sirve el modelo real y publica los resultados del estudio de los datos.

El tablero de `src/app/` ya produce recomendaciones con el modelo entrenado y muestra las métricas obtenidas. Falta el reordenador supervisado de la segunda etapa: `src/features/` y `src/models/` están preparados para alojarlo.

Las siguientes etapas incorporarán procesamiento de datos, entrenamiento y evaluación del modelo, seguimiento de experimentos, empaquetado y despliegue.