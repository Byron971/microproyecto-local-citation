"""S2.4: planificador offline y adquisición ACL OCL por lote explícito.

Default: dry-run SIN RED ni cambios en la caché.
Con --execute: a lo sumo 10 JSON citados de train, una solicitud por vez,
límite de bytes, validación de identidad y guardado atómico en caché.
NO adquiere citantes, NO etiqueta, NO construye Test Gold.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 import DEFAULT_CACHE, REPO
from proyecto_de_grado.scripts.spike_enlace_datos.medir_enlace import OCL_URL

DEFAULT_DIAG = REPO / "proyecto_de_grado/artifacts/enriquecimiento_s2_4/diagnostico_cache_train_top100.json"
VALID_ACL = re.compile(r"^[A-Z]\d{2}-\d{4}$")
MAX_BATCH = 10
MAX_FILE_BYTES = 5_000_000


def _decada(acl_id: str) -> int:
    yy = int(acl_id[1:3])
    year = 1900 + yy if yy > 50 else 2000 + yy
    return year // 10 * 10


def leer_prioridades(path: Path) -> list[dict]:
    """Rechaza IDs repetidos/ilegales y reportes no derivados de TRAIN."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"No se puede leer diagnóstico: {path}") from exc
    if obj.get("tipo") != "diagnostico_offline_s2_4_solo_train":
        raise ValueError("Solo se aceptan diagnósticos S2.4 de train.")
    filas = obj.get("prioridad_descarga_train")
    if not isinstance(filas, list) or not filas:
        raise ValueError("No hay documentos train pendientes en este diagnóstico.")
    vistos, limpias = set(), []
    for x in filas:
        if not isinstance(x, dict):
            raise ValueError("Entrada de prioridad inválida.")
        pid = x.get("cited_id")
        n = x.get("contextos_train_potenciales")
        if (
            not isinstance(pid, str) or not VALID_ACL.fullmatch(pid)
            or pid in vistos or type(n) is not int or n < 1
        ):
            raise ValueError(f"ID de prioridad duplicado o inválido: {pid!r}")
        vistos.add(pid)
        limpias.append({"cited_id": pid, "contextos_train_potenciales": n,
                         "decada": _decada(pid)})
    return sorted(limpias, key=lambda x: (-x["contextos_train_potenciales"], x["cited_id"]))


def planificar(filas: list[dict], cache: Path, limite: int = 6) -> dict:
    if not 1 <= limite <= MAX_BATCH:
        raise ValueError(f"El lote debe contener entre 1 y {MAX_BATCH} documentos.")
    # Excluir solamente documentos que tienen archivo verificado o un 404 previo.
    elegibles = []
    omitidos = Counter()
    for item in filas:
        pid = item["cited_id"]
        if (cache / f"{pid}.json").is_file():
            omitidos["ya_existe_en_cache"] += 1
        elif (cache / f"{pid}.404").exists():
            omitidos["404_ya_conocido"] += 1
        else:
            elegibles.append(item)

    n_top = (limite + 1) // 2
    escogidos = elegibles[:n_top]
    elegidos = {r["cited_id"] for r in escogidos}
    decadas = {r["decada"] for r in escogidos}
    # La otra mitad diversifica por década para no seleccionar solo artículos
    # de alta frecuencia que sobrerrepresenten un mismo periodo histórico.
    for fila in elegibles[n_top:]:
        if len(escogidos) >= limite:
            break
        if fila["decada"] in decadas:
            continue
        escogidos.append(fila)
        elegidos.add(fila["cited_id"])
        decadas.add(fila["decada"])
    for fila in elegibles:
        if len(escogidos) >= limite:
            break
        if fila["cited_id"] not in elegidos:
            escogidos.append(fila)
            elegidos.add(fila["cited_id"])
    return {
        "tipo": "plan_acceso_ocl_train_s2_4",
        "solicitados": limite,
        "seleccionados": len(escogidos),
        "documentos": escogidos,
        "contextos_train_potenciales_suma_no_verificada": sum(x["contextos_train_potenciales"] for x in escogidos),
        "descartes": dict(omitidos),
        "sin_descargas": True,
    }


def _descargar_uno(acl_id: str, cache: Path, *, max_bytes: int,
                  pausa: float, intentos: int = 3, abrir=urllib.request.urlopen,
                  dormir=time.sleep) -> dict:
    """Nunca deja un JSON parcial ni marca como 404 un fallo transitorio."""
    destino = cache / f"{acl_id}.json"
    ausente = cache / f"{acl_id}.404"
    if destino.exists():
        return {"cited_id": acl_id, "estado": "ya_existia"}
    if ausente.exists():
        return {"cited_id": acl_id, "estado": "404_anterior"}
    url = OCL_URL.format(L=acl_id[0], YY=acl_id[1:3], ID=acl_id)
    for intento in range(intentos):
        try:
            with abrir(url, timeout=30) as response:
                size = response.headers.get("Content-Length") if hasattr(response, "headers") else None
                if size is not None and int(size) > max_bytes:
                    return {"cited_id": acl_id, "estado": "supera_limite_bytes"}
                datos = response.read(max_bytes + 1)
                if len(datos) > max_bytes:
                    return {"cited_id": acl_id, "estado": "supera_limite_bytes"}
            doc = json.loads(datos.decode("utf-8-sig"))
            if (
                not isinstance(doc, dict) or doc.get("paper_id") != acl_id
                or not isinstance(doc.get("pdf_parse"), dict)
                or not isinstance(doc["pdf_parse"].get("body_text"), list)
                or not doc["pdf_parse"]["body_text"]
            ):
                return {"cited_id": acl_id, "estado": "estructura_o_id_invalido"}
            # Escribir solo después de validar: replace atómico sobre la misma carpeta.
            temporal = cache / f".{acl_id}.partial"
            try:
                with temporal.open("xb") as f:
                    f.write(datos)
                if destino.exists():
                    return {"cited_id": acl_id, "estado": "ya_existia"}
                temporal.rename(destino)
            finally:
                temporal.unlink(missing_ok=True)
            return {"cited_id": acl_id, "estado": "descargado",
                    "bytes": len(datos), "sha256": hashlib.sha256(datos).hexdigest()}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                ausente.touch(exist_ok=True)
                return {"cited_id": acl_id, "estado": "404_confirmado"}
            if exc.code not in (429, 500, 502, 503, 504):
                return {"cited_id": acl_id, "estado": f"http_{exc.code}"}
            if intento == intentos - 1:
                return {"cited_id": acl_id, "estado": f"http_{exc.code}_agotado"}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if intento == intentos - 1:
                return {"cited_id": acl_id, "estado": "red_o_disco_error",
                        "detalle": type(exc).__name__}
        except (UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            return {"cited_id": acl_id, "estado": "respuesta_invalida"}
        dormir(max(pausa, 1.0) * (2 ** intento))
    return {"cited_id": acl_id, "estado": "sin_resultado"}


def ejecutar_plan(plan: dict, cache: Path, *, max_bytes: int = MAX_FILE_BYTES,
                  pausa: float = 2.0, abrir=urllib.request.urlopen,
                  dormir=time.sleep) -> dict:
    if not 1 <= max_bytes <= MAX_FILE_BYTES or pausa < 1.0:
        raise ValueError("Máximo 5 MB por documento y pausa mínima 1 segundo.")
    cache.mkdir(parents=True, exist_ok=True)
    resultados = []
    for i, row in enumerate(plan["documentos"]):
        if i:
            dormir(pausa)
        resultados.append(_descargar_uno(row["cited_id"], cache, max_bytes=max_bytes,
                                       pausa=pausa, abrir=abrir, dormir=dormir))
    return {"tipo": "ejecucion_lote_acl_ocl_train_s2_4", "resultados": resultados,
            "conteos": dict(Counter(r["estado"] for r in resultados))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diagnostico", type=Path, default=DEFAULT_DIAG)
    ap.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--limite", type=int, default=6)
    ap.add_argument("--execute", action="store_true", help="Opt-in: autorizar red y caché.")
    ap.add_argument("--pausa", type=float, default=2.0)
    ap.add_argument("--max-bytes", type=int, default=MAX_FILE_BYTES)
    args = ap.parse_args(argv)
    try:
        lista = leer_prioridades(args.diagnostico)
        plan = planificar(lista, args.cache, args.limite)
        print("=== S2.4 | ADQUISICIÓN ACL OCL ===")
        print("Plan (solo train):", json.dumps(plan, ensure_ascii=False, indent=2))
        if not args.execute:
            print("MODO SEGURO: no se descargó ni escribió ningún archivo.")
            return 0
        resultado = ejecutar_plan(plan, args.cache, max_bytes=args.max_bytes, pausa=args.pausa)
        print("RESULTADOS:", json.dumps(resultado, ensure_ascii=False, indent=2))
        if any(r["estado"] not in ("descargado", "ya_existia", "404_anterior",
                                  "404_confirmado") for r in resultado["resultados"]):
            print("AVISO: algunos archivos no se adquirieron; revisar causas sin reintentar a ciegas.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ap.exit(2, f"S2.4 adquisición: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
