import csv
import json

import pytest

from recuperacion_densa import comparar_corridas as cc


def corrida(carpeta, filas, device="cpu", en_cache=0):
    carpeta.mkdir(parents=True)
    with (carpeta / "top3.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["context_id", "metodo", "posicion", "chunk_id", "puntaje"])
        w.writeheader()
        for ctx, tops in filas.items():
            for pos, (ch, p) in enumerate(tops, 1):
                w.writerow({"context_id": ctx, "metodo": "scibert", "posicion": pos,
                            "chunk_id": ch, "puntaje": p})
                w.writerow({"context_id": ctx, "metodo": "bm25", "posicion": pos,
                            "chunk_id": "z", "puntaje": 1})
    (carpeta / "resumen.json").write_text(json.dumps({"n": len(filas)}))
    r = {"n": 1, "p50": 0.1, "p95": 0.2}
    (carpeta / "latencias_resumen.json").write_text(json.dumps({
        "embedding_articulo": {**r, "chunks_en_cache": en_cache}, "consulta_densa": r, "bm25": r,
        "carga_modelo_s": 1.0, "memoria_gpu_max_mb": None, "codificador": {"device": device}}))


TOPS = {"x1": [("a", 0.9), ("b", 0.8), ("c", 0.7)], "x2": [("b", 0.9), ("a", 0.5), ("c", 0.4)]}


def test_corridas_equivalentes(tmp_path):
    corrida(tmp_path / "a", TOPS)
    corrida(tmp_path / "b", {**TOPS, "x1": [("a", 0.9000005), ("b", 0.8), ("c", 0.7)]},
            device="cuda", en_cache=7)
    r = cc.comparar(tmp_path / "a", tmp_path / "b")
    assert r["contextos"] == r["mismo_top1"] == r["mismo_conjunto_top3"] == r["mismo_orden_top3"] == 2
    assert r["max_dif_coseno_abs"] == pytest.approx(5e-7)
    assert r["top3_csv_identico"] is False
    assert r["latencias_s"]["b"]["chunks_en_cache"] == 7
    assert r["latencias_s"]["a"]["device"] == "cpu"


def test_corridas_distintas_y_subconjunto(tmp_path):
    corrida(tmp_path / "a", TOPS)
    corrida(tmp_path / "b", {"x1": [("b", 0.9), ("a", 0.8), ("c", 0.7)]})
    r = cc.comparar(tmp_path / "a", tmp_path / "b")
    assert r["contextos"] == 1 and r["mismo_top1"] == 0
    assert r["mismo_conjunto_top3"] == 1 and r["mismo_orden_top3"] == 0


def test_sin_contextos_comunes_y_cli(tmp_path, capsys):
    corrida(tmp_path / "a", {"x1": TOPS["x1"]})
    corrida(tmp_path / "b", {"x2": TOPS["x2"]})
    assert cc.main([str(tmp_path / "a"), str(tmp_path / "b")]) == 2
    corrida(tmp_path / "c", TOPS)
    out = tmp_path / "cmp.json"
    assert cc.main([str(tmp_path / "a"), str(tmp_path / "c"), "--salida", str(out)]) == 0
    assert json.loads(out.read_text())["contextos"] == 1
