"""entrenar -> predecir de extremo a extremo con un BERT diminuto (sin descargas)."""
import hashlib
import json

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("safetensors")

from clasificacion_funcion import cli, cli_modelo, dominio, exportar, servicio  # noqa: E402

from bert_diminuto import conjunto, crear_bert  # noqa: E402


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_git", lambda: {"head": "abc", "dirty": False})
    bert = crear_bert(tmp_path / "bert")
    datos = {"train": conjunto(20), "val": conjunto(8, 100), "eval_2015": conjunto(10, 200),
             "gold_v2": [{k: v for k, v in e.items() if k != "indice"} for e in conjunto(6, 300)]}
    carpeta = tmp_path / "entradas"
    carpeta.mkdir()
    for n, v in datos.items():
        (carpeta / f"entradas_{n}.jsonl").write_text(exportar.jsonl_texto(v), encoding="utf-8")
    gold = exportar.jsonl_texto(exportar.filas_gold(datos["eval_2015"]))
    hashes = {n: {"ids_sha256": dominio.sha_ids(e["context_id"] for e in v),
                  **({"labels_sha256": dominio.sha_etiquetas({e["context_id"]: e["indice"] for e in v})}
                     if n != "gold_v2" else {})} for n, v in datos.items()}
    manifiesto = {
        "hashes": hashes, "train_ids_sha256": hashes["train"]["ids_sha256"],
        "train_labels_sha256": hashes["train"]["labels_sha256"],
        "gold_eval_2015_haiku_sha256": hashlib.sha256(gold.encode()).hexdigest(),
        "texto_sha256": {t: {n: servicio.huella_entradas(v, t) for n, v in datos.items()}
                         for t in ("A", "B", "B_sin_seccion")}}
    (tmp_path / "manifiesto_entradas.json").write_text(json.dumps(manifiesto), encoding="utf-8")
    return tmp_path


def comunes(tmp):
    return ["--entradas", str(tmp / "entradas"), "--manifiesto-entradas", str(tmp / "manifiesto_entradas.json"),
            "--encoder-ruta", str(tmp / "bert"), "--device", "cpu"]


def entrenar(tmp, entrada="B", semilla=42, *extra):
    return cli_modelo.main(["entrenar", "--encoder", "scibert", "--entrada", entrada, "--semilla",
                            str(semilla), "--epocas", "2", "--corridas", str(tmp / "corridas"),
                            *comunes(tmp), *extra])


def predecir(tmp, *extra, run="scibert_B_42"):
    return cli_modelo.main(["predecir", "--corrida", str(tmp / "corridas" / run),
                            "--salida", str(tmp / "ev" / run), *comunes(tmp), *extra])


def test_entrenar_y_predecir(entorno):
    assert entrenar(entorno) == 0
    run = entorno / "corridas/scibert_B_42"
    assert sorted(p.name for p in run.iterdir()) == [
        "manifiesto_entrenamiento.json", "metricas_val.json", "model.safetensors"]
    m = json.loads((run / "manifiesto_entrenamiento.json").read_text())
    assert m["training_labels"] == "Haiku" and m["data_use"] == "provisional_only"
    assert m["encoder"] == "scibert" and m["entrada"] == "B" and m["tokenizer"]["vocab_sha256"]
    assert m["entradas"]["train_ids_sha256"] and m["git"]["head"] == "abc"
    assert m["input_spec_sha256"] == dominio.sha_especificacion(dominio.especificacion_entrada("B", 512))
    assert predecir(entorno) == 0
    ev = entorno / "ev/scibert_B_42"
    assert sorted(p.name for p in ev.iterdir()) == [
        "manifiesto.json", "metricas_eval.json", "metricas_val.json",
        "predicciones_eval.jsonl", "predicciones_gold_v2.jsonl"]
    filas = [json.loads(l) for l in (ev / "predicciones_eval.jsonl").read_text().splitlines()]
    assert len(filas) == 10 and {f["status"] for f in filas} == {"ok"}
    assert not {"gold", "indice", "etiqueta", "label"} & set(filas[0])
    assert len((ev / "predicciones_gold_v2.jsonl").read_text().splitlines()) == 6
    assert filas[0]["experiment_id"] == "scibert_B_42" and filas[0]["gold_manifest_sha256"]
    me = json.loads((ev / "metricas_eval.json").read_text())
    assert me["estado"] == "provisional_etiquetas_haiku_no_gold_humano" and me["n"] == 10
    assert json.loads((ev / "manifiesto.json").read_text())["casos"]["gold_v2"] == 6


def test_predicciones_pasan_el_benchmark(entorno):
    paired = pytest.importorskip("src.evaluation.commercial.paired_benchmark")
    entrenar(entorno)
    predecir(entorno)
    ev = entorno / "ev/scibert_B_42"
    filas = [json.loads(l) for l in (ev / "predicciones_eval.jsonl").read_text().splitlines()]
    assert len(paired.index_predictions(filas, {f"c{i:03d}" for i in range(200, 210)}, "B")) == 10


def test_no_sobrescribe(entorno, capsys):
    assert entrenar(entorno) == 0
    assert entrenar(entorno) == 2 and "No se sobrescribe" in capsys.readouterr().err
    assert predecir(entorno) == 0
    assert predecir(entorno) == 2 and "No se sobrescribe" in capsys.readouterr().err


def test_sondeo_con_secciones_barajadas_no_pisa_la_evaluacion(entorno):
    entrenar(entorno)
    predecir(entorno)
    assert predecir(entorno, "--entrada-eval", "B_barajada") == 0
    ev = entorno / "ev/scibert_B_42"
    assert (ev / "predicciones_eval_B_barajada.jsonl").is_file()
    m = json.loads((ev / "manifiesto_B_barajada.json").read_text())
    assert m["entrada"] == "B" and m["entrada_eval"] == "B_barajada" and m["sha256_permutacion_eval"]
    f = json.loads((ev / "predicciones_eval_B_barajada.jsonl").read_text().splitlines()[0])
    assert f["experiment_id"] == "scibert_B_42_B_barajada"


def test_entrenar_b_barajada_registra_la_permutacion(entorno):
    assert entrenar(entorno, "B_barajada", 7) == 0
    m = json.loads((entorno / "corridas/scibert_B_barajada_7/manifiesto_entrenamiento.json").read_text())
    assert m["sha256_permutacion"]["train"] and m["sha256_permutacion"]["val"]
    assert m["input_spec_sha256"] == dominio.sha_especificacion(
        dominio.especificacion_entrada("B_barajada", 512, 7))


def test_entradas_alteradas_se_rechazan(entorno, capsys):
    ruta = entorno / "entradas/entradas_train.jsonl"
    filas = [json.loads(l) for l in ruta.read_text().splitlines()]
    filas[0]["top3"][0]["texto"] = "texto distinto"
    ruta.write_text(exportar.jsonl_texto(filas), encoding="utf-8")
    assert entrenar(entorno) == 2 and "no coincide" in capsys.readouterr().err


def test_dry_run_con_limite_omite_la_verificacion(entorno):
    assert entrenar(entorno, "A", 1, "--limite", "8") == 0
    m = json.loads((entorno / "corridas/scibert_A_1/manifiesto_entrenamiento.json").read_text())
    assert m["casos"] == {"train": 8, "val": 2} and m["limite"] == 8


def test_checkpoint_alterado_se_rechaza(entorno, capsys):
    entrenar(entorno)
    ckpt = entorno / "corridas/scibert_B_42/model.safetensors"
    ckpt.write_bytes(ckpt.read_bytes() + b"x")
    assert predecir(entorno) == 2 and "checkpoint_sha256" in capsys.readouterr().err


def test_falta_de_entradas_o_manifiesto(entorno, capsys):
    (entorno / "manifiesto_entradas.json").unlink()
    assert entrenar(entorno) == 2 and "cli entradas" in capsys.readouterr().err
