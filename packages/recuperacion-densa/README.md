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

`dominio.py` (puro, solo stdlib) <- `servicio.py` (via `puertos.py`) <- `cli.py` (raiz de composicion).
`adaptador_proyecto_grado.py` sera el unico modulo que importe `proyecto_de_grado.*` y `src.app.*`.
