"""BERT diminuto local y entradas sinteticas (importa torch: solo para tests con importorskip)."""
import torch
import transformers

PALABRAS = ["alpha", "beta", "gamma", "delta", "targetcit", "method", "results", "introduction",
            "otra", "vacia", "ctx", "uno", "dos", "tres"]


def crear_bert(carpeta, palabras=PALABRAS, semilla=0):
    carpeta.mkdir(parents=True, exist_ok=True)
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", *palabras]
    (carpeta / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    tok = transformers.BertTokenizerFast(str(carpeta / "vocab.txt"))
    tok.save_pretrained(carpeta)
    cfg = transformers.BertConfig(vocab_size=len(vocab), hidden_size=16, num_hidden_layers=1,
                                  num_attention_heads=2, intermediate_size=32,
                                  max_position_embeddings=512)
    torch.manual_seed(semilla)
    transformers.BertModel(cfg).save_pretrained(carpeta)
    return carpeta


def entrada(i, indice, n_ctx=6):
    palabra = "alpha" if indice == 0 else "beta"
    return {"context_id": f"c{i:03d}", "citing_id": f"P{i}", "cited_id": f"Q{i}",
            "citation_context": " ".join(["ctx", palabra, "targetcit".upper(), "uno"] * (n_ctx // 6 or 1)),
            "titulo": f"{palabra} titulo", "abstract": " ".join(["gamma", palabra] * 20),
            "top3": [{"chunk_id": f"{i}-{k}", "perfil": p, "seccion": "s",
                      "texto": " ".join([palabra, "delta"] * 30)}
                     for k, p in enumerate(["method", "results", "introduction"])],
            "indice": indice}


def conjunto(n, desde=0):
    return [entrada(desde + i, i % 2) for i in range(n)]
