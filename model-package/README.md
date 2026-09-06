# modelo-citas

Modelo de recomendación local de citas académicas, empaquetado como librería
instalable. Recupera candidatos con TF-IDF sobre el corpus de artículos y los
reordena con una regresión logística sobre cinco características del par
contexto-artículo.

El wheel incluye el modelo entrenado y los metadatos de los artículos: instalarlo
es suficiente para predecir, sin necesidad del dataset ni del repositorio.

## Uso

```python
from modelo_citas import make_prediction

resultado = make_prediction(
    context="Recent work on neural machine translation with attention",
    top_k=5,
)
print(resultado["predictions"])
```

`make_prediction` devuelve `{"predictions": [...], "version": ..., "errors": None}`.
Cada recomendación trae `posicion`, `paper_id`, `titulo`, `resumen`, `similitud`
(probabilidad del reordenador) y `similitud_tfidf` (coseno del recuperador).

`load_model()` carga el artefacto en memoria de forma explícita —útil al arrancar
un servidor— y `describe()` devuelve la ficha técnica del modelo servido.

## Entrenar y construir

```bash
tox -e train    # genera modelo_citas/trained/modelo-citas-output<VERSION>.pkl
tox             # corre las pruebas
tox -e build    # construye el wheel en dist/
```

`tox -e train` usa `../data/raw` por omisión; también acepta `--data-dir` o la
variable de entorno `MODELO_CITAS_DATA_DIR`.

La versión vive en `modelo_citas/VERSION` y da nombre al artefacto, así que al
subirla hay que reentrenar antes de construir el wheel.
