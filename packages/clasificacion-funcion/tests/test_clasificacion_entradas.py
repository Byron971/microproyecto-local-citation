import pytest

from clasificacion_funcion import dominio as d

CLS, SEP = 101, 102


class TokFalso:
    """Una palabra = un token; el id es la posicion global en el vocabulario."""
    def __init__(self):
        self.vocab = {}

    def ids(self, texto):
        return [self.vocab.setdefault(w, 1000 + len(self.vocab)) for w in texto.split()]


def caso(cid="c1", n_ctx=10, n_abs=300, n_chunk=(200, 200, 200), perfiles=("method", "results", "otra")):
    ctx = " ".join(f"c{i}" for i in range(n_ctx // 2)) + " TARGETCIT " + \
        " ".join(f"d{i}" for i in range(n_ctx // 2))
    return {"context_id": cid, "citation_context": ctx, "titulo": " ".join(f"t{i}" for i in range(80)),
            "abstract": " ".join(f"a{i}" for i in range(n_abs)),
            "top3": [{"chunk_id": f"{cid}-{i}", "texto": " ".join(f"{cid}w{i}_{j}" for j in range(n)),
                      "perfil": p} for i, (n, p) in enumerate(zip(n_chunk, perfiles))]}


def armar(c, entrada, max_len=512, tok=None):
    tok = tok or TokFalso()
    return d.ensamblar(d.tokenizar_segmentos(d.construir_segmentos(c, entrada), tok), max_len, CLS, SEP), tok


# ---- segmentos
def test_segmentos_a_y_b():
    c = caso()
    assert [s["nombre"] for s in d.construir_segmentos(c, "A")] == ["contexto", "titulo", "abstract"]
    b = d.construir_segmentos(c, "B")
    assert [s["nombre"] for s in b] == ["contexto", "chunk_1", "chunk_2", "chunk_3"]
    assert b[1]["texto"].startswith("method : ") and b[2]["texto"].startswith("results : ")
    assert not d.construir_segmentos(c, "B_sin_seccion")[1]["texto"].startswith("method")


def test_segmentos_validan_entradas():
    c = caso()
    with pytest.raises(ValueError):
        d.construir_segmentos(c, "C")
    with pytest.raises(ValueError, match="B_barajada"):
        d.construir_segmentos(c, "B_barajada")
    for malo, entrada in (({**c, "citation_context": "sin marca"}, "B"),
                          ({**c, "top3": c["top3"][:2]}, "B"),
                          ({**c, "abstract": " "}, "A")):
        with pytest.raises(ValueError):
            d.construir_segmentos(malo, entrada)


# ---- ensamblado
def test_plantilla_y_longitud_maxima():
    for entrada in ("A", "B"):
        r, _ = armar(caso(), entrada)
        assert r["input_ids"][0] == CLS and r["input_ids"][-1] == SEP
        assert r["longitud"] <= 512 and r["longitud"] == len(r["input_ids"])
    r, _ = armar(caso(n_abs=900), "A")
    assert r["longitud"] == 512  # el abstract rellena todo el presupuesto


def test_a_titulo_con_tope_y_abstract_por_la_cola():
    r, tok = armar(caso(n_abs=900), "A")
    assert r["truncados"]["titulo"] == 80 - d.TOPE_TITULO
    # presupuesto = 512 - 2 - 2; contexto 11 tokens (10 + TARGETCIT); titulo 48
    assert r["truncados"]["abstract"] == 900 - (512 - 4 - 11 - d.TOPE_TITULO)
    ids = r["input_ids"]
    # el abstract conserva su inicio (a0, a1, ...) y pierde la cola
    assert tok.vocab["a0"] in ids and tok.vocab["a899"] not in ids


def test_corto_no_se_trunca():
    r, _ = armar(caso(n_ctx=10, n_abs=20), "A")
    assert r["truncados"]["abstract"] == 0 and r["truncados"]["contexto"] == 0


def test_contexto_largo_ventana_centrada_conserva_targetcit():
    c = caso(n_ctx=600)
    c["citation_context"] = " ".join(f"p{i}" for i in range(450)) + " TARGETCIT " + \
        " ".join(f"q{i}" for i in range(450))
    for entrada in ("A", "B"):
        r, tok = armar(c, entrada)
        assert tok.vocab["TARGETCIT"] in r["input_ids"]
        assert r["truncados"]["contexto"] == 901 - d.TOPE_CONTEXTO
        # simetrico: la ventana incluye vecinos de ambos lados
        assert tok.vocab["p449"] in r["input_ids"] and tok.vocab["q0"] in r["input_ids"]


def test_targetcit_en_borde_del_contexto():
    c = caso()
    c["citation_context"] = "TARGETCIT " + " ".join(f"q{i}" for i in range(400))
    r, tok = armar(c, "B")
    assert tok.vocab["TARGETCIT"] in r["input_ids"] and tok.vocab["q0"] in r["input_ids"]
    c["citation_context"] = " ".join(f"p{i}" for i in range(400)) + " TARGETCIT"
    r, tok = armar(c, "B")
    assert tok.vocab["TARGETCIT"] in r["input_ids"] and tok.vocab["p399"] in r["input_ids"]


@pytest.mark.parametrize("longs,pres,esperado", [
    ([10, 200, 200], 100, [10, 45, 45]),
    ([300, 300, 300], 100, [34, 33, 33]),
    ([5, 5, 5], 100, [5, 5, 5]),
    ([0, 50, 400], 90, [0, 45, 45]),
    ([20, 20, 400], 100, [20, 20, 60]),
])
def test_water_filling(longs, pres, esperado):
    r = d.reparto_water_filling(longs, pres)
    assert r == esperado and sum(r) <= pres and all(a <= l for a, l in zip(r, longs))


def test_b_reparte_entre_chunks_y_reporta_truncados():
    r, _ = armar(caso(n_chunk=(30, 400, 400)), "B")
    t = r["truncados"]
    assert t["chunk_1"] == 0 and t["chunk_2"] > 0 and abs(t["chunk_2"] - t["chunk_3"]) <= 1
    assert r["longitud"] == 512


def test_ensamblar_rechaza_estructuras_invalidas():
    seg = d.tokenizar_segmentos(d.construir_segmentos(caso(), "B"), TokFalso())
    with pytest.raises(ValueError):
        d.ensamblar(seg[1:], 512, CLS, SEP)
    with pytest.raises(ValueError):
        d.ensamblar(seg, 4, CLS, SEP)


# ---- barajado
def conjunto(n=30):
    perf = ["introduction", "related_work", "method", "results", "conclusion", "otra", "vacia"]
    return [caso(f"c{i:02d}", perfiles=(perf[i % 7], perf[(i * 3) % 7], perf[(i * 5 + 1) % 7]))
            for i in range(n)]


def test_barajado_determinista_conserva_marginal_y_cambia_algo():
    casos = conjunto()
    a, sha_a = d.barajar_secciones(casos, 42)
    b, sha_b = d.barajar_secciones(casos, 42)
    assert a == b and sha_a == sha_b
    assert d.barajar_secciones(casos, 7)[1] != sha_a
    orig = sorted(c["perfil"] for x in casos for c in x["top3"])
    nuevo = sorted(p for x in a for p in x["perfiles_barajados"])
    assert orig == nuevo
    assert any(x["perfiles_barajados"] != [c["perfil"] for c in x["top3"]] for x in a)
    assert all("perfiles_barajados" not in x for x in casos)  # no muta la entrada


def test_barajado_independiente_del_orden_de_entrada():
    casos = conjunto()
    a, sha_a = d.barajar_secciones(casos, 1)
    b, sha_b = d.barajar_secciones(list(reversed(casos)), 1)
    assert sha_a == sha_b
    assert {x["context_id"]: x["perfiles_barajados"] for x in a} == \
        {x["context_id"]: x["perfiles_barajados"] for x in b}


def test_b_barajada_usa_perfiles_barajados():
    barajados, _ = d.barajar_secciones(conjunto(), 3)
    x = barajados[0]
    seg = d.construir_segmentos(x, "B_barajada")
    for i, p in enumerate(x["perfiles_barajados"], 1):
        assert seg[i]["texto"].startswith(f"{p} : ")


# ---- especificacion
def test_especificacion_independiente_del_tokenizer():
    # no recibe tokenizer: el hash es el mismo para SciBERT y SPECTER
    e = d.especificacion_entrada("B", 512)
    assert d.sha_especificacion(e) == d.sha_especificacion(d.especificacion_entrada("B", 512))
    assert d.sha_especificacion(e) != d.sha_especificacion(d.especificacion_entrada("A", 512))
    assert d.sha_especificacion(e) != d.sha_especificacion(d.especificacion_entrada("B", 256))
    assert d.sha_especificacion(e) != d.sha_especificacion(d.especificacion_entrada("B_sin_seccion", 512))


def test_especificacion_barajada_exige_semilla():
    assert d.especificacion_entrada("B_barajada", 512, 42)["semilla_barajado"] == 42
    assert d.sha_especificacion(d.especificacion_entrada("B_barajada", 512, 1)) != \
        d.sha_especificacion(d.especificacion_entrada("B_barajada", 512, 2))
    with pytest.raises(ValueError):
        d.especificacion_entrada("B_barajada", 512)
    with pytest.raises(ValueError):
        d.especificacion_entrada("B", 512, 42)
    with pytest.raises(ValueError):
        d.especificacion_entrada("X", 512)
