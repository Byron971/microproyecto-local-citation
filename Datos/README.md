# Datos

Esta carpeta indica de dónde vienen los datos del proyecto y cómo obtenerlos. Los archivos están en `data/` y se versionan con DVC, no con Git, por su tamaño.

## Origen

Las citas vienen de ACL-200, del repositorio [Local-Citation-Recommendation](https://github.com/nianlonggu/Local-Citation-Recommendation). Son 63.768 citas de artículos de lingüística computacional y 19.776 artículos con título y resumen. El texto completo de los artículos citados se prepara a partir de ACL OCL.

## Conjuntos versionados

| Carpeta | Qué contiene | Tamaño | ¿Se baja sin credenciales? |
| --- | --- | ---: | --- |
| `data/raw/` | ACL-200 original: `contexts.json`, `papers.json`, `train.json`, `val.json`, `test.json` | 67 MB | Sí |
| `data/jurado/` | Etiquetas del jurado de tres modelos abiertos sobre 18.000 citas (versión 3) | 19 MB | Sí |
| `data/dataset_funciones/` | Las 18.000 citas con la función de consenso del jurado y el uso de cada una: entrenamiento (9.893), validación (2.331), Test Gold (1.533), reserva (751), calibración (20) y excluidas | 1,5 MB | Sí |
| `data/processed/` | Datos derivados del tablero inicial | 50 MB | No, se regenera (ver abajo) |

## Cómo obtenerlos

El remoto de lectura por defecto es `publico` (HTTPS), así que no se necesitan credenciales de AWS:

```bash
uv sync --locked --group research
uv run dvc pull data/raw.dvc data/jurado.dvc data/dataset_funciones.dvc
```

`data/processed/` se regenera a partir de `data/raw/`:

```bash
uv run --group research python -m src.data.make_processed
```

## Exploración

La exploración de los datos está en [notebooks/01_exploracion_datos.ipynb](../notebooks/01_exploracion_datos.ipynb). Las hojas de anotación del Test Gold no se publican porque contienen el trabajo de los anotadores. Las métricas que salen de ellas están en `proyecto_de_grado/`.
