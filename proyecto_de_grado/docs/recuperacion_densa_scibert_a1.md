# Recuperación densa SciBERT Top-3 vs BM25 (A1, issue #102)

Comparación técnica **offline** entre SciBERT (denso) y el baseline léxico BM25 sobre los mismos chunks y contextos de train.
**No contiene Recall@3, Hit@3 ni MRR@3**: no existe gold validado de chunks (pendiente en el issue #127). El solape mide acuerdo entre métodos, no relevancia, y no permite afirmar superioridad de ninguno.

## 1. Alcance y comandos
- Rama `feature/issue-102`. Paquete: `packages/recuperacion-densa` (ver su README). No se tocan `src/app` ni `proyecto_de_grado/src`.
- Modelo: `allenai/scibert_scivocab_uncased`, revisión fijada `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1` (SHA resuelto con `descarga_modelo --resolver`; `manifiesto_modelo.json` guarda el SHA-256 de cada archivo). Mean pooling, ventanas de 512 tokens sin truncar, float64.
- Entorno: torch `2.11.0+cu128`, transformers `5.22.1`, Python 3.14.6, GPU NVIDIA GeForce RTX 4070 SUPER.
- Comandos (desde la raíz; `P="uv run --project packages/recuperacion-densa"`):
  - `$P python -m recuperacion_densa.cli --solo-validar` → 605 contextos / 91 artículos.
  - `$P --group modelo python -m recuperacion_densa.cli_modelo --device cuda --sin-cache --salida <R>/corrida_cuda_1` y la misma con caché (`corrida_cuda_2`); `--device cpu --limite 60 --sin-cache` (`cpu_60`).
- Evidencia: `docs/evidencias_recuperacion_densa_a1/`. Análisis: `notebooks/02_recuperacion_densa_scibert_top3.ipynb`.
- **Procedencia:** el manifiesto registra `git.head = ca4cc5bb…` con `dirty = true`: las corridas se hicieron con cambios sin commitear del paquete. El código evaluado es el del commit que contiene esta evidencia.

## 2. Corpus
- **605 contextos de train sobre 91 artículos** (2 632 chunks únicos), construidos con un constructor multicontexto propio. `exportar_corpus_top3.preparar()` toma un solo contexto por citado y daría como máximo 91 casos.
- Muy concentrados: P98-1013 aporta 107 contextos, P97-1023 68, E06-1015 46; 31 artículos tienen un solo contexto (mediana 2). Por eso se reporta **micro** (por contexto) y **macro** (por artículo).
- Mismo corpus que BM25 y A1: solo la caché local de 200 artículos; sin IDs excluidos de gold/piloto.

## 3. Integridad
0 violaciones, para SciBERT y BM25: cada `(cited_id, chunk_id)` pertenece al artículo del caso, con sección e índices iguales a los del corpus, sin duplicados y ≤3 resultados. BM25 nunca se abstuvo (0 contextos sin resultados).

## 4. SciBERT vs BM25 frente al azar
Coinciden X/3 chunks entre los Top-3 de ambos métodos (azar con n chunks: k²/n).

| | n | solape@3 | azar | Jaccard | mismo Top-1 |
|---|---|---|---|---|---|
| micro | 605 | 0,272 (≈0,82/3) | 0,112 (≈0,34/3) | 0,184 | 0,193 |
| macro | 91 | 0,306 (≈0,92/3) | 0,128 (≈0,38/3) | 0,212 | 0,228 |

Distribución por contexto: 0/3 en 229, 1/3 en 261, 2/3 en 112, 3/3 en solo 3. Sin P98-1013 el solape micro es 0,280 (con él, 0,272): el sesgo de concentración es pequeño en esta métrica. Coinciden algo más de lo esperado por azar, pero la mayoría de contextos comparte 0 o 1 chunk: **los métodos discrepan en general**, y este análisis no dice cuál acierta.

## 5. Secciones (heurística no validada)
| perfil | corpus | SciBERT | BM25 |
|---|---|---|---|
| otra | 50,1 % | 42,5 % | 40,9 % |
| method | 16,0 % | 12,7 % | 13,4 % |
| results | 10,6 % | 4,5 % | 8,5 % |
| introduction | 9,7 % | 17,2 % | 20,2 % |
| conclusion | 6,0 % | 8,5 % | 8,1 % |
| vacía | 4,3 % | 2,8 % | 2,1 % |
| related_work | 3,4 % | 11,7 % | 6,8 % |

Ambos métodos favorecen introducción; SciBERT sobrerrepresenta *related work* (≈3,5× el corpus) y subrepresenta *results*. Descriptivo: sin gold no se sabe si es sesgo o señal.

## 6. Similitud y hubness
- Coseno Top-1: media 0,903 (0,732–0,944); brecha Top-1–Top-2: media 0,0078. Cosenos altos y casi planos: anisotropía típica de SciBERT sin ajuste para recuperación.
- Entre los 60 artículos con ≥2 contextos, el Top-1 más frecuente se repite en el 50 % de sus contextos y el Top-3 cubre solo el 30 % de los chunks del artículo: el denso tiende a devolver los mismos chunks sin importar el contexto (hubness).

## 7. Latencia y determinismo
| etapa | CUDA p50 / p95 (s) | CPU (60 ctx) p50 / p95 (s) |
|---|---|---|
| embedding por artículo | 0,131 / 0,213 | 3,258 / 5,174 |
| consulta SciBERT | 0,0107 / 0,0156 | 0,0460 / 0,0623 |
| BM25 (incluye indexar) | 0,0011 / 0,0017 | 0,0014 / 0,0019 |

Carga del modelo 1,4 s (CUDA); memoria GPU máxima 689 MB. El embedding del artículo se paga una vez por artículo.
- **Determinismo:** `resumen.json` y `top3.csv` idénticos byte a byte entre `corrida_cuda_1` (sin caché) y `corrida_cuda_2` (con caché).
- **CPU vs CUDA (60 contextos):** mismo orden Top-3 en 60/60, mismo Top-1 en 60/60, diferencia máxima de coseno 1·10⁻⁶ (el redondeo a 6 decimales). No se observaron empates resueltos de forma distinta en esta muestra.

## 8. Gold: no ejecutado
`Recall@3`, `Hit@3` y `MRR@3` **no se calculan**: faltan hojas S2.3 adjudicadas de relevancia de chunks (issue #127). El código está listo para puntuar una calibración (`--calibracion-origen/--calibracion-carpeta`, etiqueta `calibracion_train_no_gold`), pero no se usó.

## 9. Interpretación breve para el informe
SciBERT y BM25 recuperan Top-3 distintos en la mayor parte de los contextos (coinciden en promedio ≈0,8 de 3 chunks, algo sobre el azar de ≈0,3). El denso muestra señales de anisotropía y hubness. Estas son propiedades técnicas; la calidad real de cada método queda sin evaluar hasta tener gold.

## 10. Limitaciones
- Sin gold: no hay Recall/Hit/MRR.
- Solo train y la caché de 200 artículos; el 37 % de los artículos se descarta en la extracción (A1, #101).
- Contextos concentrados en pocos artículos.
- SciBERT con mean pooling no es un recuperador entrenado.
- La heurística de sección no está validada; 4,3 % de chunks sin sección.
- Los párrafos `EQUATION` cortan oraciones y las ventanas de 512 tokens cortan por frontera.
- Latencia medida en una sola GPU (RTX 4070 SUPER) y una CPU de escritorio, no la de la API; BM25 incluye la indexación; el CPU se midió solo con 60 contextos / 20 artículos.
- La corrida se hizo con árbol de trabajo sucio (ver §1).
