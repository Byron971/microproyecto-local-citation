"""Corpus de demostración: solo TRAIN sin etiquetas y checksum reproducible."""
import json
from pathlib import Path

import pytest

from src.app.corpus_adapter import CorpusError
from src.app.corpus_preflight import auditar_train, main


def fixture_train(tmp_path: Path):
    path = tmp_path / "casos_train.json"
    data = {
        "version": 1,
        "resumen": {"tipo": "muestra_desarrollo_train_no_gold"},
        "casos": [{
            "context_id": "ctx-A",
            "split": "train",
            "citing_id": "P15-1001",
            "cited_id": "P14-1001",
            "cited_title": "Neural models",
            "citation_context": "Graph models TARGETCIT learn.",
            "sha256_ocl_citado": "1" * 64,
            "chunks": [{
                "chunk_id": "p00000-p00000",
                "texto": "Graph models combine embeddings.",
                "seccion": "Methods",
                "paragraph_indices": [0],
                "palabras": 4,
            }],
        }],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_preflight_publica_solo_metadatos_no_textos(tmp_path, capsys):
    file, _ = fixture_train(tmp_path)
    report = auditar_train(file)
    assert report["estado"] == "train_sin_gold_verificado"
    assert report["casos_train"] == 1
    assert report["articulos_citados_unicos"] == 1
    assert report["total_chunks_presentados"] == 1
    assert len(report["sha256_archivo"]) == 64
    assert "Neural" not in json.dumps(report)
    assert main(["--archivo", str(file)]) == 0
    assert json.loads(capsys.readouterr().out) == report


@pytest.mark.parametrize("level", ["raiz", "resumen", "caso", "chunk"])
def test_rechaza_claves_de_gold_sin_persistirlas(tmp_path, level):
    file, payload = fixture_train(tmp_path)
    targets = {
        "raiz": payload,
        "resumen": payload["resumen"],
        "caso": payload["casos"][0],
        "chunk": payload["casos"][0]["chunks"][0],
    }
    targets[level]["gold_label"] = "Evidence"
    file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorpusError, match="anotación"):
        auditar_train(file)


def test_bloquea_split_test_y_tipo_de_dataset_desconocido(tmp_path):
    file, d = fixture_train(tmp_path)
    d["casos"][0]["split"] = "test"
    file.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(CorpusError, match="contrato"):
        auditar_train(file)

    d["casos"][0]["split"] = "train"
    d["resumen"]["tipo"] = "gold_v2"
    file.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(CorpusError, match="procedencia"):
        auditar_train(file)


def test_bloquea_archivo_faltante(tmp_path):
    with pytest.raises(CorpusError, match="No existe"):
        auditar_train(tmp_path / "ausente.json")
