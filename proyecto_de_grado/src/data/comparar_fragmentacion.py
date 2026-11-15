"""Comparación descriptiva V1/V2 sobre la MISMA caché ACL OCL, sin Gold ni red.

No calcula calidad de recuperación ni sustituye anotación humana. No modifica
los documentos fuente ni las salidas históricas del proyecto.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar, fragmentar_v2


def comparar_cache(cache: Path, limite: int = 0) -> dict:
    if not cache.is_dir():
        raise ValueError("No existe el directorio de cache ACL OCL.")
    if limite < 0:
        raise ValueError("limite debe ser >= 0; cero significa todos los documentos.")
    archivos = sorted(cache.glob("*.json"))
    if limite:
        archivos = archivos[:limite]
    if not archivos:
        raise ValueError("No hay archivos JSON ACL OCL para comparar.")
    resultados = []
    exitos = Counter()
    razones = {"v1": Counter(), "v2": Counter()}
    for archivo in archivos:
        registro = {"paper_id": archivo.stem, "sha256_fuente": hashlib.sha256(archivo.read_bytes()).hexdigest()}
        try:
            doc = json.loads(archivo.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or doc.get("paper_id") != archivo.stem:
                raise ValueError("identidad ACL OCL incorrecta")
            cuerpo = (doc.get("pdf_parse") or {}).get("body_text")
            if not isinstance(cuerpo, list):
                raise ValueError("body_text ausente o invalido")
            parrafos = [
                {"numero": i, "texto": p["text"].strip(), "seccion": str(p.get("section") or "")}
                for i, p in enumerate(cuerpo)
                if isinstance(p, dict) and isinstance(p.get("text"), str) and p["text"].strip()
            ]
            registro["parrafos_con_texto"] = len(parrafos)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            for v in ("v1", "v2"):
                registro[v] = {"apto": False, "motivo": "entrada_invalida"}
                razones[v]["entrada_invalida"] += 1
            resultados.append(registro)
            continue
        for version, algoritmo in (("v1", fragmentar), ("v2", fragmentar_v2)):
            try:
                chunks = algoritmo(parrafos)
                registro[version] = {
                    "apto": True,
                    "n_chunks": len(chunks),
                    "n_palabras_chunk": sum(c["palabras"] for c in chunks),
                }
                exitos[version] += 1
            except (ValueError, KeyError, TypeError) as exc:
                # Texto explicativo sin contenido de los artículos.
                motivo = type(exc).__name__ + ":" + str(exc)
                registro[version] = {"apto": False, "motivo": motivo}
                razones[version][motivo] += 1
        resultados.append(registro)
    return {
        "estado": "auditoria_descriptiva_cache_no_gold",
        "advertencia": (
            "Comparación de documentos cacheados; la caché puede estar sesgada. "
            "No demuestra Recall@3, MRR@3 ni mejora en clasificación."
        ),
        "total_archivos_misma_muestra": len(archivos),
        "aceptados_v1": exitos["v1"],
        "aceptados_v2": exitos["v2"],
        "recuperados_por_v2": sum(1 for r in resultados
                                 if not r["v1"]["apto"] and r["v2"]["apto"]),
        "rechazos_por_version": {v: dict(sorted(razones[v].items())) for v in ("v1", "v2")},
        "archivos": resultados,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parents[3]
    parser.add_argument("--cache", type=Path, default=repo / "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl")
    parser.add_argument("--salida", type=Path, required=True)
    parser.add_argument("--limite", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        if args.salida.exists():
            raise ValueError("No se sobrescribe un informe existente.")
        resultado = comparar_cache(args.cache, args.limite)
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error comparacion fragmentacion: {exc}\n")
    print(json.dumps({k: v for k, v in resultado.items() if k != "archivos"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
