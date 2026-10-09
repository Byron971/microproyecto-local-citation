# Corte vertical de semana 2 — Recuperación de fragmentos (baseline)

**Estado:** funcionalidad experimental para demo, sujeta a CI y comprobación local. **No** es el modelo final de proyecto de grado ni una evaluación científica.

## Objetivo

Incorporar un primer flujo de extremo a extremo que ya utilice la arquitectura FastAPI + Nginx + tablero existente, sin cambiar el ranking de **artículos** del microproyecto.

Se implementa **BM25 léxico** sobre párrafos de **un artículo citado**, aportados explícitamente por la persona que consulta; no busca artículos ni recupera automáticamente datos de ACL OCL. El Top-3 representa ranking de **fragmentos**, no los `positive_ids` del ranking original.

## Endpoints y rutas

Se preservan:
- GET `/api/estado`, GET `/api/insights`, GET `/api/ejemplo`.
- POST `/api/recomendar` para ranking de artículos con el paquete `modelo-citas`.
- La interfaz original en `/`.

Se añade:
- POST `/api/top3-fragmentos`: recibe contexto, `cited_id` y 1–100 párrafos del artículo citado, cada uno con `chunk_id` único, `texto` y sección opcional. Devuelve hasta tres párrafos BM25 positivos, con orden determinista, puntajes **no calibrados** y abstención sin coincidencia léxica.
- Página `/static/top3.html`: formulario para ingresar contexto, ID y párrafos; enlace desde el tablero original.

### Ejemplo de petición

```json
{
  "contexto": "This approach uses graph neural representations TARGETCIT.",
  "cited_id": "DEMO-SINTETICO",
  "parrafos": [
    {"chunk_id": "p1", "texto": "Graph neural models encode nodes.", "seccion": "Methods"},
    {"chunk_id": "p2", "texto": "Experiments show variable results.", "seccion": "Results"}
  ]
}
```

La respuesta incluye `metodo="BM25_lexico_baseline"`, `alcance`, `fragmentos` y `clasificacion.estado="no_ejecutada"`. El identificador de ejemplo y sus textos son **sintéticos** y no sirven como resultados sobre ACL-200.

## Restricciones conscientemente adoptadas

- No se altera `src/app/recommender.py`, el modelo empaquetado ni su wheel de S3.
- No se descargan pesos de modelos nuevos; BM25 usa biblioteca estándar de Python. La versión actual aplica tokenización por palabras, minúsculas y lista fija de stopwords, **sin stemming, lematización ni normalización morfológica**. Ejemplos como `word/words` y `embedding/embeddings` no coinciden por sí solos. Esta es una limitación experimental, no evidencia de irrelevancia de un fragmento.
- La interfaz y el endpoint pueden funcionar sin `data/raw` ni `cache_ocl` en el contenedor, porque los párrafos se aportan por petición. En la versión siguiente un adaptador externo tomará los párrafos de un dataset versionado (sin incorporarlo a la imagen).
- No se ejecuta clasificación de nueve categorías hasta disponer de un modelo suficiente y un protocolo claro de incertidumbre. Se informa explícitamente que no se ejecutó.
- No declarar `Recall@3`, `MRR@3` ni `F1 Macro` con los ejemplos sintéticos. Requieren anotación humana y evaluación controlada.
- Top-3 no implica devolver siempre tres resultados: cuando no hay señal léxica no se inventan coincidencias.
- El endpoint manual valida **máximo 60.000 caracteres de texto** entre contexto y párrafos y **máximo 5.000 por párrafo**; no equivale todavía a un límite HTTP de bytes a nivel del proxy de producción. La interfaz verifica los mismos límites y muestra un error entendible si el servidor devuelve un fallo no JSON.
- Para comparar con SciBERT sin favorecer artificialmente al modelo neuronal, se deberá evaluar además **una variante BM25 normalizada morfológicamente**, usando el mismo conjunto, chunks, protocolo y criterios de relevancia. No se cambiará en silencio el baseline actual ni se supondrá que SciBERT lo supera sin medición.
- Esta demo es una etapa **intermedia** hacia el flujo científico completo, no una sustitución de BM25/SciBERT y Top-3 anotado del proyecto.

## Puertas de aceptación

1. Pruebas: ranking positivo, top-3 máximo, resultados vacíos, desempate estable, marcadores excluidos, controles de entrada 422, rutas antiguas conservadas; además **puntajes BM25 numéricos de referencia (IDF, K1, B)**, rareza léxica, límite agregado de texto y manejo de error no JSON en interfaz.
2. CI de rama aprobado.
3. Prueba local mediante FastAPI o Docker Compose del endpoint y la página, con enlace desde `/`.
4. Explicar en el informe de avance diferencias entre ranking de artículos del MVP y Top-3 de fragmentos.
5. Preparar lote real, reproducible y sin fuga de evaluación para medir después BM25 y SciBERT.

## Próximos incrementos, en orden

1. Adaptador de lectura segura de corpus integrado ACL-200/ACL OCL, sin DVC ni modelos de entrenamiento durante inferencia.
2. Evaluación humana de fragmentos y comparación BM25/SciBERT.
3. Clasificador de nueve funciones con abstención, registro de versión y latencia.
4. Despliegue de la solución final con URL funcional, variables de configuración y README de usuario para la rúbrica.

## Relación con rúbricas nuevas

El corte permite comenzar a documentar la **construcción de la solución** del informe de avance (35 %), mientras la demostración web y el endpoint empiezan a atender **funcionamiento** y **usabilidad** del despliegue (35 % + 35 %). No sustituye los resultados experimentales de esas rúbricas.
