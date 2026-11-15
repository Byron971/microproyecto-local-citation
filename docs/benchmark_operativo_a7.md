# A7: benchmark operacional reproducible sin Gold humano

Este paso mide **tiempo HTTP extremo a extremo**, no calidad científica.
La suite principal del microproyecto ya tiene TF-IDF + reordenador y Top-3
BM25; puede medirse aunque todavía no existan etiquetas humanas.

## Ejecución local (API real, sin simulaciones)

En terminal 1: `uv run tablero`. En terminal 2:

```bash
uv run python scripts/ci/benchmark_api.py \
  --endpoint recommend --muestras 20 --warmup 3 \
  --salida artifacts/a7_recomendacion_local.json

uv run python scripts/ci/benchmark_api.py \
  --endpoint top3-bm25 --muestras 20 --warmup 3 \
  --salida artifacts/a7_bm25_local.json
```

Si `/api/top3-scibert` está **realmente activado** (PR #173) y el modelo
SciBERT fue descargado/cargado y verificado en el mismo proceso, la
comparación operacional experimental puede ejecutar:

```bash
uv run python scripts/ci/benchmark_api.py \
  --endpoint top3-scibert --muestras 20 --warmup 3 \
  --salida artifacts/a7_scibert_local.json
```

El script rechaza respuestas si el backend declarado no coincide con el
solicitado; así no se etiqueta BM25 como SciBERT. No se debe usar esa corrida
para inferir mejoras de Recall@3 sin Gold. La URL por defecto es
`http://127.0.0.1:8000`; destinos externos exigen HTTPS y
`--permitir-remoto`. Antes de ejecutar en AWS verificar autorización de
cargos y límites de servicio.

## Qué mide y qué no

Se realizan `N` peticiones **secuenciales**, con `W` calentamientos
excluidos; reporte `latencias_ms`, mínimo, media, p50, p95 (nearest rank),
máximo, hashes del payload y plataforma del cliente. Los reportes no guardan
contexto, texto de artículo, etiquetas de función ni Gold. Los archivos se
crean solo una vez; repetir requiere una ruta nueva. No se reporta
concurrencia, consumo de RAM del servidor, GPU, costo AWS ni tarifas LLM:
esas métricas requieren instrumentación separada.

El workflow `Benchmark operacional A7 sin Gold` ejecuta los endpoints
TF-IDF y BM25 sobre una API local **real**, adjuntando JSON de evidencia
técnica a la ejecución. Sus resultados dependen del runner GitHub hospedado;
no son directamente comparables con una instancia ECS de tamaño distinto
ni con la RTX 4070 SUPER de los experimentos A1.

## Criterios de reproducibilidad

Para comparar tiempos entre modelos se debe conservar el mismo conjunto de
solicitudes, máquina, región, calentamientos y límite de timeout, y reportar
muestras y recursos. No reinterpretar p95 de 12 consultas como una garantía
de SLA ni usar estas mediciones como calidad de recuperación o clasificación.
