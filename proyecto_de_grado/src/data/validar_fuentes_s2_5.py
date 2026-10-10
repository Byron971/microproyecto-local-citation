"""Verifica catálogo de fuentes S2.5. Solo lectura, nunca importa etiquetas.

La aprobación académica, licencias y correspondencia semántica requieren
pruebas externas a este módulo; modificarlo NO habilita una fusión de datos.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from proyecto_de_grado.src.data.preparar_preetiquetado import ETIQUETAS

RAIZ = Path(__file__).resolve().parents[3]
DEFAULT_CATALOGO = RAIZ / "proyecto_de_grado/config/fuentes_citas_s2_5.json"
EXPECTED_IDS = {"ACL-200", "ACL-OCL", "MULTICITE", "ILCITER"}
MULTICITE_CODES = {
    "@BACK@", "@MOT@", "@FUT@", "@SIM@", "@DIF@", "@USE@", "@EXT@", "@UNSURE@",
}


def validar_catalogo(catalogo: dict) -> dict:
    if not isinstance(catalogo, dict) or catalogo.get("schema_version") != 1:
        raise ValueError("Versión de esquema no reconocida")
    if catalogo.get("taxonomia_proyecto") != list(ETIQUETAS):
        raise ValueError("Las nueve clases internas se modificaron o reordenaron")
    if catalogo.get("status") != "auditoria_metodologica_no_fusionada":
        raise ValueError("Estado del catálogo no autorizado")
    fuentes = catalogo.get("fuentes")
    if not isinstance(fuentes, list) or len(fuentes) != len(EXPECTED_IDS):
        raise ValueError("Catálogo incompleto")
    por_id = {}
    for fuente in fuentes:
        if not isinstance(fuente, dict):
            raise ValueError("Fuente inválida")
        ident = fuente.get("id")
        if ident in por_id or not isinstance(ident, str):
            raise ValueError("ID de fuente repetido/inválido")
        por_id[ident] = fuente
        if fuente.get("importacion_automatica_etiquetas") is not False:
            raise ValueError(f"{ident}: prohibida la importación automática de etiquetas")
        if fuente.get("mapeos_automaticos") != {}:
            raise ValueError(f"{ident}: no se admiten recodificaciones automáticas")
        if fuente.get("estado_homologacion") not in (
            "no_homologado", "fuente_documental_aceptada",
        ):
            raise ValueError(f"{ident}: estado de homologación sin revisión")
        if not isinstance(fuente.get("url"), str) or not fuente["url"].startswith("https://"):
            raise ValueError(f"{ident}: falta URL trazable")
        if not isinstance(fuente.get("licencia_dataset"), str) or not fuente["licencia_dataset"]:
            raise ValueError(f"{ident}: falta declaración de licencia/pendiente")
    if set(por_id) != EXPECTED_IDS:
        raise ValueError("IDs de fuentes distintos de los examinados")
    for ident in ("ACL-200", "ACL-OCL"):
        f = por_id[ident]
        if f.get("estado_homologacion") != "fuente_documental_aceptada":
            raise ValueError(f"{ident}: estado documental alterado")
        if f.get("etiquetas_funcion") != []:
            raise ValueError(f"{ident}: se inventaron funciones anotadas")
    m = por_id["MULTICITE"]
    if m.get("estado_homologacion") != "no_homologado" or m.get("modo_etiquetado") != "multilabel":
        raise ValueError("MultiCite no tiene equivalencia multiclase aprobada")
    codes = m.get("etiquetas_funcion")
    if not isinstance(codes, list) or len(codes) != len(MULTICITE_CODES) or set(codes) != MULTICITE_CODES:
        raise ValueError("Taxonomía original MultiCite incompleta")
    relaciones = m.get("relaciones_candidatas_no_homologadas")
    if not isinstance(relaciones, dict) or set(relaciones) != MULTICITE_CODES:
        raise ValueError("No están documentados todos los códigos MultiCite")
    if any(not isinstance(valores, list) or any(v not in ETIQUETAS for v in valores)
           for valores in relaciones.values()):
        raise ValueError("Relación candidata apunta a clase desconocida")
    if m.get("licencia_dataset") != "CC BY-NC 2.0":
        raise ValueError("Licencia MultiCite diferente de la fuente primaria")
    i = por_id["ILCITER"]
    if (i.get("estado_homologacion") != "no_homologado" or
            i.get("etiquetas_funcion") != []):
        raise ValueError("ILCiteR no se ha verificado como fuente de 9 etiquetas")
    return {
        "fuentes": len(fuentes),
        "categorias_proyecto": len(ETIQUETAS),
        "categorias_multicite_con_unsure": len(codes),
        "fuentes_con_importacion_automatica_etiquetas": 0,
        "mapeos_automaticos_aprobados": 0,
        "estado": "validado_solo_como_catalogo_no_homologado",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogo", type=Path, default=DEFAULT_CATALOGO)
    args = parser.parse_args(argv)
    try:
        datos = json.loads(args.catalogo.read_text(encoding="utf-8-sig"))
        resultado = validar_catalogo(datos)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Error S2.5: {exc}\n")
    print("=== S2.5 | FUENTES DOCUMENTADAS SIN FUSIÓN ===")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
