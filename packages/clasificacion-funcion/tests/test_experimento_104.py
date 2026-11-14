"""Evaluacion, bootstrap y perdida de `experimento_104` (sin entrenar encoders reales)."""
import pytest

pytest.importorskip("torch")
pytest.importorskip("mlflow")
pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from clasificacion_funcion import clasificador_torch as ct, dominio, experimento_104 as ex, seleccion_datos as sd  # noqa: E402
from clasificacion_funcion import registro_mlflow as rm  # noqa: E402


def _fila(cid, etiqueta, sonnet=None, haiku=None, p=0.9):
    dist = [0.0] * 11
    dist[dominio.normalizar_etiqueta(etiqueta)] = p
    dist[(dominio.normalizar_etiqueta(etiqueta) + 1) % 9] = 1 - p
    return {"context_id": cid, "citing_id": cid, "etiqueta": etiqueta, "etiqueta_entrenamiento": etiqueta,
            "fuente": "qlora", "qlora": {"label": etiqueta, "p": p, "dist": dist},
            "sonnet": {"label": sonnet, "confianza": "Alta"} if sonnet else None, "haiku": haiku, "gpt": None}


def _fuentes():
    return sd.Fuentes(qlora={}, jurado={}, haiku={}, haiku_train=set(), haiku_val={"a"}, gpt={"b": "Gap"},
                      contextos={}, ids_gold=set())


def test_conjuntos_eval_agrega_val_mixta_y_val_sonnet():
    c = dominio.CATEGORIAS
    v = [_fila("a", c[0], sonnet=c[1], haiku=c[0]), _fila("b", c[2], sonnet=c[2]), _fila("c", c[3])]
    sets = ex.conjuntos_eval(v, _fuentes())
    assert [x["etiqueta_entrenamiento"] for x in sets["val_mixta"]] == [c[0], c[2], c[3]]
    assert [x["etiqueta_entrenamiento"] for x in sets["val_sonnet"]] == [c[1], c[2]]  # sin Sonnet: fuera
    assert {x["context_id"] for x in sets["dev_haiku"]} == {"a"}


def test_con_modo_perdida_kd_y_ponderado_agregan_campos():
    c = dominio.CATEGORIAS
    caso = {"context_id": "a", "indice": 0, "_fila": _fila("a", c[0], p=0.8)}
    assert abs(sum(ex.con_modo_perdida([caso], "kd")[0]["objetivo"]) - 1) < 1e-9
    assert ex.con_modo_perdida([caso], "ponderado")[0]["peso"] == 0.8
    assert "objetivo" not in ex.con_modo_perdida([caso], "duro")[0]


def test_bootstrap_pareado_detecta_diferencia_y_es_reproducible():
    verdad = [i % 3 for i in range(90)]
    buena = list(verdad)
    mala = [(v + 1) % 3 if i % 2 else v for i, v in enumerate(verdad)]
    r = ex.bootstrap_diferencia(buena, mala, verdad, n=200, semilla=1)
    assert r["diferencia"] > 0 and r["ic95"][0] > 0 and r["prob_a_mayor"] == 1.0
    assert r == ex.bootstrap_diferencia(buena, mala, verdad, n=200, semilla=1)
    igual = ex.bootstrap_diferencia(buena, buena, verdad, n=50, semilla=1)
    assert igual["diferencia"] == 0 and igual["ic95"] == (0.0, 0.0)
    with pytest.raises(ValueError):
        ex.bootstrap_diferencia([0], [0, 1], [0, 1])


# ---------------------------------------------------------------- Entrada B (#104, notebook 06)
CONFIG_S = {"v_sha": "db20c0aa3cb1919ca6012a6573fedc7277607a6dcd08044a4d1ea57ab069ef84",
            "datos_sha": "da205e90244dbffde9059d1e6718bab3d5494821cc4583d926a3da2eddbb2313",
            "pista": "sonnet", "v_etiquetas": "sonnet", "variante": "sonnet",
            "ids_train_sha": "eb5cd4a9d79e426377d3b3393594ca00b292f885bbad7a347b7356dc6cdb47de"}
CONFIG_M = {"v_sha": "db20c0aa3cb1919ca6012a6573fedc7277607a6dcd08044a4d1ea57ab069ef84",
            "datos_sha": "77f86f0f9f7c4fce7163d6a832be4d1d0079fa655233f7a79b20fa786011f281",
            "variante": "natural",
            "ids_train_sha": "f6b7bd2fbccf3cd6351dfd77e69b04061b9c42f290e0e4b3a3a0328f8ffd77d4"}


def test_config_de_entrada_a_conserva_el_config_sha_de_los_runs_reales_de_104():
    """Valores copiados de `manifiesto_experimentos.csv` (runs reales de la Parte 2): si cambia la
    config de la entrada A, nb 05 dejaria de reanudar sus runs."""
    s = ex.config_corrida(CONFIG_S, "scibert", 42, "duro", ct.Hiperparametros(lr=3e-5, epocas=4, paciencia=3), False)
    m = ex.config_corrida(CONFIG_M, "scibert", 42, "kd", ct.Hiperparametros(), False)
    assert rm.sha_config(s) == "f5c4249e35d3b2a4"  # scibert-S-sonnet-lr3e-05-e4-s42
    assert rm.sha_config(m) == "5247ab7755fe302a"  # scibert-A-natural-kd-s42
    assert "top3_sha" not in s


def test_config_de_entrada_b_agrega_top3_sha_y_cambia_el_config_sha():
    hp = ct.Hiperparametros(lr=3e-5, epocas=4, paciencia=3)
    a = ex.config_corrida(CONFIG_S, "scibert", 42, "duro", hp, False)
    b = ex.config_corrida(CONFIG_S, "scibert", 42, "duro", hp, False, "B", "abc")
    assert b == {**a, "entrada": "B", "top3_sha": "abc"}
    assert rm.sha_config(a) != rm.sha_config(b)
    assert rm.sha_config(b) != rm.sha_config(ex.config_corrida(CONFIG_S, "scibert", 42, "duro", hp, False, "B", "xyz"))
    with pytest.raises(ValueError, match="top3_sha"):
        ex.config_corrida(CONFIG_S, "scibert", 42, "duro", hp, False, "B")


def _fuentes_b():
    ctx = {c: {"citing_id": f"P{c}", "refid": f"R{c}", "masked_text": f"texto {c} TARGETCIT fin"}
           for c in ("a", "b", "c")}
    f = sd.Fuentes(qlora={}, jurado={}, haiku={}, haiku_train=set(), haiku_val=set(), gpt={},
                   contextos=ctx, ids_gold=set())
    papers = {f"R{c}": {"title": f"titulo {c}", "abstract": f"resumen {c}"} for c in ("a", "b", "c")}
    return f, papers


def _entrada_b(cid):
    return {"context_id": cid, "top3": [{"chunk_id": f"p{i}", "perfil": "method", "seccion": "M",
                                         "texto": f"chunk {i} de {cid}"} for i in (1, 2, 3)]}


def test_casos_b_son_los_de_a_mas_top3_y_conservan_la_fila_para_kd():
    f, papers = _fuentes_b()
    c = dominio.CATEGORIAS
    filas = [_fila("a", c[0], p=0.8), _fila("b", c[1])]
    a, _ = ex.casos_a(filas, f, papers)
    b, info = ex.casos_b(filas, f, papers, {"a": _entrada_b("a"), "b": _entrada_b("b"), "c": _entrada_b("c")})
    assert [{k: v for k, v in x.items() if k != "top3"} for x in b] == a  # el input es la unica diferencia
    assert [x["top3"] for x in b] == [_entrada_b("a")["top3"], _entrada_b("b")["top3"]]
    assert info == {"entrada": 2, "casos": 2, "sin_titulo_abstract": 0}
    kd = ex.con_modo_perdida(b, "kd")
    assert abs(sum(kd[0]["objetivo"]) - 1) < 1e-9 and kd[0]["_fila"] is filas[0]


def test_casos_b_falla_cerrado_si_una_cita_no_tiene_entrada_b():
    f, papers = _fuentes_b()
    with pytest.raises(ValueError, match="sin entrada B"):
        ex.casos_b([_fila("a", dominio.CATEGORIAS[0]), _fila("b", dominio.CATEGORIAS[1])], f, papers,
                   {"a": _entrada_b("a")})
    with pytest.raises(ValueError, match="requiere `entradas_b`"):
        ex.casos_entrada("B", [_fila("a", dominio.CATEGORIAS[0])], f, papers)
    with pytest.raises(ValueError, match="no soportada"):
        ex.casos_entrada("B_sin_seccion", [], f, papers, {})


def test_el_barajado_solo_se_aplica_a_b_barajada_y_es_reproducible():
    f, papers = _fuentes_b()
    casos, _ = ex.casos_b([_fila(c, dominio.CATEGORIAS[0]) for c in ("a", "b", "c")], f, papers,
                          {c: {"context_id": c, "top3": [{"chunk_id": f"p{i}", "perfil": f"{c}{i}", "seccion": "M",
                                                          "texto": "t"} for i in (1, 2, 3)]} for c in "abc"})
    assert ex._barajar("B", casos, 42) is casos and ex._barajar("A", casos, 42) is casos
    barajados = ex._barajar("B_barajada", casos, 42)
    assert barajados == ex._barajar("B_barajada", casos, 42)
    original = sorted(ch["perfil"] for c in casos for ch in c["top3"])
    assert sorted(p for c in barajados for p in c["perfiles_barajados"]) == original  # misma marginal


def test_gold_ciego_sin_etiquetas():
    f, papers = _fuentes_b()
    a = ex.casos_gold(["b", "a"], f, papers)
    b = ex.casos_gold(["a"], f, papers, "B", {"a": _entrada_b("a")})
    assert [c["context_id"] for c in a] == ["a", "b"]
    assert all(c["indice"] is None for c in (*a, *b)) and b[0]["top3"] == _entrada_b("a")["top3"]
    with pytest.raises(ValueError, match="solo para A y B"):
        ex.casos_gold(["a"], f, papers, "B_barajada", {"a": _entrada_b("a")})
    etiquetado = [{**a[0], "indice": 3}]
    with pytest.raises(ValueError, match="sin etiqueta"):  # falla antes de cargar el modelo
        ex.predecir_gold("no_importa", "scibert", etiquetado, "A")


def test_predicciones_ciegas_solo_llevan_id_pred_y_probs(tmp_path):
    filas = [{"context_id": "a", "pred": 2, "probs": [0.1] * 9}]
    sha = ex.escribir_predicciones_ciegas(tmp_path / "gold" / "pred.jsonl", filas)
    assert sha == sd.sha_archivo(tmp_path / "gold" / "pred.jsonl") and len(sha) == 64
    for malo in ({**filas[0], "etiqueta": "Gap"}, {**filas[0], "indice": 1}, {"context_id": "a", "pred": 1}):
        with pytest.raises(ValueError, match="no permitidos"):
            ex.escribir_predicciones_ciegas(tmp_path / "x.jsonl", [malo])


def test_bootstrap_cluster_es_reproducible_y_detecta_diferencia_pareada_por_grupo():
    grupos = [f"G{i // 3}" for i in range(90)]  # 30 articulos citantes con 3 citas cada uno
    verdad = [i % 3 for i in range(90)]
    a = [[(v + 1) % 3 if i % 2 else v for i, v in enumerate(verdad)] for _ in range(3)]  # A falla la mitad
    b = [list(verdad) for _ in range(3)]
    r = ex.bootstrap_diferencia_cluster(a, b, verdad, grupos, n=100, semilla=1)
    assert r["diferencia"] > 0 and r["ic95"][0] > 0 and r["prob_b_mayor"] == 1.0
    assert r["grupos"] == 30 and r["semillas"] == 3 and r["mismo_signo_semillas"] is True
    assert all(d > 0 for d in r["diferencia_por_semilla"])
    assert r == ex.bootstrap_diferencia_cluster(a, b, verdad, grupos, n=100, semilla=1)
    nulo = ex.bootstrap_diferencia_cluster(b, b, verdad, grupos, n=50, semilla=1)
    assert nulo["diferencia"] == 0 and nulo["ic95"] == (0.0, 0.0) and nulo["mismo_signo_semillas"] is False


def test_bootstrap_cluster_remuestrea_grupos_enteros():
    """Con un solo grupo todas las remuestras son ese grupo: el IC colapsa a la diferencia observada,
    cosa que un bootstrap por caso nunca produciria."""
    verdad = [0, 1, 2, 0, 1, 2]
    a = [[0, 1, 2, 1, 2, 0]]
    b = [[0, 1, 2, 0, 1, 2]]
    r = ex.bootstrap_diferencia_cluster(a, b, verdad, ["G"] * 6, n=30, semilla=3)
    assert r["ic95"] == (r["diferencia"], r["diferencia"])
    assert r["diferencia"] == ex.bootstrap_diferencia(b[0], a[0], verdad, n=5)["diferencia"]


def test_bootstrap_cluster_valida_los_largos():
    with pytest.raises(ValueError):
        ex.bootstrap_diferencia_cluster([[0]], [[0], [0]], [0], ["G"])  # semillas distintas
    with pytest.raises(ValueError):
        ex.bootstrap_diferencia_cluster([[0]], [[0]], [0], ["G", "H"])  # grupos desalineados
    with pytest.raises(ValueError):
        ex.bootstrap_diferencia_cluster([[0, 1]], [[0]], [0], ["G"])  # prediccion desalineada
    with pytest.raises(ValueError):
        ex.bootstrap_diferencia_cluster([], [], [], [])
