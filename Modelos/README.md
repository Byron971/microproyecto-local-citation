# Modelos

Esta carpeta indica dónde están los modelos que usa la aplicación. Los pesos no se guardan en Git porque cada modelo pesa más de 1 GB.

## Modelos desplegados

La aplicación clasifica la función de una cita con dos clasificadores SciBERT, uno por cada pista de entrenamiento (M y S), y recupera los tres fragmentos más parecidos del artículo citado con SciBERT base.

| Modelo | Descarga | Tamaño | SHA-256 |
| --- | --- | ---: | --- |
| M | [modelo-M.zip](https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/modelo-M.zip) | 1,23 GB | `7b8c916def3e12d619e8e4efede8ac979efed67cb2978b111744b0ee242d4d5a` |
| S | [modelo-S.zip](https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/modelo-S.zip) | 1,23 GB | `c4b8d441a0d120569bca9ab4385351cd05743e2eda1c40fd9324283b4f604beb` |

- Catálogo de descargas: <https://proyectocitas-grupo19.click/models/>
- Huellas: [SHA256SUMS](https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/SHA256SUMS)
- Inventario de cada archivo: [manifest.json](https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/manifest.json)

Cada ZIP incluye el clasificador y la copia de SciBERT base (`allenai/scibert_scivocab_uncased`, revisión `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`). La API carga las dos pistas, así que se necesitan los dos ZIP.

## Descargar y verificar

```bash
mkdir -p /tmp/modelos-citas
curl -fL https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/modelo-M.zip -o /tmp/modelos-citas/modelo-M.zip
curl -fL https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/modelo-S.zip -o /tmp/modelos-citas/modelo-S.zip
curl -fL https://proyectocitas-grupo19.click/models/releases/ms-scibert-b8ee47317c29afbc/SHA256SUMS -o /tmp/modelos-citas/SHA256SUMS
cd /tmp/modelos-citas && sha256sum -c SHA256SUMS
```

En macOS se usa `shasum -a 256 -c SHA256SUMS`. Cómo descomprimirlos y arrancar el servicio con ellos está en la sección *Preparar el servicio científico* del [README principal](../README.md).

## De dónde salen

- Entrenamiento de M y S: [notebooks/10_modelos_finales_M_S.ipynb](../notebooks/10_modelos_finales_M_S.ipynb).
- Experimentos previos con SciBERT y SPECTER: cuadernos 04 a 07 de [notebooks/](../notebooks/).
- Modelo del tablero inicial (TF-IDF con reordenador lineal): [model-package/](../model-package/), que se instala como paquete de Python.
