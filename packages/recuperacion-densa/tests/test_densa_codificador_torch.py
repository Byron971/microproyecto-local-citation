import json

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from recuperacion_densa import codificador_torch as ct  # noqa: E402


def test_bert_diminuto_local(tmp_path):
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", *"abcdefgh"]
    (tmp_path / "vocab.txt").write_text("\n".join(vocab))
    tok = transformers.BertTokenizerFast(str(tmp_path / "vocab.txt"))
    cfg = transformers.BertConfig(vocab_size=len(vocab), hidden_size=16, num_hidden_layers=1,
                                  num_attention_heads=2, intermediate_size=32,
                                  max_position_embeddings=64)
    torch.manual_seed(0)
    modelo = transformers.BertModel(cfg)
    rev = "b" * 40
    modelo.config._commit_hash = rev
    enc = object.__new__(ct.TorchSciBERTEncoder)
    enc.torch, enc.tokenizer, enc.model, enc.device = torch, tok, modelo.eval(), "cpu"
    enc.batch_size, enc.max_length, enc.revision, enc.model_id = 2, 16, rev, "tiny"
    enc.capacidad = 16 - tok.num_special_tokens_to_add(pair=False)
    enc.ventanas_procesadas = enc.textos_procesados = 0
    largo = " ".join("abcdefgh" * 3)  # 24 tokens -> 2 ventanas (14 + 10)
    v = enc.encode([largo, "a b"])
    assert enc.ventanas_procesadas == 3 and len(v) == 2 and len(v[0]) == 16
    assert enc.encode([largo])[0] == pytest.approx(v[0], abs=1e-5)  # independiente del lote


def test_verificar_snapshot_contra_manifiesto(tmp_path):
    from recuperacion_densa.descarga_modelo import hash_manifiesto, manifiesto_de

    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "config.json").write_text("{}")
    enc = object.__new__(ct.TorchSciBERTEncoder)
    enc.model_id, enc.revision = "tiny", "b" * 40
    m = manifiesto_de(snap, "tiny", "b" * 40)
    m["sha256_manifiesto"] = hash_manifiesto(dict(m))
    man = tmp_path / "manifiesto_modelo.json"
    man.write_text(json.dumps(m))
    enc._verificar_snapshot(snap, man)  # coincide
    (snap / "config.json").write_text('{"x": 1}')
    with pytest.raises(RuntimeError, match="no coincide"):
        enc._verificar_snapshot(snap, man)
