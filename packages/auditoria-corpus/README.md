# auditoria-corpus

Auditoria de extraccion, chunks y metadatos retoricos de la cadena ACL-200 -> ACL OCL -> chunks (issue #101).
Paquete **aislado**: tiene su propio `pyproject.toml`, `uv.lock` y `.venv` (igual que `model-package`). No es miembro de un workspace todavia.

## Uso (sin red salvo `descarga`)

```bash
# Pruebas (desde packages/auditoria-corpus)
uv sync --group dev && uv run pytest -q

# Desde la raiz del repo:
# 1) UNICO paso con red: muestra fija con semilla de citados -> cache_ocl + manifiesto
uv run --project packages/auditoria-corpus python -m auditoria_corpus.descarga --n 200 --semilla 101
# 2) Auditoria sobre la cache local (determinista, sin red)
uv run --project packages/auditoria-corpus python -m auditoria_corpus.cli
```

Salidas en `proyecto_de_grado/artifacts/auditoria_a1/` (ignorado por git): `resumen.json`, `auditoria_chunks.csv` (sin texto) y `muestras_train.csv` (solo train, sin IDs de gold/piloto; columnas de verificacion manual vacias). La cobertura siempre se declara **sobre la cache local**. Nada de esto es gold ni una metrica Top-3.

## Arquitectura

`dominio.py` (puro) <- `servicio.py` (orquesta via `puertos.py`) <- `cli.py` / `descarga.py` (composition root).
`adaptador_proyecto_grado.py` es el **unico** modulo que importa `proyecto_de_grado.*`.


