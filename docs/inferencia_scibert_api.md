# Inferencia SciBERT Top-3 experimental y verificable en FastAPI

## Qué incorpora este PR

Dos rutas nuevas, independientes del backend TF-IDF/BM25 existente:

- `POST /api/top3-scibert`: ranking de hasta 3 chunks **aportados por el
  usuario**; no prueba que los chunks manuales correspondan al citado.
- `GET /api/top3-scibert/corpus/{context_id}`: ranking sobre **el citado
  original del corpus TRAIN** guardado localmente por ACL-200/OCL. Devuelve
  fuente, revisión, IDs, sección, texto y similitud coseno.

Ambas llaman a `TorchSciBERTEncoder` y al **mismo**
`recuperacion_densa.dominio.ordenar_top3` de A1, preservando mean pooling,
ventanas sin truncamiento y desempate por `chunk_id`. No usan
`puntaje_bm25`; `similitud_coseno` **no es probabilidad de relevancia**.

## Requisitos para ejecutar inferencia REAL

Este módulo está desactivado por defecto; el Dockerfile ligero y el entorno
`uv` principal **NO incluyen Torch**. Los tests CI sin pesos usan un encoder
controlado y verifican el contrato, **no una inferencia SciBERT real**.

En un equipo con recursos y con permiso para instalar dependencias:

1. `uv sync --project packages/recuperacion-densa --locked --group modelo`
   crea el entorno científico fijado en su lockfile.
2. En ese mismo entorno, instalar las dependencias de FastAPI del proyecto
   principal de acuerdo con su `uv.lock`; la API y
   `recuperacion_densa` deben verse desde el **mismo intérprete Python**.
   No mezclar versiones de Torch, Transformers o tokenizadores sin registrar.
3. Descargar el modelo con
   `uv run --project packages/recuperacion-densa --group modelo python -m recuperacion_densa.descarga_modelo`
   (el módulo descarga el snapshot `allenai/scibert_scivocab_uncased`
   exactamente en la revisión SHA fijada y compara sus archivos con el
   manifiesto A1).
4. Establecer, para el proceso FastAPI:
   `APP_SCIBERT_ENABLED=true`,
   `APP_SCIBERT_MANIFEST=proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json`
   y `APP_SCIBERT_DEVICE=cpu` (o `cuda` solo si Torch/CUDA están disponibles).
5. Iniciar FastAPI desde el intérprete con ambos paquetes instalados y comprobar
   `/api/top3-scibert` sobre un caso TRAIN. En configuración normal el mismo
   endpoint devuelve **HTTP 503**, sin sustituir SciBERT por BM25.

**Fail-closed:** si falta el manifiesto, no coincide el snapshot o falta Torch,
la opción explícita de SciBERT falla al iniciar. No se hace una descarga
sorpresiva por petición, ni se inventan resultados de Gold. Una futura imagen
de inferencia distinta de la API ligera deberá registrar memoria, latencia y
revisiones exactas antes de desplegar.

## Ejemplo de solicitud manual (sin Gold)

```json
{
  "cited_id": "P14-1001",
  "contexto": "Graph neural networks learn representations TARGETCIT.",
  "parrafos": [
    {"chunk_id": "p00000", "texto": "Graph representations learn node embeddings.", "seccion": "Methods"},
    {"chunk_id": "p00001", "texto": "Statistical approaches evaluate translations.", "seccion": "Results"}
  ]
}
```

Requiere una respuesta con `metodo=scibert_base_mean_pooling_cosine`,
`revision`, los fragmentos con `similitud_coseno` y
`clasificacion.estado=no_ejecutada`.

**No se incluye clasificador A4 en esta integración.** Para las nueve
funciones es imprescindible recuperar/validar los checkpoints A4 con el
registro del PR #171 y preparar el tokenizer y entrada A/B de cada corrida.
El Gold humano será necesario después para certificar métricas, no para
implementar la inferencia.

## Pruebas y seguridad

`uv run pytest -q tests/test_scibert_optional_api.py` usa un encoder
**sintético** y la función de ranking científica original. Comprueba
integridad, no activación por defecto, el rechazo de IDs duplicados,
el requisito de manifiesto y que la ruta corpus no sirve etiquetas Gold.
La validación de la calidad del ranking sigue pendiente de relevancia humana
y de ejecutar el modelo real en un entorno con Torch.
