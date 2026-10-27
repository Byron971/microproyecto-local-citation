
"""Integración por lotes de ACL-200 con artículos ACL OCL.

Reutiliza documentos descargados y reporta los resultados.
No descarga archivos ni modifica los datos originales.
"""

import argparse
from collections import Counter
from pathlib import Path

from proyecto_de_grado.src.data.integrar_acl import (
    cargar_json,
    integrar_contexto,
)


def procesar_lote(
    contextos,
    papers,
    cache_dir,
    refid,
    limite=10,
):
    """Procesa contextos que citan un mismo artículo."""

    if limite <= 0:
        raise ValueError("El límite debe ser mayor que cero.")

    # Buscar los contextos asociados al artículo citado.
    ids = [
        cid
        for cid, contexto in contextos.items()
        if contexto.get("refid") == refid
    ]

    seleccionados = ids[:limite]
    resultados = []

    for cid in seleccionados:
        try:
            registro = integrar_contexto(
                cid,
                contextos,
                papers,
                cache_dir,
            )

            resultados.append({
                "context_id": cid,
                "estado": "integrado",
                "citing_id": registro["citing_id"],
                "cited_id": registro["cited_id"],
                "parrafos": len(registro["paragraphs"]),
                "error": None,
            })

        except (ValueError, FileNotFoundError, KeyError) as error:
            resultados.append({
                "context_id": cid,
                "estado": "error",
                "citing_id": contextos[cid].get("citing_id"),
                "cited_id": refid,
                "parrafos": 0,
                "error": str(error),
            })

    return len(ids), resultados


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--refid",
        default="N04-1019",
        help="ID ACL del artículo citado",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Número máximo de contextos",
    )

    args = parser.parse_args()

    raiz = Path(__file__).resolve().parents[3]

    datos = raiz / "data" / "raw"

    cache = (
        raiz
        / "proyecto_de_grado"
        / "scripts"
        / "spike_enlace_datos"
        / "cache_ocl"
    )

    contextos = cargar_json(datos / "contexts.json")
    papers = cargar_json(datos / "papers.json")

    total, resultados = procesar_lote(
        contextos,
        papers,
        cache,
        refid=args.refid,
        limite=args.limit,
    )

    conteos = Counter(
        resultado["estado"] for resultado in resultados
    )

    print("\n=== INTEGRACION POR LOTES ===")
    print("Articulo citado:", args.refid)
    print("Contextos asociados:", total)
    print("Contextos examinados:", len(resultados))

    for resultado in resultados:
        print(
            resultado["context_id"],
            "|", resultado["estado"],
            "| parrafos:", resultado["parrafos"],
        )

        if resultado["error"]:
            print("  Motivo:", resultado["error"])

    print("\n=== RESUMEN ===")
    print("Integrados:", conteos["integrado"])
    print("Con errores:", conteos["error"])

    print(
        "Nota: esta prueba valida el enlace al articulo "
        "citado, no la reconstruccion del citante."
    )


if __name__ == "__main__":
    main()
