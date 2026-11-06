"""Codificador SciBERT (port de S2.8). Importa torch: solo lo carga `cli_modelo`.

Ventanas contiguas `[CLS]+w+[SEP]` sin truncar, padding manual, mean pooling con mascara y
combinacion de ventanas en float64 (media ponderada por tokens de contenido)."""
from __future__ import annotations

import platform

import torch
import transformers
from transformers import AutoModel, AutoTokenizer

from . import dominio
from .revision import MODEL_ID, validar_revision


class TorchSciBERTEncoder:
    pooling = "mean"

    def __init__(self, revision: str, model_id: str = MODEL_ID, device: str = "auto",
                 batch_size: int = 16, max_length: int = 512, local_files_only: bool = True):
        if batch_size < 1 or not 16 <= max_length <= 512:
            raise ValueError("batch_size>=1 y 16<=max_length<=512.")
        self.revision = validar_revision(revision)
        self.torch = torch
        torch.manual_seed(0)
        self.model_id, self.batch_size, self.max_length = model_id, batch_size, max_length
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA solicitado pero no esta disponible.")
        self.device = device
        kw = dict(revision=self.revision, trust_remote_code=False,
                  local_files_only=local_files_only)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, **kw)
        self.model = AutoModel.from_pretrained(model_id, **kw).to(device).eval()
        self.commit_resuelto = getattr(self.model.config, "_commit_hash", None)
        if self.commit_resuelto != self.revision:
            raise RuntimeError(f"El commit resuelto ({self.commit_resuelto}) no coincide con la "
                               f"revision fijada ({self.revision}).")
        if max_length > getattr(self.model.config, "max_position_embeddings", 512):
            raise ValueError("max_length supera los embeddings posicionales del modelo.")
        self.capacidad = max_length - self.tokenizer.num_special_tokens_to_add(pair=False)
        self.ventanas_procesadas = self.textos_procesados = 0

    def encode(self, textos: list[str]) -> list[tuple[float, ...]]:
        if not textos:
            return []
        if not all(isinstance(t, str) and t.strip() for t in textos):
            raise ValueError("SciBERT recibio un texto vacio.")
        torch, tok = self.torch, self.tokenizer
        ids = [tok.encode(t, add_special_tokens=False, truncation=False) for t in textos]
        seqs, idx, pesos = dominio.construir_lotes(ids, self.capacidad, tok.cls_token_id, tok.sep_token_id)
        vecs: list[list] = [[] for _ in textos]
        pes: list[list[int]] = [[] for _ in textos]
        with torch.inference_mode():
            for ini in range(0, len(seqs), self.batch_size):
                lote = seqs[ini:ini + self.batch_size]
                largo = max(len(s) for s in lote)
                x = torch.full((len(lote), largo), tok.pad_token_id, dtype=torch.long)
                m = torch.zeros((len(lote), largo), dtype=torch.long)
                for r, s in enumerate(lote):
                    x[r, :len(s)] = torch.tensor(s)
                    m[r, :len(s)] = 1
                x, m = x.to(self.device), m.to(self.device)
                oculto = self.model(input_ids=x, attention_mask=m).last_hidden_state
                mm = m.unsqueeze(-1)
                medios = ((oculto * mm).sum(dim=1) / mm.sum(dim=1).clamp(min=1))
                for off, v in enumerate(medios.detach().cpu().to(torch.float64).tolist()):
                    vecs[idx[ini + off]].append(v)
                    pes[idx[ini + off]].append(pesos[ini + off])
        self.textos_procesados += len(textos)
        self.ventanas_procesadas += len(seqs)
        return [dominio.media_ponderada(v, p) for v, p in zip(vecs, pes)]

    def info(self) -> dict:
        t = self.torch
        gpu = t.cuda.get_device_name(0) if self.device == "cuda" else None
        return {"model_id": self.model_id, "revision": self.revision,
                "commit_resuelto": self.commit_resuelto, "device": self.device, "gpu": gpu,
                "torch": t.__version__, "cuda": t.version.cuda,
                "transformers": transformers.__version__, "python": platform.python_version(),
                "batch_size": self.batch_size, "max_length": self.max_length,
                "pooling": self.pooling, "ventanas_procesadas": self.ventanas_procesadas,
                "textos_procesados": self.textos_procesados}

    def memoria_gpu_mb(self) -> float | None:
        if self.device != "cuda":
            return None
        return self.torch.cuda.max_memory_allocated() / 2**20
