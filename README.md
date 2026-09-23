# Recomendación Local de Citas Académicas

## Descripción

Cuando una persona escribe un artículo académico necesita identificar trabajos previos que respalden una afirmación concreta. Encontrar la referencia adecuada entre miles de publicaciones puede requerir búsquedas repetitivas por palabras clave y revisión manual de numerosos documentos.

Este proyecto implementa un prototipo de recomendación local de citas académicas. A partir de un fragmento textual que representa el contexto donde debería aparecer una cita, el sistema recupera y ordena artículos potencialmente relevantes.

La solución fue desarrollada para la materia Proyecto: Desarrollo de Soluciones y combina procesamiento de lenguaje natural, aprendizaje automático, seguimiento experimental, empaquetamiento de modelos, API, tablero web, contenedores y despliegue en AWS.

El repositorio incluye además un segundo frente de trabajo: la evaluación comparativa de modelos de lenguaje comerciales y open-weight para la clasificación de la **función de cita** en nueve categorías. Ese frente tiene su propio pipeline de prompts, ejecución, métricas y anotación, y se documenta más abajo.

Datos de origen:

[Local-Citation-Recommendation](https://github.com/nianlonggu/Local-Citation-Recommendation)

---

## Video de síntesis

Presentación del proyecto en 9 minutos: problema y contexto, modelos construidos,
demostración del tablero, despliegue y conclusiones.

**[Ver el video](reportes/reporte03/video_sintesis_entrega3.mp4)** — GitHub lo reproduce
directamente en el navegador al abrir el archivo.

El guion narrado se conserva en [`docs/video_sintesis_entrega3_literal.md`](docs/video_sintesis_entrega3_literal.md).

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
        backend FastAPI, lectura de insights y archivos estáticos del tablero
    data/
        procesamiento de datos y construcción del piloto de función de cita
    evaluation/
        métricas de ranking, diagnóstico de negativos, anotación
        commercial/
            evaluación de LLM comerciales y open-weight
    tracking/
        configuración centralizada de MLflow
    training/
        scripts de entrenamiento y cálculo de insights del tablero
    config.py
        configuración del experimento

model-package/
    paquete instalable modelo-citas
        models/        TF-IDF, reordenador lineal, modelo de citas
        processing/    features, pares de entrenamiento, validación
        config/        hiperparámetros del modelo
        train_pipeline.py
    tests/
        pruebas del modelo empaquetado

config/
    model.yaml                    hiperparámetros del modelo
    citation_eval.env.example     variables de entorno de los proveedores
    prompts/                      prompts versionados de función de cita

annotations/
    citation_function/
        artefactos de validación manual y gold provisional

data/
    raw/
    processed/
        dashboard_insights.json   único archivo procesado versionado en Git

notebooks/
    análisis exploratorio

scripts/
    utilidades de corrida (por ejemplo, open-weight local)

tests/
    pruebas del repositorio: API, evaluación, proveedores, anotación

docs/
    documentación de usuario y de los frentes de evaluación

reportes/
    reportes y evidencias del proyecto

.github/workflows/
    reporte03.yml            compila y valida el PDF del reporte
    evaluacion-citas.yml     ejecuta las pruebas del frente de evaluación

Dockerfile
Dockerfile.dashboard
docker-compose.yml
nginx.conf
pyproject.toml
uv.lock
```

---

## Separación de responsabilidades

La lógica del modelo vive en un único lugar: el paquete `modelo-citas`. El repositorio no duplica esa lógica, sino que la consume.

```text
model-package/modelo_citas/     lo que se entrena y se despliega
    models/tfidf_baseline.py    recuperación TF-IDF
    models/linear_reranker.py   reordenador lineal
    models/citation_model.py    modelo de extremo a extremo
    processing/features.py      features de pares contexto-artículo
    processing/pairs.py         pares de entrenamiento (random y hard)
    config/core.py              ModelConfig, hiperparámetros validados

src/                            lo que experimenta, mide y sirve
    config.py                   ExperimentConfig hereda de ModelConfig
                                y añade data_dir y output_dir
    training/                   corridas, MLflow, comparación de variantes
    evaluation/                 métricas de ranking y diagnóstico
    app/                        API y tablero
```

Dos consecuencias prácticas de esta separación:

- `src/config.ExperimentConfig` **hereda** de `modelo_citas.config.core.ModelConfig` en lugar de repetir sus campos, de modo que el artefacto que se mide y el que se despliega aceptan exactamente los mismos hiperparámetros.
- Los indicadores del tablero se calculan fuera de la API. `src/training/build_insights.py` genera `data/processed/dashboard_insights.json` (requiere `data/raw` y scikit-learn), y `src/app/insights.py` solamente lee ese archivo. Por eso la imagen de la API no necesita el dataset ni las dependencias de cómputo científico.
- El modelo cruza esa frontera como **wheel publicado**, no como código compartido. `model-package/` es donde se desarrolla y entrena; producción instala el paquete ya construido desde S3 y nunca ve ese directorio.

Para regenerar los insights del tablero:

```bash
uv run --group research python -m src.training.build_insights
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

`uv sync` instala únicamente lo necesario para ejecutar la API y el tablero. Incluye la descarga del wheel `modelo-citas` desde S3, de unos 60 MB, que ya trae el modelo entrenado. Las herramientas de investigación (DVC, MLflow, Jupyter, pandas, scikit-learn, matplotlib) están en el grupo opcional `research`:

```bash
uv sync --group research
```

Este grupo es necesario para recuperar datos con DVC, entrenar, evaluar y regenerar los insights del tablero.

---

## 4. Recuperar los datos con DVC

El proyecto utiliza DVC para versionar los datos. Requiere el grupo `research`.

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

Las pruebas están repartidas según la separación de responsabilidades:

```text
model-package/tests/   pruebas del modelo empaquetado
tests/                 pruebas del repositorio: API, evaluación, proveedores
```

Ejecutar toda la suite desde la raíz recoge ambos directorios y requiere el grupo `research`, porque las pruebas de entrenamiento importan MLflow y scikit-learn:

```bash
uv run --group research pytest
```

Solo las pruebas del paquete del modelo:

```bash
uv run tox -c model-package -e test_package
```

Suite completa en un entorno aislado:

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

Su código fuente vive en `model-package/`, pero el proyecto **no lo instala desde ahí**: lo descarga como wheel ya entrenado desde el bucket S3 del proyecto.

```toml
[tool.uv.sources]
modelo-citas = { url = "https://ceduque-modelo-citas-wheels.s3.amazonaws.com/wheels/modelo_citas-0.2.0-py3-none-any.whl" }
```

El wheel lleva el `.pkl` dentro, y `uv.lock` fija su hash SHA-256. Como consecuencia, para ejecutar la API no hacen falta `model-package/`, ni el dataset, ni DVC, ni las dependencias de entrenamiento: basta `pyproject.toml` y `uv.lock`.

El bucket concede únicamente `s3:GetObject` sobre el prefijo `wheels/`, así que la descarga no requiere credenciales.

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

## Publicar una versión nueva del modelo

Entrenar es responsabilidad de quien produce el modelo, no de quien lo consume. El ciclo completo es:

**1. Subir la versión.** Cada reentrenamiento es una versión nueva; un wheel publicado nunca se sobrescribe.

```bash
echo "0.3.0" > model-package/modelo_citas/VERSION
```

**2. Entrenar.** Lee `papers.json`, `contexts.json` y `train.json` desde `data/raw/`, así que los datos deben estar recuperados con DVC.

```bash
uv run --group research dvc pull
uv run tox -c model-package -e train
```

También puede apuntarse a otra ubicación de los datos:

```bash
uv run tox -c model-package -e train -- /ruta/a/data/raw
```

El artefacto queda en `model-package/modelo_citas/trained/`, con el nombre de la versión del paquete (por ejemplo `modelo-citas-output0.3.0.pkl`). Ese `.pkl` no se versiona en Git.

**3. Construir el wheel.** `MANIFEST.in` incluye `trained/*.pkl`, de modo que el modelo viaja dentro.

```bash
uv run tox -c model-package -e build
unzip -l model-package/dist/modelo_citas-0.3.0-py3-none-any.whl | grep pkl
```

**4. Publicar en S3.**

```bash
aws s3 cp model-package/dist/modelo_citas-0.3.0-py3-none-any.whl \
  s3://ceduque-modelo-citas-wheels/wheels/ \
  --content-type application/zip
```

**5. Apuntar el proyecto a la versión nueva.** Actualizar la URL en `[tool.uv.sources]` de `pyproject.toml` y volver a fijar el hash:

```bash
uv lock
```

A partir de ahí, cualquier `uv sync` o `docker compose build` toma el modelo nuevo.

---

## Trabajar sobre el código del modelo

Mientras se modifica `model-package/`, conviene instalarlo en modo editable para no tener que publicar un wheel en cada iteración:

```bash
uv pip install -e model-package
```

Las pruebas del paquete corren directamente sobre el fuente y no dependen de la URL:

```bash
uv run tox -c model-package -e test_package
```

El bucket es de lectura pública, así que cualquiera con la URL puede descargar el modelo. Para un modelo que deba permanecer privado, el camino es dejar el bucket cerrado y darle a la instancia un rol IAM con `GetObject`, lo que ya no se resuelve con una URL directa en `pyproject.toml`.

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

Los indicadores que muestra el tablero no se calculan en cada solicitud: `/api/insights` lee `data/processed/dashboard_insights.json`, generado previamente con `src/training/build_insights.py`.

El manual de usuario se encuentra en:

```text
docs/manual_usuario.md
```

---

# Evaluación de función de cita con modelos de lenguaje

Además del recomendador, el repositorio incluye un frente de evaluación comparativa de modelos de lenguaje para clasificar la **función de una cita** dentro de nueve categorías:

```text
1. Background
2. Gap
3. Basis
4. Comparison
5. Application
6. Improvement / Modification
7. Evidence
8. Identification of the Originator
9. Further Reading
```

Cada modelo responde un arreglo JSON de nueve puntajes, en ese mismo orden, para que el parseo y las métricas sean idénticos entre proveedores.

---

## Componentes

```text
config/prompts/citation_function_prompts.json
    tres estrategias versionadas: zero_shot_generic, zero_shot_detailed, few_shot

src/evaluation/commercial/
    providers_openai.py       OpenAI
    providers_gemini.py       Gemini (capa compatible con OpenAI)
    providers_cohere.py       Cohere (capa compatible con OpenAI)
    providers_openweight.py   cualquier servidor OpenAI-compatible (por ejemplo Ollama)
    runner.py                 ejecución con reintentos, latencia, tokens y errores
    metrics.py                Precision, Recall, F1 Macro/Micro y matrices de confusión
    stability.py              parseo común y estabilidad entre repeticiones
    orchestrate.py            orquestador de punta a punta
    cli.py                    ejecución de un solo proveedor

src/evaluation/annotation.py         preparación, acuerdo y consolidación del gold
src/data/build_citation_function_pilot.py   piloto reproducible de 20 casos
annotations/citation_function/       validación manual y gold provisional
```

---

## Configuración de proveedores

Las variables de ejemplo están en:

```text
config/citation_eval.env.example
```

```text
OPENAI_API_KEY / OPENAI_MODEL
GEMINI_API_KEY / GEMINI_MODEL
COHERE_API_KEY / COHERE_MODEL
OPENWEIGHT_BASE_URL / OPENWEIGHT_MODEL / OPENWEIGHT_API_KEY
```

Nunca deben versionarse credenciales reales. El identificador del modelo se controla por variable de entorno para no modificar código al cambiar de versión.

---

## Test Gold

```text
annotations/citation_function/provisional_test_gold.jsonl
    20 casos, primera validación manual por parte del equipo, uso preliminar

annotations/citation_function/test_gold.jsonl
    nombre reservado para el conjunto definitivo, después de la segunda
    validación independiente, el acuerdo entre anotadores y la reconciliación
```

El orquestador usa `test_gold.jsonl` cuando existe. Si solo hay conjunto provisional, exige el indicador `--allow-provisional` y marca los artefactos como preliminares, para impedir que un piloto se reporte como resultado final.

---

## Ejecutar una evaluación

Validar datos, prompts y configuración sin llamar a ningún proveedor:

```bash
uv run python -m src.evaluation.commercial.orchestrate --mode all --check-only
```

Ejecutar sobre el conjunto provisional:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
    --mode commercial \
    --allow-provisional \
    --request-delay-seconds 5 \
    --output-dir artifacts/citation_function_eval
```

Modos disponibles:

```text
openai      gemini      cohere      openweight
commercial  OpenAI + Gemini
all         OpenAI + Gemini + open-weight
```

`--request-delay-seconds` respeta los límites de solicitudes por minuto de las capas gratuitas; en el piloto se usaron 5 segundos para Gemini y 4 para Cohere.

Cada corrida genera, en el directorio de salida:

```text
results.jsonl
summary.csv
run_metadata.json
metrics/
    evaluation_summary.csv
    predictions.csv
    confusion_matrices/
```

Esos artefactos quedan bajo `artifacts/`, ignorado por Git.

---

## Resultados provisionales, corte 20 de septiembre de 2026

Sobre los 20 casos del gold provisional y los tres prompts:

| Modelo | Mejor prompt | F1 Macro | Accuracy | Latencia media |
|---|---|---:|---:|---:|
| Gemini 3.5 Flash-Lite | few_shot | 0,3287 | 0,65 | 1,49 s |
| Cohere Command A+ | zero_shot_detailed | 0,2614 | 0,45 | 9,27 s |
| Qwen3:8B (local, Ollama) | few_shot | 0,1742 | 0,30 | 56,60 s |

Todas las corridas tuvieron cobertura de clasificación del 100 %, sin errores de proveedor ni de formato. OpenAI quedó implementado y con preflight exitoso, pero la corrida real no produjo predicciones por `credit_balance_exhausted`; por eso no se le atribuyen métricas.

Estos números son preliminares: el conjunto tiene 20 casos, solo 5 de las 9 clases aparecen en las etiquetas, y falta la segunda validación manual independiente. El detalle está en:

```text
docs/evaluacion_comparativa_provisional_20sep.md
docs/evaluacion_comparativa_provisional_20sep.csv
```

---

## Documentación del frente

```text
docs/evaluacion_comercial.md                      proveedores y contrato de datos
docs/evaluacion_metricas.md                       pipeline de métricas
docs/openweight_local.md                          ejecución de modelos locales
docs/prompts_estabilidad.md                       prompts y medición de estabilidad
docs/guia_anotacion_funcion_cita.md               guía de anotación
docs/control_calidad_etiquetas_provisional.md     control de calidad asistido
docs/evaluacion_comparativa_provisional_20sep.md  resultados preliminares
```

---

# Integración continua

El repositorio tiene dos flujos de GitHub Actions:

```text
.github/workflows/evaluacion-citas.yml
    ejecuta las pruebas del frente de evaluación de función de cita
    en push a main y en pull requests que tocan src/evaluation/, los
    prompts o sus pruebas

.github/workflows/reporte03.yml
    compila reportes/reporte03/main.tex, verifica que el PDF no supere
    las 10 páginas y lo publica como artefacto de la corrida
```

El PDF final también está versionado en `reportes/reporte03/main.pdf`.

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
2. copia `pyproject.toml`, `uv.lock` y `README.md`;
3. instala las dependencias de ejecución (`uv sync --frozen --no-dev`), lo que descarga el wheel `modelo-citas` desde S3 con el modelo dentro;
4. copia el código del proyecto;
5. inicia FastAPI mediante Uvicorn.

Ni el entrenamiento ni la recuperación de datos ocurren en el build. `model-package/` está excluido en `.dockerignore`: la imagen no contiene el código fuente del modelo, solo el paquete instalado desde el wheel publicado.

Esto mantiene la imagen pequeña y sin credenciales: el contenedor no necesita DVC, ni el dataset crudo, ni las dependencias de entrenamiento. La única condición es que la URL declarada en `pyproject.toml` esté publicada y que `uv.lock` esté sincronizado con ella.

El único archivo procesado que sí viaja en Git y dentro de la imagen es:

```text
data/processed/dashboard_insights.json
```

que alimenta el endpoint `/api/insights` sin recalcular nada en tiempo de ejecución.

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

No hay pasos previos: el modelo se descarga del wheel publicado durante el build.

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

La instancia no necesita datos, ni DVC, ni entrenar. Solo requiere salida HTTPS hacia S3 para descargar el wheel.

Construir:

```bash
docker compose build
```

El flujo que deja lista la imagen es:

```text
máquina de entrenamiento
    data/raw (DVC)
        |
        v
    tox -c model-package -e train
        |
        v
    tox -c model-package -e build
        |
        v
    wheel publicado en S3
        |
--------|--------------------------
        v
EC2
    docker compose build
        |
        v
    uv sync --frozen  (descarga el wheel, verifica el hash)
        |
        v
    paquete modelo-citas instalado en la imagen
```

Si la URL no está publicada o el archivo cambió, `uv sync --frozen` falla por desajuste de hash en lugar de producir una imagen que no puede servir recomendaciones.

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

El modelo y la configuración necesaria quedan dentro de la imagen, junto con `data/processed/dashboard_insights.json`.

El modelo se instala desde el wheel publicado en S3, cuya lectura es pública, por lo que el build no requiere credenciales de AWS ni acceso al remoto DVC. Sí requiere salida HTTPS hacia el bucket.

Las variables de los proveedores de LLM (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `COHERE_API_KEY`, `OPENWEIGHT_*`) pertenecen al frente de evaluación de función de cita y no las usa la API desplegada.

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

Tampoco deben versionarse las llaves de los proveedores de LLM usados en la evaluación de función de cita. `config/citation_eval.env.example` contiene únicamente nombres de variables, sin valores.

El remoto DVC utilizado para recuperar los datos es:

```text
publico
```

y es de solo lectura. El build de la imagen ya no lo utiliza.

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
uv run --group research python -m src.data.make_processed
uv run --group research python -m src.training.export_top100
```

Regenerar la información precalculada del tablero:

```bash
uv run --group research python -m src.training.build_insights --force
```

Este comando escribe `data/processed/dashboard_insights.json`, que sí se versiona en Git porque lo consume la API.

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

Las dependencias están separadas por grupo según la responsabilidad de cada capa:

```text
principales   FastAPI, pydantic, modelo-citas, openai
dev           pytest, tox
research      DVC, MLflow, Jupyter, pandas, scikit-learn, matplotlib, seaborn
```

El grupo `research` no entra en la imagen de la API. Se instala solo cuando se va a entrenar, evaluar o explorar:

```bash
uv sync --group research
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
GitHub Actions
LaTeX
OpenAI API
Google Gemini
Cohere
Ollama
```

---

# Flujo reproducible resumido

## Desarrollo local

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation

uv sync --group research
uv run dvc pull
uv run --group research pytest
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
- evidencia reproducible del flujo de inferencia;
- separación de responsabilidades entre el paquete del modelo y el repositorio de experimentación;
- distribución del modelo como wheel versionado y publicado en S3, con hash fijado en `uv.lock`;
- imagen de API sin código del modelo, sin dependencias de entrenamiento y sin acceso a datos;
- integración continua para las pruebas de evaluación y la compilación del reporte;
- pipeline de evaluación de función de cita con prompts versionados, cuatro proveedores de modelos, métricas comparables y medición de estabilidad;
- validación manual del piloto de anotación y gold provisional de 20 casos.

Pendiente en el frente de función de cita:

- segunda validación manual independiente;
- cálculo del acuerdo entre anotadores;
- reconciliación de desacuerdos y congelamiento de `test_gold.jsonl`;
- repetición de las corridas sobre el Test Gold definitivo;
- consolidación de las métricas finales en el reporte.

El sistema debe considerarse un prototipo académico. Las recomendaciones dependen del corpus utilizado, de la etapa de recuperación y del modelo entrenado, y no sustituyen la revisión académica de las referencias por parte del usuario.