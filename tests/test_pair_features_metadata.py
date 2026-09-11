"""Pruebas de las caracteristicas de metadatos del reordenador v2.

Cada prueba aisla una caracteristica y comprueba que produce el valor esperado
ante un caso construido a proposito, en vez de verificar solo que el codigo
corre. Dos de ellas cubren lo que mas facilmente se rompe sin avisar: que la
version 1 siga dando exactamente las mismas cinco columnas, y que el prior de
popularidad no se calcule sobre datos que el modelo no deberia ver.
"""

import numpy as np
import pytest

from src.features.pair_features import (
    FEATURE_NAMES,
    METADATA_FEATURE_NAMES,
    PairFeatureExtractor,
    parse_acl_id,
    token_set,
)

# Articulos con anios y tipos de publicacion deliberadamente distintos: P es
# conferencia (ACL) y W es taller, de modo que same_venue pueda distinguirlos.
PAPERS = {
    "P08-1001": {"title": "statistical machine translation", "abstract": "phrase based decoding"},
    "P12-1002": {"title": "neural language models", "abstract": "recurrent networks for text"},
    "W14-1003": {"title": "workshop on parsing", "abstract": "dependency parsing shared task"},
    "J99-1004": {"title": "computational linguistics survey", "abstract": "overview of the field"},
}

# El contexto proviene de un articulo de 2012, asi que W14 (2014) es posterior
# y no puede ser una cita suya.
CONTEXTS = {
    "c1": {
        "masked_text": "we build on statistical machine translation TARGETCIT",
        "citing_id": "P12-9999",
    }
}

PARES = [{"context_id": "c1", "paper_id": paper_id} for paper_id in PAPERS]


def extractor_v2(**kwargs):
    """Extractor con metadatos activados y vocabulario sin recortar."""
    opciones = {"max_features": None, "min_df": 1, "include_metadata": True}
    opciones.update(kwargs)
    return PairFeatureExtractor(**opciones).fit(PAPERS)


def columna(matriz, nombre, ext):
    """Devuelve la columna de una caracteristica por su nombre."""
    return matriz[:, ext.feature_names.index(nombre)]


# --------------------------------------------------------------------------
# parse_acl_id
# --------------------------------------------------------------------------


def test_parse_acl_id_resuelve_el_siglo_correcto():
    # Los identificadores traen el anio en dos digitos: 95 es 1995 y 11 es 2011.
    assert parse_acl_id("W95-0110") == ("W", 1995)
    assert parse_acl_id("W11-1305") == ("W", 2011)


def test_parse_acl_id_distingue_el_tipo_de_publicacion():
    assert parse_acl_id("P08-1001")[0] == "P"
    assert parse_acl_id("J99-1004")[0] == "J"


def test_parse_acl_id_devuelve_vacio_sin_inventar_datos():
    # Ante un identificador desconocido no debe adivinar: quien llame decide
    # el valor neutro.
    assert parse_acl_id("formato-raro") == (None, None)
    assert parse_acl_id("") == (None, None)
    assert parse_acl_id(None) == (None, None)


# --------------------------------------------------------------------------
# Compatibilidad con la version 1
# --------------------------------------------------------------------------


def test_sin_metadatos_las_columnas_son_las_cinco_originales():
    ext = PairFeatureExtractor(max_features=None, min_df=1).fit(PAPERS)

    assert ext.feature_names == FEATURE_NAMES


def test_con_metadatos_las_cinco_originales_no_cambian_de_valor():
    # Es la garantia de que la version 1 sigue siendo reproducible: activar la
    # bandera agrega columnas, nunca altera las que ya existian.
    v1 = PairFeatureExtractor(max_features=None, min_df=1).fit(PAPERS)
    v2 = extractor_v2()

    assert v2.feature_names == FEATURE_NAMES + METADATA_FEATURE_NAMES
    assert np.allclose(
        v1.transform(PARES, CONTEXTS),
        v2.transform(PARES, CONTEXTS)[:, : len(FEATURE_NAMES)],
    )


# --------------------------------------------------------------------------
# Restriccion temporal
# --------------------------------------------------------------------------


def test_year_diff_es_positivo_para_articulos_anteriores():
    ext = extractor_v2()
    valores = columna(ext.transform(PARES, CONTEXTS), "year_diff", ext)
    por_id = dict(zip(PAPERS, valores, strict=True))

    # El citante es de 2012.
    assert por_id["P08-1001"] == pytest.approx(4.0)
    assert por_id["J99-1004"] == pytest.approx(13.0)


def test_is_future_marca_solo_los_posteriores_al_citante():
    ext = extractor_v2()
    valores = columna(ext.transform(PARES, CONTEXTS), "is_future", ext)
    por_id = dict(zip(PAPERS, valores, strict=True))

    # W14 es de 2014 y el citante de 2012: es una cita imposible.
    assert por_id["W14-1003"] == pytest.approx(1.0)
    assert por_id["P08-1001"] == pytest.approx(0.0)
    assert por_id["P12-1002"] == pytest.approx(0.0)


def test_anio_desconocido_deja_las_senales_temporales_en_neutro():
    # Sin identificador reconocible no hay referencia temporal, y una diferencia
    # inventada seria peor que ninguna.
    contextos = {"c1": {**CONTEXTS["c1"], "citing_id": "sin-formato"}}
    ext = extractor_v2()
    matriz = ext.transform(PARES, contextos)

    assert np.allclose(columna(matriz, "year_diff", ext), 0.0)
    assert np.allclose(columna(matriz, "is_future", ext), 0.0)


# --------------------------------------------------------------------------
# Tipo de publicacion y solapamiento
# --------------------------------------------------------------------------


def test_same_venue_compara_el_tipo_de_publicacion():
    ext = extractor_v2()
    valores = columna(ext.transform(PARES, CONTEXTS), "same_venue", ext)
    por_id = dict(zip(PAPERS, valores, strict=True))

    # El citante P12-9999 es de conferencia: coincide con los P, no con W ni J.
    assert por_id["P08-1001"] == pytest.approx(1.0)
    assert por_id["W14-1003"] == pytest.approx(0.0)
    assert por_id["J99-1004"] == pytest.approx(0.0)


def test_title_overlap_mide_la_fraccion_del_titulo_presente_en_el_contexto():
    ext = extractor_v2()
    valores = columna(ext.transform(PARES, CONTEXTS), "title_overlap", ext)
    por_id = dict(zip(PAPERS, valores, strict=True))

    # El contexto contiene las tres palabras de "statistical machine translation".
    assert por_id["P08-1001"] == pytest.approx(1.0)
    assert por_id["W14-1003"] < 0.5


def test_title_overlap_se_normaliza_por_el_titulo_y_no_por_el_contexto():
    # Alargar el contexto con texto irrelevante no debe diluir la senal: mide
    # que fraccion del titulo aparece, no al reves.
    largo = {
        "c1": {
            **CONTEXTS["c1"],
            "masked_text": CONTEXTS["c1"]["masked_text"] + " relleno" * 200,
        }
    }
    ext = extractor_v2()

    corto = columna(ext.transform(PARES, CONTEXTS), "title_overlap", ext)
    extenso = columna(ext.transform(PARES, largo), "title_overlap", ext)

    assert np.allclose(corto, extenso)


def test_token_set_normaliza_a_minusculas_y_descarta_vacios():
    assert token_set("Neural  Machine") == {"neural", "machine"}
    assert token_set(None) == set()


# --------------------------------------------------------------------------
# Prior de popularidad
# --------------------------------------------------------------------------


def test_citation_prior_crece_con_las_citas_pero_comprimido():
    ext = extractor_v2(citation_counts={"P08-1001": 100, "P12-1002": 1})
    valores = columna(ext.transform(PARES, CONTEXTS), "citation_prior", ext)
    por_id = dict(zip(PAPERS, valores, strict=True))

    assert por_id["P08-1001"] > por_id["P12-1002"] > por_id["W14-1003"]
    # Con logaritmo, cien citas no valen cien veces una: sin el, un punado de
    # articulos muy citados dominaria la escala de la columna.
    assert por_id["P08-1001"] < 10 * por_id["P12-1002"]


def test_citation_prior_es_cero_para_articulos_nunca_citados():
    ext = extractor_v2(citation_counts={"P08-1001": 5})
    valores = columna(ext.transform(PARES, CONTEXTS), "citation_prior", ext)
    por_id = dict(zip(PAPERS, valores, strict=True))

    assert por_id["W14-1003"] == pytest.approx(0.0)
    assert por_id["J99-1004"] == pytest.approx(0.0)


def test_sin_conteos_el_prior_no_aporta_senal():
    # Si nadie pasa citation_counts la columna queda constante, de modo que el
    # modelo le asigna peso nulo en lugar de aprender ruido.
    ext = extractor_v2()
    valores = columna(ext.transform(PARES, CONTEXTS), "citation_prior", ext)

    assert np.allclose(valores, 0.0)


# --------------------------------------------------------------------------
# Forma de la salida
# --------------------------------------------------------------------------


def test_la_matriz_tiene_una_columna_por_nombre_declarado():
    ext = extractor_v2()
    matriz = ext.transform(PARES, CONTEXTS)

    assert matriz.shape == (len(PARES), len(ext.feature_names))


def test_sin_pares_devuelve_una_matriz_vacia_con_el_ancho_correcto():
    ext = extractor_v2()

    assert ext.transform([], CONTEXTS).shape == (0, len(ext.feature_names))
