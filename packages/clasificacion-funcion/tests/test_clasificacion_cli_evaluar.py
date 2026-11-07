import json
import shutil

import pytest

from clasificacion_funcion import cli, comparacion, dominio, exportar

SEMILLAS = (42, 1234)
IDS = [f"g{i:02d}" for i in range(12)]


def gold_jsonl(extra=()):
    filas = [{"id": i, "citing_id": f"P{n}", "cited_id": f"Q{n}", "input": "a TARGETCIT b",
              "gold": dominio.CATEGORIAS[n % 3]} for n, i in enumerate(IDS)] + list(extra)
    return exportar.jsonl_texto(filas)


def predicciones(ids, aciertos, ruido=1):
    filas = []
    for n, i in enumerate(ids):
        verdad = n % 3
        p = verdad if n < aciertos else (verdad + ruido) % 3
        filas.append(exportar.fila_prediccion(
            i, [0.9 if k == p else 0.1 / 8 for k in range(9)], model_id="m", model_version="v",
            experiment_id="e", latency_ms=1.0, gold_manifest_sha256=None))
    return filas


@pytest.fixture
def ev(tmp_path):
    carpeta = tmp_path / "ev"
    carpeta.mkdir()
    (carpeta / "gold_eval_2015_haiku.jsonl").write_text(gold_jsonl(), encoding="utf-8")
    aciertos = {("scibert", "A"): 8, ("scibert", "B"): 10, ("specter", "A"): 5, ("specter", "B"): 4}
    for (enc, ent), n_ok in aciertos.items():
        for sem in SEMILLAS:
            d = carpeta / f"{enc}_{ent}_{sem}"
            d.mkdir()
            filas = predicciones(IDS, n_ok)
            (d / "predicciones_eval.jsonl").write_text(exportar.jsonl_texto(filas), encoding="utf-8")
            gold, _ = comparacion.indexar_gold(comparacion.leer_jsonl(gold_jsonl()))
            m = comparacion.puntuar(gold, comparacion.indexar_predicciones(filas))
            (d / "metricas_eval.json").write_text(json.dumps({"f1_macro": m["f1_macro"]}), encoding="utf-8")
            (d / "manifiesto.json").write_text(json.dumps({
                "encoder": enc, "entrada": ent, "semilla": sem, "training_labels": "Haiku",
                "data_use": "provisional_only", "checkpoint_sha256": f"{sem:04d}" * 16,
                "input_spec_sha256": ("1" if ent == "A" else "2") * 64,
                "entradas": {"train_ids_sha256": "a" * 64, "train_labels_sha256": "b" * 64}}),
                encoding="utf-8")
            if ent == "B" and enc == "scibert":
                (d / "predicciones_eval_B_barajada.jsonl").write_text(
                    exportar.jsonl_texto(predicciones(IDS, 6)), encoding="utf-8")
            (d / "predicciones_gold_v2.jsonl").write_text(
                exportar.jsonl_texto(predicciones(IDS[:8] + ["extra1"], n_ok // 2 + 1)), encoding="utf-8")
    return carpeta


def correr(ev, *extra):
    return cli.main(["evaluar", "--evidencias", str(ev), *extra])


def test_escribe_config_por_semilla_y_comparacion(ev):
    assert correr(ev) == 0
    assert sorted(p.name for p in ev.glob("a4_config_*.json")) == [
        "a4_config_semilla1234.json", "a4_config_semilla42.json"]
    comp = json.loads((ev / "comparacion.json").read_text())
    assert comp["celdas"]["scibert|B"]["agregado"]["accuracy"]["media"] == pytest.approx(10 / 12)
    assert comp["procedencia"]["gold_n"] == 12 and len(comp["procedencia"]["corridas"]) == 8
    por = {d["nombre"]: d for d in comp["deltas"]}
    assert por["scibert|A->B"]["agregado"]["accuracy"]["media"] == pytest.approx(2 / 12)
    assert por["SciBERT->SPECTER|A"]["agregado"]["accuracy"]["media"] < 0
    assert "scibert|B->B_con_eval_barajado" in por  # sondeo
    assert (ev / "comparacion.csv").read_text().splitlines()[0].startswith("tipo,nombre,semillas,n,")
    cfg = json.loads((ev / "a4_config_semilla42.json").read_text())
    assert cfg["schema_version"] == "a4_factorial_v1" and len(cfg["variants"]) == 4
    assert cfg["variants"][0]["checkpoint_sha256"] == "0042" * 16


def test_solo_validar_no_escribe(ev, capsys):
    assert correr(ev, "--solo-validar") == 0
    assert not (ev / "comparacion.json").exists() and not list(ev.glob("a4_config_*"))
    assert '"gold_n": 12' in capsys.readouterr().out


def test_no_sobrescribe(ev, capsys):
    assert correr(ev) == 0
    assert correr(ev) == 2 and "No se sobrescribe" in capsys.readouterr().err


def test_ids_no_comparables_bloquean(ev, capsys):
    ruta = ev / "scibert_A_42/predicciones_eval.jsonl"
    filas = [json.loads(l) for l in ruta.read_text().splitlines()][:-1]
    ruta.write_text(exportar.jsonl_texto(filas), encoding="utf-8")
    assert correr(ev) == 2 and "no comparables" in capsys.readouterr().err
    assert not (ev / "comparacion.json").exists()


def test_metricas_guardadas_inconsistentes_bloquean(ev, capsys):
    (ev / "specter_B_42/metricas_eval.json").write_text('{"f1_macro": 0.99}', encoding="utf-8")
    assert correr(ev) == 2 and "no coincide" in capsys.readouterr().err


def test_semilla_con_matriz_incompleta_no_genera_config(ev, capsys):
    shutil.rmtree(ev / "specter_B_1234")
    assert correr(ev) == 0
    assert "semilla 1234 sin config" in capsys.readouterr().out
    assert [p.name for p in ev.glob("a4_config_*.json")] == ["a4_config_semilla42.json"]


def test_gold_v2_privado_puntua_predicciones_ciegas(ev, tmp_path):
    privado = tmp_path / "gold_v2_privado.jsonl"
    privado.write_text(gold_jsonl([{"id": "g_sin_pred", "gold": "Gap"},
                                   {"id": "extra1", "gold": "Ambiguo"}]), encoding="utf-8")
    assert correr(ev, "--gold-v2", str(privado)) == 0
    comp = json.loads((ev / "comparacion_gold_v2.json").read_text())
    assert comp["estado"].startswith("gold_v2_dado_por_el_usuario")
    assert comp["procedencia"]["gold"] == "<ruta privada>" and comp["procedencia"]["gold_abstenciones"] == {"Ambiguo": 1}
    m = json.loads((ev / "scibert_B_42/metricas_gold_v2.json").read_text())
    assert m["n"] == 8 and m["ids_predichos"] == 9 and m["ids_sin_gold_evaluable"] == 1  # extra1 es Ambiguo
    assert not (ev / "comparacion.json").exists() and not list(ev.glob("a4_config_*"))


def test_sin_corridas_o_sin_gold(tmp_path, capsys):
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    assert correr(vacio) == 2 and "No hay corridas" in capsys.readouterr().err
