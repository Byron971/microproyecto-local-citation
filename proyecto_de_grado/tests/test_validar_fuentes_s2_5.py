"""Regresión S2.5: no confundir una fuente externa con Gold de 9 funciones."""
import copy
import json

import pytest

from proyecto_de_grado.src.data.validar_fuentes_s2_5 import (
    DEFAULT_CATALOGO, main, validar_catalogo,
)


def _catalogo():
    return json.loads(DEFAULT_CATALOGO.read_text(encoding="utf-8"))


def _fuente(catalogo, ident):
    return next(x for x in catalogo["fuentes"] if x["id"] == ident)


def test_catalogo_real_se_valida_sin_importaciones():
    datos = _catalogo()
    resumen = validar_catalogo(datos)
    assert resumen["fuentes"] == 4
    assert resumen["categorias_proyecto"] == 9
    assert resumen["fuentes_con_importacion_automatica_etiquetas"] == 0
    assert resumen["mapeos_automaticos_aprobados"] == 0


def test_prohibe_fusion_automatica_multicite():
    c = _catalogo()
    _fuente(c, "MULTICITE")["importacion_automatica_etiquetas"] = True
    with pytest.raises(ValueError, match="prohibida"):
        validar_catalogo(c)
    c = _catalogo()
    _fuente(c, "MULTICITE")["mapeos_automaticos"] = {"@USE@": "Application"}
    with pytest.raises(ValueError, match="recodificaciones"):
        validar_catalogo(c)


def test_no_confunde_multilabel_con_multiclase():
    c = _catalogo()
    _fuente(c, "MULTICITE")["modo_etiquetado"] = "multiclase"
    with pytest.raises(ValueError, match="multiclase"):
        validar_catalogo(c)


def test_ni_future_work_ni_unsure_se_convierten_en_nueve_clases():
    c = _catalogo()
    relaciones = _fuente(c, "MULTICITE")["relaciones_candidatas_no_homologadas"]
    assert relaciones["@FUT@"] == []
    assert relaciones["@UNSURE@"] == []
    assert relaciones["@SIM@"] == ["Comparison"]
    assert relaciones["@DIF@"] == ["Comparison", "Gap"]
    assert relaciones["@MOT@"] == ["Gap", "Basis"]


def test_detecta_codigos_externos_omitidos_y_clases_inventadas():
    c = _catalogo()
    _fuente(c, "MULTICITE")["etiquetas_funcion"].remove("@UNSURE@")
    with pytest.raises(ValueError, match="Taxonomía"):
        validar_catalogo(c)
    c = _catalogo()
    _fuente(c, "MULTICITE")["relaciones_candidatas_no_homologadas"]["@USE@"] = ["Use As Is"]
    with pytest.raises(ValueError, match="clase desconocida"):
        validar_catalogo(c)


def test_no_declara_etiquetas_de_funcion_para_ilciter():
    c = _catalogo()
    _fuente(c, "ILCITER")["etiquetas_funcion"] = ["Evidence"]
    with pytest.raises(ValueError, match="ILCiteR"):
        validar_catalogo(c)


def test_impide_cambio_de_taxonomia_y_estado_sin_revision():
    c = _catalogo()
    c["taxonomia_proyecto"][0] = "General"
    with pytest.raises(ValueError, match="nueve clases"):
        validar_catalogo(c)
    c = _catalogo()
    c["status"] = "fusionado"
    with pytest.raises(ValueError, match="Estado"):
        validar_catalogo(c)


def test_cli_solo_lectura_y_sin_archivos_generados(tmp_path, capsys):
    origen = _catalogo()
    destino = tmp_path / "catalogo.json"
    contenido = json.dumps(origen)
    destino.write_text(contenido, encoding="utf-8")
    assert main(["--catalogo", str(destino)]) == 0
    assert destino.read_text(encoding="utf-8") == contenido
    assert sorted(x.name for x in tmp_path.iterdir()) == ["catalogo.json"]
    assert "SIN FUSIÓN" in capsys.readouterr().out
