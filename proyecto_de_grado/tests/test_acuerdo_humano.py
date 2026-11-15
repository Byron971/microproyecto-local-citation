"""Pruebas del acuerdo entre anotadores humanos (issue #99)."""
import csv

import pytest

from proyecto_de_grado.src.data.acuerdo_humano import (CONJUNTOS, NO_EVALUABLE, acuerdo_especifico, alfa, cargar, cohen,
                                                       desacuerdos, etiqueta, medir, reporte, veredicto)
from test_auditar_tanda1 import fila, libro, xlsx   # mismo armador de libros de Excel que las pruebas del #97


def test_kappa_del_ejemplo_publicado():
    """Ejemplo de 50 propuestas (Wikipedia, «Cohen's kappa»): po = 0,7, pe = 0,5 y κ = 0,4."""
    pares = [("si", "si")] * 20 + [("si", "no")] * 5 + [("no", "si")] * 10 + [("no", "no")] * 15
    k = cohen(pares)
    assert k["po"] == pytest.approx(0.7) and k["pe"] == pytest.approx(0.5) and k["kappa"] == pytest.approx(0.4)
    # marginales distintas: pe = (3·2 + 1·2) / 16 = 0,5 (con las de un solo anotador daría 0,625)
    k = cohen([("a", "a"), ("a", "a"), ("a", "b"), ("b", "b")])
    assert k["pe"] == pytest.approx(0.5) and k["kappa"] == pytest.approx(0.5)
    assert cohen([])["kappa"] is None
    assert cohen([("a", "a"), ("a", "a")])["kappa"] is None      # una sola categoría: κ no está definido


def test_alfa_del_ejemplo_publicado_con_datos_faltantes():
    """Krippendorff (2011), «Computing Krippendorff's Alpha-Reliability»: 4 anotadores, 12 unidades, α nominal = 0,743."""
    n = None
    filas = [[1, 2, 3, 3, 2, 1, 4, 1, 2, n, n, n], [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, n, 3],
             [n, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, n], [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, n]]
    unidades = [[str(x) for x in col if x is not None] for col in zip(*filas)]
    assert alfa(unidades) == pytest.approx(0.743, abs=5e-4)


def test_alfa_calculado_a_mano():
    # 8 valores: o_aa = 2, o_ab = o_ba = 1, o_bb = 4; n_a = 3, n_b = 5; Do = 2/8, De = 30/56
    assert alfa([["a", "a"], ["a", "b"], ["b", "b"], ["b", "b"]]) == pytest.approx(1 - (2 / 8) / (30 / 56))
    assert alfa([["a", "a"], ["b", "b"], ["c"]]) == pytest.approx(1.0)   # la unidad de un solo valor no cuenta
    assert alfa([["a", "a"]]) is None                                    # sin variación no hay α
    assert alfa([["a"], ["b"]]) is None


def test_etiqueta_solo_de_filas_terminadas():
    r = lambda *a: dict(zip(("evaluable", "funcion", "confianza", "justificacion"), a))
    assert etiqueta(r("Evaluable", "Gap", "Alta", "")) == "Gap"
    assert etiqueta(r("Ambiguo", "Basis", "", "dos lecturas")) == "Basis"     # la guía pide la más probable
    assert etiqueta(r("No evaluable", "Gap", "", "texto roto")) == NO_EVALUABLE
    assert etiqueta(r("Evaluable", "Gap", "", "")) is None                   # incompleta
    assert etiqueta(r("No evaluable", "", "", "")) is None                   # falta justificar
    assert etiqueta(r("", "", "", "")) is None


def test_acuerdo_especifico():
    e = acuerdo_especifico([("Gap", "Gap"), ("Gap", "Basis"), ("Basis", "Basis")])
    assert e["Gap"] == (pytest.approx(2 / 3), 3) and e["Basis"] == (pytest.approx(2 / 3), 3)
    assert e["Evidence"] == (None, 0)


def test_medir_parejas_alfa_y_confusiones():
    etiquetas = {"Ana": {"c1": "Gap", "c2": "Basis", "c3": "Gap", "c6": "Evidence"},   # c6: solo la anotó Ana
                 "Beto": {"c1": "Gap", "c2": "Gap", "c4": "Basis"},
                 "Ceci": {"c3": "Gap", "c4": "Basis"}}
    asignadas = {"Ana": {"c1", "c2", "c3", "c5"}, "Beto": {"c1", "c2", "c4", "c5"}, "Ceci": {"c3", "c4"}}
    m = medir(etiquetas, asignadas)
    assert m["parejas"]["Ana", "Beto"]["n"] == 2 and m["parejas"]["Ana", "Beto"]["compartidas"] == 3
    assert m["parejas"]["Ana", "Ceci"]["n"] == 1 and m["parejas"]["Ana", "Ceci"]["po"] == 1.0
    assert m["citas_con_dos"] == 4
    assert m["acuerdo_observado"] == pytest.approx(3 / 4)
    assert m["confusiones"] == {("Basis", "Gap"): 1}
    assert m["alfa"] == pytest.approx(alfa([["Gap", "Gap"], ["Basis", "Gap"], ["Gap", "Gap"], ["Basis", "Basis"]]))
    assert desacuerdos(etiquetas) == [{"context_id": "c2", "anotador_1": "Ana", "etiqueta_1": "Basis",
                                       "anotador_2": "Beto", "etiqueta_2": "Gap"}]


def test_kappa_promedio_ignora_parejas_sin_kappa():
    etiquetas = {"Ana": {"c1": "Gap", "c2": "Basis", "c3": "Basis"}, "Beto": {"c1": "Gap", "c2": "Gap", "c3": "Basis"},
                 "Ceci": {}}                                              # con Ceci no hay citas en común: sin κ
    assert medir(etiquetas)["kappa_promedio"] == pytest.approx(0.4)   # (2/3 − 4/9) / (1 − 4/9)


def test_veredicto():
    assert veredicto(None) == "sin datos suficientes"
    assert veredicto(0.80) == "confiable"
    assert veredicto(0.70).startswith("aceptable")
    assert veredicto(0.66).startswith("bajo")


def test_cargar_desde_hojas_y_reporte(tmp_path):
    xlsx(tmp_path / "TestGold_T1_v2_Ana.xlsx", libro([fila("c1", "Evaluable", "Gap", "Alta"), fila("c2", "Evaluable", "Gap")]))
    xlsx(tmp_path / "TestGold_T1_v2_Beto.xlsx", libro([fila("c1", "Ambiguo", "Basis", "", "duda"), fila("c2")]))
    xlsx(tmp_path / "Calibracion3_Ana.xlsx", libro([fila("k1", "No evaluable", "", "", "roto")]))
    etiquetas, perfil, asignadas = cargar(tmp_path, CONJUNTOS["tanda1"])
    assert etiquetas == {"Ana": {"c1": "Gap"}, "Beto": {"c1": "Basis"}}      # c2 no está terminada en ninguna
    assert perfil["Beto"]["ambiguas"] == 1 and perfil["Ana"]["terminadas"] == 1 and perfil["Ana"]["asignadas"] == 2
    assert asignadas["Ana"] == {"c1", "c2"}
    assert list(cargar(tmp_path, CONJUNTOS["calibracion3"])[0]) == ["Ana"]
    texto = reporte([("Tanda 1", medir(etiquetas, asignadas), perfil)])
    assert "| Ana y Beto | 2 | 1 | 0,0% |" in texto and "Basis / Gap: 1" in texto
    assert "pocas citas" in texto
