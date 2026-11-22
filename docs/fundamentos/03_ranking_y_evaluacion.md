# Ranking y evaluación

## 1. Clasificación frente a ranking

Un clasificador responde si un par parece relevante. Un recomendador necesita,
además, comparar varios candidatos y ordenarlos.

Para una consulta, el modelo produce algo como:

| Artículo | Probabilidad estimada |
|---|---:|
| A | 0,83 |
| B | 0,61 |
| C | 0,12 |

El ranking será `A, B, C`. No es necesario que 0,83 sea una probabilidad
perfectamente calibrada para que el orden sea útil.

## 2. Arquitectura en dos etapas

Comparar cada consulta con los 19.776 artículos y aplicar un modelo complejo a
todos sería costoso. El proyecto divide el trabajo:

```text
19.776 artículos
        ↓ primera etapa: similitud TF-IDF
Top-100 candidatos
        ↓ segunda etapa: regresión logística
ranking reordenado
        ↓
Top-10 mostrado al usuario
```

La primera etapa prioriza cobertura y velocidad. La segunda intenta mejorar las
posiciones sin cambiar el conjunto recuperado.

`top_n=100` es la cantidad de candidatos entregados al reordenador. `k=10` es
la profundidad principal en la que se calculan las métricas. Son conceptos
distintos.

## 3. El techo de la segunda etapa

Si la cita correcta no aparece en el Top-100, el reordenador no puede inventarla.
Por eso Recall@100 mide el techo de la arquitectura actual.

Al reordenar exactamente los mismos candidatos:

```text
Recall@100 antes = Recall@100 después
```

Si cambia, algún candidato fue agregado, eliminado o asociado a otra consulta,
lo que indica un error de evaluación.

## 4. Línea base

Una **línea base** es un método sencillo que sirve como referencia. Aquí es el
ranking TF-IDF sin reordenamiento supervisado.

Para demostrar una mejora, ambos métodos deben usar:

- las mismas consultas;
- los mismos candidatos;
- la misma exclusión del artículo citante;
- el mismo valor de K;
- las mismas definiciones de métricas.

Cambiar simultáneamente el conjunto de candidatos y el modelo impediría saber
qué produjo la diferencia.

## 5. Recall@K

El símbolo `@10` se lee «en los primeros diez resultados». No significa diez
consultas ni diez entrenamientos: es el límite de posiciones que se inspecciona
en la lista recomendada para cada consulta.

Recall@K responde:

> ¿La cita correcta aparece entre los primeros K resultados?

Con un único artículo relevante por consulta:

```text
Recall@10 = 1  si aparece entre las posiciones 1 y 10
Recall@10 = 0  si no aparece allí
```

El promedio sobre todas las consultas produce la métrica global. Por ejemplo:

```text
Recall@10 = 0,2882
```

significa que la cita correcta apareció en el Top-10 en aproximadamente el
28,82 % de las consultas.

Esto no significa que el 28,82 % de los diez artículos recomendados sean
correctos. Esa otra pregunta corresponde a Precision@10. Si una consulta
tuviera varios artículos relevantes, su Recall@10 sería la cantidad de
relevantes recuperados en esas diez posiciones dividida entre el total de
relevantes conocidos para esa consulta; después se promedia entre consultas.

## 6. MRR@K

MRR significa **Mean Reciprocal Rank**. Premia que el primer acierto aparezca
cerca del inicio:

| Posición | Puntaje recíproco |
|---:|---:|
| 1 | 1,000 |
| 2 | 0,500 |
| 3 | 0,333 |
| 10 | 0,100 |
| Fuera del Top-K | 0,000 |

```text
MRR@K = promedio(1 / posición del primer acierto)
```

MRR no debe interpretarse como una posición promedio. Un valor mayor indica
que los primeros aciertos tienden a aparecer más arriba.

Recall y MRR se complementan: dos modelos pueden encontrar la misma cantidad de
positivos, pero ubicarlos en posiciones muy diferentes.

### Ejemplo resuelto: las dos métricas sobre las mismas consultas

Supongamos cuatro consultas, cada una con una cita correcta conocida:

| Consulta | Posición de la cita correcta | Aporte a Recall@10 | Aporte a MRR@10 |
|---|---:|---:|---:|
| A | 1 | 1 | 1 / 1 = 1 |
| B | 2 | 1 | 1 / 2 = 0,5 |
| C | 10 | 1 | 1 / 10 = 0,1 |
| D | 15 (fuera del Top-10) | 0 | 0 |

```text
Recall@10 = (1 + 1 + 1 + 0) / 4 = 0,75
MRR@10    = (1 + 0,5 + 0,1 + 0) / 4 = 0,40
```

Encontramos la cita en el Top-10 en el 75 % de las consultas. MRR también
considera que el acierto de A es más accesible que el de C. Ambas métricas
incluyen todas las consultas en el promedio, incluso aquellas sin aciertos.

Si movemos el acierto de C de la posición 10 a la 1, Recall@10 permanece en
0,75 y MRR@10 sube a 0,625. Mejoró el orden aunque se encontró la misma cantidad
de citas. Ambas métricas van de 0 a 1 y un valor mayor es mejor.

En nuestro modelo, **MRR@10 = 0,1490** es el promedio de esos puntajes
recíprocos. No significa 14,90 % de aciertos ni una posición media de
`1 / 0,1490`. En cambio, **Recall@10 = 0,2882** sí equivale al 28,82 % de
consultas con acierto en este conjunto, que tiene un positivo por consulta.

## 7. Resultados actuales

Los experimentos completos utilizaron 30.390 consultas de entrenamiento, 9.381
de validación, Top-100, dos negativos por positivo y semilla 42.

| Método | Recall@10 | MRR@10 | Recall@100 |
|---|---:|---:|---:|
| TF-IDF comparable | 0,2571 | 0,1339 | 0,5160 |
| Regresión logística + aleatorios | **0,2882** | **0,1490** | 0,5160 |
| Regresión logística + difíciles | 0,0629 | 0,0212 | 0,5160 |

La variante aleatoria mejora 12,1 % relativo en Recall@10 y 11,3 % en MRR@10
frente a TF-IDF. Por eso es la seleccionada con la evidencia actual.

La variante difícil conserva Recall@100, así que no perdió candidatos: aprendió
un orden perjudicial. Este resultado debe conservarse porque enseña una
limitación real de las características disponibles.

## 8. Cómo seleccionar un modelo

Una comparación correcta sigue este orden:

1. Definir una pregunta, por ejemplo si cambia la estrategia de negativos.
2. Mantener constantes las demás decisiones.
3. Entrenar solo con `train`.
4. Comparar Recall@K y MRR@K sobre `val`.
5. Comprobar que Recall@100 permanezca constante.
6. Revisar coeficientes y casos de error.
7. Registrar parámetros, métricas y artefactos.
8. Seleccionar una configuración y reservar `test` para el cierre.

Accuracy o AUC pueden servir como diagnóstico del clasificador, pero no
reemplazan las métricas de ranking.

## 9. Limitaciones y evolución

El recuperador TF-IDF depende de palabras compartidas. Embeddings y modelos
preentrenados como SciBERT representan significado de forma más densa y podrían
recuperar artículos relacionados aunque utilicen otro vocabulario.

Posibles extensiones:

- mezclar negativos aleatorios y difíciles;
- incorporar posición y puntaje de TF-IDF;
- usar embeddings científicos en la primera etapa;
- emplear un modelo más expresivo para reordenar;
- medir latencia y memoria además de calidad.

Cada extensión debe evaluarse por separado. Modificar muchas variables en una
sola corrida impide atribuir la mejora a una decisión concreta.

## Error frecuente

No se deben comparar métricas calculadas con diferentes candidatos o valores de
K. Aunque tengan el mismo nombre, no representan el mismo experimento.

## Ideas clave

- Recuperar candidatos y reordenarlos son tareas distintas.
- Recall mide cobertura; MRR considera la posición del primer acierto.
- Recall@100 es el techo del reordenador actual.
- La variante aleatoria es la mejor configuración validada hasta ahora.
- Un resultado negativo también produce conocimiento útil.

Siguiente lectura: [Herramientas técnicas](herramientas_tecnicas.md).
