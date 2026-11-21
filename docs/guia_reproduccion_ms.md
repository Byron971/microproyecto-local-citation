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