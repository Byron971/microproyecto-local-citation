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