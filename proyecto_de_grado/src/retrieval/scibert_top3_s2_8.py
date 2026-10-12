"""S2.8: SciBERT Top-3 offline para SOLO casos train de S2.4/S2.6.

Este módulo no genera Gold ni métricas de relevancia. La implementación
SciBERT carga PyTorch/Transformers de modo diferido para permitir pruebas
unitarias en el entorno Python del repositorio sin dependencias de GPU.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Callable

MODEL_ID = "allenai/scibert_scivocab_uncased"


def _huella_chunks(chunks: list[dict]) -> str:
    datos = [(c["chunk_id"], c["texto"], c.get("seccion")) for c in chunks]
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def validar_casos(casos: list[dict]) -> dict:
    """Bloquea fugas: solo train, una cita objetivo y corpus consistente por paper."""
    if not isinstance(casos, list) or not casos:
        raise ValueError("Se necesita una lista no vacía de casos train.")
    ids, articulos = set(), {}
    for caso in casos:
        if not isinstance(caso, dict) or caso.get("split") != "train":
            raise ValueError("Entrada no es exclusivamente train: operación bloqueada.")
        cid = caso.get("id")
        pid = caso.get("cited_id")
        contexto = caso.get("citation_context")
        chunks = caso.get("cited_chunks")
        if not isinstance(cid, str) or not cid or cid in ids:
            raise ValueError("ID de contexto vacío o duplicado.")
        ids.add(cid)
        if not isinstance(pid, str) or not pid:
            raise ValueError(f"cited_id inválido en {cid}")
        if not isinstance(contexto, str) or contexto.count("TARGETCIT") != 1:
            raise ValueError(f"Contexto sin TARGETCIT único en {cid}")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError(f"Artículo sin chunks en {cid}")
        if caso.get("evidencia_top3", {}).get("fragmentos_relevantes_adjudicados") is not None:
            raise ValueError("Se rechazó un caso con relevancias humanas: solo exploración train.")
        vistos = set()
        for c in chunks:
            if not isinstance(c, dict):
                raise ValueError(f"Chunk mal formado en {cid}")
            chunk_id, texto = c.get("chunk_id"), c.get("texto")
            if not isinstance(chunk_id, str) or not chunk_id or chunk_id in vistos:
                raise ValueError(f"chunk_id vacío/duplicado en {cid}")
            vistos.add(chunk_id)
            if not isinstance(texto, str) or not texto.strip():
                raise ValueError(f"Texto de chunk vacío en {cid}")
        version = _huella_chunks(chunks)
        if pid in articulos and articulos[pid] != version:
            raise ValueError(f"Chunks inconsistentes entre casos del mismo artículo: {pid}")
        articulos[pid] = version
    return {"casos": len(casos), "articulos": len(articulos), "chunks_unicos": sum(
        len(next(c["cited_chunks"] for c in casos if c["cited_id"] == pid))
        for pid in articulos
    )}


def _normalizar_contexto(contexto: str) -> str:
    """Marcadores ACL-200 no son términos científicos (misma regla para todos)."""
    return " ".join(contexto.replace("TARGETCIT", " ").replace("OTHERCIT", " ").split())


def _normalizar_vector(vector: list[float] | tuple[float, ...]) -> tuple[float, ...]:
    if not vector or not all(math.isfinite(float(v)) for v in vector):
        raise ValueError("Embedding vacío o no finito.")
    norma = math.sqrt(math.fsum(float(v) ** 2 for v in vector))
    if norma <= 0:
        raise ValueError("Embedding nulo.")
    return tuple(float(v) / norma for v in vector)


def ordenar_top3(query: list[float] | tuple[float, ...], chunks: list[dict],
                 vectores: list[list[float]] | list[tuple[float, ...]]) -> list[dict]:
    if len(chunks) != len(vectores):
        raise ValueError("Número de chunks y embeddings inconsistente.")
    q = _normalizar_vector(query)
    resultados = []
    for c, vec in zip(chunks, vectores):
        v = _normalizar_vector(vec)
        if len(v) != len(q):
            raise ValueError("Dimensiones de embeddings incompatibles.")
        puntaje = math.fsum(x * y for x, y in zip(q, v))
        resultados.append({"chunk_id": c["chunk_id"], "similitud_coseno": round(puntaje, 6)})
    resultados.sort(key=lambda r: (-r["similitud_coseno"], r["chunk_id"]))
    return [{"posicion": pos, **r} for pos, r in enumerate(resultados[:3], 1)]


class TorchSciBERTEncoder:
    """Mean pooling por tokens, ventanas contiguas; ningún token se descarta."""

    def __init__(self, model_id: str = MODEL_ID, revision: str = "main", device: str = "auto",
                 batch_size: int = 4, max_length: int = 512):
        if batch_size < 1 or max_length < 16 or max_length > 512:
            raise ValueError("batch_size>=1 y 16<=max_length<=512.")
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.model_id = model_id
        self.revision = revision
        self.batch_size = batch_size
        self.max_length = max_length
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA solicitado pero no está disponible.")
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(model_id, revision=revision, trust_remote_code=False).to(device).eval()
        self.model_commit = getattr(self.model.config, "_commit_hash", None)
        self.ventanas_procesadas = 0
        self.textos_procesados = 0
        self.model_max_length = getattr(self.model.config, "max_position_embeddings", 512)
        if max_length > self.model_max_length:
            raise ValueError("max_length supera los embeddings posicionales del modelo.")

    def encode(self, textos: list[str]) -> list[tuple[float, ...]]:
        if not textos:
            return []
        if not all(isinstance(t, str) and t.strip() for t in textos):
            raise ValueError("SciBERT recibió un texto vacío.")
        torch = self.torch
        capacidad = self.max_length - self.tokenizer.num_special_tokens_to_add(pair=False)
        if capacidad <= 0:
            raise ValueError("No hay espacio para tokens de contenido.")
        entradas: list[list[int]] = []
        indices: list[int] = []
        pesos: list[int] = []
        for indice, texto in enumerate(textos):
            ids = self.tokenizer.encode(texto, add_special_tokens=False, truncation=False)
            if not ids:
                raise ValueError("Tokenizer produjo secuencia vacía.")
            for comienzo in range(0, len(ids), capacidad):
                ventana = ids[comienzo:comienzo + capacidad]
                entradas.append(self.tokenizer.build_inputs_with_special_tokens(ventana))
                indices.append(indice)
                pesos.append(len(ventana))
        sumas: list[Any] = [None] * len(textos)
        cuenta = [0] * len(textos)
        with torch.inference_mode():
            for inicio in range(0, len(entradas), self.batch_size):
                lote = entradas[inicio:inicio + self.batch_size]
                preparado = self.tokenizer.pad({"input_ids": lote}, padding=True,
                                              return_attention_mask=True, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in preparado.items()}
                salida = self.model(**inputs).last_hidden_state
                mascara = inputs["attention_mask"].unsqueeze(-1)
                medios = (salida * mascara).sum(dim=1) / mascara.sum(dim=1).clamp(min=1)
                for offset, vector in enumerate(medios):
                    j = inicio + offset
                    idx, peso = indices[j], pesos[j]
                    agregado = vector.detach().cpu().to(torch.float64) * peso
                    sumas[idx] = agregado if sumas[idx] is None else sumas[idx] + agregado
                    cuenta[idx] += peso
        self.textos_procesados += len(textos)
        self.ventanas_procesadas += len(entradas)
        return [tuple((sumas[j] / cuenta[j]).tolist()) for j in range(len(textos))]


def ejecutar(casos: list[dict], encoder: Any,
             bm25_fn: Callable[[str, list[dict]], list[dict]] | None = None) -> dict:
    resumen = validar_casos(casos)
    if bm25_fn is None:
        from src.app.fragment_retrieval import recuperar_top3
        bm25_fn = recuperar_top3
    cache_docs: dict[str, tuple[str, list[dict], list]] = {}
    resultados = []
    contador = Counter()
    inicio_total = time.perf_counter()
    for caso in casos:
        pid = caso["cited_id"]
        chunks = caso["cited_chunks"]
        version = _huella_chunks(chunks)
        if pid not in cache_docs:
            cache_docs[pid] = (version, chunks, encoder.encode([c["texto"] for c in chunks]))
        elif cache_docs[pid][0] != version:
            raise ValueError(f"Corpus inconsistente para artículo {pid}")
        t0 = time.perf_counter()
        consulta = _normalizar_contexto(caso["citation_context"])
        if not consulta:
            raise ValueError("Consulta vacía tras retirar los marcadores.")
        vector_consulta = encoder.encode([consulta])[0]
        top_sem = ordenar_top3(vector_consulta, chunks, cache_docs[pid][2])
        t_scibert = time.perf_counter() - t0
        t0 = time.perf_counter()
        top_bm25 = bm25_fn(caso["citation_context"], chunks)
        t_bm25 = time.perf_counter() - t0
        ids_sem = [r["chunk_id"] for r in top_sem]
        ids_bm = [r["chunk_id"] for r in top_bm25]
        inter = len(set(ids_sem) & set(ids_bm))
        contador["coincidencias_top3"] += inter
        contador["mismo_top1"] += int(bool(ids_sem and ids_bm and ids_sem[0] == ids_bm[0]))
        contador["bm25_sin_resultados"] += int(not ids_bm)
        resultados.append({
            "context_id": caso["id"], "split": "train", "cited_id": pid,
            "chunks_disponibles": len(chunks),
            "scibert_top3": top_sem,
            "bm25_top3": [{"posicion": r["posicion"], "chunk_id": r["chunk_id"],
                            "puntaje_bm25": r["puntaje_bm25"]} for r in top_bm25],
            "coincidencia_top3": inter,
            "segundos_consulta_scibert": round(t_scibert, 5),
            "segundos_bm25": round(t_bm25, 5),
        })
    return {
        "tipo": "comparacion_tecnica_train_s2_8_no_gold",
        "modelo": getattr(encoder, "model_id", "encoder_simulado"),
        "modelo_revision_solicitada": getattr(encoder, "revision", None),
        "modelo_commit_resuelto": getattr(encoder, "model_commit", None),
        "parametros": {"max_length": getattr(encoder, "max_length", None),
                       "batch_size": getattr(encoder, "batch_size", None),
                       "pooling": "media_tokens_por_ventana_y_media_ponderada_ventanas",
                       "ventanas_sin_truncamiento": True,
                       "query_sin_marcadores": True},
        "resumen": {**resumen, **dict(contador),
                    "documentos_vectorizados_una_vez": len(cache_docs),
                    "segundos_totales": round(time.perf_counter() - inicio_total, 3),
                    "sin_relevancias_humanas": True,
                    "metricas_gold_calculadas": False},
        "resultados": resultados,
    }


def _leer_jsonl(ruta: Path, limite: int | None = None) -> list[dict]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe corpus de entrada: {ruta}")
    filas = []
    with ruta.open(encoding="utf-8-sig") as archivo:
        for linea in archivo:
            if linea.strip():
                filas.append(json.loads(linea))
                if limite is not None and len(filas) >= limite:
                    break
    return filas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--solo-validar", action="store_true")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit debe ser positivo")
    casos = _leer_jsonl(args.input, args.limit)
    resumen = validar_casos(casos)
    if args.solo_validar:
        print("S2.8 CORPUS VÁLIDO:", json.dumps(resumen, ensure_ascii=False))
        return 0
    if args.out is None:
        parser.error("Debe especificar --out para ejecutar la inferencia")
    if args.out.exists():
        parser.error("El informe ya existe; use otra ruta --out para no sobrescribirlo")
    encoder = TorchSciBERTEncoder(args.model, args.revision, args.device,
                                  args.batch_size, args.max_length)
    datos = ejecutar(casos, encoder)
    datos["sha256_entrada"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    datos["entorno"] = {"torch": encoder.torch.__version__, "cuda": encoder.torch.version.cuda,
                         "device": encoder.device}
    datos["resumen"]["textos_vectorizados"] = encoder.textos_procesados
    datos["resumen"]["ventanas_vectorizadas"] = encoder.ventanas_procesadas
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as salida:
        json.dump(datos, salida, ensure_ascii=False, indent=2)
        salida.write("\n")
    print("S2.8 INFORME:", args.out)
    print("RESUMEN:", json.dumps(datos["resumen"], ensure_ascii=False))
    print("Solo comparación técnica train; sin etiquetas ni métricas Gold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
