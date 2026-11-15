# Experimento controlado: fragmentación de párrafos V2 (issue #101)

## Problema y alcance
La función V1 de `proyecto_de_grado/src/data/exportar_corpus_top3.py` rechaza un artículo completo si uno de sus párrafos supera 300 palabras o 5.000 caracteres. Esto reduce cobertura y puede excluir artículos de manera sistemática. **Los artefactos, métricas y checkpoints existentes siguen siendo resultados V1**, no se sustituyen.

V2 es **opt-in**. Conserva la fragmentación V1 para párrafos que ya cumplen límites. En párrafos largos, divide por fronteras de tokens y prefiere oraciones completas cuando la partición resulta razonable; nunca trunca texto. Cada segmento conserva sección, índice del párrafo OCL y un ID determinista `pNNNNN-sMMM`. Rechaza tokens indivisibles que exceden 5.000 caracteres en vez de truncarlos. Para producir cifras científicas hay que ejecutar el mismo experimento con la nueva versión, nunca extrapolar datos V1.

## Comandos
Desde la raíz, con los datos DVC y la caché ACL OCL ya disponibles localmente:

```bash
uv run python -m proyecto_de_grado.src.data.comparar_fragmentacion \
  --cache proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl \
  --salida proyecto_de_grado/artifacts/comparacion_fragmentacion_v1_v2.json

uv run python -m proyecto_de_grado.src.data.exportar_corpus_top3 \
  --fragmentador v2 --limite 100 \
  --salida proyecto_de_grado/artifacts/top3_v2/casos_train_v2.json

uv run pytest -q proyecto_de_grado/tests/test_exportar_corpus_top3.py
```

La comparación procesa **la misma colección de archivos** para ambos algoritmos e informa aceptados, rechazados y recuperados por V2. La caché descargada no es una muestra aleatoria ni refleja todo ACL-200. El reporte no mide Hit@3, Recall@3, MRR@3 ni F1 de clasificación. Si no existe la caché, el script falla; no rellena cifras.

La opción predeterminada sigue siendo `--fragmentador v1`. Por protección de evidencia, V2 exige una ruta de salida nueva, distinta del artefacto por defecto, y rechaza sobrescribir archivos existentes.

## Controles de integridad y siguientes pasos
- Comparar `total_archivos_misma_muestra`, `aceptados_v1`, `aceptados_v2` y causas de rechazo. Verificar manualmente párrafos con fórmulas, bibliografía y tablas.
- Un mismo artículo puede producir fragmentos distintos y **IDs distintos** con V2. No reutilizar etiquetas Gold, juicios de relevancia ni embeddings calculados para V1 sobre esos IDs sin una nueva revisión/anotación.
- Medir si el nuevo chunking mejora las tareas Top-3 y función de cita con el **mismo conjunto de consultas**, encoders, semillas y Gold humano independiente. La hipótesis de mejora queda **abierta**.
- Validar cobertura documental de citados, no solamente los 200 artículos ya descargados.
- Mantener v1 como referencia histórica: no modificar sin discusión los checkpoints, predicciones ni resultados reportados.

## Estado de evidencia
**Implementación experimental y tests sintéticos:** disponibles en este PR. **Medición sobre la caché real / comparación científica / aprobación de cambio de protocolo:** aún pendientes de ejecutar y revisar con el equipo. **Test Gold:** no certificado por esta modificación.
