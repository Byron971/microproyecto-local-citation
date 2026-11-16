"""V1/V2: comparar mismos documentos sin Gold ni caché remota.

Fixtures sintéticos, no se modifican los datos históricos ni se infiere
mejora científica de la cobertura técnica de extracción.
"""
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.data.comparar_fragmentacion import comparar_cache, main
from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar, fragmentar_v2


def _words(n, stem="graph"):
    return " ".join(f"{stem}{i:03d}" for i in range(n))


def _write(cache: Path, paper: str, paragraphs: list[dict] | None):
    doc = {"paper_id": paper, "pdf_parse": {"body_text": paragraphs}}
    path = cache / f"{paper}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _par(numero, text, section="Methods"):
    return {"numero": numero, "texto": text, "seccion": section}


def test_v2_preserva_fragmentos_v1_en_texto_corto():
    paragraphs = [
        _par(0, _words(26), "Introduction"),
        _par(1, _words(18), "Introduction"),
        _par(2, _words(50, "transformer"), "Methods"),
    ]
    old, new = fragmentar(paragraphs), fragmentar_v2(paragraphs)
    assert new == old
    assert sum(c["palabras"] for c in new) == 94
    assert all(len(c["paragraph_indices"]) <= 2 for c in new)


@pytest.mark.parametrize("count", [301, 315, 650, 910])
def test_v2_divide_largos_sin_perder_una_palabra(count):
    original = _words(count)
    with pytest.raises(ValueError, match="demasiado largo"):
        fragmentar([_par(4, original)])
    chunks = fragmentar_v2([_par(4, original)])
    assert len(chunks) >= 2
    assert sum(x["palabras"] for x in chunks) == count
    assert all(1 <= x["palabras"] <= 300 for x in chunks)
    assert all(len(x["texto"]) <= 5000 for x in chunks)
    assert all(x["paragraph_indices"] == [4] for x in chunks)
    assert all(x["seccion"] == "Methods" for x in chunks)
    assert len({x["chunk_id"] for x in chunks}) == len(chunks)
    assert " ".join(" ".join(chunk["texto"].split()) for chunk in chunks) == original


def test_v2_conserva_numeros_seccion_y_orden_entre_largos_y_cortos():
    original = [
        _par(10, _words(7, "introduction"), "Introduction"),
        _par(11, _words(340, "method"), "Methods"),
        _par(12, _words(8, "result"), "Results"),
    ]
    chunks = fragmentar_v2(original)
    assert sum(c["palabras"] for c in chunks) == 355
    assert [c["seccion"] for c in chunks] == [
        "Introduction", "Methods", "Methods", "Results"
    ]
    assert [c["paragraph_indices"] for c in chunks] == [[10], [11], [11], [12]]
    assert [c["chunk_id"] for c in chunks] == [
        "p00010-p00010", "p00011-s000", "p00011-s001", "p00012-p00012"
    ]


def test_comparador_usa_exactamente_misma_cache_para_v1_y_v2(tmp_path):
    cache = tmp_path / "ocl"
    cache.mkdir()
    _write(cache, "P14-0001", [{"text": _words(30), "section": "Methods"}])
    _write(cache, "P14-0002", [{"text": _words(301), "section": "Results"}])
    _write(cache, "P14-0003", [{"text": _words(710), "section": "Methods"}])
    _write(cache, "P14-0004", None)
    report = comparar_cache(cache)
    assert report["estado"] == "auditoria_descriptiva_cache_no_gold"
    assert report["total_archivos_misma_muestra"] == 4
    assert report["aceptados_v1"] == 1
    assert report["aceptados_v2"] == 3
    assert report["recuperados_por_v2"] == 2
    assert [row["paper_id"] for row in report["archivos"]] == [
        "P14-0001", "P14-0002", "P14-0003", "P14-0004"
    ]
    assert all(len(row["sha256_fuente"]) == 64 for row in report["archivos"])
    assert report["archivos"][-1]["v1"]["motivo"] == "entrada_invalida"
    assert report["archivos"][-1]["v2"]["motivo"] == "entrada_invalida"
    assert "Recall" in report["advertencia"]
    assert "Graph" not in json.dumps(report)


def test_comparador_rechaza_cache_ausente_y_vacia(tmp_path):
    with pytest.raises(ValueError, match="No existe"):
        comparar_cache(tmp_path / "no-existe")
    cache = tmp_path / "empty"
    cache.mkdir()
    with pytest.raises(ValueError, match="No hay archivos"):
        comparar_cache(cache)
    with pytest.raises(ValueError, match="limite"):
        comparar_cache(cache, limite=-1)


def test_cli_no_sobrescribe_evidencia_y_limite_es_determinista(tmp_path, capsys):
    cache = tmp_path / "ocl"
    cache.mkdir()
    _write(cache, "P14-0002", [{"text": _words(305), "section": "Methods"}])
    _write(cache, "P14-0001", [{"text": _words(5), "section": "Methods"}])
    output = tmp_path / "reporte.json"
    assert main(["--cache", str(cache), "--salida", str(output), "--limite", "1"]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_archivos_misma_muestra"] == 1
    assert report["archivos"][0]["paper_id"] == "P14-0001"
    with pytest.raises(SystemExit) as err:
        main(["--cache", str(cache), "--salida", str(output)])
    assert err.value.code == 2
    assert json.loads(output.read_text(encoding="utf-8")) == report
