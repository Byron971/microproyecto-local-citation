"""Benchmark factorial A4: SciBERT/SPECTER × entradas A/B sobre idéntico Gold.

Solo compara predicciones existentes. No entrena, no llama proveedores, nunca
certifica el Gold ni produce métricas de tesis si se carece de evidencia.
Los resultados de desarrollo llevan una advertencia PROVISIONAL explícita.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random
import re
import sys
from typing import Any

from .gold_policy import inspect_gold
from .metrics import CATEGORIES
from .paired_benchmark import index_gold, index_predictions, model_metrics, read_jsonl
from .schema import EvaluationCase

ENCODERS = ("SciBERT", "SPECTER")
INPUTS = ("A", "B")
SOURCES = ("Haiku", "Jurado")
_SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _required(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Falta {field}")
    return value.strip()


def _sha(value: object, field: str) -> str:
    token = _required(value, field)
    if not _SHA256_RE.fullmatch(token):
        raise ValueError(f"{field} debe ser un SHA-256 hexadecimal")
    return token.lower()


def load_config(path: Path) -> list[dict[str, str]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema_version") != "a4_factorial_v1":
        raise ValueError("Configuración A4 debe declarar schema_version=a4_factorial_v1")
    if obj.get("data_use") != "provisional_only":
        raise ValueError("Sin certificado Gold, data_use debe ser provisional_only")
    data = obj.get("variants")
    if not isinstance(data, list) or not data:
        raise ValueError("No hay variantes de modelo")
    arms: list[dict[str, str]] = []
    names: set[str] = set()
    cells: set[tuple[str, str, str]] = set()
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("Cada variante debe ser un objeto")
        name = _required(row.get("name"), "name")
        if name in names:
            raise ValueError(f"Nombre de variante duplicado: {name}")
        names.add(name)
        encoder = _required(row.get("encoder"), f"{name}.encoder")
        input_name = _required(row.get("input"), f"{name}.input")
        source = _required(row.get("training_labels"), f"{name}.training_labels")
        if encoder not in ENCODERS or input_name not in INPUTS or source not in SOURCES:
            raise ValueError(f"{name}: matriz A4 inválida")
        cell = source, encoder, input_name
        if cell in cells:
            raise ValueError(f"Celda A4 duplicada: {cell}")
        cells.add(cell)
        candidate = {
            "name": name,
            "encoder": encoder,
            "input": input_name,
            "training_labels": source,
            "predictions": _required(row.get("predictions"), f"{name}.predictions"),
            "checkpoint_sha256": _sha(row.get("checkpoint_sha256"), f"{name}.checkpoint_sha256"),
            "train_ids_sha256": _sha(row.get("train_ids_sha256"), f"{name}.train_ids_sha256"),
            "train_labels_sha256": _sha(row.get("train_labels_sha256"), f"{name}.train_labels_sha256"),
            "input_spec_sha256": _sha(row.get("input_spec_sha256"), f"{name}.input_spec_sha256"),
        }
        arms.append(candidate)

    for source in set(x["training_labels"] for x in arms):
        group = [x for x in arms if x["training_labels"] == source]
        observed = {(x["encoder"], x["input"]) for x in group}
        needed = {(e, a) for e in ENCODERS for a in INPUTS}
        if observed != needed:
            raise ValueError(
                f"{source}: matriz A4 incompleta; faltan {sorted(needed - observed)}"
            )
        # Comparaciones controladas requieren misma lista de entrenamiento.
        for field in ("train_ids_sha256", "train_labels_sha256"):
            if len({x[field] for x in group}) != 1:
                raise ValueError(f"{source}: {field} difiere entre las 4 corridas")
        for input_name in INPUTS:
            specs = {
                x["input_spec_sha256"] for x in group if x["input"] == input_name
            }
            if len(specs) != 1:
                raise ValueError(
                    f"{source}: entrada {input_name} no usa la misma definición "
                    "de características en ambos encoders"
                )
    return arms


def _safe_prediction_path(config_dir: Path, relative: str) -> Path:
    """Rechaza rutas absolutas y escapes fuera del directorio del manifiesto."""
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts or not relative.strip():
        raise ValueError("Predicciones: ruta relativa sin directorios ascendentes")
    target = (config_dir / candidate).resolve()
    if not target.is_relative_to(config_dir.resolve()):
        raise ValueError("Predicciones fuera del directorio autorizado")
    if not target.is_file():
        raise ValueError(f"No existe archivo de predicciones: {relative}")
    return target


def _paired(
    ids: list[str],
    gold: dict[str, dict[str, Any]],
    pred_a: dict[str, int],
    pred_b: dict[str, int],
    *,
    key_a: str,
    key_b: str,
    factor: str,
    bootstrap_draws: int = 0,
    seed: int = 42,
) -> dict[str, Any]:
    y = [gold[c]["gold"] for c in ids]
    left = [pred_a[c] for c in ids]
    right = [pred_b[c] for c in ids]
    left_metrics = model_metrics(y, left)
    right_metrics = model_metrics(y, right)
    result: dict[str, Any] = {
        "variant_a": key_a,
        "variant_b": key_b,
        "factor": factor,
        "same_gold_ids": len(ids),
        "delta_f1_macro_b_minus_a": right_metrics["f1_macro"] - left_metrics["f1_macro"],
        "delta_accuracy_b_minus_a": right_metrics["accuracy"] - left_metrics["accuracy"],
        "paired_cases": {
            "a_only_correct": sum(a == t and b != t for t, a, b in zip(y, left, right)),
            "b_only_correct": sum(b == t and a != t for t, a, b in zip(y, left, right)),
            "both_correct": sum(a == t and b == t for t, a, b in zip(y, left, right)),
            "both_wrong": sum(a != t and b != t for t, a, b in zip(y, left, right)),
            "same_prediction": sum(a == b for a, b in zip(left, right)),
        },
        "wrong_by_gold_class": {
            cat: {
                "a_wrong": sum(t == idx and a != t for t, a in zip(y, left)),
                "b_wrong": sum(t == idx and b != t for t, b in zip(y, right)),
            }
            for idx, cat in enumerate(CATEGORIES)
        },
        "bootstrap_cluster_95pct": None,
    }
    if bootstrap_draws:
        group: dict[str, list[int]] = {}
        for ix, cid in enumerate(ids):
            group.setdefault(gold[cid]["citing_id"], []).append(ix)
        papers = sorted(group)
        if len(papers) < 2:
            raise ValueError("Bootstrap por documento exige >= 2 documentos citantes")
        rng = random.Random(seed)
        deltas: list[float] = []
        for _ in range(bootstrap_draws):
            indices = [
                ix for doc in (rng.choice(papers) for _ in papers)
                for ix in group[doc]
            ]
            yy = [y[ix] for ix in indices]
            aa = [left[ix] for ix in indices]
            bb = [right[ix] for ix in indices]
            deltas.append(
                model_metrics(yy, bb)["f1_macro"] -
                model_metrics(yy, aa)["f1_macro"]
            )
        deltas.sort()
        low = deltas[int(0.025 * (len(deltas) - 1))]
        high = deltas[int(0.975 * (len(deltas) - 1))]
        result["bootstrap_cluster_95pct"] = {
            "lower": low,
            "upper": high,
            "draws": bootstrap_draws,
            "seed": seed,
            "unit": "citing_id",
            "method": "percentile",
            "n_citing_documents": len(papers),
            "note": "Intervalo exploratorio, NO evidencia de significación final",
        }
    return result


def run_factorial(
    gold_rows: list[dict[str, Any]],
    arms: list[dict[str, str]],
    predictions_by_name: dict[str, list[dict[str, Any]]],
    *,
    bootstrap_draws: int = 0,
    seed: int = 42,
) -> dict[str, Any]:
    if not gold_rows:
        raise ValueError("Gold vacío")
    if bootstrap_draws not in (0,) and bootstrap_draws < 100:
        raise ValueError("bootstrap_draws debe ser cero o >=100")
    if bootstrap_draws > 10000:
        raise ValueError("bootstrap_draws demasiado alto")
    if len(set(x["name"] for x in arms)) != len(arms):
        raise ValueError("Nombres de variantes duplicados")
    gold = index_gold(gold_rows)
    ids = sorted(gold)
    expected = set(ids)
    if {x["name"] for x in arms} != set(predictions_by_name):
        raise ValueError("Faltan o sobran variantes con predicciones")
    indexed = {
        x["name"]: index_predictions(predictions_by_name[x["name"]], expected, x["name"])
        for x in arms
    }
    report: dict[str, Any] = {
        "status": "PROVISIONAL_NO_CERTIFICADO",
        "test_gold_certified": False,
        "ready_for_final_article": False,
        "n_same_gold": len(ids),
        "n_gold_classes_present": len(set(item["gold"] for item in gold.values())),
        "nine_class_taxonomy": list(CATEGORIES),
        "variants": {},
        "contrasts": [],
        "warnings": [
            "No se ha certificado la procedencia humana ni adjudicación del Test Gold.",
            "La matriz A4 no demuestra que los encoders se hayan entrenado correctamente; "
            "requiere inspección de checkpoints y manifiestos.",
            "Los errores/abstenciones de proveedor se rechazan, no se eliminan del denominador.",
        ],
    }
    by_source: dict[str, dict[tuple[str, str], str]] = {}
    for arm in arms:
        name = arm["name"]
        report["variants"][name] = {
            "encoder": arm["encoder"], "input": arm["input"],
            "training_labels": arm["training_labels"],
            "checkpoint_sha256": arm["checkpoint_sha256"],
            "train_ids_sha256": arm["train_ids_sha256"],
            "train_labels_sha256": arm["train_labels_sha256"],
            "input_spec_sha256": arm["input_spec_sha256"],
            "metrics": model_metrics(
                [gold[c]["gold"] for c in ids],
                [indexed[name][c] for c in ids],
            ),
        }
        by_source.setdefault(arm["training_labels"], {})[
            (arm["encoder"], arm["input"])
        ] = name

    for source, variants in sorted(by_source.items()):
        for encoder in ENCODERS:
            a, b = variants[(encoder, "A")], variants[(encoder, "B")]
            diff = _paired(
                ids, gold, indexed[a], indexed[b], key_a=a, key_b=b,
                factor="input", bootstrap_draws=bootstrap_draws, seed=seed,
            )
            diff["training_labels"] = source
            report["contrasts"].append(diff)
        for input_name in INPUTS:
            a = variants[("SciBERT", input_name)]
            b = variants[("SPECTER", input_name)]
            diff = _paired(
                ids, gold, indexed[a], indexed[b], key_a=a, key_b=b,
                factor="encoder", bootstrap_draws=bootstrap_draws, seed=seed,
            )
            diff["training_labels"] = source
            report["contrasts"].append(diff)

    if set(by_source) == set(SOURCES):
        # Comparación por fuente de etiquetas solo donde el conjunto de IDs
        # usado para entrenar es el mismo; el contenido de etiquetas puede variar.
        for encoder in ENCODERS:
            for input_name in INPUTS:
                haiku_name = by_source["Haiku"][(encoder, input_name)]
                jury_name = by_source["Jurado"][(encoder, input_name)]
                a = next(x for x in arms if x["name"] == haiku_name)
                b = next(x for x in arms if x["name"] == jury_name)
                if a["train_ids_sha256"] != b["train_ids_sha256"]:
                    report["warnings"].append(
                        f"{encoder} {input_name}: Haiku/Jurado no controlados por "
                        "diferente train_ids_sha256; no generar delta causal."
                    )
                    continue
                diff = _paired(
                    ids, gold, indexed[haiku_name], indexed[jury_name],
                    key_a=haiku_name, key_b=jury_name, factor="training_labels",
                    bootstrap_draws=bootstrap_draws, seed=seed,
                )
                diff["input"] = input_name
                report["contrasts"].append(diff)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matriz A4 SciBERT/SPECTER: solo provisional")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provisional", action="store_true")
    parser.add_argument("--bootstrap-draws", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        if not args.provisional:
            raise ValueError("Gold no certificado: solo se admite --provisional")
        arms = load_config(args.config)
        data = read_jsonl(args.gold)
        cases = [
            EvaluationCase(
                id=_required(r.get("id"), "gold.id"),
                input=_required(r.get("input"), "gold.input"),
                gold=r.get("gold"),
                metadata={key: r[key] for key in ("citing_id", "cited_id") if key in r},
            )
            for r in data
        ]
        audit = inspect_gold(args.gold, cases, raw_dir=args.raw_dir)
        if audit.reasons:
            raise ValueError("Política Gold bloqueada: " + "; ".join(audit.reasons))
        prediction_paths = {
            arm["name"]: _safe_prediction_path(args.config.parent, arm["predictions"])
            for arm in arms
        }
        predictions = {key: read_jsonl(path) for key, path in prediction_paths.items()}
        result = run_factorial(
            data, arms, predictions, bootstrap_draws=args.bootstrap_draws,
            seed=args.seed,
        )
        result["provenance"] = {
            "gold_sha256": sha256(args.gold),
            "config_sha256": sha256(args.config),
            "predictions_sha256": {
                key: sha256(path) for key, path in sorted(prediction_paths.items())
            },
            "raw_dir_verified": True,
            "human_gold_certified": False,
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "a4_factorial_provisional.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with (args.output_dir / "a4_model_scores.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow((
                "variant", "encoder", "input", "training_labels", "n",
                "f1_macro_9", "f1_micro", "accuracy",
            ))
            for name, v in sorted(result["variants"].items()):
                met = v["metrics"]
                writer.writerow((
                    name, v["encoder"], v["input"], v["training_labels"],
                    met["n"], met["f1_macro"], met["f1_micro"], met["accuracy"],
                ))
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        print(f"Benchmark A4 bloqueado: {exc}", file=sys.stderr)
        return 2
    print(f"Matriz A4 PROVISIONAL: {result['n_same_gold']} ejemplos; "
          f"{len(result['variants'])} variantes, {len(result['contrasts'])} contrastes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
