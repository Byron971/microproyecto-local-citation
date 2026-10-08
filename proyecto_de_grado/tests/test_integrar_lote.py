
"""Pruebas de integración por lotes ACL-200 + ACL OCL."""

import json

import pytest

from proyecto_de_grado.src.data.integrar_lote import procesar_lote


def preparar_datos(tmp_path):
    """Construye tres contextos y un documento ACL OCL."""

    contextos = {
        "CTX-001": {
            "citing_id": "P15-0001",
            "refid": "N04-1019",
            "masked_text": "We apply TARGETCIT."
        },
        "CTX-002": {
            "citing_id": "P15-0002",
            "refid": "N04-1019",
            "masked_text": "According to TARGETCIT."
        },
        "CTX-003": {
            "citing_id": "P15-0003",
            "refid": "N04-1019",
            "masked_text": "Our method follows TARGETCIT."
        },
    }

    papers = {
        "N04-1019": {
            "title": "Example scientific article",
            "abstract": "Scientific abstract."
        }
    }

    documento = {
        "paper_id": "N04-1019",
        "title": "Example scientific article",
        "pdf_parse": {
            "body_text": [
                {
                    "text": "First paragraph.",
                    "section": "Introduction"
                },
                {
                    "text": "Second paragraph.",
                    "section": "Methods"
                }
            ]
        }
    }

    ruta = tmp_path / "N04-1019.json"
    ruta.write_text(
        json.dumps(documento),
        encoding="utf-8"
    )

    return contextos, papers


def test_integra_tres_contextos(tmp_path):
    contextos, papers = preparar_datos(tmp_path)

    total, resultados = procesar_lote(
        contextos, papers, tmp_path,
        refid="N04-1019", limite=3
    )

    assert total == 3
    assert len(resultados) == 3
    assert all(r["estado"] == "integrado" for r in resultados)
    assert all(r["parrafos"] == 2 for r in resultados)


def test_respeta_limite(tmp_path):
    contextos, papers = preparar_datos(tmp_path)

    total, resultados = procesar_lote(
        contextos, papers, tmp_path,
        refid="N04-1019", limite=2
    )

    assert total == 3
    assert len(resultados) == 2


def test_detecta_documento_faltante(tmp_path):
    contextos, papers = preparar_datos(tmp_path)

    (tmp_path / "N04-1019.json").unlink()

    total, resultados = procesar_lote(
        contextos, papers, tmp_path,
        refid="N04-1019", limite=3
    )

    assert total == 3
    assert all(r["estado"] == "error" for r in resultados)
    assert all(r["parrafos"] == 0 for r in resultados)


def test_continua_si_un_contexto_es_invalido(tmp_path):
    contextos, papers = preparar_datos(tmp_path)

    contextos["CTX-002"]["masked_text"] = (
        "Context without target citation."
    )

    total, resultados = procesar_lote(
        contextos, papers, tmp_path,
        refid="N04-1019", limite=3
    )

    estados = [r["estado"] for r in resultados]

    assert total == 3
    assert estados.count("integrado") == 2
    assert estados.count("error") == 1


def test_rechaza_limite_invalido(tmp_path):
    contextos, papers = preparar_datos(tmp_path)

    with pytest.raises(ValueError, match="límite"):
        procesar_lote(
            contextos, papers, tmp_path,
            refid="N04-1019", limite=0
        )


def test_articulo_sin_contextos(tmp_path):
    contextos, papers = preparar_datos(tmp_path)

    total, resultados = procesar_lote(
        contextos, papers, tmp_path,
        refid="N99-9999", limite=10
    )

    assert total == 0
    assert resultados == []
