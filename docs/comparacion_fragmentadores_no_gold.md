# Fragmentación V1 vs. V2: verificación técnica sin Test Gold

## Qué existe y qué agrega esta verificación

`proyecto_de_grado/src/data/exportar_corpus_top3.py` incluye los
fragmentadores V1 y V2. El módulo
`proyecto_de_grado/src/data/comparar_fragmentacion.py` ya permite
compararlos sobre la **misma caché ACL OCL**. Este cambio no reemplaza
ninguno; agrega pruebas en CI que garantizan:

- V2 es igual a V1 para párrafos cortos dentro de la misma sección.
- V1 rechaza los párrafos largos en lugar de truncarlos silenciosamente.
- V2 preserva todas las palabras del párrafo original y conserva
  `paragraph_indices`, sección y `chunk_id` único.
- Ambos fragmentadores se comparan sobre exactamente los mismos archivos.
- Los informes no sobrescriben ejecuciones anteriores y reportan hashes
  de los documentos, sin texto, anotaciones humanas o etiquetas Gold.

## Ejecución en cualquier clon: pruebas automáticas con texto sintético

```bash
uv sync --locked --group dev
uv run pytest -q tests/test_comparar_fragmentacion_no_gold.py
```

GitHub Actions las ejecuta sin credenciales, snapshots, Torch ni datos
privados; un CI verde garantiza las **invariantes de la implementación**,
no una mejoría sobre el corpus real ni en Recall@3.

## Ejecución adicional cuando exista la caché ACL OCL

El comando ya existente analiza la **caché auténtica completa** de los
documentos de desarrollo y genera un JSON nuevo sin sobrescribir.

```bash
uv run python -m proyecto_de_grado.src.data.comparar_fragmentacion \
  --cache proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl \
  --salida proyecto_de_grado/artifacts/fragmentacion/ocl_v1_v2_2026_11.json
```

La salida reporta `total_archivos_misma_muestra`, `aceptados_v1`,
`aceptados_v2`, `recuperados_por_v2`, razones de rechazo, número de
chunks y SHA-256 del archivo OCL. La ejecución necesita que la caché
tenga al menos un documento; CI no intenta descargar la caché.

**Limitación importante:** es una auditoría descriptiva de los archivos
OCL disponibles. No mide la relevancia de fragmentos, Recall@3, MRR@3,
calidad de clasificación A/B ni generaliza automáticamente a artículos
no incluidos en la caché. Las mejoras de cobertura deben etiquetarse
como **técnicas**, nunca como mejores resultados científicos sin Gold.

## Próxima actividad que sí depende de los archivos reales

Si los documentos OCL están en el equipo de entrenamiento, ejecutar
el comando anterior y conservar el JSON como evidencia. Después elegir
la estrategia V1/V2 para las nuevas corridas, sin sobrescribir los
manifiestos de V1, y volver a crear embeddings con un identificador
explícito de fragmentador para evitar comparar configuraciones distintas.
