# Herramientas técnicas del proyecto

## 1. Preparar el entorno y los datos

Ejecute los comandos desde la raíz del repositorio. El proyecto utiliza Python
3.14 y uv para instalar las dependencias de `uv.lock`:

```bash
uv sync --locked
uv run dvc pull
```

DVC descarga los datos cuando tiene acceso al remoto. El entrenamiento necesita
`papers.json`, `contexts.json`, `train.json` y `val.json` en `data/raw/`.
El conjunto `test.json` solo se lee al solicitar la evaluación final.

## 2. Definir los parámetros en un único YAML

Edite [config/model.yaml](../../config/model.yaml). La configuración se valida
con Pydantic al comenzar, siguiendo el patrón YAML del Taller 5. Las claves
desconocidas y valores inválidos generan un error antes del entrenamiento.

| Clave YAML | Valor inicial | Significado |
|---|---:|---|
| `data_dir` | `data/raw` | Carpeta de los datos originales |
| `output_dir` | `artifacts` | Carpeta para modelos y resultados locales |
| `seed` | `42` | Semilla del muestreo y clasificador |
| `negative_strategy` | `random` | `random` o `hard` |
| `negatives_per_positive` | `2` | Negativos por cada cita conocida |
| `top_n` | `100` | Candidatos que recibe el reordenador |
| `k` | `10` | Profundidad principal de evaluación; no puede superar Top-N |
| `max_features` | `50000` | Límite del vocabulario TF-IDF |
| `min_df` | `2` | Artículos mínimos que deben contener un término |
| `c` | `1.0` | Inverso de la regularización; se registra como `C` en MLflow |

Las rutas relativas se resuelven desde la raíz del repositorio. Todos los
valores del experimento están en este archivo; la CLI solo elige la operación,
un YAML alternativo o el modelo que se evaluará.

### Cómo elegir y modificar cada valor

Estos valores son los iniciales del YAML, no valores que el lector pueda omitir:
el archivo debe contener todas las claves de la tabla.

| Clave | Valores y efecto del cambio |
|---|---|
| `data_dir` | Ruta a una carpeta con los JSON. Cambiarla cambia los datos del experimento; no mezclar particiones de distintas versiones. |
| `output_dir` | Ruta donde crear una subcarpeta por run. Cambia dónde se guardan los resultados, no el aprendizaje. |
| `seed` | Entero no negativo. Mantener `42` para comparar estrategias con el mismo muestreo reproducible; otra semilla produce otros negativos aleatorios. |
| `negative_strategy` | `random` elige negativos al azar; `hard` toma los primeros candidatos incorrectos del ranking TF-IDF. Cambia qué ejemplos aprende a distinguir el clasificador. |
| `negatives_per_positive` | Entero positivo. Con `2`, cada positivo aporta dos negativos: 30.390 consultas con un positivo generan 91.170 pares. Aumentarlo cambia la proporción de clases y el costo de entrenamiento. |
| `top_n` | Entero positivo. Con `100`, el modelo reordena hasta cien artículos por consulta. Aumentarlo puede recuperar más positivos y exige más trabajo; nunca supera el catálogo disponible tras excluir el citante. Para `hard`, debe haber suficientes candidatos para los negativos solicitados. |
| `k` | Entero positivo, menor o igual que `top_n`. Con `10`, las métricas principales son Recall@10 y MRR@10. Cambiarlo modifica la evaluación, no los pesos del clasificador. |
| `max_features` | Entero positivo. Es un máximo de términos, no el tamaño garantizado del vocabulario. Aumentarlo permite conservar más términos, con mayor costo de memoria. Afecta al recuperador y al extractor. |
| `min_df` | Entero positivo. Con `2`, una palabra debe aparecer en al menos dos artículos. Aumentarlo descarta más términos raros; un valor excesivo puede dejar el vocabulario vacío. |
| `c` | Número finito mayor que cero. Un valor pequeño aplica regularización más fuerte; uno grande permite coeficientes menos restringidos. Un valor mayor no garantiza mejores métricas. |

Para el experimento principal, comience con el YAML versionado y cambie solo
`negative_strategy` entre las dos corridas. Después puede comparar, por ejemplo,
`c: 0.1` con `c: 1.0` manteniendo las demás decisiones. Seleccione utilizando
validación; no ajuste parámetros mirando los resultados de `test`.

Cambiar el YAML requiere un nuevo entrenamiento para generar un nuevo artefacto.
El comando `evaluate` siempre respeta la configuración almacenada en el modelo.

Las decisiones estables permanecen en el código: unigramas, stop words en
inglés, normalización L2, StandardScaler, pesos de clase sin balance adicional
y límite de 1.000 iteraciones. No necesitan opciones para la comparación actual.

Los valores TF-IDF se aplican tanto al recuperador como al extractor. Los
candidatos se generan con el recuperador ajustado en esa corrida, evitando
reutilizar una caché de otro vocabulario o configuración.

Para comprender los parámetros consulte [TF-IDF](01_texto_y_tfidf.md),
[Modelo supervisado](02_modelo_supervisado.md) y
[Ranking y evaluación](03_ranking_y_evaluacion.md).

## 3. Entrenar y validar

```bash
uv run python -m src.training.run_linear_reranker train
```

Este comando lee `config/model.yaml`, ajusta TF-IDF sobre el catálogo, construye
pares exclusivamente de `train` y ajusta el escalador y clasificador con esos
pares. Después evalúa en `val` y registra la corrida en MLflow.

Al finalizar imprime la ruta del modelo:

```text
artifacts/<run_id>/
├── model.joblib
├── config.yaml
└── validation.json
```

Cada corrida tiene su propia carpeta. `model.joblib` contiene el recuperador,
el extractor, el clasificador, la configuración y las huellas SHA-256 de los
datos. `config.yaml` es una copia de la configuración utilizada;
`validation.json` conserva métricas, coeficientes, intercepto y tiempos.

Para comparar estrategias:

1. Entrenar con `negative_strategy: random`.
2. Cambiar solo esa clave a `hard` y repetir el comando.
3. Comparar las métricas de validación en MLflow.
4. Conservar la ruta del modelo seleccionado.

Opcionalmente puede indicar otro YAML completo:

```bash
uv run python -m src.training.run_linear_reranker train --config config/model.yaml
```

## 4. Evaluar un modelo ya entrenado

Reemplazar `<run_id>` por el identificador que imprimió el entrenamiento.

Validación repetida:

```bash
uv run python -m src.training.run_linear_reranker evaluate \
  --model artifacts/<run_id>/model.joblib --split val
```

Evaluación final en prueba:

```bash
uv run python -m src.training.run_linear_reranker evaluate \
  --model artifacts/<run_id>/model.joblib --split test
```

Ambos comandos cargan el artefacto completo y utilizan su configuración
guardada. Editar el YAML actual no modifica un modelo ya entrenado. Ningún
componente se vuelve a ajustar durante la evaluación.

Use `val` para seleccionar la configuración y `test` una vez elegida.
Cada evaluación crea un run con `source_run_id`, que identifica el entrenamiento
de origen. Se verifican las huellas del catálogo, contextos y, para validación,
la partición original; la huella del split evaluado también queda registrada.

Cargue únicamente artefactos Joblib de confianza, pues la deserialización puede
ejecutar código Python.

## 5. Ejecutar las pruebas automatizadas

“Test del modelo” puede significar dos cosas: evaluar calidad sobre `test.json`
o verificar el código. Los comandos siguientes verifican el código con datos
sintéticos y un almacén MLflow temporal:

```bash
uv run pytest -q
uv run tox
uv run tox -e smoke-model
```

pytest ejecuta las pruebas en el entorno actual. Tox crea un entorno aislado.
La prueba de integración entrena, guarda, recarga y evalúa las dos estrategias,
comprobando que evaluar nunca invoque `fit`.

No hace falta reducir el corpus mediante parámetros de muestreo para verificar
rápidamente el flujo: `smoke-model` utiliza un corpus pequeño de prueba.

## 6. Revisar experimentos en MLflow

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Abra http://localhost:5000. Para registrar futuras corridas en el servidor del
equipo, configure su dirección antes de entrenar:

```bash
export MLFLOW_TRACKING_URI="http://SERVIDOR:8050"
```

La dirección es una opción del entorno, no un hiperparámetro del modelo.
La variable no transfiere los runs que ya están almacenados localmente.

### Referencia de parámetros y métricas registrados

Los parámetros del YAML aparecen en Parameters (`c` aparece como `C`).
Además se registran:

| Nombre | Interpretación |
|---|---|
| `n_train_queries` | Consultas utilizadas para aprender |
| `n_val_queries` | Consultas de validación en el entrenamiento |
| `n_training_pairs` | Total de pares positivos y negativos |
| `candidate_policy` | `top_n_excluding_citing_paper` |
| `feature_version` | `pair_features_v1` |
| `source_run_id` | Entrenamiento de origen en runs de evaluación |
| `split` / `n_eval_queries` | Partición y tamaño de una evaluación |

Las etiquetas `stage` y `split` distinguen entrenamiento con validación
(`train`, `val`) de evaluaciones posteriores (`evaluate`, `val` o `test`).

| Métrica | Qué mide |
|---|---|
| `recall_at_k` / `mrr` | Métricas principales truncadas al `k` configurado |
| `recall_at_10`, `mrr_at_10`, etc. | Desglose por profundidad |
| `baseline_recall_at_*` / `baseline_mrr_at_*` | TF-IDF sobre los mismos candidatos |
| `train_feature_seconds` | Preparación de recuperador, extractor, pares y características |
| `training_seconds` | Ajuste de escalador y regresión |
| `retrieval_seconds` | Recuperación de candidatos de evaluación |
| `reranking_seconds` | Extracción de características y reordenamiento de evaluación |
| `inference_ms_per_query` | Promedio del reordenamiento por consulta, sin recuperación ni API |

Se evalúan K = 1, 5, 10, 20, 50 y 100 cuando no superan Top-N; siempre se
incluyen el K principal y Top-N. Recall@Top-N debe coincidir antes y después.

### Artefactos y compatibilidad

Los nuevos runs guardan `model/model.joblib`, `model/config.yaml` y
`model/validation.json`; el resumen también aparece en
`evaluation/summary.json`. Los runs antiguos tienen extractor y clasificador
por separado: siguen siendo evidencia histórica, pero no se cargan con el nuevo
comando `evaluate`. Genere un nuevo artefacto mediante `train`.

Los coeficientes corresponden a las cinco características en el orden indicado
en `feature_names`. Su interpretación está en [Modelo supervisado](02_modelo_supervisado.md).

## 7. Organización y mantenimiento

| Archivo | Responsabilidad |
|---|---|
| `config/model.yaml` / `src/config.py` | Configuración y validación |
| `src/models/linear_reranker.py` | Pipeline y puntuación |
| `src/models/citation_model.py` | Agrupar componentes ajustados para inferencia |
| `src/training/experiment.py` | Entrenar, persistir y registrar experimentos |
| `src/evaluation/evaluate_reranker.py` | Evaluación comparable |
| `src/training/run_linear_reranker.py` | Interfaz de comandos |

Si MLflow no muestra un run, revise `MLFLOW_TRACKING_URI`. Si los datos cambiaron,
recupere su versión original con DVC o entrene un modelo nuevo. Si la configuración
falla, revise el nombre de la clave y el mensaje de validación.

Antes de integrar cambios:

```bash
uv run tox
git diff --check
git status --short
```

La [especificación](../specs/especificacion_tecnica.md) define el alcance de la entrega.
