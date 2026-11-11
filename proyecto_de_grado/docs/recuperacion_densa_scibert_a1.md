# Recuperación densa SciBERT Top-3 vs BM25 (A1, issue #102)

Comparación técnica **offline** entre SciBERT (denso) y el baseline léxico BM25 sobre los mismos chunks y contextos de train.
**No contiene Recall@3, Hit@3 ni MRR@3**: no existe gold validado de chunks (pendiente en el issue #127). El solape mide acuerdo entre métodos, no relevancia, y no permite afirmar superioridad de ninguno.

## 1. Alcance y comandos
- Rama `feature/issue-102`. Paquete: `packages/recuperacion-densa` (ver su README). No se tocan `src/app` ni `proyecto_de_grado/src`.
- Modelo: `allenai/scibert_scivocab_uncased`, revisión fijada `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1` (SHA resuelto con `descarga_modelo --resolver`; `manifiesto_modelo.json` guarda el SHA-256 de cada archivo). Mean pooling, ventanas de hasta 512 tokens sin truncar, float64. El codificador verifica el snapshot contra `manifiesto_modelo.json` al cargar.
- Entorno: torch `2.11.0+cu128`, transformers `5.22.1`, Python 3.14.6, GPU NVIDIA GeForce RTX 4070 SUPER.
- Comandos (desde la raíz; `P="uv run --project packages/recuperacion-densa"`):
  - `$P python -m recuperacion_densa.cli --solo-validar` → 603 contextos / 89 artículos.
  - `$P --group modelo python -m recuperacion_densa.cli_modelo --device cuda --cache <R>/cache_verificacion --salida <R>/corrida_cuda_1` (caché en frío) y la misma con la misma caché (`corrida_cuda_2`, caché en caliente); `--device cpu --limite 60 --sin-cache` (`cpu_60`).
  - Todo lo anterior lo orquesta `scripts/verificar_recuperacion_densa.sh`, que exige árbol limpio y regenera la evidencia (`comparar_corridas` produce `cpu_vs_cuda_60.json` y `cuda_frio_vs_caliente.json`).
- Evidencia: `docs/evidencias_recuperacion_densa_a1/`. Análisis: `notebooks/02_recuperacion_densa_scibert_top3.ipynb`.
- **Procedencia:** el manifiesto registra `git.head = 6a2d9634…` con `dirty = false`: la evidencia se generó con el árbol limpio, con el código de ese commit.

## 2. Corpus
- **603 contextos de train sobre 89 artículos** (2 574 chunks únicos), construidos con un constructor multicontexto propio. `exportar_corpus_top3.preparar()` toma un solo contexto por citado y daría como máximo 89 casos.
- **Autocitas excluidas** (aquí «autocita» = `citing_id == cited_id`, no autoría compartida): 2 contextos cuyo `citing_id` coincide con el artículo citado (eliminan 2 artículos; antes 605/91). Además se descartó 1 chunk de texto idéntico a otro del mismo artículo (se conserva el `chunk_id` menor). La validación rechaza ambos casos (fail-closed).
- Muy concentrados: P98-1013 aporta 107 contextos, P97-1023 68, E06-1015 46; 29 artículos tienen un solo contexto (mediana 2). Por eso se reporta **micro** (por contexto) y **macro** (por artículo).
- Mismo corpus que BM25 y A1: solo la caché local de 200 artículos; sin IDs excluidos de gold/piloto.

## 3. Integridad
0 violaciones, para SciBERT y BM25: cada `(cited_id, chunk_id)` pertenece al artículo del caso, con sección e índices iguales a los del corpus, sin duplicados y ≤3 resultados. BM25 nunca se abstuvo (0 contextos sin resultados).

## 4. SciBERT vs BM25 frente al azar
Coinciden X/3 chunks entre los Top-3 de ambos métodos (azar con n chunks: k²/n).

| | n | solape@3 | azar | Jaccard | mismo Top-1 |
|---|---|---|---|---|---|
| micro | 603 | 0,271 (≈0,81/3) | 0,112 (≈0,34/3) | 0,182 | 0,191 |
| macro | 89 | 0,298 (≈0,89/3) | 0,128 (≈0,38/3) | 0,203 | 0,210 |

Distribución por contexto: 0/3 en 229, 1/3 en 260, 2/3 en 112, 3/3 en solo 2. Sin P98-1013 el solape micro es 0,278 (con él, 0,271): el sesgo de concentración es pequeño en esta métrica. Coinciden algo más de lo esperado por azar, pero la mayoría de contextos comparte 0 o 1 chunk: **los métodos discrepan en general**, y este análisis no dice cuál acierta.

## 5. Secciones (heurística no validada)
| perfil | corpus | SciBERT | BM25 |
|---|---|---|---|
| otra | 50,3 % | 42,6 % | 41,0 % |
| method | 16,1 % | 12,8 % | 13,4 % |
| results | 10,5 % | 4,4 % | 8,4 % |
| introduction | 9,4 % | 17,2 % | 20,2 % |
| conclusion | 6,0 % | 8,5 % | 8,1 % |
| vacía | 4,2 % (de los chunks únicos del corpus de esta evaluación) | 2,7 % | 2,0 % |
| related_work | 3,4 % | 11,8 % | 6,8 % |

Ambos métodos favorecen introducción; SciBERT sobrerrepresenta *related work* (≈3,4× el corpus) y subrepresenta *results*. Descriptivo: sin gold no se sabe si es sesgo o señal.

**Nota sobre la base de las proporciones:** la columna «corpus» es sobre chunks únicos (cada chunk cuenta una vez); las de SciBERT y BM25 son sobre los puestos Top-3 de todos los contextos (micro), de modo que los artículos muy citados pesan más. No es una comparación macro, y parte de la diferencia puede deberse a la concentración de contextos y no al método.

## 6. Similitud y hubness
- Coseno Top-1: media 0,903 (0,732–0,944); brecha Top-1–Top-2: media 0,0078. Cosenos altos y casi planos: anisotropía típica de SciBERT sin ajuste para recuperación.
- Entre los 60 artículos con ≥2 contextos (misma métrica para ambos métodos):

| | Top-1 más frecuente (fracción de contextos) | cobertura Top-3 (fracción de chunks del artículo) |
|---|---|---|
| SciBERT | 0,50 | 0,30 |
| BM25 | 0,40 | 0,38 |

  SciBERT repite más el mismo chunk y cubre menos chunks que BM25, así que muestra más hubness que el baseline léxico. Pero BM25 también repite su Top-1 en el 40 % de los contextos, de modo que parte de la concentración viene de la estructura del corpus (pocos chunks relevantes por artículo, contextos parecidos) y no solo del modelo. Sin gold no se sabe si esa repetición es error o acierto.

## 7. Latencia y determinismo
| etapa | CUDA p50 / p95 (s) | CPU (60 ctx) p50 / p95 (s) |
|---|---|---|
| embedding por artículo | 0,198 / 0,323 (frío) · 0,0016 / 0,0031 (caliente) | 3,239 / 5,174 |
| consulta SciBERT | 0,0097 / 0,0145 (frío) · 0,0140 / 0,0185 (caliente) | 0,0484 / 0,0613 |
| BM25 (incluye indexar) | 0,0011 / 0,0016 | 0,0015 / 0,0020 |

Carga del modelo ≈1,9 s (CUDA); memoria GPU máxima 689 MB. «Frío» = caché vacía (`corrida_cuda_1`, 1 acierto por un texto repetido entre artículos); «caliente» = misma caché ya llena (`corrida_cuda_2`, **2 574 de 2 574 chunks, 100 %**). Con la caché caliente el embedding por artículo baja de ~0,2 s a ~1,6 ms (lectura de disco), pero **no es cero**. La consulta densa no cambia por la caché; su diferencia entre corridas (0,010 vs 0,014 s) es variación de la GPU en una sola medición.
- **Determinismo:** `resumen.json` y `top3.csv` idénticos byte a byte entre `corrida_cuda_1` (frío) y `corrida_cuda_2` (caliente), diferencia de coseno 0 (`cuda_frio_vs_caliente.json`). **Alcance:** en la corrida caliente los vectores de los fragmentos salen de la caché de la corrida 1, así que esta prueba solo muestra que la consulta se repite igual, no que codificar los fragmentos sea reproducible; esa evidencia es la de CPU vs CUDA.
- **CPU vs CUDA (60 contextos):** mismo orden Top-3 en 60/60, mismo Top-1 en 60/60, diferencia máxima de coseno 1·10⁻⁶ (el redondeo a 6 decimales). No se observaron empates resueltos de forma distinta en esta muestra.

## 8. Gold: no ejecutado
`Recall@3`, `Hit@3` y `MRR@3` **no se calculan**: faltan hojas S2.3 adjudicadas de relevancia de chunks (issue #127). El código está listo para puntuar una calibración (`--calibracion-origen/--calibracion-carpeta`, etiqueta `calibracion_train_no_gold`), pero no se usó.

## 9. Interpretación breve para el informe
SciBERT y BM25 recuperan Top-3 distintos en la mayor parte de los contextos (coinciden en promedio ≈0,8 de 3 chunks, algo sobre el azar de ≈0,3). El denso muestra señales de anisotropía y más hubness que BM25 (Top-1 repetido en 50 % vs 40 % de los contextos), aunque BM25 también concentra. **Ojo con el piso:** esa cifra no puede bajar de 1/m (m = contextos por artículo); el piso promedio es ≈0,27 y los 19 artículos con m = 2 tienen piso 0,5. Sobre el piso, la diferencia es ≈0,23 (denso) frente a ≈0,13 (BM25): la comparación entre métodos vale, pero la cifra absoluta exagera la concentración. Estas son propiedades técnicas; la calidad real de cada método queda sin evaluar hasta tener gold.

## 10. Limitaciones
- Sin gold: no hay Recall/Hit/MRR.
- Solo train y la caché de 200 artículos; el 37 % de los artículos se descarta en la extracción (A1, #101).
- Contextos concentrados en pocos artículos.
- SciBERT con mean pooling no es un recuperador entrenado.
- La heurística de sección no está validada; 4,3 % de chunks sin sección (denominador: todos los chunks extraídos por A1 en #101; el 4,2 % de §5 es sobre los chunks únicos de esta evaluación, por eso difieren).
- Los párrafos `EQUATION` cortan oraciones. Ningún texto superó 512 tokens en este corpus (ventanas procesadas = textos procesados = 3 177), por lo que no hubo corte por ventanas.
- Latencia medida en una sola GPU (RTX 4070 SUPER) y una CPU de escritorio, no la de la API; BM25 incluye la indexación; el CPU se midió solo con 60 contextos / 20 artículos; la latencia en caliente es una sola corrida.
- Micro y macro no son intercambiables, y las proporciones de sección del §5 mezclan bases distintas (chunks únicos vs puestos Top-3 por contexto).
