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
