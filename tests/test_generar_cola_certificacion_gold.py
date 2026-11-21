"""Pruebas de cola privada; no usan anotaciones ni textos reales."""
from scripts.generar_cola_certificacion_gold import generar
from tests.test_auditar_certificacion_gold import preparar


def test_cola_sin_texto_y_sin_adjudicar(tmp_path):
    preparar(tmp_path)
    filas = generar(tmp_path)
    assert len(filas) == 3  # B unica, C discrepancia, D Opus; A concordancia completa
    assert {x["tarea"] for x in filas} == {
        "segunda_anotacion_humana_independiente",
        "adjudicacion_humana_desacuerdo",
        "anotacion_humana_independiente",
    }
    assert all(x["etiqueta_adjudicada"] == "" for x in filas)
    assert all("Contexto original (inglés)" not in x for x in filas)
    assert all(x["estado_revision"] == "PENDIENTE" for x in filas)
