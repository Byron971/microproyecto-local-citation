"""Pruebas de selección reproducible y ausencia de fuga del pre-etiquetado."""
import json
import pytest

from proyecto_de_grado.src.data.preparar_preetiquetado import (
    ETIQUETAS,
    construir_candidatos,
    guardar,
)


def datos_ficticios():
    contextos = {}
    papers = {}
    train = []
    for i in range(8):
        cid = f"CTX-{i}"
        refid = f"REF-{i}"
        contextos[cid] = {"masked_text": f"Prior work TARGETCIT example {i} OTHERCIT.", "refid": refid, "citing_id": f"CIT-{i}"}
        papers[refid] = {"title": f"Paper {i}", "abstract": f"Abstract {i}"}
        train.append({"context_id": cid, "positive_ids": [refid]})
    contextos["CTX-7"]["masked_text"] = "No target citation here"
    return contextos, papers, train


def test_excluye_reservados_y_casos_invalidos():
    contextos, papers, train = datos_ficticios()
    filas, resumen = construir_candidatos(contextos, papers, train, {"CTX-2"}, limite=100)
    assert len(filas) == 6
    assert "CTX-2" not in {f["id"] for f in filas}
    assert "CTX-7" not in {f["id"] for f in filas}
    assert resumen["motivos_exclusion"]["reservado_practica_calibracion"] == 1
    assert resumen["motivos_exclusion"]["marcador_targetcit_invalido"] == 1


def test_muestra_reproducible_sin_etiquetas():
    c, p, t = datos_ficticios()
    una, r = construir_candidatos(c, p, t, set(), limite=4, semilla=42)
    otra, _ = construir_candidatos(c, p, list(reversed(t)), set(), limite=4, semilla=42)
    assert una == otra
    assert len(una) == 4
    assert all(f["split"] == "train" and f["citation_context"].count("TARGETCIT") == 1 for f in una)
    assert all("gold" not in f and "label" not in f for f in una)
    assert len(ETIQUETAS) == 9
    assert r["etiquetas_generadas"] == 0


def test_limite_invalido():
    c, p, t = datos_ficticios()
    with pytest.raises(ValueError, match="mayor que cero"):
        construir_candidatos(c, p, t, set(), limite=0)


def test_salida_jsonl_y_resumen(tmp_path):
    c, p, t = datos_ficticios()
    filas, resumen = construir_candidatos(c, p, t, set(), limite=3)
    destino, info = guardar(filas, resumen, tmp_path)
    recuperados = [json.loads(x) for x in destino.read_text(encoding="utf-8").splitlines()]
    assert recuperados == filas
    contenido = json.loads(info.read_text(encoding="utf-8"))
    assert contenido["seleccionados"] == 3
    assert len(contenido["sha256_candidatos"]) == 64
