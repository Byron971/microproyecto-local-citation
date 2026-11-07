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
