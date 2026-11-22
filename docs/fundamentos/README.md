# Fundamentos del recomendador local de citas

## Propósito

Esta carpeta es una introducción breve al aprendizaje automático y al
procesamiento de lenguaje natural utilizados en el proyecto. No presupone
experiencia previa: comienza con la representación del texto y termina con la
evaluación del ranking producido por el modelo.

La intención no es cubrir todo PLN, sino explicar lo necesario para:

- comprender por qué funciona el prototipo;
- interpretar sus resultados;
- modificar el modelo sin romper el protocolo experimental;
- identificar sus limitaciones y posibles mejoras.

## Orden recomendado

1. [Texto y TF-IDF](01_texto_y_tfidf.md): cómo se convierte lenguaje en
   números y cómo se calcula similitud léxica.
2. [Modelo supervisado](02_modelo_supervisado.md): cómo aprende la regresión
   logística a distinguir pares relevantes.
3. [Ranking y evaluación](03_ranking_y_evaluacion.md): cómo se construye y
   mide el recomendador de dos etapas.
4. [Herramientas técnicas](herramientas_tecnicas.md): cómo preparar el entorno,
   ejecutar pruebas, manejar datos y revisar experimentos.

Después puede consultarse la
[especificación técnica](../specs/especificacion_tecnica.md), que traduce estos
conceptos en requisitos, módulos y criterios de terminado.

## Mapa mental del proyecto

```text
Contexto donde falta una cita
            ↓
Limpieza y representación TF-IDF
            ↓
Recuperación de 100 artículos candidatos
            ↓
Características contexto-artículo
            ↓
Regresión logística
            ↓
Ranking de candidatos
            ↓
Evaluación con Recall@K y MRR@K
```

## Glosario mínimo

| Término | Significado en este proyecto |
|---|---|
| Contexto | Fragmento donde debe recomendarse una cita |
| Consulta | Representación del contexto enviada al recuperador |
| Candidato | Artículo que podría recomendarse |
| Positivo | Artículo que realmente fue citado |
| Negativo | Artículo usado como ejemplo no relevante |
| Característica | Número que describe un par contexto-artículo |
| Modelo | Función que aprende a producir un puntaje |
| Ranking | Lista de candidatos ordenada por puntaje |
| Run | Una ejecución experimental registrada en MLflow |

## Dónde está cada parte en el código

| Concepto | Implementación principal |
|---|---|
| Recuperación TF-IDF | `src/models/tfidf_baseline.py` |
| Pares aleatorios | `src/data/build_pairs.py` |
| Pares difíciles | `src/data/build_hard_pairs.py` |
| Características | `src/features/pair_features.py` |
| Regresión logística | `src/models/linear_reranker.py` |
| Entrenamiento y evaluación | `src/training/run_linear_reranker.py` |
| Métricas | `src/evaluation/ranking_metrics.py` |
| Seguimiento MLflow | `src/tracking/mlflow_setup.py` |
