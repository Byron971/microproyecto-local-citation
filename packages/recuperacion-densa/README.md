# recuperacion-densa

Evaluacion **offline** de recuperacion densa Top-3 con SciBERT frente al baseline BM25 (issue #102).
Paquete aislado (propio `pyproject.toml`, `uv.lock` y `.venv`), igual que `auditoria-corpus`.

**Alcance:** comparacion tecnica sobre train, sin gold. No calcula Recall@3 ni MRR@3 hasta que
exista relevancia de chunks validada (issue #127).

## Pruebas (sin torch)

```bash
cd packages/recuperacion-densa && uv sync --locked && uv run pytest -q
```

El grupo `modelo` (torch/transformers) es opt-in: `uv sync --group modelo`.

## Arquitectura

`dominio.py` (puro, solo stdlib) <- `servicio.py` (via `puertos.py`) <- `cli.py` (raiz de composicion, sin torch) <- `cli_modelo.py` (inyecta el codificador torch).
`adaptador_proyecto_grado.py` sera el unico modulo que importe `proyecto_de_grado.*` y `src.app.*`.

## Resultados (issue #102)
Resumen en `proyecto_de_grado/docs/recuperacion_densa_scibert_a1.md`; evidencia en `proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/`; análisis en `notebooks/02_recuperacion_densa_scibert_top3.ipynb`.

- 605 contextos de train / 91 artículos, 0 violaciones de integridad, salidas deterministas (CUDA con y sin caché idénticas; CPU = CUDA en 60/60 contextos).
- Solape@3 SciBERT–BM25: 0,27 (micro) y 0,31 (macro) frente a ≈0,11 / 0,13 por azar. **Mide acuerdo, no relevancia.**
- **Sin gold: no se calcula Recall@3 / Hit@3 / MRR@3** (pendiente issue #127).
- Ejecución con modelo: `uv run --project packages/recuperacion-densa --group modelo python -m recuperacion_densa.cli_modelo`.

## Fragmentación V2 sin anotaciones humanas (experimental)

La versión histórica V1 rechaza artículos con párrafos de más de 300 palabras;
la V2 conserva el texto en segmentos de hasta 300 palabras, con IDs de chunk
distintos. **V1 continúa siendo la opción predeterminada y es la que corresponde
a los resultados científicos históricos**.

Se puede ejecutar una validación sin torch ni datos Gold:

```bash
uv run --project packages/recuperacion-densa python -m recuperacion_densa.cli \
  --fragmentador v2 --solo-validar \
  --exportar-casos proyecto_de_grado/artifacts/top3_v2/entrada_train_v2.json
```

Para comparar ambos fragmentadores con el mismo SciBERT real, ejecutar dos
corridas en **directorios nuevos**, usando el mismo modelo, revisión, semilla y
corpus de entrada ACL OCL. Instalar primero el grupo `modelo` y suministrar
las rutas de datos/cache preparadas en el proyecto:

```bash
uv run --project packages/recuperacion-densa --group modelo \
  python -m recuperacion_densa.cli_modelo \
  --fragmentador v2 --salida proyecto_de_grado/artifacts/top3_v2/corrida_scibert
```

El manifiesto registra `fragmentador=v2` y la entrada exportada lleva
`estrategia_fragmentacion`. No se permite solicitar `--fragmentador v2`
con `--entrada`, pues ese JSON ya tiene chunks construidos. Para puntuar la
relevancia, cualquier Gold V1 debe revisarse/reanotarse sobre los nuevos IDs:
**esta modificación no demuestra mejora de Hit@3, Recall@3, MRR@3 ni F1.**
Los tests sin torch usan un codificador falso únicamente para verificar
contratos y no deben presentarse como evidencia de inferencia SciBERT.

