# Recomendación Local de Citas Académicas

Microproyecto desarrollado para la materia Proyecto: Desarrollo de Soluciones.

## Descripción

El proyecto busca desarrollar un prototipo de recomendación local de citas académicas mediante técnicas de aprendizaje automático.

El sistema recibe como entrada un contexto textual académico en inglés y busca generar un ranking de artículos candidatos potencialmente relevantes para ser citados.

Actualmente, el proyecto incluye versionamiento de datos con DVC, análisis exploratorio del conjunto de datos y una maqueta funcional compuesta por un frontend y un backend desarrollado en FastAPI.

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
- `maqueta/`: frontend y backend mínimo del prototipo.
- `src/`: código fuente del proyecto.
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

La configuración de los remotos DVC no se almacena de forma compartida en el repositorio. Cada integrante debe configurar localmente un remoto DVC al que tenga acceso antes de utilizar operaciones como:

```bash
uv run dvc pull
```

o:

```bash
uv run dvc push
```

Para verificar el estado de los datos:

```bash
uv run dvc status
```

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

## Maqueta del prototipo

La carpeta `maqueta/` contiene una maqueta funcional de la interfaz propuesta para el recomendador local de citas.

Está compuesta por:

- frontend desarrollado con HTML, CSS y JavaScript;
- backend mínimo desarrollado con FastAPI;
- endpoint `POST /predict`.

En el estado actual, la maqueta todavía no utiliza un modelo de recomendación entrenado.

El endpoint devuelve recomendaciones fijas:

- `Paper A`: 0.91
- `Paper B`: 0.84
- `Paper C`: 0.76

Esto permite validar el flujo:

```text
Usuario
   ↓
Frontend
   ↓
POST /predict
   ↓
FastAPI
   ↓
Respuesta
   ↓
Frontend
```

### 1. Levantar el backend

Desde la raíz del proyecto:

```bash
uv run maqueta-back
```

El backend quedará disponible en:

```text
http://127.0.0.1:8000
```

### 2. Levantar el frontend

En otra terminal:

```bash
uv run maqueta-front
```

El frontend quedará disponible en:

```text
http://localhost:3000
```

### 3. Probar la maqueta

Abrir:

```text
http://localhost:3000
```

Escribir un contexto académico en inglés y presionar:

```text
Recommend citations
```

El frontend enviará el contexto al endpoint:

```text
http://localhost:8000/predict
```

y mostrará las recomendaciones devueltas por el backend.

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
- maqueta del frontend;
- backend mínimo en FastAPI;
- comunicación funcional entre frontend y backend.
- seguimiento de experimentos preparado con MLflow;
- estructura inicial de pruebas automatizadas con pytest;

La maqueta permite probar el flujo completo de la aplicación, pero todavía utiliza recomendaciones fijas y no incorpora un modelo de aprendizaje automático entrenado.

Las siguientes etapas incorporarán procesamiento de datos, entrenamiento y evaluación del modelo, seguimiento de experimentos, empaquetado y despliegue.