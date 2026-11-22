# Recomendación de artículos y análisis M/S integrado

**Actualización preparada:** la búsqueda de artículos utiliza SciBERT sobre todo
el catálogo y la preparación de fragmentos usa V2 más deduplicación del notebook
10 (37 artículos aptos). Véase [búsqueda semántica](busqueda_semantica_scibert.md).
Las cifras de 22 artículos y fragmentación V1 que aparecen abajo documentan el
primer despliegue integrado, anterior a esta corrección.

## Recorrido

En la portada se escribe un contexto en inglés y se pulsa **Recomendar**.
Cada resultado indica si tiene texto preparado. Al desplegar el título de un
artículo disponible, **Analizar cita · Top-3 y M/S** abre el contexto original.
El usuario coloca el cursor donde irá la cita o selecciona una cita existente y
pulsa **Marcar posición de cita**; luego **Analizar este artículo**.

El servidor resuelve título, resumen y todos los candidatos del mismo artículo.
La respuesta contiene tres fragmentos, sección, similitud, procedencia y las
nueve puntuaciones de cada modelo. Se señalan desacuerdos entre M y S.
Editar el contexto descarta los resultados anteriores. Cambiar la consulta de
recomendación oculta el análisis del resultado anterior hasta volver a recomendar.
La pantalla `/analisis-ms` conserva la entrada manual como herramienta avanzada.

Los puntajes de recomendación, la similitud y softmax tienen significados distintos.
Ninguno certifica que una publicación respalde una afirmación ni mide porcentaje
de acierto del análisis. El usuario debe revisar la publicación.

## Corpus inicial y cobertura

`config/corpus_ms.json` contiene **22 artículos aptos de 38 candidatos** seleccionados
mediante los primeros diez resultados, sin duplicados, de cuatro consultas
ilustrativas inventadas:

- Neural approaches for scientific document classification
- Neural machine translation with attention mechanisms
- Dependency parsing and natural language syntax
- Word embeddings and semantic similarity

El catálogo del recomendador contiene **19.776 artículos**: estos 22 representan
solo una cobertura inicial, elegida para probar el flujo, sin muestreo representativo.
Los otros artículos siguen siendo recomendables; la interfaz explica que no tienen
texto preparado. No se filtra ni se altera el ranking para favorecer la cobertura.

Los 16 candidatos excluidos tienen párrafos que exceden las reglas V1; el archivo
registra cada exclusión. No se truncan, duplican o sustituyen textos para completarlos.
Ampliar la cobertura requiere preparar más artículos o validar por separado el
fragmentador V2 ya existente en el repositorio; no cambiarlo silenciosamente.

Origen: [WINGNUS/ACL-OCL](https://huggingface.co/datasets/WINGNUS/ACL-OCL), revisión
`300ee6c5e5629d042bfc07cbc406e2f330b53659`. La sección de licencia de su ficha declara
**CC BY-NC 4.0**; conservar atribución y uso académico no comercial. Autores del
corpus: Shaurya Rohatgi, Yanxia Qin, Benjamin Aw, Niranjana Unnithan y Min-Yen Kan,
*The ACL OCL Corpus: advancing Open science in Computational Linguistics* (2022).
La ficha también tiene una etiqueta MIT: se conserva la condición más específica
de la sección dedicada al corpus. Los metadatos provienen del catálogo ACL local.

Cada artículo preserva ID ACL, URL de publicación, URL OCL fijada por revisión,
SHA256 del JSON original, sección y posiciones de párrafos. Se usa
`exportar_corpus_top3.fragmentar` V1: hasta dos párrafos consecutivos de la misma
sección, hasta 300 palabras, sin truncar contenido.
El corpus completo tiene SHA256
`1163c583d54f66ab8d63d8424fdfa064423a0317e65d4c47273635dd85681204`.

## Contrato y operación

- `POST /api/analisis-cita-ms/disponibilidad`: `{"paper_ids":["S15-1012"]}`;
  hasta 20 IDs, disponibilidad y cantidad de fragmentos por artículo.
- `POST /api/analisis-cita-ms/articulo`: `{"paper_id":"S15-1012","contexto":"Earlier work TARGETCIT proposed neural classification."}`.
  El cliente no decide título, resumen o fragmentos. La respuesta añade `articulo`
  con identidad, fuente, licencia, hash del contenido y cantidad de candidatos.
- 404: artículo sin texto preparado; 422: contexto inválido; 429: inferencia
  ocupada, con `Retry-After: 5`; 503: corpus inválido o servicio no disponible.

Se valida el corpus al arrancar, antes de declarar readiness: identidad de ID y
publicación, SHA256 de procedencia con formato válido y contrato completo de
entrada M/S, incluyendo límites de tamaño y fragmentos únicos. La imagen fija el
contenido mediante su digest; el SHA del corpus identifica cualquier cambio.
No se descargan PDFs o textos externos en peticiones HTTP. El contenido validado
se conserva en memoria por proceso. No se cachean resultados de inferencia.
Las rutas nuevas se dirigen al mismo servicio científico mediante el behavior del
ALB `/api/analisis-cita-ms/*`; la API estándar conserva su destino.

Para reconstruir el mismo corpus, extraer `ids_solicitados` a un JSON de IDs y ejecutar:

```bash
PYTHONPATH=. .venv/bin/python scripts/preparar_corpus_ms.py \
  --ids artifacts/corpus_ms/ids.json \
  --revision 300ee6c5e5629d042bfc07cbc406e2f330b53659 \
  --salida artifacts/corpus_ms/corpus.json
```

La caché descargada queda en `artifacts/corpus_ms/cache/`; no contiene TRAIN,
Gold ni anotaciones humanas. La imagen incluye explícitamente solo el corpus
preparado y público, separado del release privado e inmutable de pesos M/S.

## Verificación

- Pruebas de backend: resolución de identidad del servidor, metadatos y
  fragmentos correctos, cobertura parcial, contexto sin marca, corrupción,
  menos de tres fragmentos e IDs duplicados. No cargan pesos.
- Pruebas de interfaz: marcar posición, enviar solo ID y contexto, descartar
  resultados al editar, impedir análisis de artículos sin texto.
- Inferencia local real por ID `S15-1012`, contexto inventado, 42 candidatos:
  4.103 s, tres fragmentos, M y S `Background`. No es una evaluación de calidad.
- Recorrido local real en navegador: recomendar, abrir `S15-1012`, marcar posición
  con el botón y analizar. Se mostraron tres fragmentos y nueve puntuaciones M/S.
- Recorrido real desde la SPA pública: mismas acciones, con 42 candidatos,
  Top-3 y ambas distribuciones visibles. Se verificó la ausencia de texto en
  `D15-1167`. Captura: `artifacts/ms_integration/web_integrada.png`.
- Aceptación pública por ID: 16.784 s; texto más extenso preparado (`P15-1004`,
  46 candidatos): 21.483 s; máximo número de candidatos (`W98-0511`, 55): 11.238 s.
  No son percentiles ni pruebas de carga sostenida. Backend: siete pruebas
  ligeras aprobadas; frontend: 31 pruebas aprobadas y compilación de producción.

Evidencias de compilación, despliegue y aceptación pública:
`artifacts/ms_integration/`. Las versiones anteriores del servicio y los archivos
de la SPA se conservan para rollback; véase `despliegue_cientifico_aws.md`.

Pendientes: ampliar cobertura, medir carga y documentos extremos, cerrar la
equivalencia completa del notebook y activar el workflow remoto. Estos trabajos
no se confunden con la prueba funcional del recorrido.
