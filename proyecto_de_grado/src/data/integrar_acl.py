
"""Integración inicial de ACL-200 y ACL OCL.

Relaciona un contexto académico con el artículo citado,
utilizando el identificador ACL Anthology.

Conserva la cita objetivo y recupera los párrafos del
artículo citado junto con sus secciones.
"""

import json
from pathlib import Path


def cargar_json(ruta):
    """Carga un archivo JSON."""
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)


def integrar_contexto(context_id, contextos, papers, cache_dir):
    """Integra un contexto ACL-200 con su artículo en ACL OCL."""

    contexto = contextos[context_id]

    citado_id = contexto["refid"]
    citante_id = contexto["citing_id"]
    texto_contexto = contexto["masked_text"]

    if texto_contexto.count("TARGETCIT") != 1:
        raise ValueError(
            f"El contexto {context_id} no tiene una cita objetivo única."
        )

    if citado_id not in papers:
        raise ValueError(
            f"El artículo {citado_id} no existe en ACL-200."
        )

    paper = papers[citado_id]

    ruta_ocl = Path(cache_dir) / f"{citado_id}.json"

    if not ruta_ocl.exists():
        raise FileNotFoundError(
            f"No encontramos ACL OCL para {citado_id}."
        )

    documento = cargar_json(ruta_ocl)

    ocl_id = documento.get("paper_id")

    if ocl_id != citado_id:
        raise ValueError(
            f"ID incorrecto: esperado {citado_id}, "
            f"recibido {ocl_id}."
        )

    cuerpo = documento.get("pdf_parse", {}).get(
        "body_text", []
    )

    parrafos = []

    for numero, parrafo in enumerate(cuerpo):
        texto = str(parrafo.get("text") or "").strip()

        if not texto:
            continue

        seccion = str(parrafo.get("section") or "").strip()

        parrafos.append({
            "numero": numero,
            "texto": texto,
            "seccion": seccion
        })

    if not parrafos:
        raise ValueError(
            f"El artículo {citado_id} no contiene párrafos."
        )

    registro = {
        "context_id": context_id,
        "citing_id": citante_id,
        "cited_id": citado_id,
        "citation_context": texto_contexto,
        "cited_title": paper.get("title", ""),
        "cited_abstract": paper.get("abstract", ""),
        "ocl_paper_id": ocl_id,
        "ocl_title": documento.get("title", ""),
        "paragraphs": parrafos
    }

    return registro


def main():
    """Prueba la integración de un artículo conocido."""

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

    # Contexto cuya descarga ya verificamos.
    ejemplo_id = "P15-2138_N04-1019_0"

    registro = integrar_contexto(
        ejemplo_id,
        contextos,
        papers,
        cache
    )

    print("\n=== REGISTRO INTEGRADO ===")
    print("Contexto:", registro["context_id"])
    print("Citante:", registro["citing_id"])
    print("Citado:", registro["cited_id"])
    print("ID ACL OCL:", registro["ocl_paper_id"])
    print("Título ACL-200:", registro["cited_title"])
    print("Título ACL OCL:", registro["ocl_title"])

    print("Párrafos:", len(registro["paragraphs"]))

    con_seccion = sum(
        bool(p["seccion"])
        for p in registro["paragraphs"]
    )

    print("Párrafos con sección:", con_seccion)

    marcador_conservado = (
        registro["citation_context"].count("TARGETCIT") == 1
    )

    print("TARGETCIT conservado:", marcador_conservado)

    print("\nINTEGRACIÓN INICIAL EXITOSA")


if __name__ == "__main__":
    main()
