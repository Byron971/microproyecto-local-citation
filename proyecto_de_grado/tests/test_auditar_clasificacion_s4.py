"""Pruebas sin red, sin GPU y sin datos personales o Gold."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.evaluation.auditar_clasificacion_s4 import auditar, guardar, ETIQUETAS


def sha(s):
    return hashlib.sha256(s).hexdigest()


def persist(tmp: Path, *, mutate=None):
    base = tmp
    chunks = [
        {"chunk_id": "p001", "texto": "Study methods of citation analysis."},
        {"chunk_id": "p002", "texto": "The evidence supports the claim."},
        {"chunk_id": "p003", "texto": "A third chunk on experiments."},
    ]
    casos = [{
        "id": f"CTX-{i}", "split": "train", "cited_id": f"Paper-{i//2}",
        "citation_context": f"We use TARGETCIT in experiment {i}.",
        "cited_chunks": copy.deepcopy(chunks),
    } for i in range(3)]
    c1 = []
    c2 = []
    retrievals = []
    for i, caso in enumerate(casos):
        cid = caso["id"]
        top = [{"chunk_id": c["chunk_id"], "similitud_coseno": round(0.9 - j*.1, 6)} for j, c in enumerate(chunks)]
        retrievals.append({"context_id": cid, "cited_id": caso["cited_id"], "split": "train", "scibert_top3": top})
        c1.append({"id": cid, "split": "train", "model": "qwen3:4b-instruct", "run_fingerprint": "h1", "status": "ok", "response_format": "label", "evidence_mode": "none", "retrieved_chunks": [], "suggested_label": "Basis" if i != 2 else "Gap", "is_human_label": False})
        c2.append({"id": cid, "split": "train", "model": "qwen3:4b-instruct", "run_fingerprint": "h2", "status": "ok", "response_format": "label", "evidence_mode": "scibert_top3", "retrieved_chunks": [
            {"posicion": j+1, "chunk_id": c["chunk_id"], "cited_id": caso["cited_id"], "text_sha256": sha(c["texto"].encode()), "similitud_coseno_no_calibrada": top[j]["similitud_coseno"]} for j,c in enumerate(chunks)
        ], "suggested_label": "Basis" if i != 1 else "Application", "is_human_label": False})
    inputs = {"corpus": casos, "retrieval": None, "c1": c1, "c2": c2, "resumen_c1": None, "resumen_c2": None}
    if mutate:
        mutate(inputs)
    def dump(obj, path, jsonl):
        raw = ("".join(json.dumps(row, ensure_ascii=False)+"\n" for row in obj) if jsonl else json.dumps(obj, ensure_ascii=False)+"\n").encode()
        path.write_bytes(raw)
        return sha(raw)
    path_corpus = base / "corpus.jsonl"
    corpus_digest = dump(inputs["corpus"], path_corpus, True)
    inputs["retrieval"] = inputs["retrieval"] or {"tipo": "comparacion_tecnica_train_s2_8_no_gold", "sha256_entrada": corpus_digest, "modelo": "allenai/scibert_scivocab_uncased", "modelo_commit_resuelto": "rev", "resumen": {"metricas_gold_calculadas": False}, "resultados": retrievals}
    path_rep = base / "retrieval.json"
    rep_digest = dump(inputs["retrieval"], path_rep, False)
    s1 = {"input_sha256": corpus_digest, "model": "qwen3:4b-instruct", "run_fingerprint": "h1", "response_format": "label", "evidence_mode": "none"}
    s2 = {"input_sha256": corpus_digest, "reporte_s2_8_sha256": rep_digest, "model": "qwen3:4b-instruct", "run_fingerprint": "h2", "response_format": "label", "evidence_mode": "scibert_top3"}
    inputs["resumen_c1"] = inputs["resumen_c1"] or s1
    inputs["resumen_c2"] = inputs["resumen_c2"] or s2
    paths = {"corpus": path_corpus, "retrieval": path_rep}
    for name in ("c1", "c2", "resumen_c1", "resumen_c2"):
        path = base / (name + (".jsonl" if name in ("c1", "c2") else ".json"))
        dump(inputs[name], path, name in ("c1", "c2"))
        paths[name] = path
    return paths


def test_casos_validos_sin_metricas_gold(tmp_path):
    r, dif = auditar(**persist(tmp_path))
    assert r["total_contextos_train"] == 3
    assert r["articulos_citados"] == 2
    assert r["casos_pareados_validos"] == 3
    assert r["casos_cambiados"] == 2
    assert len(dif) == 2
    assert r["f1_macro"] is None and r["metricas_gold_calculadas"] is False
    assert r["concentracion_c1"]["basis_count"] == 2
    assert list(r["distribucion_c1"]) == list(ETIQUETAS)


def test_guardar_archivos_sin_sobrescribir(tmp_path):
    inputdir = tmp_path / "inputs"
    inputdir.mkdir()
    r, dif = auditar(**persist(inputdir))
    output = tmp_path / "out"
    files = guardar(r, dif, output)
    assert len(files) == 3
    assert all(f.is_file() for f in files)
    assert json.loads(files[0].read_text(encoding="utf-8"))["metricas_gold_calculadas"] is False
    with pytest.raises(FileExistsError):
        guardar(r, dif, output)


def test_rechaza_gold_en_prediccion(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c1"][0].update(is_human_label=True))
    with pytest.raises(ValueError, match="etiquetas humanas"):
        auditar(**p)


def test_rechaza_test_split(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["corpus"][0].update(split="test"))
    with pytest.raises(ValueError, match="split train"):
        auditar(**p)


def test_rechaza_c2_chunk_de_otro_articulo(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c2"][0]["retrieved_chunks"][0].update(cited_id="OTRO"))
    with pytest.raises(ValueError, match="fragmentos ajenos"):
        auditar(**p)


def test_rechaza_c2_hash_de_texto(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c2"][0]["retrieved_chunks"][0].update(text_sha256="0"*64))
    with pytest.raises(ValueError, match="huella de texto"):
        auditar(**p)


def test_rechaza_etiqueta_invalida(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c1"][0].update(suggested_label="Unknown"))
    with pytest.raises(ValueError, match="fuera de taxonomía"):
        auditar(**p)


def test_rechaza_modelo_distinto(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c2"][0].update(model="another"))
    with pytest.raises(ValueError, match="modelo o fingerprint"):
        auditar(**p)


def test_rechaza_ids_repetidos(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c1"].append(copy.deepcopy(x["c1"][0])))
    with pytest.raises(ValueError, match="repetido"):
        auditar(**p)


def test_rechaza_corpus_cambiado_respecto_scibert(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x.update(retrieval={"tipo": "comparacion_tecnica_train_s2_8_no_gold", "sha256_entrada": "hash_erroneo", "resumen": {"metricas_gold_calculadas": False}, "resultados": []}))
    with pytest.raises(ValueError, match="SHA256"):
        auditar(**p)


def test_rechaza_no_pareados(tmp_path):
    p = persist(tmp_path, mutate=lambda x: x["c1"].pop())
    with pytest.raises(ValueError, match="IDs no coinciden"):
        auditar(**p)


def test_registra_error_sin_inventar_etiqueta(tmp_path):
    def invalid(x):
        x["c1"][0].update(status="parse_error", suggested_label=None)
    r, d = auditar(**persist(tmp_path, mutate=invalid))
    assert r["casos_pareados_validos"] == 2
    assert r["estados_c1"]["parse_error"] == 1
    assert r["casos_cambiados"] == 2
