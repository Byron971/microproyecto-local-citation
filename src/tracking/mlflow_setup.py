"""Configuración centralizada de MLflow para el seguimiento de experimentos.

Todos los entrenamientos del proyecto deben registrarse a través de este módulo
en lugar de llamar a ``mlflow`` directamente. La razón es que la comparación
entre modelos solo sirve si todos los runs viven en el mismo experimento y
nombran sus métricas igual: si cada integrante define sus propias convenciones,
la interfaz de MLflow muestra columnas distintas por run y no se pueden
comparar lado a lado.

Nota sobre el almacenamiento: MLflow 3.x dejó el backend de archivos
(``./mlruns``) en modo mantenimiento y lanza una excepción si se usa. Por eso
el proyecto guarda los runs en una base SQLite local, que no requiere levantar
ningún servidor y sí admite todas las funciones actuales.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow

# Nombre único del experimento del proyecto. Se usa uno solo, y no uno por
# modelo, precisamente para poder comparar la línea base contra los modelos
# supervisados en una misma tabla de la interfaz de MLflow.
EXPERIMENT_NAME = "recomendacion-local-citas"

# Raíz del repositorio, deducida desde la ubicación de este archivo
# (``src/tracking/mlflow_setup.py`` → tres niveles arriba). Sirve para que la
# base de datos y los artefactos queden siempre en el mismo lugar sin importar
# desde qué carpeta se ejecute el script.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Base SQLite donde MLflow registra los runs. Es local a cada integrante y está
# ignorada por Git.
DEFAULT_DB_NAME = "mlflow.db"

# Carpeta donde MLflow deja los artefactos (modelos serializados, gráficas).
# La base SQLite solo guarda métricas y parámetros, los archivos van aparte.
DEFAULT_ARTIFACTS_DIR = "mlartifacts"

# Variable de entorno estándar de MLflow. Si el equipo decide más adelante
# levantar un servidor compartido, basta con exportarla y este módulo la
# respeta sin cambiar código.
TRACKING_URI_ENV_VAR = "MLFLOW_TRACKING_URI"


def get_tracking_uri(db_path: str | Path | None = None) -> str:
    """Devuelve el URI de seguimiento que debe usar MLflow.

    Prioriza la variable de entorno ``MLFLOW_TRACKING_URI`` para permitir un
    servidor compartido; si no está definida, cae en una base SQLite local.

    Parameters
    ----------
    db_path:
        Ruta de la base SQLite. Por defecto ``mlflow.db`` en la raíz del
        repositorio.

    Returns
    -------
    str
        URI de seguimiento listo para ``mlflow.set_tracking_uri``.
    """
    configured_uri = os.environ.get(TRACKING_URI_ENV_VAR)

    if configured_uri:
        return configured_uri

    resolved_path = Path(db_path or PROJECT_ROOT / DEFAULT_DB_NAME).resolve()

    # SQLAlchemy espera barras normales incluso en Windows, y el prefijo
    # ``sqlite:///`` seguido de una ruta absoluta.
    return f"sqlite:///{resolved_path.as_posix()}"


def get_artifacts_uri(artifacts_dir: str | Path | None = None) -> str:
    """Devuelve el URI donde MLflow debe guardar los artefactos.

    Parameters
    ----------
    artifacts_dir:
        Carpeta de artefactos. Por defecto ``mlartifacts`` en la raíz del
        repositorio.

    Returns
    -------
    str
        URI de tipo ``file://`` apuntando a la carpeta de artefactos.
    """
    resolved_dir = Path(artifacts_dir or PROJECT_ROOT / DEFAULT_ARTIFACTS_DIR)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    return resolved_dir.resolve().as_uri()


def configure_mlflow(
    experiment_name: str = EXPERIMENT_NAME,
    db_path: str | Path | None = None,
    artifacts_dir: str | Path | None = None,
) -> str:
    """Deja MLflow listo para registrar runs del proyecto.

    Debe llamarse una vez al inicio de cada script de entrenamiento. Crea el
    experimento si no existe, de modo que un integrante que acaba de clonar el
    repositorio no tenga que prepararlo a mano.

    Parameters
    ----------
    experiment_name:
        Experimento bajo el que se agrupan los runs.
    db_path:
        Ruta de la base SQLite local.
    artifacts_dir:
        Carpeta donde se guardan los artefactos.

    Returns
    -------
    str
        URI de seguimiento efectivamente aplicado.
    """
    tracking_uri = get_tracking_uri(db_path)
    mlflow.set_tracking_uri(tracking_uri)

    # El experimento se crea explícitamente para poder fijar dónde van los
    # artefactos; ``set_experiment`` por sí solo no permite indicarlo y los
    # dejaría en una ruta que depende del directorio de ejecución.
    if mlflow.get_experiment_by_name(experiment_name) is None:
        mlflow.create_experiment(
            experiment_name,
            artifact_location=get_artifacts_uri(artifacts_dir),
        )

    mlflow.set_experiment(experiment_name)

    return tracking_uri


def build_run_name(model_name: str, variant: str | None = None) -> str:
    """Construye el nombre de un run siguiendo la convención del equipo.

    El formato es ``modelo[-variante]-YYYYmmdd-HHMMSS``. El modelo va primero
    para que la lista de runs quede agrupada por familia al ordenarla
    alfabéticamente, y la marca de tiempo (en UTC, como el resto del proyecto)
    distingue reentrenamientos del mismo modelo. Incluye segundos
    porque dos runs lanzados en el mismo minuto colisionarían de otro modo.

    Parameters
    ----------
    model_name:
        Familia del modelo, por ejemplo ``tfidf`` o ``regresion-logistica``.
    variant:
        Identificador opcional de la variante probada, por ejemplo ``bigramas``.

    Returns
    -------
    str
        Nombre del run.
    """
    if not model_name:
        raise ValueError("model_name no puede estar vacío.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    parts = [model_name]

    if variant:
        parts.append(variant)

    parts.append(timestamp)

    return "-".join(parts)


@contextmanager
def start_run(
    model_name: str,
    variant: str | None = None,
    params: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Abre un run de MLflow con la convención de nombres del equipo.

    Se usa como gestor de contexto para garantizar que el run se cierre aunque
    el entrenamiento falle; un run abierto contamina los siguientes.

    Parameters
    ----------
    model_name:
        Familia del modelo que se está entrenando.
    variant:
        Identificador opcional de la variante.
    params:
        Hiperparámetros a registrar al inicio del run.

    Yields
    ------
    mlflow.ActiveRun
        Run activo, por si se necesita su identificador.
    """
    run_name = build_run_name(model_name, variant)

    with mlflow.start_run(run_name=run_name) as active_run:
        # El nombre del modelo se registra además como etiqueta porque filtrar
        # por etiqueta en la interfaz es más cómodo que buscar por prefijo del
        # nombre del run.
        mlflow.set_tag("modelo", model_name)

        if variant:
            mlflow.set_tag("variante", variant)

        if params:
            mlflow.log_params(params)

        yield active_run


def log_ranking_metrics(
    recall_at_k: float,
    mrr: float,
    k: int,
) -> None:
    """Registra las métricas de ranking con nombres consistentes.

    Envuelve el registro para que todos los runs usen las mismas claves y
    puedan compararse en una sola tabla. El valor de ``k`` queda como parámetro
    del run, no como parte del nombre de la métrica, para poder graficar la
    evolución de ``recall_at_k`` entre runs con distintos ``k``.

    Parameters
    ----------
    recall_at_k:
        Recall@K calculado con ``src.evaluation.ranking_metrics``.
    mrr:
        Mean Reciprocal Rank calculado con el mismo módulo.
    k:
        Valor de K empleado al calcular el Recall.
    """
    if k <= 0:
        raise ValueError("k debe ser un entero positivo.")

    mlflow.log_param("k", k)
    mlflow.log_metric("recall_at_k", recall_at_k)
    mlflow.log_metric("mrr", mrr)
