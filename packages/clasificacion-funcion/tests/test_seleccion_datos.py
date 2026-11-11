"""Reglas anti-fuga y de calidad de `seleccion_datos` con fixtures pequenos (sin archivos)."""
import pytest

from clasificacion_funcion import dominio, seleccion_datos as sd

CLASES = dominio.CATEGORIAS


def _ctx(cid, citing, texto=None):
    return {"citing_id": citing, "refid": "X00-0000", "masked_text": texto or f"texto {cid} TARGETCIT"}


def _qlora(clase, p=0.95):
    dist = [0.0] * 11
    dist[CLASES.index(clase)] = p
    return {"label": clase, "p": p, "dist": dist}


def fuentes(n_por_clase=10):
    """Citantes P10-xxxx (2010), una cita por citante, mas casos de 2014/2015 y de gold."""
    qlora, contextos, jurado, haiku = {}, {}, {}, {}
    k = 0
    for clase in CLASES:
        for _ in range(n_por_clase):
            cid = f"P10-{1000 + k}_X00-0000_0"
            qlora[cid] = _qlora(clase, 0.6 + 0.4 * (k % 5) / 5)
            contextos[cid] = _ctx(cid, f"P10-{1000 + k}")
            k += 1
    for anio in ("14", "15"):
        cid = f"P{anio}-2000_X00-0000_0"
        qlora[cid] = _qlora("Background")
        contextos[cid] = _ctx(cid, f"P{anio}-2000")
    gold = "P10-9000_X00-0000_0"
    contextos[gold] = _ctx(gold, "P10-9000")
    qlora[gold] = _qlora("Gap")
    contextos["P10-9000_X00-1111_1"] = _ctx("P10-9000_X00-1111_1", "P10-9000")  # mismo citante
    qlora["P10-9000_X00-1111_1"] = _qlora("Gap")
    contextos["P10-8000_X00-0000_0"] = _ctx("P10-8000_X00-0000_0", "P10-8000", f"texto {gold} TARGETCIT")
    qlora["P10-8000_X00-0000_0"] = _qlora("Gap")  # texto identico al de un caso del gold
    return sd.Fuentes(qlora=qlora, jurado=jurado, haiku=haiku, haiku_train=set(), haiku_val=set(),
                      gpt={}, contextos=contextos, ids_gold={gold}, ids_excluidos=set())


def test_anio_de():
    assert (sd.anio_de("P15-1102_P13-2093_1"), sd.anio_de("P87-1011_X_0"), sd.anio_de("D00-1_X_0")) == (2015, 1987, 2000)


def test_pool_excluye_anios_gold_citantes_y_textos_repetidos():
    f = fuentes()
    pool, info = sd.construir_pool(f)
    ids = {x["context_id"] for x in pool}
    assert not any(sd.anio_de(i) in (2014, 2015) for i in ids)
    assert "P10-9000_X00-0000_0" not in ids and "P10-9000_X00-1111_1" not in ids
    assert "P10-8000_X00-0000_0" not in ids
    assert info["descartes"] == {"anio_excluido": 2, "id_vetado": 1, "citante_gold": 1, "texto_gold": 1}


def test_pool_descarta_abstenciones_de_cualquier_fuente():
    f = fuentes()
    cid = next(iter(f.qlora))
    f.qlora[cid] = {"label": "Ambiguo", "p": 0.9, "dist": [0.0] * 11}
    pool, info = sd.construir_pool(f)
    assert cid not in {x["context_id"] for x in pool} and info["descartes"]["qlora_abstiene"] == 1


def test_jerarquia_de_calidad():
    q = _qlora("Basis", 0.95)
    base = {"qlora": q, "haiku": None, "jurado": None}
    assert sd.nivel_etiqueta(base) == ("Basis", 4)
    assert sd.nivel_etiqueta({**base, "qlora": _qlora("Basis", 0.6)}) == ("Basis", 6)
    assert sd.nivel_etiqueta({**base, "qlora": _qlora("Basis", 0.3)}) == (None, None)
    assert sd.nivel_etiqueta({**base, "haiku": "Gap"}) == ("Gap", 2)
    j3 = {"voto": "Evidence", "acuerdo": 3, "qlora": "Basis"}
    assert sd.nivel_etiqueta({**base, "haiku": "Gap", "jurado": j3}) == ("Evidence", 1)
    j2 = {"voto": "Basis", "acuerdo": 2, "qlora": "Basis"}
    assert sd.nivel_etiqueta({**base, "qlora": _qlora("Basis", 0.6), "jurado": j2}) == ("Basis", 3)
    j2b = {"voto": "Gap", "acuerdo": 2, "qlora": "Basis"}
    assert sd.nivel_etiqueta({**base, "qlora": _qlora("Basis", 0.6), "jurado": j2b}) == ("Gap", 5)
    sin = {"voto": "SIN_CONSENSO", "acuerdo": 1, "qlora": "Basis"}
    assert sd.nivel_etiqueta({**base, "jurado": sin}) == ("Basis", 4)


def test_dist9_renormaliza_sin_abstenciones():
    d = sd.dist9([0.5, 0.25] + [0.0] * 7 + [0.2, 0.05])
    assert len(d) == 9 and sum(d) == pytest.approx(1.0) and d[0] == pytest.approx(2 / 3)


def test_validacion_agrupada_reproducible_y_con_forzados():
    f = fuentes(30)
    pool, _ = sd.construir_pool(f)
    forzar = {pool[0]["citing_id"]}
    a = sd.dividir_validacion(pool, forzar, semilla=2026, tamano=40, n_particiones=20)
    b = sd.dividir_validacion(pool, forzar, semilla=2026, tamano=40, n_particiones=20)
    assert a == b and forzar <= a
    assert {x["citing_id"] for x in pool if x["citing_id"] in a}.isdisjoint(
        {x["citing_id"] for x in pool if x["citing_id"] not in a})


def test_construir_todo_sin_fugas_y_topes():
    f = fuentes(30)
    res = sd.construir_todo(f, tope=12, tamano_v=40, n_particiones=20)
    ids_v = {x["context_id"] for x in res["v"]}
    cit_v = {x["citing_id"] for x in res["v"]}
    assert res["fugas"]["total_fugas"] == 0
    for nombre, filas in res["variantes"].items():
        assert not ({x["context_id"] for x in filas} & ids_v) and not ({x["citing_id"] for x in filas} & cit_v)
        if nombre != "natural":  # `natural` no balancea: sin tope por clase
            assert max(sd.conteos(filas).values()) <= 12, nombre


def test_verificar_falla_cerrado_si_train_toca_v_o_2015():
    f = fuentes(10)
    res = sd.construir_todo(f, tope=12, tamano_v=20, n_particiones=5)
    v, train = res["v"], res["variantes"]["qlora_p50"]
    with pytest.raises(ValueError, match="Fuga"):
        sd.verificar({"malo": train + v[:1]}, v, f)
    intruso = {**train[0], "context_id": "P15-2000_X00-0000_0", "citing_id": "P15-2000"}
    f.contextos[intruso["context_id"]] = _ctx(intruso["context_id"], "P15-2000")
    with pytest.raises(ValueError, match="anios excluidos"):
        sd.verificar({"malo": train + [intruso]}, v, f)


def test_auditar_fuentes_acuerdo_y_precision_por_tramo():
    f = fuentes(2)
    ids = [c for c in f.qlora if c.startswith("P10-1")][:4]
    for i, c in enumerate(ids):
        f.haiku[c] = f.qlora[c]["label"] if i < 3 else "Gap" if f.qlora[c]["label"] != "Gap" else "Basis"
    a = sd.auditar_fuentes(f)
    par = a["acuerdo_pares"]["qlora~haiku"]
    assert par["n"] == 4 and par["acuerdo"] == pytest.approx(0.75)
    assert a["acuerdo_pares"]["qlora~gpt"] == {"n": 0, "acuerdo": None}
    assert sum(v["n"] for k, v in a["precision_qlora_por_p"].items() if "haiku" in k) == 4
