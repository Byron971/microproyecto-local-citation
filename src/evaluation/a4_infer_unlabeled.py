"""A4 2x2: prepara o ejecuta predicciones ciegas SIN etiquetas Gold.

El modo por defecto solo inspecciona entradas y su SHA. --apply exige cuatro
checkpoints históricos y dos snapshots fijados y verifica ACL-200 oficial.
No entrena, no hace tuning, no llama APIs comerciales y no calcula F1.
Las predicciones y sus manifiestos son archivos LOCALES privados.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

from proyecto_de_grado.src.evaluation.top3_gold_gate import check_acl_official
from src.app.checkpoint_gate import REPO
from src.app.science_preflight import preflight

ROOT = REPO
DEFAULT_SCIBERT = ROOT / (
    "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json"
)
DEFAULT_SPECTER = ROOT / (
    "proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_modelo_specter.json"
)
EVIDENCE = ROOT / "proyecto_de_grado/docs/evidencias_clasificacion_a4"
ARMS = (
    ("scibert_A_42", "scibert", "A"),
    ("scibert_B_42", "scibert", "B"),
    ("specter_A_42", "specter", "A"),
    ("specter_B_42", "specter", "B"),
)
ALLOWED_CASE = frozenset({
    "context_id", "citing_id", "cited_id", "split", "context_sha256",
    "citation_context", "cited_title", "cited_abstract", "chunks",
    "sha256_ocl_citado",
})
ALLOWED_CHUNK = frozenset({
    "chunk_id", "texto", "seccion", "paragraph_indices", "palabras",
})


class InputError(ValueError):
    """No se permite usar Gold, identidades falsas o información incompleta."""


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def nonblank(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field}: se requiere string no vacío")
    return value.strip()


def read_unlabeled_inputs(path: Path) -> tuple[list[dict], dict[str, dict]]:
    rows = []
    ids: set[str] = set()
    indexed: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig") as file:
        for line_no, raw in enumerate(file, 1):
            if not raw.strip():
                raise InputError(f"Línea {line_no}: no se permiten líneas vacías")
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise InputError(f"Línea {line_no}: JSON inválido") from exc
            if not isinstance(item, dict) or set(item) - ALLOWED_CASE:
                raise InputError(f"Línea {line_no}: campos no permitidos (incluye etiquetas)")
            cid = nonblank(item.get("context_id"), "context_id")
            if cid in ids:
                raise InputError("context_id repetido; no duplicar ejemplos de evaluación")
            ids.add(cid)
            citing = nonblank(item.get("citing_id"), "citing_id")
            cited = nonblank(item.get("cited_id"), "cited_id")
            context = nonblank(item.get("citation_context"), "citation_context")
            title = nonblank(item.get("cited_title"), "cited_title")
            abstract = nonblank(item.get("cited_abstract"), "cited_abstract")
            if item.get("split") != "test" or context.count("TARGETCIT") != 1:
                raise InputError(f"{cid}: solo test held-out y un TARGETCIT")
            if len(context) > 4000 or len(title) > 600 or len(abstract) > 12000:
                raise InputError(f"{cid}: tamaño de texto superior al contrato de API")
            digest = hashlib.sha256(context.encode("utf-8")).hexdigest()
            if item.get("context_sha256") != digest:
                raise InputError(f"{cid}: hash del contexto no corresponde a los bytes")
            chunks = item.get("chunks")
            if not isinstance(chunks, list) or not 3 <= len(chunks) <= 500:
                raise InputError(f"{cid}: el artículo debe contener 3..500 chunks")
            local: set[str] = set()
            sanitized = []
            for chunk in chunks:
                if not isinstance(chunk, dict) or set(chunk) - ALLOWED_CHUNK:
                    raise InputError(f"{cid}: chunk con campos prohibidos o inválidos")
                chunk_id = nonblank(chunk.get("chunk_id"), "chunk_id")
                texto = nonblank(chunk.get("texto"), "texto")
                section = chunk.get("seccion")
                if (chunk_id in local or len(texto) > 5000
                        or len(texto.split()) > 300
                        or section is not None and not isinstance(section, str)):
                    raise InputError(f"{cid}: chunks repetidos, largos o sin sección válida")
                local.add(chunk_id)
                sanitized.append({
                    "chunk_id": chunk_id, "texto": texto, "seccion": section,
                })
            indexed[cid] = {
                "citing_id": citing, "cited_id": cited,
                "context_sha256": digest, "chunks": local,
            }
            rows.append({
                "context_id": cid, "citation_context": context,
                "cited_title": title, "cited_abstract": abstract,
                "citing_id": citing, "cited_id": cited,
                "chunks": sanitized,
            })
    if not rows:
        raise InputError("Corpus held-out vacío")
    return rows, indexed


def metadata_plan(inputs: Path, *, raw_dir: Path | None = None) -> dict:
    rows, index = read_unlabeled_inputs(inputs)
    official = check_acl_official(index, raw_dir) if raw_dir is not None else None
    return {
        "status": ("INPUTS_ACL_OFICIAL_VERIFICADOS_SIN_INFERENCIA"
                   if official is not None else "SOLO_ESTRUCTURA_ACL_NO_VERIFICADO"),
        "input_sha256": hash_file(inputs),
        "n_inputs_unlabeled": len(rows),
        "n_four_arms_expected": 4,
        "acl_official_sha256": official,
        "gold_labels_read": False,
        "predictions_executed": False,
        "test_gold_certified": False,
    }


def _verify_prediction(arm: tuple[str, str, str], prediction: dict) -> None:
    name, encoder, input_name = arm
    scores = prediction.get("puntuaciones_softmax")
    if (prediction.get("modelo") != name or prediction.get("encoder") != encoder
            or prediction.get("entrada") != input_name
            or prediction.get("training_labels") != "Haiku"
            or prediction.get("validacion") != "provisional_no_gold_humano"
            or not isinstance(scores, list) or len(scores) != 9):
        raise RuntimeError("El clasificador no respetó la identidad/contrato A4.")
    vals = [s.get("score") for s in scores if isinstance(s, dict)]
    if (len(vals) != 9 or any(not isinstance(x, (int, float))
                             or not math.isfinite(x) or x < 0 or x > 1 for x in vals)
            or abs(sum(vals) - 1) > 0.001):
        raise RuntimeError("Probabilidades A4 inválidas/no calibradas o corruptas.")
    if prediction.get("clase") not in [s["categoria"] for s in scores]:
        raise RuntimeError("Clase seleccionada no corresponde a la taxonomía de nueve.")


def _arm_evidence(name: str, encoder: str, input_name: str) -> dict:
    archived = EVIDENCE / name / "manifiesto.json"
    if not archived.is_file() or archived.is_symlink():
        raise RuntimeError(f"No hay evidencia histórica para {name}")
    manifest = json.loads(archived.read_text(encoding="utf-8"))
    if (manifest.get("experiment_id") != name
            or manifest.get("encoder") != encoder
            or manifest.get("entrada") != input_name
            or manifest.get("training_labels") != "Haiku"):
        raise RuntimeError(f"{name}: manifiesto incompatible")
    sources = manifest.get("entradas")
    if not isinstance(sources, dict):
        raise RuntimeError(f"{name}: faltan fingerprints de entrenamiento")
    required = ("train_ids_sha256", "train_labels_sha256")
    for key in required:
        if not isinstance(sources.get(key), str) or len(sources[key]) != 64:
            raise RuntimeError(f"{name}: falta {key}")
    return manifest


def build_factorial_config(evidences: dict[str, dict]) -> dict:
    variants = []
    for name, encoder, input_name in ARMS:
        m = evidences[name]
        variants.append({
            "name": name,
            "encoder": "SciBERT" if encoder == "scibert" else "SPECTER",
            "input": input_name, "training_labels": "Haiku",
            "predictions": name + ".jsonl",
            "checkpoint_sha256": m["checkpoint_sha256"],
            "train_ids_sha256": m["entradas"]["train_ids_sha256"],
            "train_labels_sha256": m["entradas"]["train_labels_sha256"],
            "input_spec_sha256": m["input_spec_sha256"],
        })
    # Validar el contrato real del benchmark ANTES de escribir artefactos finales.
    from src.evaluation.commercial.a4_factorial_benchmark import load_config
    return {
        "schema_version": "a4_factorial_v1", "data_use": "provisional_only",
        "variants": variants,
    }


def run_four_arm(inputs: Path, *, raw_dir: Path, checkpoint_root: Path,
                 output_dir: Path, scibert_manifest: Path = DEFAULT_SCIBERT,
                 specter_manifest: Path = DEFAULT_SPECTER,
                 device: str = "cpu") -> dict:
    if device not in {"cpu", "cuda", "auto"}:
        raise InputError("Dispositivo debe ser cpu/cuda/auto")
    if output_dir.exists() or output_dir.is_symlink():
        raise InputError("Directorio de salida ya existe; no sobrescribir evidencia.")
    if output_dir.parent.is_symlink():
        raise InputError("Carpeta padre de salida no debe ser enlace simbólico.")
    rows, identities = read_unlabeled_inputs(inputs)
    raw_hashes = check_acl_official(identities, raw_dir)
    audit = preflight(checkpoint_root, include_specter=True)
    if not audit.get("ready_four_a4"):
        raise RuntimeError("Faltan pesos originales A4 o snapshots pinned de SciBERT/SPECTER.")
    from src.app.classifier_runtime import A4Classifier
    from src.app.scibert_runtime import SciBERTRuntime

    dense = SciBERTRuntime.load(scibert_manifest, device=device)
    top3 = {}
    for row in rows:
        ranking = dense.top3(row["citation_context"], row["chunks"], document_key=None)
        if len(ranking) != 3 or len({x["chunk_id"] for x in ranking}) != 3:
            raise RuntimeError("SciBERT no devolvió tres chunks únicos reales.")
        top3[row["context_id"]] = ranking
    del dense
    gc.collect()

    # Los cuatro clasificadores se cargan DE UNO EN UNO para reducir RAM CPU.
    predicted: dict[str, list[dict]] = {}
    evidences: dict[str, dict] = {}
    for arm in ARMS:
        name, encoder, input_name = arm
        historical = _arm_evidence(*arm)
        evidence_path = EVIDENCE / name / "manifiesto.json"
        encoder_manifest = scibert_manifest if encoder == "scibert" else specter_manifest
        model = A4Classifier.load(
            checkpoint_root / name, evidence_path, encoder_manifest,
            device=device, entrada=input_name,
        )
        output = []
        for row in rows:
            prediction = (
                model.classify(row["citation_context"],
                               row["cited_title"], row["cited_abstract"])
                if input_name == "A" else
                model.classify(row["citation_context"], top3=top3[row["context_id"]])
            )
            _verify_prediction(arm, prediction)
            output.append({
                "case_id": row["context_id"], "status": "ok",
                "pred_label": prediction["clase"],
                "pred_index": prediction["indice_clase"],
                "model_id": name,
                "latency_model_ms": prediction["latencia_modelo_ms"],
            })
        predicted[name] = output
        evidences[name] = historical
        del model
        gc.collect()

    config = build_factorial_config(evidences)
    # Validación de consistencia cruzada: mismos train IDs/fuentes, inputs A/B.
    names = [row["case_id"] for row in next(iter(predicted.values()))]
    if any([row["case_id"] for row in rows_] != names for rows_ in predicted.values()):
        raise RuntimeError("Predicciones sin alineación de IDs entre las cuatro celdas.")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".a4-unlabeled-", dir=output_dir.parent
    ) as scratch:
        temp = Path(scratch)
        for name, items in predicted.items():
            with (temp / (name + ".jsonl")).open("x", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
        with (temp / "a4_factorial_config.json").open("x", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            f.write("\n")
        # Reutilizar el gate original para detectar configuraciones comparativas
        # incompletas, injustas o sin fingerprints.
        from src.evaluation.commercial.a4_factorial_benchmark import load_config
        load_config(temp / "a4_factorial_config.json")
        result = {
            "status": "PREDICCIONES_A4_CIEGAS_NO_EVALUADAS",
            "input_sha256": hash_file(inputs),
            "raw_acl_sha256": raw_hashes,
            "models": {name: {
                "checkpoint_sha256": evidences[name]["checkpoint_sha256"],
                "predictions_sha256": hash_file(temp / (name + ".jsonl")),
            } for name in predicted},
            "config_sha256": hash_file(temp / "a4_factorial_config.json"),
            "n_cases": len(rows), "n_models": 4,
            "contains_gold_labels": False,
            "test_gold_certified": False,
            "results_computed": False,
            "warning": "Predicciones provisionales Haiku, NO F1 ni Gold.",
        }
        with (temp / "run_manifest.json").open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.rename(temp, output_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inputs", required=True, type=Path,
                   help="JSONL privado SIN etiquetas, held-out ACL-200")
    p.add_argument("--raw-dir", type=Path, help="ACL oficial en DVC (obligatorio con --apply)")
    p.add_argument("--checkpoint-root", type=Path,
                   default=ROOT / "proyecto_de_grado/artifacts/clasificacion_a4/corridas")
    p.add_argument("--scibert-manifest", type=Path, default=DEFAULT_SCIBERT)
    p.add_argument("--specter-manifest", type=Path, default=DEFAULT_SPECTER)
    p.add_argument("--device", default="cpu")
    p.add_argument("--output-dir", type=Path, help="Carpeta nueva para cuatro predicciones")
    p.add_argument("--apply", action="store_true",
                   help="Ejecutar inferencia genuina con pesos disponibles; nunca reentrena")
    a = p.parse_args(argv)
    try:
        if a.apply:
            if a.raw_dir is None or a.output_dir is None:
                raise InputError("--apply requiere --raw-dir y --output-dir")
            report = run_four_arm(
                a.inputs, raw_dir=a.raw_dir, checkpoint_root=a.checkpoint_root,
                output_dir=a.output_dir,
                scibert_manifest=a.scibert_manifest,
                specter_manifest=a.specter_manifest, device=a.device,
            )
        else:
            report = metadata_plan(a.inputs, raw_dir=a.raw_dir)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError,
            json.JSONDecodeError) as exc:
        p.exit(2, f"A4 offline bloqueado: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
