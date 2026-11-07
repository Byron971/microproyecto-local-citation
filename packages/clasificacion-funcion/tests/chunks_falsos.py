"""Piezas falsas para chunks y recuperacion: sin red, sin torch."""
import hashlib
import json


def fragmentar_falso(parrafos):
    if any("PARRAFO_LARGO" in p["texto"] for p in parrafos):
        raise ValueError("Parrafo demasiado largo: requiere division por oraciones.")
    return [{"chunk_id": f"p{p['numero']:05d}", "texto": p["texto"], "seccion": p["seccion"],
             "paragraph_indices": [p["numero"]], "palabras": len(p["texto"].split())}
            for p in parrafos]


def crear_integrar(parrafos_por_citado):
    def integrar(cid, contextos, papers, cache_dir):
        ctx = contextos[cid]
        cited = ctx["refid"]
        if cited not in papers:
            raise ValueError(f"El articulo {cited} no existe en ACL-200.")
        return {"context_id": cid, "citing_id": ctx["citing_id"], "cited_id": cited,
                "ocl_paper_id": cited, "cited_title": f"titulo {cited}",
                "citation_context": ctx["masked_text"], "paragraphs": parrafos_por_citado[cited]}
    return integrar


def parrafos(cited, n=4, largo=False):
    secciones = ["Introduction", "Method", "Results", "Conclusion", "Related work"]
    return [{"numero": i, "seccion": secciones[i % 5],
             "texto": f"{cited} parrafo {i} " + ("PARRAFO_LARGO" if largo and i == 1 else "texto")}
            for i in range(n)]


def preparar_cache(carpeta, citados, ausentes=(), no_encontrados=()):
    carpeta.mkdir(parents=True, exist_ok=True)
    for c in citados:
        if c in no_encontrados:
            (carpeta / f"{c}.404").write_text("")
        elif c not in ausentes:
            (carpeta / f"{c}.json").write_text(json.dumps({"paper_id": c}), encoding="utf-8")


class CodificadorFalso:
    model_id = "falso/encoder"
    revision = "f" * 40
    pooling = "mean"
    device = "cpu"

    def __init__(self):
        self.llamadas = 0

    def encode(self, textos):
        self.llamadas += 1
        return [tuple(b / 255 + 0.01 for b in hashlib.sha256(t.encode()).digest()[:8]) for t in textos]

    def info(self):
        return {"model_id": self.model_id, "revision": self.revision, "device": "cpu"}
