"""Clasificador [CLS] con un BERT diminuto local: sin descargas, en CPU."""
import hashlib
import json

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
pytest.importorskip("safetensors")

from clasificacion_funcion import clasificador_torch as ct  # noqa: E402
from clasificacion_funcion import dominio, exportar  # noqa: E402

from bert_diminuto import PALABRAS, conjunto, crear_bert  # noqa: E402

@pytest.fixture
def base(tmp_path):
    ruta = crear_bert(tmp_path / "bert")
    return ruta, ct.TokenizadorHF(ruta)


def ejemplos(tok, entradas, tipo="B", max_len=128):
    return ct.preparar_ejemplos(entradas, tipo, tok, max_len)


def entrenar(base, tmp_path, nombre="run", semilla=1, hp=None, tipo="B"):
    ruta, tok = base
    hp = hp or ct.Hiperparametros(max_len=128, epocas=2, batch_size=4, acumulacion=2)
    ct.fijar_determinismo(semilla)
    modelo = ct.ClasificadorCLS(ruta, semilla)
    salida = tmp_path / nombre
    res = ct.entrenar(modelo, ejemplos(tok, conjunto(20), tipo), ejemplos(tok, conjunto(8, 100), tipo),
                      tok.pad_id, semilla, hp, salida, torch.device("cpu"))
    return modelo, res, salida


def test_hiperparametros_fijados_en_el_plan():
    hp = ct.Hiperparametros()
    assert (hp.max_len, hp.lr, hp.weight_decay, hp.warmup) == (512, 2e-5, 0.01, 0.1)
    assert (hp.batch_size, hp.acumulacion, hp.epocas, hp.paciencia) == (8, 2, 6, 2)
    assert (hp.clip, hp.dropout, hp.pesos_clase) == (1.0, 0.1, True)


def test_nueve_logits(base):
    ruta, tok = base
    modelo = ct.ClasificadorCLS(ruta, 0).eval()
    ej = ejemplos(tok, conjunto(3))
    ids = torch.tensor([e["input_ids"][:20] for e in ej])
    assert modelo(ids, torch.ones_like(ids)).shape == (3, 9)
    assert modelo.cabeza.out_features == 9


def test_misma_semilla_mismos_pesos_de_la_cabeza(base):
    ruta, _ = base
    a, b, c = (ct.ClasificadorCLS(ruta, s) for s in (7, 7, 8))
    assert torch.equal(a.cabeza.weight, b.cabeza.weight)
    assert not torch.equal(a.cabeza.weight, c.cabeza.weight)
    assert torch.equal(a.encoder.embeddings.word_embeddings.weight,
                       c.encoder.embeddings.word_embeddings.weight)  # el encoder es el mismo


def test_entrenamiento_guarda_mejor_checkpoint_y_manifiesto(base, tmp_path):
    modelo, res, salida = entrenar(base, tmp_path)
    ckpt = salida / "model.safetensors"
    assert ckpt.is_file() and res["checkpoint_sha256"] == hashlib.sha256(ckpt.read_bytes()).hexdigest()
    assert res["epocas_ejecutadas"] == len(res["historial"]) == 2 and not res["parada_temprana"]
    assert 1 <= res["mejor_epoca"] <= 2 and res["casos"] == {"train": 20, "val": 8}
    assert res["metricas_val"]["f1_macro"] == max(h["f1_macro_val"] for h in res["historial"])
    assert res["hiperparametros"]["lr"] == 2e-5 and "gpu" in res["hardware"]
    assert res["pesos_clase"][0] == pytest.approx(20 / (9 * 10))
    json.dumps(res)  # serializable


def test_checkpoint_reproduce_las_predicciones_del_mejor_modelo(base, tmp_path):
    ruta, tok = base
    modelo, res, salida = entrenar(base, tmp_path)
    val = ejemplos(tok, conjunto(8, 100))
    nuevo = ct.ClasificadorCLS(ruta, 1)
    ct.cargar_checkpoint(nuevo, salida / "model.safetensors", res["checkpoint_sha256"])
    p, _ = ct.predecir_probabilidades(nuevo, val, tok.pad_id, torch.device("cpu"), 4)
    pred = [max(range(9), key=lambda i: (x[i], -i)) for x in p]
    m = dominio.metricas([e["indice"] for e in val], pred)
    assert m["f1_macro"] == pytest.approx(res["metricas_val"]["f1_macro"])
    with pytest.raises(RuntimeError, match="checkpoint_sha256"):
        ct.cargar_checkpoint(nuevo, salida / "model.safetensors", "0" * 64)


def test_parada_temprana_por_paciencia(base, tmp_path):
    hp = ct.Hiperparametros(max_len=128, epocas=6, paciencia=1, lr=0.0, batch_size=4)
    _, res, _ = entrenar(base, tmp_path, hp=hp)
    # con lr=0 el F1 de val no mejora: 1 epoca mejor + 1 sin mejora = parada
    assert res["epocas_ejecutadas"] == 2 and res["mejor_epoca"] == 1 and res["parada_temprana"]


def test_misma_semilla_misma_corrida_y_otra_semilla_distinta(base, tmp_path):
    _, a, _ = entrenar(base, tmp_path, "a", semilla=5)
    _, b, _ = entrenar(base, tmp_path, "b", semilla=5)
    _, c, _ = entrenar(base, tmp_path, "c", semilla=6)
    assert a["checkpoint_sha256"] == b["checkpoint_sha256"]
    assert a["historial"][0]["loss_train"] == b["historial"][0]["loss_train"]
    assert a["checkpoint_sha256"] != c["checkpoint_sha256"]


def test_sin_pesos_y_validaciones(base, tmp_path):
    hp = ct.Hiperparametros(max_len=128, epocas=1, pesos_clase=False)
    _, res, _ = entrenar(base, tmp_path, hp=hp)
    assert res["pesos_clase"] is None
    ruta, tok = base
    ct.fijar_determinismo(0)
    modelo = ct.ClasificadorCLS(ruta, 0)
    ej = ejemplos(tok, conjunto(4))
    with pytest.raises(ValueError):
        ct.entrenar(modelo, [], ej, tok.pad_id, 0, hp, tmp_path / "x", torch.device("cpu"))
    sin_y = [{**e, "indice": None} for e in ej]
    with pytest.raises(ValueError, match="etiquetas"):
        ct.entrenar(modelo, sin_y, ej, tok.pad_id, 0, hp, tmp_path / "y", torch.device("cpu"))


def test_entradas_a_b_y_truncamiento(base):
    _, tok = base
    largo = conjunto(4)
    for e in largo:
        e["top3"][0]["texto"] = " ".join(["alpha"] * 400)
    for tipo in ("A", "B", "B_sin_seccion"):
        ej = ejemplos(tok, largo, tipo, max_len=64)
        assert all(len(e["input_ids"]) <= 64 and e["input_ids"][0] == tok.cls_id for e in ej)
    r = ct.resumen_truncamiento(ejemplos(tok, largo, "B", max_len=64))
    assert r["segmentos"]["chunk_1"]["frac_truncado"] == 1.0 and r["casos"] == 4
    assert ct.resumen_truncamiento([]) == {}


def test_b_barajada_requiere_perfiles_barajados(base):
    _, tok = base
    c = conjunto(6)
    with pytest.raises(ValueError, match="B_barajada"):
        ejemplos(tok, c, "B_barajada")
    barajados, _ = dominio.barajar_secciones(c, 3)
    assert len(ejemplos(tok, barajados, "B_barajada")) == 6


def test_huella_del_tokenizer_distingue_vocabularios(tmp_path):
    a = ct.TokenizadorHF(crear_bert(tmp_path / "a"))
    b = ct.TokenizadorHF(crear_bert(tmp_path / "b", palabras=PALABRAS[::-1]))
    assert a.info()["vocab_sha256"] != b.info()["vocab_sha256"]
    assert a.info() == ct.TokenizadorHF(tmp_path / "a").info() and a.info()["vocab_size"] == 19


def test_probabilidades_y_filas_de_prediccion(base, tmp_path):
    ruta, tok = base
    modelo, _, _ = entrenar(base, tmp_path)
    ej = ejemplos(tok, conjunto(5, 200))
    p, lat = ct.predecir_probabilidades(modelo, ej, tok.pad_id, torch.device("cpu"), 2)
    assert len(p) == len(lat) == 5 and all(abs(sum(x) - 1) < 1e-5 for x in p)
    filas = ct.filas_prediccion(ej, p, lat, model_id="tiny", model_version="v", experiment_id="e",
                                gold_manifest_sha256="g")
    assert set(filas[0]) == set(exportar.ESQUEMA_PREDICCION) and filas[0]["case_id"] == "c200"
    paired = pytest.importorskip("src.evaluation.commercial.paired_benchmark")
    assert len(paired.index_predictions(filas, {e["context_id"] for e in ej}, "t")) == 5


# ---------------------------------------------------------------- perdida suave, pesos, callback
def _logits_y():
    torch.manual_seed(0)
    return torch.randn(6, 9), torch.tensor([0, 3, 8, 1, 1, 5])


def test_perdida_suave_one_hot_igual_a_la_dura():
    logits, y = _logits_y()
    pesos = torch.tensor(dominio.pesos_clase(y.tolist()), dtype=torch.float32)
    dura = torch.nn.CrossEntropyLoss(weight=pesos)(logits, y)
    suave = ct.calcular_perdida(logits, y, pesos, objetivo=torch.nn.functional.one_hot(y, 9).float())
    assert torch.allclose(dura, suave, atol=1e-6)


def test_perdida_sin_campos_opcionales_igual_a_cross_entropy():
    logits, y = _logits_y()
    assert torch.allclose(ct.calcular_perdida(logits, y), torch.nn.CrossEntropyLoss()(logits, y),
                          atol=1e-6)


def test_pesos_de_muestra_iguales_a_uno_no_cambian_la_perdida():
    logits, y = _logits_y()
    pesos = torch.tensor(dominio.pesos_clase(y.tolist()), dtype=torch.float32)
    base_ = ct.calcular_perdida(logits, y, pesos)
    assert torch.allclose(base_, ct.calcular_perdida(logits, y, pesos, peso=torch.ones(6)), atol=1e-6)
    assert not torch.allclose(base_, ct.calcular_perdida(logits, y, pesos, peso=torch.tensor(
        [1.0, 0.1, 1.0, 1.0, 1.0, 1.0])), atol=1e-6)


def test_entrenar_con_objetivo_peso_y_callback(base, tmp_path):
    ruta, tok = base
    hp = ct.Hiperparametros(max_len=128, epocas=2, batch_size=4, acumulacion=2, paciencia=5)
    train = ejemplos(tok, conjunto(20), "B")
    for e in train:
        e["objetivo"] = [1.0 if i == e["indice"] else 0.0 for i in range(9)]
        e["peso"] = 0.5
    vistas = []
    modelo = ct.ClasificadorCLS(ruta, 1)
    res = ct.entrenar(modelo, train, ejemplos(tok, conjunto(8, 100), "B"), tok.pad_id, 1, hp,
                      tmp_path / "kd", torch.device("cpu"), al_terminar_epoca=vistas.append)
    assert [v["epoca"] for v in vistas] == [1, 2] == [h["epoca"] for h in res["historial"]]
    assert all(v["loss_train"] == v["loss_train"] for v in vistas)  # finita (no NaN)


def test_preparar_ejemplos_conserva_objetivo_y_peso(base):
    _, tok = base
    entradas = conjunto(4)
    entradas[0].update(objetivo=[0.7, 0.3] + [0.0] * 7, peso=0.4)
    res = ejemplos(tok, entradas, "B")
    assert res[0]["objetivo"] == [0.7, 0.3] + [0.0] * 7 and res[0]["peso"] == 0.4
    assert "objetivo" not in res[1] and "peso" not in res[1]  # solo cuando la entrada los trae


def test_perdida_kd_y_ponderada_cambia_el_entrenamiento_pasando_por_preparar_ejemplos(base, tmp_path):
    """Regresion: `preparar_ejemplos` descartaba `objetivo`/`peso` y kd/ponderado == duro."""
    ruta, tok = base
    hp = ct.Hiperparametros(max_len=128, epocas=1, batch_size=4, acumulacion=2)

    def perdida(extra, nombre):
        entradas = conjunto(20)
        for e in entradas:
            e.update(extra(e))
        ct.fijar_determinismo(1)
        res = ct.entrenar(ct.ClasificadorCLS(ruta, 1), ejemplos(tok, entradas, "B"),
                          ejemplos(tok, conjunto(8, 100), "B"), tok.pad_id, 1, hp,
                          tmp_path / nombre, torch.device("cpu"))
        return res["historial"][0]["loss_train"]

    duro = perdida(lambda e: {}, "duro")
    kd = perdida(lambda e: {"objetivo": [0.6 if i == e["indice"] else 0.05 for i in range(9)]}, "kd")
    pond = perdida(lambda e: {"peso": 0.2 if e["indice"] == 0 else 1.0}, "pond")
    assert kd != duro and pond != duro


def test_entrenar_reporta_pico_de_memoria_gpu_solo_en_cuda(base, tmp_path):
    _, res, _ = entrenar(base, tmp_path)
    assert "gpu_mem_pico_gb" in res and res["gpu_mem_pico_gb"] is None  # CPU
