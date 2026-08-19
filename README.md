# Recomendación Local de Citas Académicas

Microproyecto desarrollado para la materia Proyecto: Desarrollo de Soluciones.

## Descripción

El proyecto busca desarrollar un prototipo de recomendación local de citas académicas mediante técnicas de aprendizaje automático.

El sistema recibirá como entrada un contexto textual académico en inglés y generará un ranking de artículos candidatos potencialmente relevantes para ser citados.

## Fuente de datos

El proyecto utiliza como fuente principal el conjunto de datos disponible en el repositorio:

Local Citation Recommendation

https://github.com/nianlonggu/Local-Citation-Recommendation

Los datos incluyen contextos locales de cita, información de artículos académicos y particiones para entrenamiento, validación y prueba.

## Estructura del proyecto

- `data/raw/`: datos originales.
- `data/processed/`: datos procesados.
- `notebooks/`: análisis exploratorio y experimentación.
- `src/`: código fuente del proyecto.
- `reports/`: resultados y soportes.
- `reports/figures/`: gráficas generadas durante el análisis.

## Instalación y ejecución local

### Requisitos previos

- Python 3.14 o superior
- [uv](https://docs.astral.sh/uv/) para la gestión del entorno y las dependencias (alternativamente puede usarse `pip`)
  - [Guía de instalación de uv](https://docs.astral.sh/uv/getting-started/installation/)
  - [uv sync (gestión de entornos y dependencias)](https://docs.astral.sh/uv/concepts/projects/sync/)
- Git

### 1. Clonar el repositorio

```bash
git clone <url-de-este-repositorio>
cd microproyecto-local-citation
```

### 2. Instalar dependencias

Con `uv`:

```bash
uv sync
```

Alternativamente, con `pip`:

**Linux / macOS**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell bloquea la ejecución del script de activación (error de política de ejecución), habilitarla para la sesión actual con:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
> ```

**Windows (CMD)**

```bat
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

### 3. Obtener los datos

Los datos **no** se incluyen en este repositorio. Deben obtenerse desde el repositorio [Local-Citation-Recommendation](https://github.com/nianlonggu/Local-Citation-Recommendation), puntualmente desde su carpeta `data/custom`, y ubicarse en la carpeta `data/raw/` de este proyecto.

1. Clonar (o descargar) el repositorio de datos:

   ```bash
   git clone https://github.com/nianlonggu/Local-Citation-Recommendation.git
   ```

2. Copiar el contenido de `Local-Citation-Recommendation/data/custom/` hacia `data/raw/` en este proyecto:

   ```bash
   cp Local-Citation-Recommendation/data/custom/* data/raw/
   ```

3. Verificar que `data/raw/` quede con los archivos: `contexts.json`, `papers.json`, `train.json`, `val.json` y `test.json`.

> Si se cuenta con acceso al remoto S3 configurado en DVC (`aws-remote`), los datos ya versionados también pueden recuperarse ejecutando `dvc pull`.

### 4. Ejecutar el proyecto

```bash
uv run jupyter notebook notebooks/
```

## Tecnologías

- Python
- Git
- DVC
- Amazon S3
- Scikit-learn
- MLflow
- FastAPI
- Docker

## Estado actual

Proyecto en fase de preparación de datos e infraestructura de versionamiento.