"""Registro de los experimentos del issue #104 en MLflow (backend SQLite de la raiz).

Reutiliza `src.tracking.mlflow_setup` (raiz del repo, en `pythonpath`). Solo lo importan el
notebook y los tests con `importorskip("mlflow")`: el grupo `experimentos` es opt-in."""
import hashlib
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path

import matplotlib
import mlflow
import pandas as pd
from src.tracking import mlflow_setup

from . import dominio

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

EXPERIMENTO = "clasificacion-funcion-104"
ESTADO = "provisional_sin_gold_humano"
REGLA_ANTIFUGA = "excluye_2014_2015+v2+tg2700+citantes"
REPO = Path(__file__).resolve().parents[4]
_activo = {"experimento": EXPERIMENTO}  # el ultimo configurado: donde busca la reanudacion


def configurar(experimento: str = EXPERIMENTO, db_path=None, artifacts_dir=None) -> str:
    _activo["experimento"] = experimento
    return mlflow_setup.configure_mlflow(experiment_name=experimento, db_path=db_path,
                                         artifacts_dir=artifacts_dir)


def sha_config(config: dict) -> str:
    """Huella de la configuracion de un run: base de la reanudacion."""
    texto = json.dumps(config, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def estado_git(repo: Path = REPO) -> dict:
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        return {"git_head": git("rev-parse", "HEAD"), "dirty": str(bool(git("status", "--porcelain")))}
    except (OSError, subprocess.CalledProcessError):
        return {"git_head": "desconocido", "dirty": "desconocido"}


def corrida_terminada(config_sha: str, experimento: str | None = None) -> str | None:
    """run_id de un run FINISHED con el mismo `config_sha` (para saltarlo), o None."""
    exp = mlflow.get_experiment_by_name(experimento or _activo["experimento"])
    if exp is None:
        return None
    runs = mlflow.search_runs([exp.experiment_id], max_results=1, output_format="list",
                              filter_string=f"tags.config_sha = '{config_sha}' and status = 'FINISHED'")
    return runs[0].info.run_id if runs else None


@contextmanager
def abrir_corrida(nombre: str, config: dict, tags: dict | None = None, hardware: dict | None = None):
    """Abre un run con params, tags de trazabilidad y hardware. Rinde `None` si ya existe uno
    FINISHED con la misma configuracion. Una excepcion deja el run FAILED y se propaga."""
    csha = sha_config(config)
    previo = corrida_terminada(csha)
    if previo:
        yield None
        return
    with mlflow.start_run(run_name=mlflow_setup.build_run_name(nombre)) as run:
        mlflow.set_tags({"issue": "104", "estado": ESTADO, "regla_antifuga": REGLA_ANTIFUGA,
                         "config_sha": csha, **estado_git(), **(tags or {}),
                         **{f"hw_{k}": str(v) for k, v in (hardware or {}).items()}})
        mlflow.log_params({k: str(v)[:500] for k, v in config.items()})
        yield run


def log_epoca(registro: dict) -> None:
    """Callback de `entrenar(al_terminar_epoca=...)`: metricas por epoca."""
    paso = registro["epoca"]
    mlflow.log_metrics({"loss_train": registro["loss_train"], "f1_macro_val": registro["f1_macro_val"],
                        "accuracy_val": registro["accuracy_val"], "segundos_epoca": registro["segundos"]},
                       step=paso)


def log_metricas(prefijo: str, m: dict) -> None:
    """Macro/micro, accuracy y F1 por clase de un conjunto (`val`, `dev_haiku`, `ref_gpt`)."""
    planas = {f"{prefijo}_{k}": m[k] for k in ("accuracy", "f1_macro", "f1_micro", "precision_macro",
                                               "recall_macro", "f1_weighted")}
    for c in m["per_class"]:
        planas[f"{prefijo}_f1_{c['label'].replace(' / ', '_').replace(' ', '_')}"] = c["f1"]
    mlflow.log_metrics(planas)
    mlflow.log_metric(f"{prefijo}_n", m["n"])


def log_dataset(nombre: str, ids: list[str], etiquetas: list[str], contexto: str) -> None:
    """`mlflow.log_input` con digest = sha de los ids."""
    df = pd.DataFrame({"context_id": ids, "etiqueta": etiquetas})
    ds = mlflow.data.from_pandas(df, name=nombre, digest=dominio.sha_ids(ids)[:16])
    mlflow.log_input(ds, context=contexto)


def log_matriz_confusion(m: dict, nombre: str) -> None:
    """Matriz de confusion como json y png (artefactos del run)."""
    mlflow.log_dict({"clases": list(dominio.CATEGORIAS), "matriz": m["confusion_matrix"]},
                    f"confusion_{nombre}.json")
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(m["confusion_matrix"], cmap="Blues")
    ax.set_xticks(range(dominio.N_CLASES), labels=[c[:10] for c in dominio.CATEGORIAS], rotation=60,
                  ha="right")
    ax.set_yticks(range(dominio.N_CLASES), labels=[c[:10] for c in dominio.CATEGORIAS])
    for i, fila in enumerate(m["confusion_matrix"]):
        for j, v in enumerate(fila):
            ax.text(j, i, v, ha="center", va="center", fontsize=7)
    ax.set_xlabel("predicho")
    ax.set_ylabel("verdad")
    fig.tight_layout()
    mlflow.log_figure(fig, f"confusion_{nombre}.png")
    plt.close(fig)


def registrar_corridas_a4(raiz: Path, experimento: str = EXPERIMENTO, **kw_configurar) -> list[str]:
    """Backfill de #103: un run por corrida de `clasificacion_a4/corridas`, sin reentrenar.

    Idempotente: se salta las corridas ya registradas (mismo `config_sha`)."""
    configurar(experimento, **kw_configurar)
    ids = []
    for carpeta in sorted(Path(raiz).iterdir()):
        ruta_m, ruta_v = carpeta / "manifiesto_entrenamiento.json", carpeta / "metricas_val.json"
        if not (ruta_m.is_file() and ruta_v.is_file()):
            continue
        man = json.loads(ruta_m.read_text(encoding="utf-8"))
        val = json.loads(ruta_v.read_text(encoding="utf-8"))
        config = {"origen": "backfill_issue_103", "experiment_id": man["experiment_id"],
                  "checkpoint_sha256": man["checkpoint_sha256"]}
        with abrir_corrida(f"a4-{man['experiment_id']}", config, {
                "fuente": "backfill_103", "checkpoint": str(carpeta / "model.safetensors"),
                "checkpoint_sha256": man["checkpoint_sha256"], "git_head_original": man["git"].get("head", ""),
                "etiquetas": man.get("training_labels", "")}, man.get("hardware")) as run:
            if run is None:
                continue
            mlflow.log_params({"encoder": man["encoder"], "entrada": man["entrada"], "semilla": man["semilla"],
                               "model_version": man["model_version"],
                               **{f"hp_{k}": v for k, v in man["hiperparametros"].items()}})
            for h in man["historial"]:
                log_epoca(h)
            log_metricas("val", val)
            mlflow.log_metric("segundos_entrenamiento", man["segundos_entrenamiento"])
            mlflow.log_artifact(str(ruta_m))
            log_matriz_confusion(val, "val")
            ids.append(run.info.run_id)
    return ids


def exportar_manifiesto(destino: Path, experimento: str = EXPERIMENTO) -> pd.DataFrame:
    """`manifiesto_experimentos.csv/json` desde MLflow: run_id, config, metricas, rutas y sha."""
    exp = mlflow.get_experiment_by_name(experimento)
    df = mlflow.search_runs([exp.experiment_id], output_format="pandas") if exp else pd.DataFrame()
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino / "manifiesto_experimentos.csv", index=False)
    (destino / "manifiesto_experimentos.json").write_text(
        df.to_json(orient="records", force_ascii=False, indent=2, date_format="iso"), encoding="utf-8")
    return df
