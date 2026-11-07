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

## Trazabilidad: campo `git` de los manifiestos

Cada manifiesto (`manifiesto_preparacion.json`, `manifiesto_recuperacion.json`,
`manifiesto_entradas.json` y el de cada corrida) registra el estado de git:

| Campo | Significado |
|---|---|
| `head` | Commit sobre el que se ejecuto el paso. |
| `dirty` | `true` solo si habia cambios en el **codigo** (todo salvo `proyecto_de_grado/docs/evidencias_clasificacion_a4/`). |
| `evidencia_sin_commit` | `true` si habia evidencia generada por el propio flujo sin commitear. |

Cada paso del flujo escribe archivos nuevos en la carpeta de evidencias, asi que
`evidencia_sin_commit: true` es lo normal cuando se commitea al final. Para una
reproduccion limpia basta con `dirty: false`.

**Manifiestos generados el 2026-11-06 (antes de este cambio).** Registraban un unico
`dirty` que incluia la evidencia; por eso casi todos dicen `dirty: true`. El codigo en el
`head` registrado no difiere del HEAD actual: `git diff <head> HEAD -- packages scripts src
proyecto_de_grado/src` esta vacio (verificado con `81634c5` y `21496e0`). No se editaron
esos manifiestos a mano porque otros archivos referencian sus SHA.

El README completo se escribe al final del plan (commit 12).
