# Especificación técnica del entregable: modelo supervisado de relevancia

## 1. Objetivo

Implementar, evaluar y registrar un reordenador supervisado que asigne un
puntaje de relevancia a cada par contexto-artículo y vuelva a ordenar los
candidatos recuperados por TF-IDF.

El entregable debe permitir responder de manera reproducible:

> ¿Entrenar con negativos difíciles mejora Recall@K y MRR frente a TF-IDF y
> frente al mismo clasificador entrenado con negativos aleatorios?

La teoría detrás de cada componente se explica en la
[ruta de fundamentos](../fundamentos/README.md). Los nombres registrados y los
comandos de cada corrida se detallan en
[Herramientas técnicas](../fundamentos/herramientas_tecnicas.md).

## 2. Alcance

### 2.1 Incluido

- Construcción de características de similitud y longitud.
- Generación reproducible de negativos difíciles desde el Top-100 TF-IDF.
- Entrenamiento de una regresión logística con negativos aleatorios.
- Entrenamiento de la misma regresión con negativos difíciles.
- Reordenamiento del mismo conjunto de candidatos de validación.
- Evaluación con métricas de ranking.
- Registro de parámetros, métricas y artefactos en MLflow.
- Pruebas automatizadas y documentación.
- Tabla, captura y conclusiones para el reporte 02.

### 2.2 Fuera del alcance mínimo

- Fine-tuning de SciBERT.
- Modelos comerciales o redes neuronales.
- Empaquetamiento como archivo wheel.
- Integración definitiva con la API y el tablero.
- Evaluación final sobre el conjunto de prueba.

Estas actividades pueden realizarse después. No deben retrasar la comparación
mínima requerida por el issue #6.

## 3. Insumos ya disponibles

| Componente | Ubicación | Estado o uso |
|---|---|---|
| Datos fuente | `data/raw/` | Artículos, contextos y splits oficiales |
| Pares aleatorios | `src/data/build_pairs.py` | Variante de control |
| Recuperador TF-IDF | `src/models/tfidf_baseline.py` | Generación inicial de candidatos |
| Exportador Top-100 | `src/training/export_top100.py` | Insumo del reordenador |
| Extracción de hard negatives | `src/evaluation/diagnose_negatives.py` | Base para la estrategia difícil |
| Métricas | `src/evaluation/ranking_metrics.py` | Recall@K y MRR |
| Configuración MLflow | `src/tracking/mlflow_setup.py` | Experimento y nombres comunes |
| Línea base ejecutable | `src/training/run_tfidf_baseline.py` | Comparación de referencia |
| Características del par | `src/features/pair_features.py` | Implementado y probado |
| Pares difíciles | `src/data/build_hard_pairs.py` | Implementado y probado |
| Reordenador lineal | `src/models/linear_reranker.py` | Implementado y probado |
| Entrenamiento supervisado | `src/training/run_linear_reranker.py` | Implementado; configuración YAML e inferencia persistida |
| Pruebas aisladas | `tox.ini` | Implementado con Tox 4 |

El código mínimo ya existe. El trabajo pendiente se concentra en ejecutar los
dos experimentos completos, analizar los resultados registrados en MLflow e
incorporar la evidencia y las conclusiones al reporte 02.

## 4. Decisiones obligatorias de diseño

### 4.1 Particiones

- Ajustar escalador y clasificador solamente con pares de `train`. El TF-IDF
  se ajusta sobre el catálogo fijo de artículos, sin etiquetas ni contextos de validación.
- Utilizar `val` para comparar estrategias y escoger una configuración.
- Reservar `test` para la evaluación final posterior.
- No volver a dividir los pares con `train_test_split`.

### 4.2 Unidad de datos

La unidad de entrenamiento es un par:

```text
context_id, paper_id, label
```

La unidad de evaluación es una consulta completa con su lista de candidatos.
Las métricas se calculan después de agrupar por `context_id`.

### 4.3 Candidatos

- Usar Top-N = 100 tanto en entrenamiento difícil como en validación.
- Excluir los artículos positivos al generar negativos.
- Excluir el artículo citante de todos los rankings.
- No insertar artificialmente positivos ausentes en la evaluación.
- Recalcular la línea base si se modifica su política de candidatos.

### 4.4 Comparación controlada

Las variantes aleatoria y difícil deben compartir:

- el mismo algoritmo;
- las mismas características;
- el mismo número de negativos por positivo;
- la misma semilla cuando corresponda;
- las mismas consultas y candidatos de validación;
- las mismas definiciones de Recall@K y MRR.

La estrategia de negativos debe ser la única diferencia del experimento
principal.

## 5. Herramientas y patrones esperados por la materia

La implementación debe adaptar los patrones de los talleres 4 y 5:

- `Pipeline` de scikit-learn para mantener juntas las transformaciones y el
  clasificador.
- `StandardScaler` para escalar similitudes y longitudes.
- `LogisticRegression` como primera versión supervisada.
- `predict_proba(X)[:, 1]` como puntaje de ranking.
- MLflow para registrar cada corrida, no solamente una captura.
- `mlflow.sklearn.log_model` o un artefacto equivalente para conservar el
  modelo completo.
- Configuración reproducible mediante argumentos o configuración central.
- Semilla explícita.
- Pruebas de entrenamiento y predicción con pytest.

No se copiarán literalmente algunas decisiones de los ejemplos:

- no escalar antes de separar los datos;
- no usar validación cruzada por filas de pares;
- no seleccionar mediante accuracy;
- no guardar únicamente el clasificador si los vectorizadores quedan fuera;
- no construir un wheel en esta entrega.

Se incorporó Tox porque el equipo ya lo utilizó en los talleres. En este
proyecto se usa como orquestador de pruebas aisladas; no reemplaza a `uv`, no
entrena el corpus completo y no obliga a empaquetar la aplicación.

Si posteriormente se aplica validación cruzada, deberá agruparse por
`context_id` mediante `GroupKFold` para evitar que pares de una misma consulta
aparezcan simultáneamente en entrenamiento y validación.

---

## 6. Diseño concreto de la implementación

Los nombres siguientes son una organización sugerida. Pueden adaptarse a las
convenciones del equipo.

### 6.1 Módulo de características

Archivo sugerido:

```text
src/features/pair_features.py
```

Responsabilidades:

- limpiar contextos;
- construir los textos de título y abstract;
- ajustar o recibir el vectorizador TF-IDF;
- calcular características para una lista de pares;
- devolver `X`, etiquetas y metadatos de contexto/artículo;
- conservar siempre el mismo orden de columnas.

### 6.2 Generación de pares difíciles

Archivo sugerido:

```text
src/data/build_hard_pairs.py
```

Responsabilidades:

- leer el Top-100 por consulta;
- excluir positivos y artículo citante;
- seleccionar `n_hard` negativos;
- emitir pares con la misma estructura que los pares aleatorios;
- almacenar los parámetros de generación;
- producir resultados deterministas.

También se puede extender `src/data/build_pairs.py`, siempre que las estrategias
`random` y `hard` queden claramente separadas y probadas.

### 6.3 Modelo

Archivo sugerido:

```text
src/models/linear_reranker.py
```

Responsabilidades:

- construir el `Pipeline` de escalamiento y regresión logística;
- entrenar;
- producir probabilidades de relevancia;
- reordenar candidatos conservando sus identificadores.

### 6.4 Script de entrenamiento

Archivo sugerido:

```text
src/training/run_linear_reranker.py
```

Responsabilidades:

1. Cargar datos y candidatos TF-IDF.
2. Elegir `random` o `hard` mediante un argumento de línea de comandos.
3. Construir características de entrenamiento.
4. Entrenar el modelo.
5. Puntuar todos los candidatos Top-100 de validación.
6. Reordenar por consulta.
7. Calcular métricas de ranking.
8. Registrar parámetros, métricas y artefactos en MLflow.
9. Mostrar un resumen reproducible en consola.

Interfaz implementada:

```bash
uv run python -m src.training.run_linear_reranker train
uv run python -m src.training.run_linear_reranker evaluate \
  --model artifacts/<run_id>/model.joblib --split val
```

Los parámetros se definen únicamente en `config/model.yaml`, validado por
`src/config.py`. Cambie `negative_strategy` para comparar variantes.
`train` incluye evaluación en validación; `evaluate` carga el modelo completo
con su configuración guardada sin reajustar ningún componente.

Los candidatos se regeneran con el recuperador del modelo. No se consume la
caché Top-100 anterior porque no acredita qué vocabulario la produjo.
La evaluación en `test` está disponible mediante `--split test`, reservada
para después de la selección del modelo.


---

## 7. Plan de experimentación mínimo

### 7.1 Preparación

1. Verificar que existen los datos crudos.
2. Revisar `config/model.yaml`.
3. El entrenamiento genera pares y candidatos con esa configuración.
4. Unificar la exclusión del artículo citante.
5. Ejecutar las pruebas existentes.

Comandos ya disponibles:

```bash
uv run python -m src.data.make_processed
uv run python -m src.training.export_top100 --splits train val
uv run pytest -q
```

No se recomienda usar `test` durante esta etapa de selección.

### 7.2 Corrida de control

Volver a ejecutar TF-IDF con la política definitiva de candidatos y registrar:

- Top-N = 100;
- métricas en K = 1, 5, 10, 20, 50 y 100;
- tiempo y versión de datos.

Esta será la referencia válida para los dos reordenadores.

### 7.3 Experimento A: negativos aleatorios

- Regresión logística.
- Dos negativos por positivo.
- Semilla 42.
- Características mínimas.
- Evaluación sobre todo el Top-100 de validación.

### 7.4 Experimento B: negativos difíciles

- Mismo algoritmo.
- Mismas características.
- Misma cantidad de negativos.
- Negativos extraídos del Top-100 TF-IDF.
- Misma evaluación de validación.

### 7.5 Extensiones opcionales

Solo después de completar la comparación mínima:

- ajustar `C`;
- probar `class_weight="balanced"`;
- añadir posición y puntaje TF-IDF;
- mezclar negativos aleatorios y difíciles;
- comparar diferente cantidad de negativos;
- probar un clasificador lineal alternativo.

Cada cambio debería corresponder a una corrida distinta. No conviene modificar
varias decisiones al mismo tiempo porque luego no se sabrá cuál produjo la
mejora.

---

## 8. Pruebas automatizadas necesarias

Además de las pruebas actuales, el entregable debería comprobar:

### Características

- la similitud es mayor para textos relacionados que para textos no
  relacionados;
- las columnas se generan siempre en el mismo orden;
- los marcadores `TARGETCIT` y `OTHERCIT` no se usan como señal;
- títulos o abstracts vacíos no rompen el pipeline;
- las longitudes se calculan correctamente.

### Negativos difíciles

- ningún positivo aparece como negativo;
- el artículo citante se excluye;
- se conserva el orden TF-IDF;
- se respeta `n_hard`;
- dos ejecuciones generan el mismo resultado.

### Modelo y reordenamiento

- el modelo devuelve un puntaje por candidato;
- el ranking queda en orden descendente;
- no se pierden ni duplican candidatos;
- cada ranking permanece asociado a su consulta;
- Recall@100 no cambia al reordenar los mismos candidatos.

### MLflow

- las dos estrategias usan el mismo experimento;
- se registran `negative_strategy`, `top_n`, `k` y la semilla;
- las métricas conservan los nombres acordados por el equipo.

---

## 9. Cómo interpretar los posibles resultados

### Caso A: negativos difíciles mejoran MRR y Recall@10

Esta es la evidencia más favorable. Indicaría que entrenar con candidatos
parecidos a los observados en producción ayuda a subir los positivos dentro del
ranking.

Conclusión posible:

> El reordenador entrenado con negativos difíciles fue seleccionado porque
> obtuvo mayor MRR@10 y Recall@10 que la línea base y que la variante entrenada
> con negativos aleatorios, bajo el mismo conjunto de candidatos.

### Caso B: accuracy alta con aleatorios, pero ranking sin mejora

Este resultado confirmaría que la clasificación con negativos aleatorios mide
una tarea demasiado fácil.

Conclusión posible:

> Aunque la variante aleatoria obtuvo alta accuracy, no mejoró las métricas de
> ranking. La métrica de clasificación no representa adecuadamente el uso real
> del reordenador.

### Caso C: ninguna variante supera TF-IDF

También es un resultado válido. Podría indicar que:

- las características contienen casi la misma información que TF-IDF;
- el modelo lineal no captura relaciones semánticas suficientes;
- se requieren más negativos por consulta;
- el techo del recuperador limita el sistema;
- el siguiente experimento debería utilizar embeddings científicos.

No se deben ocultar resultados negativos. La entrega evalúa el proceso,
reproducibilidad, análisis y justificación, no solamente obtener un número
superior.

### Caso D: Recall@100 cambia

Esto sugiere un error experimental, porque reordenar no cambia el conjunto de
candidatos. Antes de interpretar otras métricas se debe revisar:

- exclusión del artículo citante;
- pérdida o duplicación de identificadores;
- consultas evaluadas;
- tamaño del ranking;
- asociación entre rankings y contextos.

---

## 10. Contenido que debe incorporarse al reporte

### 10.1 Subsección del modelo supervisado

Debe explicar brevemente:

- qué modelo se utilizó;
- qué representa cada ejemplo;
- qué características recibe;
- cómo se construyeron los negativos;
- cómo se convirtió la probabilidad en un ranking;
- sobre qué partición se entrenó y evaluó.

### 10.2 Tabla comparativa

Formato recomendado:

| Modelo | Negativos | Recall@10 | MRR@10 | Cambio de MRR |
|---|---|---:|---:|---:|
| TF-IDF | No aplica | 0,2541* | 0,1249* | Referencia |
| Regresión logística | Aleatorios | Resultado | Resultado | Resultado |
| Regresión logística | Difíciles | Resultado | Resultado | Resultado |

`*` La línea base debe recalcularse si cambia la política de exclusión del
artículo citante.

### 10.3 Evidencia de MLflow

Incluir una captura en la que se observen, en el mismo experimento:

- línea base;
- variante aleatoria;
- variante difícil;
- parámetros que diferencian las corridas;
- Recall@K y MRR comparables.

### 10.4 Observaciones y conclusiones

Las conclusiones deben responder:

1. ¿Qué variante obtuvo mejor ranking?
2. ¿La accuracy contó la misma historia que MRR y Recall@K?
3. ¿Qué efecto tuvo usar negativos difíciles?
4. ¿Qué modelo se selecciona para el prototipo?
5. ¿Cuál es la principal limitación observada?

### 10.5 Reporte de trabajo en equipo

Actualizar el aporte de José Zambrana con evidencia concreta:

- extractor de características;
- generación de negativos difíciles;
- entrenamiento del reordenador;
- evaluación de ranking;
- corridas y artefactos MLflow;
- pruebas y documentación;
- Pull Request y commits correspondientes.

---

## 11. Definición de terminado

Estado actualizado: `x` significa que existe implementación y verificación
automatizada; los puntos sin marcar necesitan una corrida completa, evidencia
en el reporte o el flujo de integración del equipo.

El issue puede considerarse terminado cuando se cumpla todo lo siguiente:

- [x] Existen características de similitud con título, abstract y longitudes.
- [x] Los transformadores se ajustan sin utilizar etiquetas de validación ni prueba.
- [x] Existe generación reproducible de negativos difíciles.
- [x] Positivos y artículo citante quedan excluidos de los negativos.
- [x] Se entrenó una variante completa con negativos aleatorios.
- [x] Se entrenó otra variante completa con negativos difíciles.
- [x] Ambas rutas reordenan exactamente los mismos candidatos de validación.
- [x] El script calcula Recall@K y MRR con el mismo conjunto de candidatos.
- [x] La selección se basa en métricas de ranking, no en accuracy o AUC.
- [x] Los dos runs están registrados en el experimento compartido de MLflow.
- [x] El script almacena el modelo y sus transformaciones como artefactos.
- [x] Existen pruebas automatizadas para características, negativos y ranking.
- [x] El procedimiento está documentado en el README y esta especificación.
- [x] Los resultados y conclusiones están incorporados al reporte 02.
- [x] La contribución aparece en el reporte de trabajo en equipo.
- [ ] Los cambios están versionados mediante commits y Pull Request.

### 11.1 Resultados obtenidos en el servidor MLflow compartido

Las corridas completas utilizaron 30.390 consultas de entrenamiento, 9.381
consultas de validación, Top-N igual a 100, dos negativos por positivo y semilla
42. Además de la comparación mínima (una corrida por estrategia de negativos),
se ejecutó un barrido de regularización (`c` = 0,1 / 1,0 / 10,0) por estrategia,
seis corridas en total, registradas en el experimento compartido de MLflow
(`http://100.53.183.142:8050`) y verificadas vía su API REST.

| Método | Recall@10 | MRR@10 | Recall@100 |
|---|---:|---:|---:|
| TF-IDF sobre candidatos comparables | 0,2571 | 0,1339 | 0,5160 |
| Regresión logística + aleatorios (`c=1,0`) | **0,2882** | **0,1490** | 0,5160 |
| Regresión logística + difíciles (`c=1,0`) | 0,0629 | 0,0212 | 0,5160 |

El valor de `c` no altera esta conclusión: las tres corridas con negativos
aleatorios quedan dentro de 0,0001 de MRR@10 entre sí, y las tres con negativos
difíciles también. La variante aleatoria es la seleccionada con la evidencia
actual. La variante difícil no perdió candidatos —Recall@100 es idéntico—, sino
que aprendió un orden perjudicial. En sus datos de entrenamiento, la similitud
media con el abstract fue 0,2726 para los negativos difíciles y 0,1295 para los
positivos; por eso la regresión asignó a esta señal un coeficiente de -2,09 en
las tres corridas. El resultado indica que usar exclusivamente los dos falsos
positivos léxicos más altos produce un cambio de distribución demasiado fuerte
para las cinco características disponibles, y que no es un artefacto de la
regularización elegida. Una mezcla de negativos aleatorios y difíciles queda
como extensión, no como parte de la comparación mínima.

---

## 12. Orden de trabajo recomendado

Para reducir el riesgo de llegar al final con resultados incomparables:

1. **Unificar primero el protocolo de candidatos y métricas.**
2. **Implementar y probar el extractor de características.**
3. **Implementar y probar la generación de negativos difíciles.**
4. **Entrenar la variante con negativos aleatorios.**
5. **Entrenar la variante con negativos difíciles.**
6. **Evaluar ambas sobre el mismo Top-100 de validación.**
7. **Registrar modelos, parámetros, métricas y artefactos en MLflow.**
8. **Analizar resultados antes de escoger una variante.**
9. **Incorporar tabla, captura y conclusiones al reporte.**
10. **Actualizar evidencia individual y abrir el Pull Request.**

La prioridad no es producir muchas variantes. La prioridad es que dos variantes
simples sean reproducibles, comparables y permitan explicar qué se aprendió del
experimento.
