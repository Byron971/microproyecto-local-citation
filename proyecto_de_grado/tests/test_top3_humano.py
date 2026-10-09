"""S2.3: los juicios humanos y la evaluación no pueden ser simulados."""
import csv
import json

import pytest

from proyecto_de_grado.src.evaluation.top3_humano import (
    ProtocoloError, evaluar_calibracion, leer_casos,
    preparar_hojas, puntajes_top3,
)


def _corpus(tmp_path, *, split="train"):
    ruta = tmp_path / "corpus.json"
    doc = {
        "version": 1, "resumen": {"tipo": "muestra_desarrollo_train_no_gold"},
        "casos": [{
            "context_id": "D13-1157_P12-1007_0", "split": split,
            "citing_id": "D13-1157", "cited_id": "P12-1007",
            "cited_title": "Discourse Treebank",
            "citation_context": "Graph neural methods TARGETCIT were compared.",
            "chunks": [
                {"chunk_id": "p0", "texto": "Neural graph algorithms are useful.",
                 "seccion": "Methods", "paragraph_indices": [0]},
                {"chunk_id": "p1", "texto": "Neural models improve results.",
                 "seccion": "Results", "paragraph_indices": [1]},
                {"chunk_id": "p2", "texto": "Language syntax is important.",
                 "seccion": "Introduction", "paragraph_indices": [2]},
            ],
        }, {
            "context_id": "W13-4005_W08-1111_0", "split": split,
            "citing_id": "W13-4005", "cited_id": "W08-1111",
            "cited_title": "Other Paper",
            "citation_context": "New research TARGETCIT is described here.",
            "chunks": [
                {"chunk_id": "q0", "texto": "Text for a second cited paper.",
                 "seccion": "Abstract", "paragraph_indices": [0]}
            ],
        }],
    }
    ruta.write_text(json.dumps(doc), encoding="utf-8")
    return ruta


def _completar_csv(ruta, labels):
    with ruta.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames
        rows = list(reader)
    for row in rows:
        key = (row["context_id"], row["chunk_id"])
        if key in labels:
            row["relevante_0_1"] = str(labels[key])
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_hojas_ciegas_exhaustivas_y_sin_puntajes(tmp_path):
    src = _corpus(tmp_path)
    carpeta = tmp_path / "hojas"
    manifest = preparar_hojas(src, carpeta)
    assert manifest["estado"] == "calibracion_train_no_gold"
    assert manifest["juicios_por_anotador"] == 4
    assert len(manifest["sha256_fuente"]) == 64
    for nombre in ("anotador_a.csv", "anotador_b.csv", "adjudicacion_plantilla.csv"):
        texto = (carpeta / nombre).read_text(encoding="utf-8-sig")
        assert "puntaje_bm25" not in texto
        assert "posicion" not in texto
        assert "TARGETCIT" in texto
        with (carpeta / nombre).open(encoding="utf-8-sig", newline="") as fh:
            filas = list(csv.DictReader(fh))
        assert len(filas) == 4
        assert all(not fila["relevante_0_1"] for fila in filas)
        assert len({(f["context_id"], f["chunk_id"]) for f in filas}) == 4


def test_preparar_no_sobrescribe_el_trabajo_humano(tmp_path):
    src = _corpus(tmp_path)
    carpeta = tmp_path / "hojas"
    preparar_hojas(src, carpeta)
    with pytest.raises(ProtocoloError, match="no se sobrescriben"):
        preparar_hojas(src, carpeta)


def test_rechaza_test_y_val_y_archivo_falso(tmp_path):
    for split in ("val", "test"):
        with pytest.raises(ProtocoloError, match="Identidad/split"):
            leer_casos(_corpus(tmp_path, split=split))
    ruta = _corpus(tmp_path)
    doc = json.loads(ruta.read_text())
    doc["resumen"]["tipo"] = "test_gold_final"
    ruta.write_text(json.dumps(doc))
    with pytest.raises(ProtocoloError, match="Solo se admite"):
        leer_casos(ruta)


def test_metricas_con_gold_multiple_y_sin_relevantes():
    m = puntajes_top3(["a", "b", "c", "d"], {"b", "d"})
    assert m["hit_3"] == 1
    assert m["recall_3"] == 0.5
    assert m["rr_3"] == 0.5
    assert puntajes_top3(["a", "b"], set()) is None
    cero = puntajes_top3(["x", "y"], {"z"})
    assert cero["hit_3"] == cero["recall_3"] == cero["rr_3"] == 0
    with pytest.raises(ProtocoloError, match="duplicado"):
        puntajes_top3(["a", "a"], {"a"})


def test_juicios_incompletos_impiden_cualquier_metica(tmp_path):
    src = _corpus(tmp_path)
    carpeta = tmp_path / "hojas"
    preparar_hojas(src, carpeta)
    with pytest.raises(ProtocoloError, match="incompleta"):
        evaluar_calibracion(src, carpeta)


def test_exige_adjudicacion_de_desacuerdos_y_excluye_sin_relevantes(tmp_path):
    src = _corpus(tmp_path)
    carpeta = tmp_path / "hojas"
    preparar_hojas(src, carpeta)
    a = {("D13-1157_P12-1007_0", "p0"): 1,
         ("D13-1157_P12-1007_0", "p1"): 0,
         ("D13-1157_P12-1007_0", "p2"): 0,
         ("W13-4005_W08-1111_0", "q0"): 0}
    b = dict(a)
    b[("D13-1157_P12-1007_0", "p1")] = 1
    _completar_csv(carpeta / "anotador_a.csv", a)
    _completar_csv(carpeta / "anotador_b.csv", b)
    with pytest.raises(ProtocoloError, match="adjudicaciones"):
        evaluar_calibracion(src, carpeta)
    _completar_csv(
        carpeta / "adjudicacion_plantilla.csv",
        {("D13-1157_P12-1007_0", "p1"): 1},
    )
    resumen = evaluar_calibracion(src, carpeta)
    assert resumen["juicios_por_anotador"] == 4
    assert resumen["desacuerdos"] == 1
    assert resumen["acuerdo_observado"] == 0.75
    assert resumen["total_casos"] == 2
    assert resumen["casos_elegibles"] == 1
    assert resumen["casos_sin_relevantes"] == 1
    assert resumen["casos"][0]["n_relevantes"] == 2
    assert resumen["estado"] == "calibracion_train_no_gold"
    assert resumen["hit_3"] is not None


def test_artefacto_modificado_invalida_hojas(tmp_path):
    src = _corpus(tmp_path)
    carpeta = tmp_path / "hojas"
    preparar_hojas(src, carpeta)
    doc = json.loads(src.read_text())
    doc["casos"][0]["cited_title"] = "Changed title"
    src.write_text(json.dumps(doc))
    with pytest.raises(ProtocoloError, match="ha cambiado"):
        evaluar_calibracion(src, carpeta)


def test_rechaza_filas_duplicadas_y_fuera_de_corpus(tmp_path):
    src = _corpus(tmp_path)
    carpeta = tmp_path / "hojas"
    preparar_hojas(src, carpeta)
    ruta = carpeta / "anotador_a.csv"
    _completar_csv(ruta, {
        ("D13-1157_P12-1007_0", "p0"): 1,
        ("D13-1157_P12-1007_0", "p1"): 0,
        ("D13-1157_P12-1007_0", "p2"): 0,
        ("W13-4005_W08-1111_0", "q0"): 0,
    })
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0])
    with ruta.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows + [rows[0]])
    with pytest.raises(ProtocoloError, match="duplicado"):
        evaluar_calibracion(src, carpeta)
