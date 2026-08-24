# Recomendación Local de Citas Académicas

Microproyecto desarrollado para la materia Proyecto: Desarrollo de Soluciones.

## Descripción

El proyecto busca desarrollar un prototipo de recomendación local de citas académicas mediante técnicas de aprendizaje automático.

El sistema recibe como entrada un contexto textual académico en inglés y busca generar un ranking de artículos candidatos potencialmente relevantes para ser citados.

Actualmente, el proyecto incluye el versionamiento de los datos con DVC, un análisis exploratorio del conjunto de datos y una maqueta funcional de la interfaz con un backend desarrollado en FastAPI.

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

- `data/`: metadatos y versionamiento de los datos mediante DVC.
- `data/raw/`: datos originales utilizados por el proyecto.
- `data/processed/`: espacio destinado a datos procesados.
- `notebooks/`: análisis exploratorio y experimentación.
- `maqueta/`: interfaz del prototipo y backend mínimo en FastAPI.
- `src/`: código fuente del proyecto.
- `reportes/`: informes y soportes del proyecto.
- `requirements.txt`: dependencias necesarias para ejecutar el proyecto.
- `pyproject.toml`: configuración del proyecto Python.

## Instalación y ejecución local

### Requisitos previos

- Python 3.14 o superior
- Git

### 1. Clonar el repositorio

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

### 2. Instalar dependencias

El proyecto utiliza `pip` y el archivo `requirements.txt` para instalar las dependencias.

#### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

#### Windows (PowerShell)

Crear el entorno virtual:

```powershell
python -m venv .venv
```

Si PowerShell bloquea la ejecución del script de activación por la política de ejecución, habilitarla únicamente para la sesión actual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Activar el entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instalar las dependencias:

```powershell
python -m pip install -r requirements.txt
```

#### Windows (CMD)

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### 3. Obtener los datos

Los archivos de datos no se almacenan directamente en Git debido a su tamaño.

El proyecto utiliza DVC para mantener el versionamiento de los datos mediante el archivo `data/raw.dvc`.

Para obtener los datos directamente desde la fuente original, se puede clonar el repositorio:

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

### Uso de DVC

Los datos están versionados mediante DVC.

El archivo:

```text
data/raw.dvc
```

contiene la referencia a la versión de los datos utilizada por el proyecto.

La configuración de los remotos DVC no se almacena de forma compartida en este repositorio. Cada integrante debe configurar localmente un remoto al que tenga acceso antes de utilizar comandos como `dvc pull` o `dvc push`.

Para verificar el estado local de los datos:

```bash
dvc status
```

## Ejecutar el análisis exploratorio

Con el entorno virtual activado:

```bash
jupyter notebook notebooks/
```

Abrir el notebook:

```text
notebooks/01_exploracion_datos.ipynb
```

El notebook contiene el análisis exploratorio inicial del conjunto de datos, incluyendo características de los textos, particiones y análisis de similitud entre contextos y artículos citados.

## Maqueta del prototipo

La carpeta `maqueta/` contiene una maqueta de la interfaz propuesta para el recomendador local de citas.

La maqueta está compuesta por:

- Un frontend desarrollado con HTML, CSS y JavaScript.
- Un backend mínimo desarrollado con FastAPI.
- Un endpoint `/predict` que recibe un contexto de cita.

En el estado actual, la maqueta no utiliza todavía un modelo de recomendación entrenado.

El endpoint devuelve recomendaciones fijas:

- `Paper A`: 0.91
- `Paper B`: 0.84
- `Paper C`: 0.76

Esto permite validar el flujo completo:

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

Con el entorno virtual activado:

```bash
python -m uvicorn maqueta.main:app --host 127.0.0.1 --port 8000
```

El backend quedará disponible en:

```text
http://127.0.0.1:8000
```

### 2. Levantar el frontend

Abrir una segunda terminal, activar el entorno virtual y ejecutar:

```bash
python -m http.server 3000 --directory maqueta
```

El frontend quedará disponible en:

```text
http://localhost:3000
```

### 3. Probar la maqueta

Abrir en el navegador:

```text
http://localhost:3000
```

Escribir un contexto académico en inglés y presionar:

```text
Recommend citations
```

El frontend envía el contexto al endpoint:

```text
http://localhost:8000/predict
```

y muestra las recomendaciones devueltas por el backend.

## Dependencias principales

Las dependencias del proyecto se encuentran registradas en `requirements.txt` e incluyen:

- DVC con soporte para Amazon S3
- Jupyter
- IPykernel
- Matplotlib
- Pandas
- Seaborn
- Scikit-learn
- FastAPI

## Tecnologías

Utilizadas o configuradas durante el desarrollo:

- Python
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

Tecnologías contempladas para etapas posteriores del microproyecto:

- MLflow
- Docker

## Estado actual

Actualmente se encuentran implementados:

- Estructura inicial del repositorio.
- Control de versiones con Git.
- Versionamiento de los datos con DVC.
- Obtención y almacenamiento local del dataset.
- Análisis exploratorio inicial de los datos.
- Notebook reproducible de exploración.
- Maqueta del frontend.
- Backend mínimo en FastAPI.
- Comunicación funcional entre frontend y backend.

La maqueta permite probar el flujo completo de la aplicación, pero todavía utiliza recomendaciones fijas y no incorpora un modelo de aprendizaje automático entrenado.

Las siguientes etapas del proyecto incorporarán el procesamiento de datos, entrenamiento y evaluación del modelo, seguimiento de experimentos, empaquetado y despliegue.