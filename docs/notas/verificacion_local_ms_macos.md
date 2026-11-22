# Verificación local de SciBERT + M/S en macOS

Fecha: 21 de noviembre de 2026. Equipo: macOS Apple Silicon; inferencia CPU.

## Resultado

SciBERT, M y S ejecutaron inferencia real sin conexión sobre el caso TRAIN suministrado por el equipo. El smoke devolvió `ok: true`, sin errores. El POST local `/api/analisis-cita-ms` devolvió HTTP 200 en 11,242 s, incluyendo carga inicial del servicio; es una observación individual, no un benchmark.

Coincidieron revisión SciBERT, entrada AB de 512 tokens y orden de fragmentos: `p00011-p00012`, `p00002-p00003`, `p00065-p00065`. M predijo Evidence con puntuación 0,458719; S, Background con 0,866311 (referencia 0,866312). La diferencia máxima observada en esas puntuaciones fue 0,000001, dentro de la tolerancia explícita de 0,005. La respuesta HTTP contiene nueve puntuaciones por modelo, con suma aproximadamente uno.

Esto demuestra funcionamiento y coincidencia operacional para ese caso; no evalúa calidad científica ni utiliza Gold. No se probaron aún React local ni despliegue científico AWS en esta etapa.

## Archivos locales

- Entorno aislado: `.venv-ms`, Python 3.12.10.
- Versiones principales: Torch 2.6.0, Transformers 5.21.0, huggingface-hub 2.4.0, safetensors 0.8.0, FastAPI 0.165.0, Uvicorn 0.54.0.
- Lista completa instalada: `artifacts/ms_local/requirements_instalados.txt`.
- Caché: `artifacts/huggingface/hub/models--allenai--scibert_scivocab_uncased/snapshots/24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1/`.
- Checkpoints y manifiestos: `proyecto_de_grado/artifacts/experimentos_10/{M,S}/`.
- Solicitud, referencia, respuesta HTTP y reportes: `artifacts/ms_local/` (contenido local excluido de Git).

SciBERT se descargó con `recuperacion_densa.descarga_modelo`, que verificó los seis archivos contra el manifiesto versionado. Se desactivó Xet para el reintento porque la primera descarga no mostró progreso. No se alteraron los hashes esperados.

## Repetir comprobación offline

Desde la raíz del repositorio, con los archivos anteriores disponibles:

```bash
export HF_HOME="$PWD/artifacts/huggingface"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTHONPATH="$PWD/packages/recuperacion-densa/src:$PWD"
python scripts/verificar_artefactos_ms.py
.venv-ms/bin/python scripts/smoke_real_ms.py \
  --solicitud artifacts/ms_local/solicitud_real_ms.json \
  --referencia artifacts/ms_local/respuesta_real_ms.json \
  --salida artifacts/ms_local/smoke_referencia.json
```

## Iniciar API local y probar HTTP

Con las mismas variables de entorno, ejecutar:

```bash
.venv-ms/bin/python -c 'from fastapi import FastAPI; from src.app.ms_router import router; import uvicorn; app=FastAPI(title="API científica M/S local"); app.include_router(router); uvicorn.run(app, host="127.0.0.1", port=8001)'
```

En otra terminal, desde la raíz:

```bash
curl --fail-with-body --max-time 180 \
  http://127.0.0.1:8001/api/analisis-cita-ms \
  -H 'Content-Type: application/json' \
  --data-binary @artifacts/ms_local/solicitud_real_ms.json \
  -o artifacts/ms_local/respuesta_http.json
```

El servidor se inicia solo en loopback. Detener con Ctrl+C al terminar. El endpoint de estado no sustituye este POST. La instalación por PYTHONPATH reproduce el procedimiento del equipo; formalizar la instalación de paquetes y el entorno Linux sigue siendo trabajo del despliegue.
