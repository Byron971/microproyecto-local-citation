# Modelo supervisado

## 1. Qué significa aprender con supervisión

En aprendizaje supervisado se presentan ejemplos acompañados por una respuesta
conocida. La unidad de entrenamiento del proyecto es un par:

```text
(context_id, paper_id, label)
```

La etiqueta `label` indica:

- `1`: el artículo fue citado y es un ejemplo positivo;
- `0`: el artículo no fue citado y es un ejemplo negativo.

El modelo intenta aprender una función que reciba las características del par y
estime su probabilidad de relevancia.

## 2. Características utilizadas

El texto no llega directamente al clasificador. `PairFeatureExtractor` produce
cinco números:

| Característica | Qué describe |
|---|---|
| `similarity_title` | Similitud TF-IDF entre contexto y título |
| `similarity_abstract` | Similitud TF-IDF entre contexto y abstract |
| `context_length` | Cantidad de palabras del contexto |
| `title_length` | Cantidad de palabras del título |
| `abstract_length` | Cantidad de palabras del abstract |

La **ingeniería de características** consiste en elegir señales numéricas que
puedan ayudar al modelo. Estas cinco son simples e interpretables; no garantizan
que puedan representar relaciones semánticas complejas.

## 3. Regresión logística

Pese a su nombre, la regresión logística se utiliza para clasificación. Primero
combina las características con pesos aprendidos:

```text
z = b + w₁x₁ + w₂x₂ + ... + w₅x₅
```

Después aplica la función sigmoide:

```text
P(relevante) = 1 / (1 + e⁻ᶻ)
```

El resultado está entre 0 y 1. En este proyecto no se usa principalmente para
decidir una clase rígida; se usa como puntaje para ordenar candidatos:

```python
predict_proba(X)[:, 1]
```

Cuanto mayor sea la probabilidad estimada, más arriba queda el artículo.

## 4. Escalamiento y coeficientes

Las similitudes suelen estar entre 0 y 1, mientras las longitudes pueden superar
100 palabras. `StandardScaler` transforma cada columna para que tenga una escala
comparable antes de entrenar.

El proyecto conserva escalador y regresión dentro de un `Pipeline`:

```text
características → StandardScaler → LogisticRegression
```

Después del escalamiento:

- un coeficiente positivo aumenta la probabilidad estimada;
- un coeficiente negativo la reduce;
- un valor absoluto grande indica mayor influencia dentro del modelo.

Los coeficientes muestran asociaciones aprendidas, no relaciones causales.

## 5. Regularización y otros hiperparámetros

Un **parámetro aprendido** es un valor encontrado por el modelo, como un
coeficiente. Un **hiperparámetro** se elige antes de entrenar.

| Hiperparámetro | Función |
|---|---|
| `C` | Inverso de la intensidad de regularización |
| `class_weight` | Importancia asignada a cada clase |
| `max_iter` | Máximo de iteraciones del optimizador |
| `seed` | Control de operaciones aleatorias |

Un `C` pequeño aplica regularización más fuerte y restringe los coeficientes;
uno grande permite un ajuste más flexible. `max_iter=1000` es un límite: el
entrenamiento puede finalizar antes si converge.

## 6. Negativos aleatorios y difíciles

### Negativos aleatorios

Se eligen del catálogo completo, excluyendo siempre el positivo y el artículo
citante. Suelen ser temáticamente diferentes y fáciles de distinguir.

Ventaja: enseñan una separación general entre textos relacionados y no
relacionados. Riesgo: la tarea de entrenamiento puede ser más sencilla que los
casos vistos después de TF-IDF.

### Negativos difíciles

Se toman de los primeros resultados incorrectos de TF-IDF. Comparten bastante
vocabulario con el contexto, por lo que se parecen a los candidatos observados
durante el reordenamiento.

Ventaja: concentran el aprendizaje en errores reales del recuperador. Riesgo:
si se usan exclusivamente ejemplos extremos y las características son
insuficientes, el modelo puede aprender una relación perjudicial.

En el experimento completo:

| Clase | Similitud media con el abstract |
|---|---:|
| Positivos | 0,1295 |
| Negativos aleatorios | 0,0170 |
| Negativos difíciles | 0,2726 |

Los negativos difíciles eran, en promedio, más similares que los positivos.
La regresión logística asignó aproximadamente `-2,09` a
`similarity_abstract`, invirtió esa señal y empeoró el ranking. Esto no implica
que los negativos difíciles sean siempre malos; indica que la combinación
exclusiva usada aquí es demasiado exigente para las cinco características.

## 7. Particiones y fuga de información

El conjunto se divide por consultas:

- `train`: aprende escalador y clasificador;
- `val`: compara alternativas y selecciona el modelo;
- `test`: se reserva para una evaluación final posterior.

La **fuga de información** ocurre cuando el entrenamiento utiliza respuestas o
estadísticas que solo deberían conocerse en validación o prueba. Un ejemplo
sería escalar todas las filas antes de separar los datos.

Tampoco conviene dividir aleatoriamente una tabla de pares: pares del mismo
`context_id` podrían terminar simultáneamente en entrenamiento y validación.

## 8. Reproducibilidad

Con los mismos datos, código, parámetros y `seed=42`, el experimento debe
producir los mismos negativos y resultados equivalentes. La semilla no mejora
la calidad; permite repetir la comparación.

La configuración principal usa dos negativos por positivo:

```text
30.390 consultas × 3 pares = 91.170 pares de entrenamiento
```

## Error frecuente

Una accuracy alta sobre pares aleatorios no demuestra que el ranking sea útil.
El producto necesita colocar la cita correcta arriba entre candidatos parecidos.

## Ideas clave

- La etiqueta supervisa qué pares deberían recibir puntajes altos.
- La regresión logística produce una probabilidad interpretable.
- El escalamiento evita que las unidades dominen los coeficientes.
- Los negativos determinan qué distinción aprende el modelo.
- Validación y prueba no deben utilizarse para ajustar el clasificador.

Siguiente lectura: [Ranking y evaluación](03_ranking_y_evaluacion.md).
