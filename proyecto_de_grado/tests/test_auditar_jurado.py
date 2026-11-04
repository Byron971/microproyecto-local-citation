"""Pruebas de la auditoría del jurado (issues #93 y #94)."""
import pytest

from proyecto_de_grado.src.data.auditar_jurado import (
    SIN_CONSENSO, auditar_entradas, kappa_cohen, kappa_fleiss, medir_consenso, voto_mayoritario,
)


def fila(cid, qlora, qwen, llama):
    """Fila del jurado con el voto calculado como lo hace el cuaderno."""
    voto, k = voto_mayoritario([qlora, qwen, llama])
    return {"context_id": cid, "voto": voto, "jueces_de_acuerdo": str(k), "qlora": qlora, "qwen": qwen, "llama": llama}


def jueces_de(jurado):
    """Archivos de juez coherentes con el CSV: (filas por cita, número de líneas)."""
    return {n: ({r["context_id"]: {"etiqueta": r[n], "estable": True} for r in jurado}, len(jurado))
            for n in ("qwen", "llama")}


def test_voto_mayoritario():
    assert voto_mayoritario(["Basis", "Basis", "Gap"]) == ("Basis", 2)
    assert voto_mayoritario(["Gap", "Gap", "Gap"]) == ("Gap", 3)
    assert voto_mayoritario(["Basis", "Gap", "Evidence"]) == (SIN_CONSENSO, 1)


def test_kappa_cohen_acuerdo_total_y_al_azar():
    assert kappa_cohen(["A", "B", "A", "B"], ["A", "B", "A", "B"]) == 1.0
    assert kappa_cohen(["A", "A", "B", "B"], ["A", "B", "A", "B"]) == pytest.approx(0.0)


def test_kappa_fleiss_ejemplo_calculado_a_mano():
    # 3 jueces, 4 citas: P̄ = (1 + 1/3 + 1/3 + 1/3) / 4 = 0,5; p(A) = 7/12, p(B) = 5/12; Pe = 74/144
    listas = [["A", "A", "B", "A"], ["A", "B", "B", "B"], ["A", "A", "A", "B"]]
    assert kappa_fleiss(listas) == pytest.approx((0.5 - 74 / 144) / (1 - 74 / 144))


def test_auditoria_limpia_no_reporta_problemas():
    jurado = [fila("a", "Basis", "Basis", "Gap"), fila("b", "Gap", "Evidence", "Basis")]
    aud = auditar_entradas(jurado, jueces_de(jurado), {"a": {}, "b": {}})
    assert (aud["repetidos_csv"], aud["fuera_de_acl200"], aud["voto_distinto"], aud["acuerdo_distinto"]) == (0, 0, 0, 0)
    assert all(d["faltan"] == d["sobran"] == d["distinta_al_csv"] == 0 for d in aud["jueces"].values())


def test_auditoria_detecta_voto_mal_copiado_y_juez_incompleto():
    jurado = [fila("a", "Basis", "Basis", "Gap"), fila("b", "Gap", "Gap", "Basis")]
    jueces = jueces_de(jurado)
    del jueces["llama"][0]["b"]                          # a llama le falta una cita
    jueces["qwen"][0]["a"]["etiqueta"] = "Evidence"       # el archivo de qwen no coincide con su columna del CSV
    jurado[1]["voto"] = "Basis"                           # el voto del CSV no sigue la regla de mayoría
    aud = auditar_entradas(jurado, jueces)
    assert aud["jueces"]["llama"]["faltan"] == 1
    assert aud["jueces"]["qwen"]["distinta_al_csv"] == 1
    assert aud["voto_distinto"] == 1


def test_consenso_cuenta_minoria_por_juez():
    jurado = [fila("a", "Basis", "Basis", "Gap"), fila("b", "Gap", "Basis", "Gap"), fila("c", "Gap", "Gap", "Gap")]
    con = medir_consenso(jurado)
    assert con["niveles"][3] == 1 and con["niveles"][2] == 2
    assert con["minoria"] == {"llama": 1, "qwen": 1}
    assert con["parejas"][("qlora", "llama")]["acuerdo"] == pytest.approx(2 / 3)
