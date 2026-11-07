# clasificacion-funcion

Clasificacion supervisada de la funcion de la cita (9 clases, entropia cruzada)
con dos encoders cientificos (SciBERT y SPECTER) y dos entradas (A: contexto +
titulo/abstract del citado; B: contexto + seccion + chunks Top-3), evaluados
sobre el mismo Test Gold (issue #103, A4).

Todo resultado es **PROVISIONAL** mientras el Gold humano v2 no este congelado
(#100): las etiquetas de entrenamiento son de Haiku.

Paquete hermano de `recuperacion-densa` (no lo extiende: su validacion bloquea
todo lo que no sea split train).

## Uso

```bash
uv sync --locked          # sin torch
uv run pytest -q
uv sync --group modelo    # opt-in: instala torch (CUDA 12.8)
```

El README completo se escribe al final del plan (commit 12).
