# Búsqueda de artículos con SciBERT y análisis M/S

## Decisión y alcance

El usuario confirmó que **Recomendar debe usar SciBERT sobre títulos y resúmenes
de todo el catálogo**, con Top-3 y M/S cuando exista texto completo preparado.
La portada deja de usar TF-IDF + reordenador lineal. No se hace fallback
silencioso al modelo anterior si falla el servicio científico.

La búsqueda semántica es una **extensión experimental de producto**. El notebook
`10_modelos_finales_M_S.ipynb` recibe un artículo citado ya identificado: no entrena
un recomendador global. Los checkpoints M y S siguen clasificando nueve funciones
retóricas de cita usando la entrada AB; no se utilizan sus logits para ordenar
artículos. No se ha demostrado que la nueva búsqueda supere al modelo anterior.

## Recuperación de artículos

- Modelo de la API: `scibert-articulos-v1`.
- Encoder: `allenai/scibert_scivocab_uncased`, revisión verificada
  `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`.
- Corpus: los **19.776 artículos** de `data/raw/papers.json`, SHA256
  `999d6b77fed44d6bb6ed1c49c532c02aaa19f21b9e6d65e569201c2a2c7ee749`.
- Representación: título y resumen, ventanas de hasta 510 tokens de contenido
  con CLS/SEP, mean pooling con máscara y media ponderada por tokens entre
  ventanas. No se truncan resúmenes largos. Es el encoder base utilizado en
  recuperación densa; no un encoder ajustado para recomendación global.
- Ranking: embeddings normalizados, similitud coseno, redondeo a seis decimales
  y desempate por ID ACL. No intervienen TF-IDF ni el clasificador lineal.
- Preparación offline mediante `scripts/construir_indice_scibert.py`; lotes
  reanudables, matriz float32 y manifiesto de hashes. Los vectores CPU y MPS
  se contrastan numéricamente; no se trata de un benchmark de relevancia.
- En HTTP se codifica únicamente la consulta y se busca en la matriz ya cargada.
  El índice y sus metadatos se obtienen del S3 privado, por inventario inmutable
  separado del release de pesos M/S, y se verifican antes de readiness.

Contrato:

```text
GET  /api/analisis-cita-ms/modelos
POST /api/analisis-cita-ms/recomendar
     {"contexto":"Scientific text in English", "top_k":10, "modelo":"scibert-articulos-v1"}
```

La respuesta conserva las recomendaciones con título, resumen, ID y posición,
y añade revisión SciBERT, versión del índice, método y tamaño del catálogo.
El puntaje se llama **Similitud SciBERT**. Las rutas públicas habituales
`/api/recomendar` y `/api/modelos` se dirigen también al servicio científico;
no conservan TF-IDF como alternativa silenciosa. El servicio baseline continúa
atendiendo los demás endpoints; sus rutas locales originales se conservan para
pruebas históricas, pero no definen el recomendador público vigente.

## Top-3 y M/S: corrección de fragmentación

El corpus inicial integrado utilizaba V1 y contenía 22 artículos. Al revisar el
notebook 10 se confirmó que corresponde usar **V2 más deduplicación por texto
normalizado**, conservando el menor ID de fragmento y el orden original.
V2 divide párrafos largos por límites de palabras y, cuando es posible, de oración;
mantiene hasta 300 palabras y 5000 caracteres sin perder texto. Los párrafos cortos
conservan la agrupación V1 por sección y continuidad.

La preparación corregida cubre **37 de los 38 artículos revisados**. `J08-4003`
supera el límite actual de 100 candidatos y se excluye explícitamente.
Los 19.776 artículos siguen participando en la búsqueda; solo esos 37 tienen
el análisis completo habilitado. No se altera el ranking para favorecerlos.

La comparación de las funciones extraídas del notebook con el código de
preparación confirmó igualdad exacta de IDs, textos, secciones, índices de párrafos
y conteos de palabras en los 38 artículos descargados. Evidencia local:
`artifacts/ms_integration/auditoria_fragmentacion_v2.json`.

SHA256 del corpus V2 preparado:
`56fbf67a8407cbef9068fc1a10c1e1d6b5b714ebac08752d81016698d5b0bea7`.
Fuente y condiciones de uso: revisión ACL-OCL
`300ee6c5e5629d042bfc07cbc406e2f330b53659`; atribución y CC BY-NC 4.0 según la
[ficha del corpus](https://huggingface.co/datasets/WINGNUS/ACL-OCL).

## Concurrencia y fallos

La búsqueda de artículos y el análisis M/S comparten un único slot de inferencia.
Si está ocupado, se responde 429 con `Retry-After: 5`; no se encola trabajo que
pueda superar los 30 segundos de API Gateway. La web conserva un timeout de
32 segundos y muestra el error. No se almacenan embeddings de consultas privadas.

Se rechazan índices corruptos, incompatibles o con IDs duplicados y vectores no
finitos, no normalizados o de dimensión distinta a 768. Los archivos numpy se
leen con `allow_pickle=False`. El corpus y los modelos se verifican al arrancar.

## Preparar y distribuir el índice

```bash
HF_HOME="$PWD/artifacts/huggingface" HF_HUB_OFFLINE=1 \
  PYTHONPATH=.:packages/recuperacion-densa/src \
  .venv-ms/bin/python scripts/construir_indice_scibert.py --device mps

AWS_PROFILE=josezambrana python scripts/publicar_indice_scibert.py
```

Usar un Python con boto3 en el segundo comando. Para CPU, omitir `--device mps`.
No cambiar de dispositivo, lote o catálogo dentro de un directorio parcialmente
calculado; iniciar otro directorio con `--salida` y preservarlo como evidencia.
Repetir el mismo comando reanuda los lotes normalizados ya válidos. El progreso
se consulta en `artifacts/scientific_search/progreso.json`.
El publicador escribe `config/search_release.json` solo tras descargar y verificar
los tres archivos desde S3; no sobreescribe una release remota de contenido distinto.
El rol ECS existente puede leer el nuevo prefijo `releases/` sin ampliar permisos.

## Validación y pendientes

Pruebas de contrato: ranking semántico, desempates, integridad de hashes,
ausencia de fallback, límites, estado de catálogo y concurrencia. La interfaz
comprueba que catálogo y recomendaciones utilicen las rutas científicas.
La preparación V2 se contrasta contra las funciones reales del notebook.

La equivalencia completa de entrenamiento/evaluación del notebook, la relevancia
de las recomendaciones, el Gold y los percentiles de carga siguen siendo trabajos
separados. La selección de la mejor corrida mediante test Gold descrita en el
notebook impide tratar ese mismo test como evaluación independiente sin revisar
su protocolo. Ninguna prueba funcional de esta entrega certifica precisión.

Antes de publicar: completar el índice, distribuirlo con hashes, probar localmente
el ranking real, actualizar la imagen y validar el recorrido desde la web pública.
Los datos de TRAIN privado y Gold no forman parte del índice ni de los POST de prueba.
