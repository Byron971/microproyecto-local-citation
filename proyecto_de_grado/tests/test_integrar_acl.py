
"""Pruebas del módulo de integración ACL-200 + ACL OCL."""

import json

import pytest

from proyecto_de_grado.src.data.integrar_acl import integrar_contexto


def preparar_datos(tmp_path, documento_id="N04-1019"):
    """Crea datos de prueba sin modificar los originales."""

    contexto_id = "P15-2138_N04-1019_0"

    contextos = {
        contexto_id: {
            "citing_id": "P15-2138",
            "refid": "N04-1019",
            "masked_text": "We use TARGETCIT and compare OTHERCIT."
        }
    }

    papers = {
        "N04-1019": {
            "title": "Evaluating Content Selection",
            "abstract": "A scientific summarization study."
        }
    }

    documento = {
        "paper_id": documento_id,
        "title": "Evaluating Content Selection",
        "pdf_parse": {
            "body_text": [
                {
                    "text": "First scientific paragraph.",
                    "section": "Introduction"
                },
                {
                    "text": "Second scientific paragraph.",
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

    return contexto_id, contextos, papers, tmp_path


def test_integracion_correcta(tmp_path):
    """Integra correctamente dos fuentes compatibles."""

    cid, contextos, papers, cache = preparar_datos(tmp_path)

    registro = integrar_contexto(
        cid, contextos, papers, cache
    )

    assert registro["cited_id"] == "N04-1019"
    assert registro["ocl_paper_id"] == "N04-1019"
    assert len(registro["paragraphs"]) == 2

    assert registro["paragraphs"][0]["seccion"] == "Introduction"
    assert registro["paragraphs"][1]["seccion"] == "Methods"


def test_conserva_targetcit(tmp_path):
    """La integración no debe eliminar la cita objetivo."""

    cid, contextos, papers, cache = preparar_datos(tmp_path)

    registro = integrar_contexto(
        cid, contextos, papers, cache
    )

    assert registro["citation_context"].count("TARGETCIT") == 1


def test_rechaza_identificador_incorrecto(tmp_path):
    """Detecta documentos asociados a un ID equivocado."""

    cid, contextos, papers, cache = preparar_datos(
        tmp_path,
        documento_id="DOCUMENTO-INCORRECTO"
    )

    with pytest.raises(ValueError, match="ID incorrecto"):
        integrar_contexto(cid, contextos, papers, cache)


def test_detecta_documento_faltante(tmp_path):
    """Informa cuando no existe el artículo completo."""

    cid, contextos, papers, cache = preparar_datos(tmp_path)

    (tmp_path / "N04-1019.json").unlink()

    with pytest.raises(FileNotFoundError):
        integrar_contexto(cid, contextos, papers, cache)


def test_rechaza_contexto_sin_cita_objetivo(tmp_path):
    """Rechaza contextos que no permiten identificar la cita."""

    cid, contextos, papers, cache = preparar_datos(tmp_path)

    contextos[cid]["masked_text"] = "Context without citation."

    with pytest.raises(ValueError, match="cita objetivo"):
        integrar_contexto(cid, contextos, papers, cache)


def test_rechaza_documento_sin_parrafos(tmp_path):
    """Evita crear registros sin texto científico utilizable."""

    cid, contextos, papers, cache = preparar_datos(tmp_path)

    ruta = tmp_path / "N04-1019.json"

    documento = json.loads(ruta.read_text(encoding="utf-8"))
    documento["pdf_parse"]["body_text"] = []

    ruta.write_text(
        json.dumps(documento),
        encoding="utf-8"
    )

    with pytest.raises(ValueError, match="no contiene párrafos"):
        integrar_contexto(cid, contextos, papers, cache)
