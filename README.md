# Recomendación Local de Citas Académicas

## Descripción

Cuando una persona escribe un artículo académico necesita identificar trabajos previos que respalden una afirmación concreta. Encontrar la referencia adecuada entre miles de publicaciones puede requerir búsquedas repetitivas por palabras clave y revisión manual de numerosos documentos.

Este proyecto implementa un prototipo de recomendación local de citas académicas. A partir de un fragmento textual que representa el contexto donde debería aparecer una cita, el sistema recupera y ordena artículos potencialmente relevantes.

La solución fue desarrollada para la materia Proyecto: Desarrollo de Soluciones y combina procesamiento de lenguaje natural, aprendizaje automático, seguimiento experimental, empaquetamiento de modelos, API, tablero web, contenedores y despliegue en AWS.

Datos de origen:

[Local-Citation-Recommendation](https://github.com/nianlonggu/Local-Citation-Recommendation)

---

## Arquitectura general

El sistema está compuesto por las siguientes capas:

```text
Usuario
   |
   | HTTP :8080
   v
Dashboard web
Nginx
   |
   | /api/*
   v
FastAPI
   |
   v
Paquete modelo-citas
   |
   +-- Recuperación TF-IDF
   |
   +-- Reordenador lineal
   |
   v
Ranking de artículos académicos
```

Durante el despliegue con Docker Compose se ejecutan dos contenedores:

```text
microproyecto-citas-dashboard
    Nginx
    Puerto interno: 80
    Puerto del host: 8080

microproyecto-citas-api
    FastAPI + modelo-citas
    Puerto interno: 8000
    Puerto del host: 8000
```

El dashboard no se comunica con la API mediante la IP pública de la máquina. Nginx utiliza la red interna creada por Docker Compose y redirige las solicitudes `/api/*` hacia:

```text
http://api:8000
```

---

## Estructura del proyecto

```text
src/
    app/
        backend FastAPI y archivos estáticos del tablero
    data/
        procesamiento de datos
    evaluation/
        métricas y evaluación
    features/
        construcción de características
    models/
        lógica de modelos
    tracking/
        configuración centralizada de MLflow
    training/
        scripts de entrenamiento

model-package/
    paquete instalable modelo-citas

config/
    configuración de modelos

data/
    raw/
    processed/

notebooks/
    análisis exploratorio

tests/
    pruebas automatizadas

docs/
    documentación de usuario

reportes/
    reportes y evidencias del proyecto

Dockerfile
Dockerfile.dashboard
docker-compose.yml
nginx.conf
pyproject.toml
uv.lock
```

---

# Ejecución local

## Requisitos

Para ejecutar el proyecto localmente se recomienda tener instalados:

- Git
- uv
- Docker Desktop, si se desea ejecutar la versión contenerizada

Python es administrado por `uv`.

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

---

## 2. Instalar uv

Linux o macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## 3. Crear el entorno e instalar dependencias

```bash
uv sync
```

---

## 4. Recuperar los datos con DVC

El proyecto utiliza DVC para versionar los datos.

El remoto predeterminado es:

```text
publico
```

Este remoto es de solo lectura y puede utilizarse sin credenciales adicionales.

Ejecutar:

```bash
uv run dvc pull
```

También puede comprobarse el estado mediante:

```bash
uv run dvc status
```

Los archivos principales esperados en `data/raw/` son:

```text
contexts.json
papers.json
train.json
val.json
test.json
```

---

## 5. Ejecutar pruebas

```bash
uv run pytest
```

También puede utilizarse tox:

```bash
uv run tox
```

Prueba rápida del modelo supervisado:

```bash
uv run tox -e smoke-model
```

---

# Análisis exploratorio

El análisis exploratorio puede abrirse con:

```bash
uv run jupyter notebook notebooks/01_exploracion_datos.ipynb
```

El tablero también contiene una sección denominada:

```text
Estudio de los datos
```

que presenta indicadores y análisis del corpus utilizado.

---

# Línea base

La línea base utiliza:

```text
TF-IDF + similitud coseno
```

Los artículos y los contextos se representan mediante vectores TF-IDF y se ordenan según su similitud.

Ejecutar:

```bash
uv run python -m src.training.run_tfidf_baseline
```

Ejemplo con parámetros:

```bash
uv run python -m src.training.run_tfidf_baseline --k 5 --limit 200
```

Referencia obtenida sobre validación para K=10:

```text
Recall@10 = 0,2541
MRR@10    = 0,1249
```

---

# Modelo supervisado

El modelo supervisado implementa un reordenador lineal.

La arquitectura utilizada es:

```text
Recuperación TF-IDF
        |
        v
Top-N candidatos
        |
        v
Features de similitud y longitud
        |
        v
StandardScaler
        |
        v
LogisticRegression
        |
        v
Ranking final
```

Los hiperparámetros se encuentran en:

```text
config/model.yaml
```

El entrenamiento puede ejecutarse mediante:

```bash
uv run python -m src.training.run_linear_reranker train
```

La evaluación puede ejecutarse con:

```bash
uv run python -m src.training.run_linear_reranker evaluate --model artifacts/<run_id>/model.joblib --split val
```

Los experimentos compararon, entre otras configuraciones, dos estrategias de generación de negativos:

```text
random
hard
```

La estrategia seleccionada para el modelo final fue:

```text
random
```

porque obtuvo mejores resultados de ranking en validación.

---

# Seguimiento experimental con MLflow

Los experimentos se gestionan mediante:

```text
src/tracking/mlflow_setup.py
```

El nombre unificado del experimento es:

```text
recomendacion-local-citas
```

Por defecto, si no existe un servidor remoto, MLflow utiliza una base SQLite local:

```text
mlflow.db
```

y guarda artefactos en:

```text
mlartifacts/
```

Para utilizar MLflow localmente:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Luego abrir:

```text
http://localhost:5000
```

---

## Variable de entorno MLFLOW_TRACKING_URI

El proyecto soporta un servidor MLflow remoto mediante la variable:

```text
MLFLOW_TRACKING_URI
```

Ejemplo Linux:

```bash
export MLFLOW_TRACKING_URI=http://<IP_SERVIDOR>:8050
```

Ejemplo PowerShell:

```powershell
$env:MLFLOW_TRACKING_URI="http://<IP_SERVIDOR>:8050"
```

Si esta variable no está definida, el proyecto utiliza automáticamente el backend SQLite local.

`MLFLOW_TRACKING_URI` se utiliza para entrenamiento y seguimiento de experimentos.

No es una variable obligatoria para ejecutar la API o el dashboard contenerizados.

---

# Paquete del modelo

El modelo utilizado por la aplicación se distribuye como un paquete instalable denominado:

```text
modelo-citas
```

ubicado en:

```text
model-package/
```

Ejemplo de uso:

```python
from modelo_citas import make_prediction

resultado = make_prediction(
    context="Recent work on neural machine translation with attention",
    top_k=5,
)

print(resultado["predictions"])
```

Cada recomendación incluye información como:

```text
posicion
paper_id
titulo
resumen
similitud
similitud_tfidf
```

---

## Entrenamiento del paquete

Para generar manualmente el artefacto:

```bash
uv run tox -c model-package -e train
```

Después puede reinstalarse el paquete con:

```bash
uv sync --reinstall-package modelo-citas
```

El modelo entrenado se almacena dentro de:

```text
model-package/modelo_citas/trained/
```

con un nombre basado en la versión del paquete.

Ejemplo:

```text
modelo-citas-output0.1.0.pkl
```

El archivo `.pkl` no se versiona en Git.

---

## Construcción del wheel

```bash
uv run tox -c model-package -e build
```

El wheel resultante queda en:

```text
model-package/dist/
```

---

# API

El backend utiliza FastAPI.

Entre sus endpoints principales se encuentran:

```text
GET  /api/estado
GET  /api/insights
GET  /api/ejemplo
POST /api/recomendar
```

Cuando se ejecuta localmente, la documentación automática de FastAPI puede consultarse en:

```text
http://127.0.0.1:8000/docs
```

---

# Tablero web

El tablero permite:

- introducir manualmente un contexto de cita;
- utilizar un ejemplo real del corpus;
- solicitar recomendaciones;
- seleccionar la cantidad de resultados;
- consultar títulos y resúmenes;
- visualizar el puntaje de relevancia;
- identificar si la cita correcta quedó dentro del ranking;
- consultar análisis de datos;
- visualizar desempeño del modelo;
- consultar diagnóstico de negativos.

El manual de usuario se encuentra en:

```text
docs/manual_usuario.md
```

---

# Contenerización

La solución utiliza dos imágenes Docker independientes.

---

## Contenedor de API

Archivo:

```text
Dockerfile
```

Imagen:

```text
microproyecto-citas-api:0.1.0
```

El Dockerfile:

1. instala `uv`;
2. instala las dependencias;
3. copia el proyecto;
4. recupera los datos mediante DVC;
5. genera el artefacto entrenado de `modelo-citas`;
6. vuelve a sincronizar el paquete para incluir el artefacto;
7. inicia FastAPI mediante Uvicorn.

El entrenamiento del modelo durante el build es importante porque el archivo `.pkl` no se almacena en Git.

La API escucha dentro del contenedor en:

```text
8000
```

---

## Contenedor del dashboard

Archivo:

```text
Dockerfile.dashboard
```

Imagen:

```text
microproyecto-citas-dashboard:0.1.0
```

El contenedor utiliza:

```text
nginx:alpine
```

y sirve los archivos estáticos del tablero.

Nginx escucha internamente en:

```text
80
```

---

# Docker Compose

Los dos servicios se orquestan mediante:

```text
docker-compose.yml
```

Servicios:

```text
api
dashboard
```

El servicio `api` posee un healthcheck sobre:

```text
http://127.0.0.1:8000/api/estado
```

El dashboard tiene la dependencia:

```text
service_healthy
```

por lo que Docker Compose espera a que la API esté saludable antes de iniciar el dashboard.

---

## Construir las imágenes

```bash
docker compose build
```

Para construir únicamente la API:

```bash
docker compose build api --progress=plain
```

---

## Levantar los servicios

```bash
docker compose up -d
```

---

## Verificar los contenedores

```bash
docker compose ps
```

El estado esperado es similar a:

```text
microproyecto-citas-api        Up (...) (healthy)
microproyecto-citas-dashboard  Up (...)
```

---

## Consultar logs

```bash
docker compose logs
```

Logs de ambos servicios:

```bash
docker compose logs --no-color --tail=40 api dashboard
```

Para comprobar solicitudes reales de inferencia:

```bash
docker compose logs --no-color api | grep "POST"
```

Una recomendación correcta desde el tablero debe generar una respuesta similar a:

```text
POST /api/recomendar HTTP/1.1" 200 OK
```

---

## Detener los servicios

```bash
docker compose down
```

---

# Puertos

La configuración actual utiliza:

| Servicio | Puerto del contenedor | Puerto del host | Uso |
|---|---:|---:|---|
| Dashboard Nginx | 80 | 8080 | Interfaz web |
| FastAPI | 8000 | 8000 | API |
| MLflow remoto | 8050 | 8050 | Seguimiento experimental, cuando se utiliza |

Para acceder al tablero desplegado:

```text
http://<IP_PUBLICA_EC2>:8080
```

La API no necesita exponerse públicamente para que el tablero funcione, ya que Nginx se comunica con ella mediante la red interna de Docker utilizando:

```text
api:8000
```

---

# Despliegue en AWS EC2

La Entrega 3 despliega la solución contenerizada en una instancia Amazon EC2.

La arquitectura es:

```text
Internet
   |
   | HTTP :8080
   v
Amazon EC2
   |
   +-----------------------------+
   | Docker Compose              |
   |                             |
   | Dashboard / Nginx           |
   | container :80               |
   | host      :8080             |
   |             |               |
   |             | /api/*        |
   |             v               |
   | FastAPI                     |
   | container :8000             |
   |                             |
   +-----------------------------+
```

---

## Configuración utilizada en la Entrega 3

La infraestructura utilizada durante la validación fue:

```text
Proveedor:          Amazon Web Services
Servicio:           EC2
Sistema operativo:  Ubuntu Server 24.04 LTS
Tipo de instancia:  t3.small
Almacenamiento:     20 GiB gp3
Orquestación:       Docker Compose
```

La dirección IP pública de una instancia de AWS Academy puede cambiar si la instancia se detiene y vuelve a iniciar.

Por esta razón, la documentación utiliza:

```text
<IP_PUBLICA_EC2>
```

en lugar de almacenar permanentemente una IP específica.

---

# Reglas de seguridad recomendadas

El grupo de seguridad de EC2 debe permitir únicamente los puertos necesarios.

Para el entorno académico utilizado en este proyecto:

```text
Puerto 22 / TCP
Uso: SSH
Origen recomendado: Mi IP

Puerto 8080 / TCP
Uso: Dashboard
Origen recomendado: Mi IP
```

No es necesario abrir públicamente el puerto `8000` para que el dashboard pueda consumir la API.

La comunicación Nginx -> FastAPI ocurre dentro de la red Docker.

---

# Crear una instancia EC2

Configuración utilizada:

```text
Ubuntu Server 24.04 LTS
Arquitectura x86_64
t3.small
20 GiB gp3
IP pública habilitada
```

También debe crearse o seleccionarse un par de claves SSH.

Ejemplo:

```text
microproyecto-citas-key.pem
```

La clave privada debe mantenerse únicamente en el equipo del usuario.

Nunca debe copiarse al repositorio.

---

# Conectarse por SSH

Ejemplo:

```bash
ssh -i /ruta/microproyecto-citas-key.pem ubuntu@<DNS_PUBLICO_EC2>
```

Desde PowerShell en Windows puede utilizarse una ruta como:

```powershell
ssh -i "$HOME\Downloads\microproyecto-citas-key.pem" ubuntu@<DNS_PUBLICO_EC2>
```

---

# Preparar EC2

Actualizar los paquetes:

```bash
sudo apt update
```

Instalar Docker y Docker Compose:

```bash
sudo apt install -y docker.io docker-compose-v2
```

Habilitar Docker:

```bash
sudo systemctl enable --now docker
```

Verificar:

```bash
docker --version
docker compose version
git --version
```

---

# Clonar el proyecto en EC2

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

Si se está trabajando sobre una rama específica:

```bash
git branch --show-current
```

Para actualizar posteriormente el código:

```bash
git pull
```

---

# Construir la solución en EC2

Primero comprobar la configuración:

```bash
docker compose config --quiet
```

Construir:

```bash
docker compose build
```

El Dockerfile de la API ejecuta durante la construcción:

```text
DVC pull
        |
        v
data/raw
        |
        v
train_pipeline
        |
        v
modelo-citas-output<VERSION>.pkl
        |
        v
paquete modelo-citas instalado
```

Esto permite que la imagen final sea capaz de iniciar la API con el modelo entrenado disponible.

---

# Iniciar el despliegue

```bash
docker compose up -d
```

Verificar:

```bash
docker compose ps
```

Estado esperado:

```text
microproyecto-citas-api        Up (...) (healthy)
microproyecto-citas-dashboard  Up (...)
```

---

# Comprobar la API en EC2

Desde la propia instancia:

```bash
curl http://127.0.0.1:8000/api/estado
```

La respuesta debe contener:

```json
{
  "listo": true
}
```

El objeto también puede incluir información del modelo cargado, número de artículos, configuración y versión.

---

# Comprobar el dashboard desde un navegador externo

Abrir:

```text
http://<IP_PUBLICA_EC2>:8080
```

La interfaz debe mostrar:

```text
Modelo listo
```

Una validación funcional completa consiste en:

1. abrir el dashboard desde un navegador externo;
2. pulsar `Usar un ejemplo real`;
3. comprobar que aparece un contexto del corpus;
4. pulsar `Recomendar citas`;
5. comprobar que aparece el ranking de artículos;
6. revisar que títulos, posiciones, similitudes y resúmenes sean visibles.

---

# Validar la inferencia mediante logs

Después de realizar una recomendación desde el navegador:

```bash
docker compose logs --no-color api | grep "POST"
```

Debe aparecer una línea similar a:

```text
POST /api/recomendar HTTP/1.1" 200 OK
```

Esto confirma el flujo:

```text
Navegador
   |
   v
Nginx
   |
   v
FastAPI
   |
   v
modelo-citas
   |
   v
ranking
   |
   v
respuesta HTTP 200
```

---

# Variables de entorno del despliegue

## Variables obligatorias

La configuración actual de Docker Compose no requiere variables de entorno obligatorias para ejecutar:

```text
api
dashboard
```

El modelo y la configuración necesaria se construyen dentro de la imagen.

Los datos utilizados durante el build se recuperan mediante el remoto DVC público.

---

## Variables opcionales

Para seguimiento experimental mediante un servidor MLflow remoto:

```text
MLFLOW_TRACKING_URI
```

Ejemplo:

```bash
export MLFLOW_TRACKING_URI=http://<IP_MLFLOW>:8050
```

Esta variable no es necesaria para servir recomendaciones desde la API.

---

# Credenciales y secretos

No deben versionarse:

```text
*.pem
credenciales de AWS
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN
contraseñas
tokens
archivos .env con secretos
```

Las credenciales temporales de AWS Academy se utilizan únicamente en el entorno local o de laboratorio cuando son necesarias.

El despliegue de este proyecto no requiere almacenar credenciales AWS dentro de las imágenes Docker.

El remoto DVC utilizado durante el build es:

```text
publico
```

y es de solo lectura.

---

# Evidencias de despliegue

Las evidencias de la Entrega 3 se almacenan en:

```text
reportes/reporte03/
```

Entre las evidencias del despliegue en AWS se encuentran:

```text
issue#31_aws_ec2_infraestructura.png
issue#31_aws_contenedores_activos.png
issue#31_aws_logs_post_recomendacion.png
issue#31_aws_recomendacion_real.png
```

Estas evidencias documentan:

- infraestructura EC2;
- instancia en ejecución;
- comprobaciones de estado;
- contenedores activos;
- API saludable;
- puertos publicados;
- solicitud POST de inferencia con respuesta HTTP 200;
- recomendación real ejecutada desde un navegador externo.

---

# Gestión de datos con DVC

Los datos no se almacenan directamente en Git debido a su tamaño.

Archivos DVC principales:

```text
data/raw.dvc
data/processed.dvc
```

Descargar los datos:

```bash
uv run dvc pull
```

Remoto público:

```text
publico
```

También existen remotos utilizados por integrantes del equipo para escritura.

Las credenciales de esos remotos no deben versionarse.

---

## Regenerar datos procesados

```bash
uv run python -m src.data.make_processed
uv run python -m src.training.export_top100
```

---

## Alternativa manual sin DVC

```bash
git clone https://github.com/nianlonggu/Local-Citation-Recommendation.git
```

Después copiar los archivos requeridos desde el dataset original hacia:

```text
data/raw/
```

---

# Dependencias

El proyecto utiliza `uv`.

Las dependencias se declaran en:

```text
pyproject.toml
```

y sus versiones resueltas se fijan en:

```text
uv.lock
```

Agregar una dependencia:

```bash
uv add <paquete>
```

Eliminar:

```bash
uv remove <paquete>
```

Sincronizar:

```bash
uv sync
```

Actualizar el lockfile:

```bash
uv lock
```

---

# requirements.txt

`requirements.txt` se mantiene como artefacto de compatibilidad para herramientas que todavía esperan ese formato.

Puede regenerarse mediante:

```bash
uv export --locked --no-dev --format requirements.txt --no-hashes --output-file requirements.txt
```

No debe editarse manualmente si puede regenerarse desde `pyproject.toml` y `uv.lock`.

---

# Tecnologías utilizadas

```text
Python
uv
Git
GitHub
DVC
Amazon S3
AWS EC2
Docker
Docker Compose
Nginx
FastAPI
Uvicorn
scikit-learn
pandas
MLflow
SQLite
Jupyter
pytest
tox
setuptools
```

---

# Flujo reproducible resumido

## Desarrollo local

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation

uv sync
uv run dvc pull
uv run pytest
```

---

## Ejecución contenerizada local

```bash
docker compose build
docker compose up -d
docker compose ps
```

Abrir:

```text
http://127.0.0.1:8080
```

---

## Despliegue en EC2

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation

docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Abrir externamente:

```text
http://<IP_PUBLICA_EC2>:8080
```

Comprobar logs:

```bash
docker compose logs --no-color api | grep "POST"
```

---

# Estado de la solución

La solución implementa actualmente:

- recuperación de candidatos mediante TF-IDF;
- reordenamiento supervisado;
- evaluación con métricas de ranking;
- comparación experimental con MLflow;
- empaquetamiento del modelo;
- API FastAPI;
- tablero interactivo;
- manual de usuario;
- pruebas automatizadas;
- contenerización de API y dashboard;
- orquestación mediante Docker Compose;
- healthcheck de la API;
- comunicación interna mediante Nginx;
- despliegue funcional en Amazon EC2;
- acceso desde navegador externo;
- evidencia reproducible del flujo de inferencia.

El sistema debe considerarse un prototipo académico. Las recomendaciones dependen del corpus utilizado, de la etapa de recuperación y del modelo entrenado, y no sustituyen la revisión académica de las referencias por parte del usuario.