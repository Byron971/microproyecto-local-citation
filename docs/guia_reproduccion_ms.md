# Guia de reproduccion: demostracion SciBERT + M/S

## Estado de validacion

Demostracion ejecutada exitosamente en Windows con CPU y
un caso real de la particion TRAIN.

La reproduccion desde un clon limpio esta pendiente de validar.
La evaluacion cientifica en Test Gold es independiente de
esta demostracion funcional.

## Arquitectura

- API estandar: Docker, puerto 8000.
- API cientifica M/S: Python 3.12, puerto 8001.
- Frontend: React + Vite, puerto asignado por Vite.

La API cientifica ejecuta recuperacion SciBERT Top-3,
construccion de entrada AB y clasificacion de nueve funciones
mediante dos checkpoints independientes, M y S.

## Entorno utilizado

- Python 3.12.13
- PyTorch 2.6.0+cpu
- Transformers 5.21.0
- FastAPI 0.165.0
- Uvicorn 0.54.0
- huggingface_hub 2.4.0
- safetensors 0.8.0
- Node.js 26.13.1
- npm 10.4.0
- Docker 29.9.2

Estas versiones describen el entorno validado; no constituyen
todavia una instalacion limpia verificada.

## Artefactos necesarios

Los checkpoints originales se esperan en:

- proyecto_de_grado/artifacts/experimentos_10/M/model.safetensors
- proyecto_de_grado/artifacts/experimentos_10/S/model.safetensors

Cada carpeta debe contener tambien su
manifiesto_entrenamiento.json original.

La ubicacion y los hashes estan en:
docs/manifiesto_distribucion_ms.json

Los checkpoints NO estan incluidos en Git. Su mecanismo de
descarga esta pendiente de asignacion y autorizacion.

Tambien se necesita el snapshot local de SciBERT:
allenai/scibert_scivocab_uncased
revision 24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1

La carga cientifica se realiza sin descargar automaticamente
modelos en tiempo de inferencia.

## Verificacion previa obligatoria de artefactos M/S

Desde la raiz del repositorio, antes de iniciar la API cientifica:

```powershell
python scripts/verificar_artefactos_ms.py
```

El comando **no descarga checkpoints** ni importa Torch. Verifica para M y S:
presencia, tamaño esperado, SHA-256 de los pesos y coherencia del manifiesto
de entrenamiento (hash, revision SciBERT y entrada AB). Devuelve JSON y
termina con codigo 1 si hay una falla. Para ejecutar solo las pruebas
sinteticas de este control:

```powershell
uv run pytest -q tests/test_verificar_artefactos_ms.py
```

La prevalidacion **no garantiza** que el snapshot de HuggingFace este
instalado, que el codigo cientifico funcione con Python 3.12 ni que
la inferencia real sea exitosa. No sustituye la ejecucion POST con un
caso TRAIN autorizado ni demuestra metricas cientificas sobre Gold.

No subir pesos, anotaciones Gold ni credenciales a Git. El lugar autorizado
para distribuir los pesos aun esta pendiente de decision del equipo.

## Reproduccion en clon de codigo limpio (Windows, CPU)

Este procedimiento crea una **segunda carpeta**: no cambia de rama, borra ni
reorganiza el repositorio de trabajo original. Es una prueba de clon limpio
**del codigo** con pesos y ejemplo TRAIN transferidos desde un entorno
ya verificado; no es una prueba de aprovisionamiento autonomo de modelos
en una maquina sin cache HuggingFace.

1. En PowerShell, desde fuera de la carpeta del repositorio original:

```powershell
$original = "C:\ruta\absoluta\microproyecto-local-citation-actualizado"
git clone --branch integration/cierre-cientifico-20261120 --single-branch https://github.com/Byron971/microproyecto-local-citation.git ms-clon-limpio
cd ms-clon-limpio
```

2. Copiar **solo** los checkpoints y sus manifiestos de entrenamiento a las
rutas esperadas. No copiar la carpeta `.venv-science`, todo `artifacts`
ni los ficheros de Gold:

```powershell
foreach ($pista in @("M", "S")) {
  $fuente = Join-Path $original "proyecto_de_grado/artifacts/experimentos_10/$pista"
  $destino = Join-Path (Get-Location).Path "proyecto_de_grado/artifacts/experimentos_10/$pista"
  New-Item -ItemType Directory -Force -Path $destino | Out-Null
  Copy-Item (Join-Path $fuente "model.safetensors") $destino -ErrorAction Stop
  Copy-Item (Join-Path $fuente "manifiesto_entrenamiento.json") $destino -ErrorAction Stop
}
New-Item -ItemType Directory -Force -Path ".\artifacts\ms_smoke_local" | Out-Null
Copy-Item (Join-Path $original "proyecto_de_grado/artifacts/demo_real_ms/solicitud_real_ms.json") ".\artifacts\ms_smoke_local\solicitud.json" -ErrorAction Stop
Copy-Item (Join-Path $original "proyecto_de_grado/artifacts/demo_real_ms/respuesta_real_ms.json") ".\artifacts\ms_smoke_local\referencia.json" -ErrorAction Stop
python scripts/verificar_artefactos_ms.py
```

El script de verificacion debe terminar con `listo=true`. La solicitud
contiene texto cientifico y **solo permanece local** (la carpeta
`artifacts/` esta ignorada por Git).

3. Instalar el entorno cientifico **aislado de Python 3.12**. No utilizar
`uv sync` del proyecto principal ni del paquete `recuperacion-densa`
porque ambos manifiestos exigen Python >=3.14 y esta prueba se basa
en el entorno de ejecucion Python 3.12 documentado:

```powershell
uv python install 3.12
uv venv --python 3.12 .venv-ms
uv pip install --python .venv-ms\Scripts\python.exe "torch==2.6.0" --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv-ms\Scripts\python.exe "transformers==5.21.0" "huggingface-hub==2.4.0" "safetensors==0.8.0" "fastapi==0.165.0" "uvicorn==0.54.0"
```

Estas son las versiones **reportadas** en el entorno local exitoso.
La resolucion de dependencias en una instalacion limpia aun debe ser
comprobada y las versiones ajustadas solo con una justificacion
registrada y una nueva ejecucion. El entorno necesita el snapshot
SciBERT de la revision fijada, disponible en la cache HuggingFace local;
el runtime no lo descarga al ejecutar.

4. Ejecutar con el codigo de ese clon. La variable de entorno hace
disponible el paquete de recuperacion sin instalarlo desde su
`pyproject.toml` incompatible con Python 3.12:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "packages\recuperacion-densa\src") + [IO.Path]::PathSeparator + (Get-Location).Path
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
.\.venv-ms\Scripts\python.exe scripts/smoke_real_ms.py --solicitud .\artifacts\ms_smoke_local\solicitud.json --referencia .\artifacts\ms_smoke_local\referencia.json --tolerancia 0.005 --salida .\artifacts\ms_smoke_local\resumen.json
```

La comparación requiere igualdad de revisión SciBERT, método,
longitud de entrada AB, IDs y orden de Top-3 y clases M/S. Permite
una diferencia absoluta máxima de 0.005 en softmax de cada clase
predicha, porque la representación numérica puede variar entre
entornos y CPU/GPU. Es una **tolerancia operativa explícita**,
no un intervalo estadístico ni una validación de calidad.

Para certificar una ejecución se requiere salida `"ok": true`,
código de retorno cero, hashes y versiones en `resumen.json`;
si falla, preservar el error y no declarar reproducción.

## Arranque en el entorno Windows ya preparado

Ejecutar desde la raiz del repositorio.

### 1. API estandar

docker compose up -d api

Verificar:
http://127.0.0.1:8000/api/estado

### 2. API cientifica

En otra terminal PowerShell:

$env:PYTHONPATH = (
  (Join-Path (Get-Location) "packages\recuperacion-densa\src") +
  [IO.Path]::PathSeparator + (Get-Location).Path
)

.\.venv-science\Scripts\python.exe -c "from fastapi import FastAPI; from src.app.ms_router import router; import uvicorn; app = FastAPI(title='API cientifica M/S'); app.include_router(router); uvicorn.run(app, host='127.0.0.1', port=8001)"

Verificar:
http://127.0.0.1:8001/api/analisis-cita-ms/estado

IMPORTANTE: el endpoint de estado comprueba existencia de
archivos, pero no demuestra carga o inferencia real.

La configuracion actual del paquete recuperacion-densa
declara Python >=3.14. La ejecucion cientifica probada
utilizo Python 3.12 y PYTHONPATH apuntando al codigo fuente.
Este procedimiento debe formalizarse y probarse desde cero.

### 3. Frontend

En una tercera terminal PowerShell:

cd frontend
npm ci
npm run build
npm run dev

Abrir la direccion local mostrada por Vite y navegar a:
/analisis-ms

El proxy de Vite envia las solicitudes cientificas al
puerto 8001 y las demas solicitudes API al puerto 8000.

## Prueba funcional

1. Importar un JSON valido con contexto, titulo,
   abstract y al menos tres candidatos.
2. El contexto debe incluir TARGETCIT exactamente una vez.
3. Ejecutar Analizar cita.
4. Comprobar Top-3, entrada AB y resultados de M/S.

Para el caso TRAIN D08-1068 previamente verificado:
- Candidatos: 46.
- Recuperador: scibert_base_mean_pooling_cosine.
- Tokens AB: 512.
- Modelo M: Evidence, puntuacion softmax ~0.458719.
- Modelo S: Background, puntuacion softmax ~0.866312.

Las puntuaciones softmax no representan precision
cientifica validada.

## Limitaciones pendientes

- Distribuir checkpoints por almacenamiento autorizado.
- Validar descarga e integridad en un clon limpio.
- Formalizar instalacion reproducible del entorno cientifico.
- Validar nuevamente el arranque y la inferencia.
- Mantener separado TRAIN de la evaluacion Test Gold.
- No publicar anotaciones Gold ni predicciones sensibles.