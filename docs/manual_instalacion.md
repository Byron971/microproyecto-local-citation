# Manual de instalación

Este manual describe la arquitectura actual de la Entrega 3. La ejecución de producción ya no entrena el modelo durante el arranque ni durante el build de Docker: la API instala `modelo-citas` 0.2.0 como wheel versionado desde S3, con el modelo entrenado incluido y su hash fijado en `uv.lock`.

La validación posterior al refactor se realizó en Windows 11 con WSL2 y Docker Desktop. La suite completa ejecutó 202 pruebas sin fallos y la ejecución contenerizada respondió correctamente en la API y en el tablero con una recomendación real.

## Requisitos previos

| Herramienta | Uso |
|---|---|
| Git | Clonar y actualizar el repositorio |
| uv | Crear el entorno e instalar dependencias |
| Docker Desktop + Docker Compose | Ejecución contenerizada recomendada |
| WSL2 en Windows | Backend Linux utilizado por Docker Desktop |

No es necesario instalar Python manualmente: `uv` descarga la versión declarada por el proyecto.

Para ejecutar la API y el tablero no se necesitan credenciales de AWS, DVC ni un entrenamiento local del modelo. El wheel de `modelo-citas` se descarga desde una URL pública de S3 definida en `pyproject.toml` y bloqueada en `uv.lock`.

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/Byron971/microproyecto-local-citation.git
cd microproyecto-local-citation
```

Si el repositorio ya existe:

```bash
git pull origin main
```

## 2. Instalar uv

Linux o macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Cerrar y volver a abrir la terminal si `uv` no aparece inmediatamente en el `PATH`.

## 3. Instalación para ejecutar la aplicación

```bash
uv sync
```

Este comando instala las dependencias de producción y descarga `modelo-citas` 0.2.0 desde el wheel publicado. El wheel ya contiene el artefacto entrenado; no se requiere ejecutar `train_pipeline`, copiar archivos `.pkl` ni reinstalar manualmente el paquete.

Comprobación opcional:

```bash
uv run python -c "import modelo_citas; print('modelo-citas importado correctamente')"
```

## 4. Ejecución local sin Docker

Iniciar FastAPI:

```bash
uv run uvicorn src.app.main:app --host 127.0.0.1 --port 8000
```

Comprobar el estado:

```text
http://127.0.0.1:8000/api/estado
```

La respuesta debe incluir, entre otros datos:

```text
"listo": true
"modelo": "TF-IDF + reordenador lineal"
"version": "0.2.0"
```

La documentación Swagger/OpenAPI queda disponible en:

```text
http://127.0.0.1:8000/docs
```

El archivo `data/processed/dashboard_insights.json` ya está precalculado y versionado. La API lo lee durante la ejecución; no vuelve a generar el análisis científico al arrancar.

---

## 5. Ejecución recomendada con Docker Compose

Con Docker Desktop funcionando:

```bash
docker compose up --build
```

Compose levanta dos servicios:

| Contenedor | Puerto | Función |
|---|---:|---|
| `microproyecto-citas-api` | 8000 | FastAPI + wheel `modelo-citas` |
| `microproyecto-citas-dashboard` | 8080 | Nginx + interfaz web |

Abrir el tablero:

```text
http://localhost:8080
```

Comprobar la API:

```text
http://localhost:8000/api/estado
```

El dashboard se comunica con la API por la red interna de Docker Compose. Nginx redirige las solicitudes `/api/*` hacia el servicio `api:8000`.

Importante: el `Dockerfile` actual no ejecuta DVC ni entrenamiento. Durante el build instala el wheel publicado desde S3 y después copia únicamente el código necesario de la aplicación.

### Validación funcional

El flujo validado para la Entrega 3 fue:

1. `docker compose up --build`.
2. `/api/estado` respondió HTTP 200 con `listo=true`.
3. La API cargó `modelo-citas` versión 0.2.0 y un catálogo de 19.776 artículos.
4. El tablero abrió en `localhost:8080`.
5. Se utilizó `Usar un ejemplo real`.
6. `Recomendar citas` devolvió un ranking de artículos y permitió consultar el resumen del resultado seleccionado.

Que la cita correcta no aparezca en el Top-K de un ejemplo particular no indica un fallo de infraestructura; representa el resultado del modelo para esa consulta.

---

## 6. Entorno de investigación, DVC y pruebas

DVC, MLflow, scikit-learn, pandas, Jupyter y las demás dependencias científicas están separadas en el grupo `research`.

Instalarlo:

```bash
uv sync --group research
```

Descargar los datos versionados:

```bash
uv run --group research dvc pull
```

Comprobar DVC:

```bash
uv run --group research dvc status
```

Ejecutar la suite completa:

```bash
uv run --group research pytest
```

Validación más reciente del refactor:

```text
202 passed
```

También aparecieron advertencias de deprecación de NumPy/Joblib, pero no hubo fallos de pruebas.

Los datos son necesarios para reproducir entrenamiento, notebooks y análisis; no son necesarios para construir o ejecutar la imagen de producción de la API.

---

## 7. Entrenamiento y publicación de una nueva versión del modelo

Este paso es solo para desarrollo del modelo, no para utilizar la aplicación.

El código de entrenamiento vive en `model-package/`. La frontera de producción se mantiene mediante un wheel versionado:

```text
model-package / entrenamiento
        ↓
wheel modelo-citas
        ↓
S3 público + hash en uv.lock
        ↓
FastAPI / Docker
```

Cuando se publique una versión nueva, se debe:

1. entrenar y validar el modelo desde el entorno de investigación;
2. actualizar la versión del paquete;
3. construir un wheel que incluya el artefacto entrenado;
4. publicar un archivo nuevo en el bucket S3 de wheels;
5. actualizar la URL de `[tool.uv.sources]` en `pyproject.toml`;
6. ejecutar `uv lock`;
7. volver a ejecutar pruebas y validación Docker.

Un wheel publicado no debe sobrescribirse silenciosamente, porque `uv.lock` fija su identidad mediante hash.

---

## 8. Endpoints principales

| Ruta | Método | Descripción |
|---|---|---|
| `/api/estado` | GET | Estado y metadatos del modelo |
| `/api/recomendar` | POST | Genera el ranking de recomendaciones |
| `/api/insights` | GET | Indicadores precalculados del análisis |
| `/api/ejemplo` | GET | Carga un ejemplo real para la demostración |
| `/docs` | GET | Swagger/OpenAPI |

Ejemplo de cuerpo para recomendar:

```json
{
  "contexto": "Recent work on neural machine translation with attention...",
  "top_k": 10
}
```

---

## 9. Solución de problemas

### Docker instalado, pero no aparece la sección Server en `docker info`

Abrir Docker Desktop y esperar a que el motor esté en ejecución:

```powershell
docker desktop start
docker desktop status
docker info
```

No ejecutar `docker compose up` hasta que `docker info` muestre correctamente la sección `Server`.

### WSL2 indica que la virtualización no está disponible

Comprobar:

```powershell
wsl --status
wsl --version
```

En PowerShell como Administrador, si Windows todavía no tiene habilitados los componentes:

```powershell
wsl.exe --install --no-distribution
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
bcdedit /set hypervisorlaunchtype auto
```

Reiniciar Windows. La virtualización por hardware también debe estar habilitada en BIOS/UEFI.

### `uv : The term 'uv' is not recognized`

Cerrar y volver a abrir la terminal después de instalar `uv`.

### Puerto 8000 o 8080 ocupado

En Windows:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Get-NetTCPConnection -LocalPort 8080 -State Listen
```

Detener el proceso que ocupa el puerto o modificar temporalmente el mapeo.

### Problemas al descargar datos con DVC

Recordar que DVC pertenece al entorno de investigación:

```bash
uv sync --group research
uv run --group research dvc pull
```

Los problemas de credenciales de un remoto privado de escritura no impiden ejecutar la aplicación; el runtime de producción no usa DVC.

---

## 10. Variables de entorno

| Variable | Uso |
|---|---|
| `MLFLOW_TRACKING_URI` | Servidor de MLflow durante experimentación |
| `OPENAI_API_KEY` | Evaluación opcional con OpenAI |
| `GEMINI_API_KEY` | Evaluación opcional con Gemini |
| `COHERE_API_KEY` | Evaluación opcional con Cohere |

Las credenciales no deben almacenarse en Git ni dentro de las imágenes Docker.

---

## Resumen de instalación para la entrega

Para demostrar la aplicación:

```bash
git pull origin main
docker compose up --build
```

Después abrir:

```text
Dashboard: http://localhost:8080
API:       http://localhost:8000/api/estado
Swagger:   http://localhost:8000/docs
```

Para reproducir experimentación y pruebas:

```bash
uv sync --group research
uv run --group research dvc pull
uv run --group research pytest
```
