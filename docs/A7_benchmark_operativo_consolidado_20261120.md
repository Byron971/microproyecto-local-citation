# A7 — Evidencia operacional y estimación de recursos (corte 20-11-2026)

**Estado:** evidencia local documentada; no implica validación de Gold, despliegue productivo ni costo AWS observado.

## 1. Alcance y procedencia
Se consolidan salidas mostradas en consola por el equipo y rutas de JSON guardadas localmente. **Este documento no inspeccionó los bytes de los JSON originales**, que deben adjuntarse y comprobarse antes de la entrega. La metodología HTTP se alinea con `docs/benchmark_operativo_a7.md` del repositorio.

- Host: Intel Core i7-12650H, 10 núcleos físicos / 16 lógicos, RAM física 15,71 GiB.
- Docker: 16 procesadores lógicos expuestos y 8.170.135.552 bytes (7,61 GiB) de memoria.
- Modelos de clasificación: Python 3.12.13, PyTorch 2.6.0+cpu, Transformers 5.21.0; sin GPU.
- Checkpoints M y S del notebook `10_modelos_finales_M_S.ipynb`: hashes SHA-256 coincidentes con sus manifiestos.
- Snapshot SciBERT fijado: `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`.
- La API Docker estándar ejecuta recomendación empaquetada TF-IDF+lineal y Top-3 BM25. **No se confirmó inferencia SciBERT Top-3 en esa API** (la prueba del endpoint devolvió 503).

## 2. Benchmark HTTP de API (ejecuciones locales independientes)
Resultados comunicados de `scripts/ci/benchmark_api.py`. Solicitudes secuenciales, tres calentamientos, 30 mediciones; no representa concurrencia. Las operaciones y payloads no son equivalentes.

| Operación | n | p50 (ms) | p95 (ms) | Media (ms) | Evidencia local |
|---|---:|---:|---:|---:|---|
| Top-3 BM25 | 30 | 5,875 | 26,017 | 10,184 | `artifacts/a7_bm25_local_20261120.json` |
| Recomendación TF-IDF + lineal, corrida 1 | 30 | 27,224 | 48,666 | 30,943 | `artifacts/a7_recommend_local_20261120.json` |
| Recomendación TF-IDF + lineal, corrida 2 | 30 | 23,299 | 45,643 | 27,023 | `artifacts/a7_recommend_local_20261120_v2.json` |

**Interpretación:** son latencias HTTP end-to-end de operaciones distintas y datos de prueba sintéticos. No se comparan como si fueran una misma tarea ni se infiere eficacia de recuperación.

## 3. Benchmark de clasificación SciBERT M y S
Pruebas de inferencia en CPU **sin HTTP ni recuperación Top-3**. Entrada AB sintética de 512 tokens con `TARGETCIT`, título, abstract y tres fragmentos aportados previamente. Se ensambló con reglas de presupuesto del notebook 10. Cada corrida por modelo: 3 warmups y 30 mediciones secuenciales.

| Corrida | Modelo | p50 (ms) | p95 (ms) | Carga (s) | RAM proceso tras carga (MiB) |
|---|---|---:|---:|---:|---:|
| v1 | S | 1.482,601 | 1.538,291 | 8,02 | No disponible |
| v1 | M | 1.460,477 | 1.533,879 | 3,24 | No disponible |
| v2 | S | 1.491,997 | 1.565,152 | 6,96 | 706,9 |
| v2 | M | 1.617,047 | 1.977,621 | 2,97 | 714,8 |

Evidencias locales:
- `artifacts/a7_clasificadores_ms_ab_20261120.json` (v1)
- `artifacts/a7_clasificadores_ms_ab_20261120_v2.json` (v2)

La memoria indicada corresponde al RSS del **proceso Python completo después de la carga**, no a la memoria incremental del modelo, pico de RAM, RAM de Docker ni memoria máxima con solicitudes concurrentes. En v2 M/S se ejecutaron secuencialmente dentro del mismo proceso; por ello las cifras de memoria no permiten atribuir exactamente el consumo a cada modelo de forma aislada. La carga de checkpoint es independiente de la latencia por petición.

La diferencia de latencias entre corridas no permite concluir superioridad operativa estable. Los modelos M y S tienen **objetivos de entrenamiento diferentes**; las predicciones sintéticas (`Background` para S e `Improvement / Modification` para M) no son juicios de calidad.

## 4. Instantánea Docker y limitaciones
En un `docker stats --no-stream` posterior:
- API: **249 MiB** de memoria y CPU **26,55 %** en ese instante.
- Dashboard: **15,5 MiB** de memoria y CPU **0 %**.
- Suma instantánea de memoria de ambos contenedores: **264,5 MiB**.

La instantánea no es una medición en carga ni simultánea con el benchmark M/S. No se debe sumar directamente como requisito mínimo de despliegue. La variante `docker-compose.science.yml` incluye un `mem_limit: 12g`, superior a la memoria asignada a Docker en esta máquina: no se validó la pila científica con ese Compose.

## 5. Costos: escenario, no facturación
No hay registro de costo AWS observado, telemetría de ECS, facturas ni validación de una instancia de nube. Para presupuestar una operación 24/7, la fórmula es:

`costo_mensual_computo_USD = tarifa_instancia_USD_por_hora × 730`

El presupuesto integral debe añadir, según arquitectura, disco EBS, transferencia de datos, direcciones IP públicas, balanceador, observabilidad, almacenamiento de artefactos, impuestos y eventuales cargos por créditos de CPU. Cualquier cifra por instancia requiere tarifa vigente, región y fecha de consulta documentadas. El rendimiento en EC2/ECS no se extrapola de estas mediciones locales.

## 6. Estado científico y asuntos abiertos
**Completado:** verificación SHA de M/S; carga estricta de pesos; tokenización SciBERT; inferencia de ambas cabezas de 9 clases; benchmark CPU sintético; benchmarks HTTP de la API; instantánea Docker.

**Pendiente para una conclusión completa de A7:** (a) adjuntar y revisar JSON originales, hashes y parámetros; (b) comprobar ensamble AB con casos reales TRAIN sin fuga ni Gold; (c) evaluar extremo a extremo con el backend real habilitado, si se dispone de pesos y configuración; (d) medir memoria pico y concurrencia, de forma opcional; (e) obtener precios oficiales fechados o una cotización AWS y explicitar supuestos; (f) integrar en artículo sin presentar estos resultados como F1, Recall@3 o SLA.

## 7. Texto de resultados para el artículo
> En un equipo Intel Core i7-12650H (10 núcleos físicos, 16 lógicos, 15,71 GiB de RAM), se caracterizó la inferencia local de los clasificadores SciBERT M y S mediante entradas AB sintéticas de 512 tokens, tres calentamientos y 30 mediciones secuenciales por corrida. En la segunda ejecución, el modelo S obtuvo latencias p50/p95 de 1.491,997/1.565,152 ms y el modelo M de 1.617,047/1.977,621 ms. La memoria RSS del proceso después de cargar cada modelo fue de 706,9 y 714,8 MiB, respectivamente. De forma separada, la API contenedorizada registró un consumo instantáneo de 249 MiB y el dashboard de 15,5 MiB. Estas pruebas demuestran factibilidad técnica de inferencia en CPU, pero no evalúan precisión sobre Gold, carga concurrente ni costo de infraestructura en producción.

## 8. Referencias internas
- `notebooks/10_modelos_finales_M_S.ipynb`
- `docs/benchmark_operativo_a7.md`
- `scripts/ci/benchmark_api.py`
- `docker-compose.yml`
- `docker-compose.science.yml`

**Control de divulgación:** guardar en Git únicamente este resumen agregado y, si el equipo lo autoriza, JSON técnicos sin textos privados, credenciales, modelos ni etiquetas individuales.
