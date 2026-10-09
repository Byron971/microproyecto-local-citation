# S2.2 — Primer Top-3 con documentos reales ACL-200 + ACL OCL

**Alcance:** primer corte funcional de desarrollo con hasta cinco contextos *train* de ACL-200 y sus artículos citados (texto completo de ACL OCL). No es evaluación final, anotación humana ni producción.

## Decisiones para evitar reprocesos

- Reutilizamos `integrar_contexto()` y el índice de splits G0.6; no creamos nuevos extractores de PDF.
- Excluimos los IDs ya usados en piloto/práctica y cualquier `val` o `test`.
- Solo empleamos los documentos locales de `proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl`. **No hay descargas automáticas ni inferencias pagas.**
- Cada registro enlaza un `context_id`, `citing_id` y `cited_id`; valida que `paper_id` ACL OCL sea el `cited_id` real.
- Formamos chunks de **hasta dos párrafos consecutivos** de una sola sección y **máximo 300 palabras**. Si un párrafo supera 300 palabras (o 5000 caracteres), rechazamos ese artículo de esta muestra y anotamos la causa, sin omitirlo silenciosamente.
- Los fragmentos incluyen `chunk_id`, texto, sección e índices del párrafo original. El registro conserva SHA-256 de su JSON ACL OCL.
- La selección de casos es determinista **para un conjunto de caché dado**; diferentes cachés pueden producir muestras distintas. Los identificadores y las huellas permiten comparar procedencia; no se debe atribuir representatividad a esta pequeña muestra.
- El artefacto local de salida se ignora en Git (`proyecto_de_grado/artifacts/`). No se suben textos completos a Git ni se incorporan al wheel o la imagen Docker por defecto.

## Preparación local del artefacto (Windows, raíz del repositorio)

```powershell
# Requiere data/raw ya recuperado por DVC y cache OCL disponible.
python -m proyecto_de_grado.src.data.exportar_corpus_top3 --limite 5
```

Resultado:

`proyecto_de_grado/artifacts/top3_s2/casos_train.json`

Si dice «No hay casos train con ACL OCL en cache», **no ejecutar descargas masivas**; revisar qué artículos hay en caché y escoger un conjunto explícito de desarrollo.

## Servirlo con FastAPI

Detener la instancia actual del servidor, hacer `git pull --ff-only` después de confirmar la rama y arrancar:

```powershell
python -m uvicorn src.app.main:app --host 127.0.0.1 --port 8000
```

La API lee el archivo por defecto si existe. Para un artefacto en otra ruta, configurar `TOP3_CORPUS_PATH` antes de arrancar.

Rutas:
- `GET /api/top3-corpus/ejemplos`: IDs y títulos de los casos train cargados.
- `GET /api/top3-corpus/{context_id}`: BM25 hasta 3 fragmentos, procedencia e índices.
- `/static/top3.html`: botón **Consultar caso real ACL OCL**. El modo manual y el ejemplo sintético siguen disponibles.

Si el artefacto falta, el nuevo endpoint devuelve **503 con explicación**, sin inventar resultados ni afectar el recomendador anterior.

## Pruebas

```powershell
python -m pytest -q tests/test_top3_fragmentos.py tests/test_top3_corpus_real.py proyecto_de_grado/tests/test_exportar_corpus_top3.py
```

Los tests usan datos sintéticos controlados. Para demostrar funcionamiento **con artículos reales**, hay que exportar y ejecutar la consulta en Windows; conservar ID, documento citado, sección, número de chunks y estados.

## Evidencia funcional local comprobada (9-oct-2026)

En Windows se ejecutaron las pruebas de S2.2 (23 aprobadas) y la exportación encontró dos contextos train en la caché existente: `D13-1157_P12-1007_0` y `W13-4005_W08-1111_0`. En la interfaz se observó el caso `D13-1157_P12-1007_0`, artículo citado `P12-1007`, con **32 fragmentos** y **Top-3 recuperado**; puntajes visibles 33,8833 (párrafo OCL 5) y 20,4599 (párrafo OCL 6). Estos resultados demuestran integración funcional local, **no relevancia adjudicada** ni calidad científica de BM25. La muestra de dos casos no autoriza estimaciones de cobertura del corpus.

## Límites científicos y de despliegue

- Esta muestra no aporta etiquetas de función de cita ni relevancia de fragmentos **adjudicada por humanos**.
- La cita usada para consultar sigue siendo el `masked_text` original de ACL-200: puede estar truncada. La reconstrucción en G1.3 todavía requiere aprobación humana.
- No se puede calcular Recall@3/MRR@3 validado con este artefacto. El siguiente incremento debe preparar una referencia humana y comparar BM25/SciBERT sobre el mismo universo.
- **Limitación léxica:** BM25 actual no aplica stemming/lematización; `word` y `words` se consideran palabras diferentes. No usar solo esta variante morfológicamente cruda para afirmar una mejora de SciBERT: preparar comparación adicional BM25-normalizado sobre exactamente los mismos casos y chunks.
- En la ruta manual de párrafos suministrados por el usuario existe un máximo de **60.000 caracteres de texto acumulado**. Para despliegue público habrá que restringir también el tamaño HTTP de solicitudes en el proxy; no confundir ambos límites.
- El modo antiguo `POST /api/top3-fragmentos` **recibe textos del solicitante** y no puede garantizar su procedencia; el modo nuevo de corpus sí usa fragmentos precalculados de un `cited_id` documentado en la exportación.
- No se afirma que esta ruta esté desplegada públicamente o que los cinco casos sean representativos.
