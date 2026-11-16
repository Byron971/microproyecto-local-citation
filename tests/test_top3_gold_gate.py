"""Pruebas 100% sintéticas: no tocan Gold, citas privadas ni servicios de red."""
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from proyecto_de_grado.src.evaluation.top3_gold_gate import (
    ProtocolError, adjudicate, audit, check_exclusions, load_judgments,
    load_universe, score_rankings,
)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def data(tmp_path):
    m = tmp_path / "manifest.json"
    m.write_text(json.dumps({
        "schema_version": 1, "purpose": "heldout_chunk_relevance",
        "used_for_tuning": False,
        "cases": [
            {"context_id": "q1", "citing_id": "citing-1", "cited_id": "paper-A",
             "split": "test", "context_sha256": sha("q1"),
             "chunks": [{"chunk_id": f"p{i}", "text_sha256": sha(f"a-{i}"),
                         "section": "Methods"} for i in range(1, 5)]},
            {"context_id": "q2", "citing_id": "citing-2", "cited_id": "paper-B",
             "split": "test", "context_sha256": sha("q2"),
             "chunks": [{"chunk_id": f"k{i}", "text_sha256": sha(f"b-{i}"),
                         "section": "Results"} for i in range(1, 4)]},
        ],
    }), encoding="utf-8")
    exclusions = tmp_path / "exclusions.json"
    exclusions.write_text(json.dumps({
        "schema_version": 1,
        "train_context_ids": ["train-1"],
        "validation_context_ids": ["val-1"],
        "prompt_selection_context_ids": [],
        "ranking_tuning_context_ids": [],
        "train_citing_ids": ["other-citing"],
        "validation_citing_ids": [],
        "train_pairs": ["other-citing::paper-A"],
        "validation_pairs": []
    }), encoding="utf-8")

    judgments = tmp_path / "judgments.csv"
    rows = []
    # q1: p1,p3 son relevantes; p3 tiene desacuerdo humano.
    values = {"q1": {"p1": ("1", "1"), "p2": ("0", "0"),
                     "p3": ("1", "0"), "p4": ("0", "0")},
              "q2": {"k1": ("0", "0"), "k2": ("0", "0"),
                     "k3": ("0", "0")}}
    for context, chunks in values.items():
        for chunk, pair in chunks.items():
            for annotator, value in zip(("human-A", "human-B"), pair):
                rows.append({"context_id": context, "chunk_id": chunk,
                             "annotator_id": annotator, "relevance": value})
    write_csv(judgments, ("context_id", "chunk_id", "annotator_id", "relevance"), rows)

    adj = tmp_path / "adjudications.csv"
    write_csv(adj, ("context_id", "chunk_id", "adjudicator_id", "relevance", "reason"),
              [{"context_id": "q1", "chunk_id": "p3", "adjudicator_id": "human-C",
                "relevance": "1", "reason": "evidencia sintética de contraste"}])

    ranks = tmp_path / "rankings.csv"
    rrows = []
    for context, methods in {
        "q1": {"bm25": ("p4", "p2", "p1"), "scibert": ("p3", "p2", "p1")},
        "q2": {"bm25": ("k2", "k1", "k3"), "scibert": ("k3", "k2", "k1")},
    }.items():
        for method, chunks in methods.items():
            for position, chunk in enumerate(chunks, 1):
                rrows.append({"context_id": context, "method": method,
                              "rank": str(position), "chunk_id": chunk})
    write_csv(ranks, ("context_id", "method", "rank", "chunk_id"), rrows)
    return m, exclusions, judgments, adj, ranks


def test_resultados_sinteticos_con_denominador_real(data):
    report = audit(*data)
    result = report["results_from_supplied_judgments_only"]
    assert report["human_gold_certified"] is False
    assert report["blindness_certified"] is False
    assert report["pairs_adjudicated"] == 1
    assert report["universe_pairs"] == 7
    assert result["queries_total"] == 2
    assert result["queries_evaluable"] == 1
    assert result["queries_sin_chunk_relevante"] == 1
    assert result["methods"]["bm25"] == {
        "hit_at_3": 1, "recall_at_3": 0.5, "mrr_at_3": 0.333333}
    assert result["methods"]["scibert"] == {
        "hit_at_3": 1, "recall_at_3": 1, "mrr_at_3": 1}
    assert all(len(v) == 64 for v in report["sha256"].values())
    assert "q1" not in json.dumps(report)


def test_no_se_permite_gold_o_scores_en_manifiesto(data):
    original = json.loads(data[0].read_text())
    original["cases"][0]["scores"] = [0.9]
    data[0].write_text(json.dumps(original))
    with pytest.raises(ProtocolError, match="no puede contener"):
        load_universe(data[0])


def test_no_split_test_o_fuga_por_citante(data):
    original = json.loads(data[0].read_text())
    original["cases"][0]["split"] = "train"
    data[0].write_text(json.dumps(original))
    with pytest.raises(ProtocolError, match="split"):
        load_universe(data[0])


def test_fuga_de_documento_y_par_se_bloquea(data):
    cases, _ = load_universe(data[0])
    excludes = json.loads(data[1].read_text())
    excludes["train_citing_ids"] = ["citing-1"]
    data[1].write_text(json.dumps(excludes))
    with pytest.raises(ProtocolError, match="leakage"):
        check_exclusions(data[1], cases)
    excludes["train_citing_ids"] = []
    excludes["train_pairs"] = ["citing-2::paper-B"]
    data[1].write_text(json.dumps(excludes))
    with pytest.raises(ProtocolError, match="par citante-citado"):
        check_exclusions(data[1], cases)


def test_rechaza_anotacion_solo_top3(data):
    _, universe = load_universe(data[0])
    with data[2].open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if (r["context_id"], r["chunk_id"]) != ("q1", "p4")]
    write_csv(data[2], ("context_id", "chunk_id", "annotator_id", "relevance"), rows)
    with pytest.raises(ProtocolError, match="CADA chunk"):
        load_judgments(data[2], universe)


def test_rechaza_autoanotacion_unica_y_abstencion_sin_adjudicar(data):
    _, universe = load_universe(data[0])
    with data[2].open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["context_id"] == "q1" and r["chunk_id"] == "p2" and r["annotator_id"] == "human-A":
            r["relevance"] = "abstain"
    write_csv(data[2], ("context_id", "chunk_id", "annotator_id", "relevance"), rows)
    primary = load_judgments(data[2], universe)
    with pytest.raises(ProtocolError, match="Todos los desacuerdos"):
        adjudicate(data[3], primary)


def test_adjudicador_debe_ser_tercero(data):
    _, universe = load_universe(data[0])
    primary = load_judgments(data[2], universe)
    with data[3].open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows[0]["adjudicator_id"] = "human-A"
    write_csv(data[3], ("context_id", "chunk_id", "adjudicator_id", "relevance", "reason"), rows)
    with pytest.raises(ProtocolError, match="tercero"):
        adjudicate(data[3], primary)



def test_acuerdo_unanime_no_requiere_tercer_adjudicador(data):
    cases, universe = load_universe(data[0])
    with data[2].open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row["context_id"] == "q1" and row["chunk_id"] == "p3":
            row["relevance"] = "1"
    write_csv(data[2], ("context_id", "chunk_id", "annotator_id", "relevance"), rows)
    write_csv(data[3],
              ("context_id", "chunk_id", "adjudicator_id", "relevance", "reason"), [])
    primary = load_judgments(data[2], universe)
    final = adjudicate(data[3], primary)
    assert final[("q1", "p3")] == 1
    assert len(final) == len(universe)


def test_rechaza_rankings_repetidos_y_citados_ajenos(data):
    cases, universe = load_universe(data[0])
    primary = load_judgments(data[2], universe)
    consensus = adjudicate(data[3], primary)
    with data[4].open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows[0]["chunk_id"] = "k1"
    write_csv(data[4], ("context_id", "method", "rank", "chunk_id"), rows)
    with pytest.raises(ProtocolError, match="fuera del documento"):
        score_rankings(data[4], cases, consensus)


def test_no_reescribe_el_reporte_ni_publica_etiquetas(data, tmp_path):
    from proyecto_de_grado.src.evaluation.top3_gold_gate import main
    output = tmp_path / "resumen.json"
    args = [
        "--manifest", str(data[0]), "--exclusions", str(data[1]),
        "--judgments", str(data[2]), "--adjudications", str(data[3]),
        "--rankings", str(data[4]), "--output", str(output),
    ]
    assert main(args) == 0
    assert "human-A" not in output.read_text()
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
