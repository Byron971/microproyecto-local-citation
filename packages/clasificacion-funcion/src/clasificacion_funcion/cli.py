"""Raiz de composicion sin torch.

Uso (desde la raiz del repo):
  PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.cli \\
      preparar --solo-validar
  PYTHONPATH=. uv run --project packages/clasificacion-funcion python -m clasificacion_funcion.cli preparar
Todo resultado es PROVISIONAL: las etiquetas de entrenamiento y de eval son de Haiku.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from auditoria_corpus.dominio import perfil_seccion
from recuperacion_densa.cache_embeddings import CacheDisco
from recuperacion_densa.dominio import SIN_SECCION

from . import adaptador_proyecto_grado as ad
from . import comparacion, dominio, exportar, servicio

EVIDENCIAS = ad.REPO / "proyecto_de_grado/docs/evidencias_clasificacion_a4"
ARTEFACTOS = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/preparacion"
COL_MOTIVOS = ["conjunto", "context_id", "motivo"]
COL_ETIQUETAS = ["context_id", "indice", "etiqueta"]
COL_EXCLUIDOS = ["conjunto", "context_id", "motivo", "etiqueta"]
COL_TOP3 = ["context_id", "posicion", "cited_id", "chunk_id", "seccion", "perfil_seccion",
            "paragraph_indices", "puntaje"]
TOP3_A1 = ad.REPO / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/top3.csv"
ENTRADAS_ART = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/entradas"
UMBRAL_COBERTURA = 60.0
TIPOS_ENTRADA = ("A", "B", "B_sin_seccion")
CACHE_EMBEDDINGS = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/cache_embeddings"


def crear_fuentes():
    return ad.FuentesProyectoGrado()


def _sha_archivo(ruta: Path) -> str | None:
    ruta = Path(ruta)
    return hashlib.sha256(ruta.read_bytes()).hexdigest() if ruta.is_file() else None


def _git() -> dict:
    def run(*a):
        return subprocess.run(["git", "-C", str(ad.REPO), *a], capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        return {"head": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"head": None, "dirty": None}


def _publicar(destino: Path, contenido: str) -> None:
    """Escritura atomica que nunca sobrescribe: .tmp y enlace duro (falla si ya existe)."""
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(contenido, encoding="utf-8", newline="")
    try:
        os.link(tmp, destino)
    finally:
        tmp.unlink(missing_ok=True)


def _csv_texto(columnas: list[str], filas: list[dict]) -> str:
    buffer = io.StringIO()
    w = csv.DictWriter(buffer, fieldnames=columnas, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    w.writerows(filas)
    return buffer.getvalue()


def _json_texto(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _lineas(valores) -> str:
    return "".join(f"{v}\n" for v in valores)


def _resumen(r: dict) -> dict:
    conjuntos = r["conjuntos"]
    abst: dict = {}
    for a in r["abstenciones"]:
        por = abst.setdefault(a["conjunto"], {})
        por[a["motivo"]] = por.get(a["motivo"], 0) + 1
    return {
        "estado": r["estado"],
        "fuente_etiquetas": r["fuente_etiquetas"],
        "casos": {n: len(c) for n, c in conjuntos.items()},
        "abstenciones": abst,
        "excluidos": len(r["excluidos"]),
        "citados_requeridos": len(r["citados_requeridos"]),
        "total_fugas": r["fugas"]["total_fugas"],
    }


def _archivos(r: dict, fuentes, args) -> tuple[dict[Path, str], dict[Path, str]]:
    """(evidencias versionadas, artefactos ignorados por git) -> contenido."""
    conjuntos = r["conjuntos"]
    ev, art = {}, {}
    for nombre, casos in conjuntos.items():
        ev[args.salida / f"ids_{nombre}.txt"] = _lineas(sorted(c["context_id"] for c in casos))
    for nombre in ("train", "val", "eval_2015"):
        art[args.artefactos / f"etiquetas_{nombre}.csv"] = _csv_texto(COL_ETIQUETAS, [
            {"context_id": c["context_id"], "indice": c["indice"], "etiqueta": c["etiqueta"]}
            for c in conjuntos[nombre]])
    ev[args.salida / "abstenciones.csv"] = _csv_texto(COL_MOTIVOS, r["abstenciones"])
    ev[args.salida / "excluidos_preparacion.csv"] = _csv_texto(COL_MOTIVOS, r["excluidos"])
    ev[args.salida / "fugas.json"] = _json_texto(r["fugas"])
    ev[args.salida / "citados_requeridos.txt"] = _lineas(r["citados_requeridos"])
    hashes = {}
    for nombre in ("train", "val", "eval_2015"):
        hashes[nombre] = {
            "ids_sha256": dominio.sha_ids(c["context_id"] for c in conjuntos[nombre]),
            "labels_sha256": dominio.sha_etiquetas(
                {c["context_id"]: c["indice"] for c in conjuntos[nombre]}),
        }
    hashes["gold_v2"] = {"ids_sha256": dominio.sha_ids(c["context_id"] for c in conjuntos["gold_v2"])}
    manifiesto = {
        **_resumen(r), "hashes": hashes, "git": _git(), "limite": args.limite,
        "entradas": {n: _sha_archivo(p) for n, p in sorted(fuentes.rutas().items())},
    }
    ev[args.salida / "manifiesto_preparacion.json"] = _json_texto(manifiesto)
    return ev, art


def preparar(args) -> int:
    fuentes = crear_fuentes()
    r = servicio.cargar_conjuntos(fuentes, args.fuente_etiquetas, args.limite)
    print(_json_texto(_resumen(r)), end="")
    if args.solo_validar:
        print("--solo-validar: no se escribio nada.")
        return 0
    ev, art = _archivos(r, fuentes, args)
    existentes = [p for p in (*ev, *art) if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    for carpeta in (args.salida, args.artefactos):
        carpeta.mkdir(parents=True, exist_ok=True)
    for ruta, contenido in {**ev, **art}.items():
        _publicar(ruta, contenido)
    print(f"Evidencias: {args.salida}\nArtefactos (gitignored): {args.artefactos}")
    return 0


def _filas_top3(top3: dict[str, list[dict]]) -> list[dict]:
    return [{"context_id": ctx, "posicion": r["posicion"], "cited_id": r["cited_id"],
             "chunk_id": r["chunk_id"], "seccion": r.get("seccion") or SIN_SECCION,
             "perfil_seccion": perfil_seccion(r.get("seccion")),
             "paragraph_indices": "|".join(map(str, r.get("paragraph_indices") or [])),
             "puntaje": r["similitud_coseno"]}
            for ctx in sorted(top3) for r in top3[ctx]]


def _resumen_casos(casos: dict, excluidos: list[dict], conjuntos: dict) -> dict:
    por_conjunto = {}
    for n, original in conjuntos.items():
        motivos: dict[str, int] = {}
        for e in excluidos:
            if e["conjunto"] == n:
                motivos[e["motivo"]] = motivos.get(e["motivo"], 0) + 1
        total = len(original)
        por_conjunto[n] = {"contextos": total, "con_chunks": len(casos[n]),
                           "cobertura_pct": round(100 * len(casos[n]) / total, 2) if total else None,
                           "excluidos_por_motivo": dict(sorted(motivos.items()))}
    return por_conjunto


def recuperar(args, fabrica_codificador: Callable | None) -> int:
    """Top-3 con SciBERT base (revision de A1) para train/val/eval_2015/gold_v2."""
    fuentes = crear_fuentes()
    r = servicio.cargar_conjuntos(fuentes, args.fuente_etiquetas, args.limite)
    contextos = fuentes.indice()[1]
    casos, excluidos = servicio.construir_casos_split(
        r["conjuntos"], contextos, ad.cargar_papers(args.raw), args.cache_ocl, ad.integrar,
        ad.fragmentar)
    cobertura = _resumen_casos(casos, excluidos, r["conjuntos"])
    print(_json_texto({"cobertura": cobertura}), end="")
    if args.solo_validar:
        print("--solo-validar: no se cargo el modelo ni se escribio nada.")
        return 0
    if fabrica_codificador is None:
        raise ValueError("Falta un codificador; use `cli_modelo` o --solo-validar.")
    destinos = [args.salida / f"top3_{n}.csv" for n in casos] + [
        args.salida / "excluidos_recuperacion.csv", args.salida / "manifiesto_recuperacion.json"]
    existentes = [p for p in destinos if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    t0 = time.perf_counter()
    codificador = fabrica_codificador(args)
    cache = None if args.sin_cache else CacheDisco(args.cache)
    resultados = {n: servicio.recuperar_top3(c, codificador, cache, max_length=args.max_length,
                                             pooling=getattr(codificador, "pooling", "mean"))
                  for n, c in casos.items()}
    regresion = None
    if args.regresion_a1 and Path(args.regresion_a1).is_file():
        regresion = servicio.regresion_top3(
            resultados["train"]["top3"], leer_csv_top3(args.regresion_a1))
        if regresion["discrepancias"]:
            raise ValueError(f"Regresion contra A1 fallida: {regresion['discrepancias'][:5]}")
    contenido = {args.salida / f"top3_{n}.csv": _csv_texto(COL_TOP3, _filas_top3(res["top3"]))
                 for n, res in resultados.items()}
    contenido[args.salida / "excluidos_recuperacion.csv"] = _csv_texto(COL_MOTIVOS, excluidos)
    manifiesto = {
        "estado": r["estado"], "git": _git(), "limite": args.limite, "cobertura": cobertura,
        "encoder": codificador.info(),
        "sha256_manifiesto_modelo": _sha_manifiesto(args.manifiesto_modelo),
        "huellas": {n: res["huella"] for n, res in resultados.items()},
        "chunks_en_cache": {n: res["chunks_en_cache"] for n, res in resultados.items()},
        "regresion_a1": regresion,
        "segundos": round(time.perf_counter() - t0, 1),
        "entradas": {"manifiesto_ocl": _sha_archivo(args.manifiesto_ocl),
                     "manifiesto_preparacion": _sha_archivo(args.salida / "manifiesto_preparacion.json"),
                     "papers.json": _sha_archivo(args.raw / "papers.json"),
                     "contexts.json": _sha_archivo(args.raw / "contexts.json")},
        "salidas": {p.name: hashlib.sha256(t.encode("utf-8")).hexdigest()
                    for p, t in sorted(contenido.items())},
    }
    contenido[args.salida / "manifiesto_recuperacion.json"] = _json_texto(manifiesto)
    args.salida.mkdir(parents=True, exist_ok=True)
    for ruta, texto in contenido.items():
        _publicar(ruta, texto)
    print(f"Top-3 escrito en {args.salida} | regresion A1: {regresion}")
    return 0


def entradas(args) -> int:
    """Interseccion controlada: A y B usan exactamente los mismos context_id."""
    fuentes = crear_fuentes()
    r = servicio.cargar_conjuntos(fuentes, args.fuente_etiquetas, args.limite)
    contextos = fuentes.indice()[1]
    papers = ad.cargar_papers(args.raw)
    casos, excl_chunks = servicio.construir_casos_split(
        r["conjuntos"], contextos, papers, args.cache_ocl, ad.integrar, ad.fragmentar)
    top3 = {}
    for n in r["conjuntos"]:
        ruta = args.top3 / f"top3_{n}.csv"
        if not ruta.is_file():
            raise FileNotFoundError(f"Falta {ruta}: ejecute `cli_modelo recuperar` primero.")
        top3[n] = servicio.agrupar_top3(leer_csv_top3(ruta))
    res = servicio.interseccion(r["conjuntos"], casos, excl_chunks, top3, papers)
    ent, resumen = res["entradas"], res["resumen"]
    bloqueos = [{"conjunto": n, "cobertura_pct": resumen[n]["cobertura_pct"],
                 "umbral_pct": args.umbral_cobertura,
                 "accion": "registrar en #103 y proponer otro fragmentador en un issue aparte; "
                           "no modificar la regla de A1"}
                for n in ("train", "eval_2015", "gold_v2")
                if (resumen[n]["cobertura_pct"] or 0) < args.umbral_cobertura]
    print(_json_texto({"cobertura": {n: [v["interseccion"], v["candidatos"], v["cobertura_pct"]]
                                     for n, v in resumen.items()}}), end="")
    if bloqueos:
        print(f"BLOQUEO: cobertura < {args.umbral_cobertura}% en "
              f"{', '.join(b['conjunto'] for b in bloqueos)} (queda registrado en el manifiesto).")
    if args.solo_validar:
        print("--solo-validar: no se escribio nada.")
        return 3 if bloqueos and args.exigir_cobertura else 0
    hashes = {}
    for n in ("train", "val", "eval_2015"):
        hashes[n] = {"ids_sha256": dominio.sha_ids(e["context_id"] for e in ent[n]),
                     "labels_sha256": dominio.sha_etiquetas(
                         {e["context_id"]: e["indice"] for e in ent[n]})}
    hashes["gold_v2"] = {"ids_sha256": dominio.sha_ids(e["context_id"] for e in ent["gold_v2"])}
    espec = {t: dominio.sha_especificacion(dominio.especificacion_entrada(t, args.max_len))
             for t in TIPOS_ENTRADA}
    gold_eval = exportar.jsonl_texto(exportar.filas_gold(ent["eval_2015"]))
    ev = {args.salida / f"ids_interseccion_{n}.txt": _lineas(e["context_id"] for e in v)
          for n, v in ent.items()}
    ev[args.salida / "excluidos.csv"] = _csv_texto(COL_EXCLUIDOS, res["excluidos"])
    ev[args.salida / "gold_eval_2015_haiku.jsonl"] = gold_eval
    manifiesto = {
        "estado": r["estado"], "git": _git(), "fuente_etiquetas": r["fuente_etiquetas"],
        "limite": args.limite, "max_len": args.max_len, "umbral_cobertura_pct": args.umbral_cobertura,
        "cobertura": resumen, "bloqueos_cobertura": bloqueos,
        "train_ids_sha256": hashes["train"]["ids_sha256"],
        "train_labels_sha256": hashes["train"]["labels_sha256"],
        "input_spec_sha256": espec, "hashes": hashes,
        "texto_sha256": {t: {n: servicio.huella_entradas(v, t) for n, v in ent.items()}
                         for t in TIPOS_ENTRADA},
        "gold_eval_2015_haiku_sha256": hashlib.sha256(gold_eval.encode("utf-8")).hexdigest(),
        "entradas": {**{f"top3_{n}.csv": _sha_archivo(args.top3 / f"top3_{n}.csv") for n in ent},
                     "manifiesto_ocl": _sha_archivo(args.manifiesto_ocl),
                     "manifiesto_recuperacion": _sha_archivo(args.top3 / "manifiesto_recuperacion.json")},
    }
    ev[args.salida / "manifiesto_entradas.json"] = _json_texto(manifiesto)
    art = {args.artefactos / f"entradas_{n}.jsonl": exportar.jsonl_texto(
        [{k: v for k, v in e.items() if k != "chunks"} for e in v]) for n, v in ent.items()}
    existentes = [p for p in (*ev, *art) if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    for carpeta in (args.salida, args.artefactos):
        carpeta.mkdir(parents=True, exist_ok=True)
    for ruta, contenido in {**ev, **art}.items():
        _publicar(ruta, contenido)
    print(f"Evidencias: {args.salida}\nEntradas con texto (gitignored): {args.artefactos}")
    return 3 if bloqueos and args.exigir_cobertura else 0


def descubrir_corridas(evidencias: Path) -> dict[tuple[str, str, int], Path]:
    corridas = {}
    for d in sorted(Path(evidencias).iterdir()):
        m = comparacion.PATRON_CORRIDA.match(d.name)
        if m and d.is_dir() and (d / "manifiesto.json").is_file():
            corridas[(m[1], m[2], int(m[3]))] = d
    return corridas


def _texto_archivo(ruta: Path) -> str:
    if not Path(ruta).is_file():
        raise FileNotFoundError(f"Falta {ruta}")
    return Path(ruta).read_text(encoding="utf-8")


def evaluar(args) -> int:
    """Puntua las predicciones contra un Gold y compara las corridas (sin reentrenar nunca).

    Sin --gold-v2: eval 2015 con etiquetas Haiku (PROVISIONAL) + una config a4_factorial_v1 por
    semilla + comparacion.{json,csv}. Con --gold-v2 <ruta privada>: puntua las predicciones
    ciegas sobre los ids con gold evaluable y escribe comparacion_gold_v2.{json,csv}."""
    ev = Path(args.evidencias)
    corridas = descubrir_corridas(ev)
    if not corridas:
        raise FileNotFoundError(f"No hay corridas en {ev}: ejecute scripts/entrenar_clasificacion_a4.sh")
    v2 = args.gold_v2 is not None
    ruta_gold = Path(args.gold_v2) if v2 else Path(args.gold or ev / "gold_eval_2015_haiku.jsonl")
    gold, abstenciones = comparacion.indexar_gold(comparacion.leer_jsonl(_texto_archivo(ruta_gold),
                                                                          ruta_gold.name))
    archivo, sufijo = ("predicciones_gold_v2.jsonl", "_gold_v2") if v2 else ("predicciones_eval.jsonl", "")
    metricas, sondeo, shas = {}, {}, {}
    for (enc, ent, sem), d in corridas.items():
        pred = comparacion.indexar_predicciones(
            comparacion.leer_jsonl(_texto_archivo(d / archivo), f"{d.name}/{archivo}"))
        metricas[(enc, ent, sem)] = comparacion.puntuar(gold, pred, exacto=not v2)
        shas[f"{d.name}/{archivo}"] = hashlib.sha256((d / archivo).read_bytes()).hexdigest()
        if not v2:
            guardado = json.loads(_texto_archivo(d / "metricas_eval.json"))
            if abs(guardado["f1_macro"] - metricas[(enc, ent, sem)]["f1_macro"]) > 1e-9:
                raise ValueError(f"{d.name}: metricas_eval.json no coincide con el Gold recalculado.")
        barajado = d / "predicciones_eval_B_barajada.jsonl"
        if not v2 and ent == "B" and barajado.is_file():
            sondeo[(enc, sem)] = comparacion.puntuar(gold, comparacion.indexar_predicciones(
                comparacion.leer_jsonl(barajado.read_text(encoding="utf-8"), barajado.name)))
            shas[f"{d.name}/{barajado.name}"] = hashlib.sha256(barajado.read_bytes()).hexdigest()
    comp = comparacion.comparar(metricas, sondeo)
    comp["procedencia"] = {"gold": ruta_gold.name if not v2 else "<ruta privada>",
                           "gold_sha256": hashlib.sha256(ruta_gold.read_bytes()).hexdigest(),
                           "gold_n": len(gold), "gold_abstenciones": abstenciones,
                           "corridas": [d.name for d in corridas.values()], "predicciones_sha256": shas}
    if v2:
        comp["estado"] = "gold_v2_dado_por_el_usuario_sin_verificar_congelacion_100"
        comp["advertencias"] = ["Este paquete no certifica el Gold v2: confirme la congelacion en #100."]
    salidas = {ev / f"comparacion{sufijo}.json": _json_texto(comp),
               ev / f"comparacion{sufijo}.csv": _csv_texto(comparacion.COLUMNAS_CSV,
                                                           comparacion.filas_csv(comp))}
    if v2:
        for (enc, ent, sem), d in corridas.items():
            salidas[d / "metricas_gold_v2.json"] = _json_texto(
                {"estado": comp["estado"], **metricas[(enc, ent, sem)]})
    else:
        for sem in sorted({s for _, _, s in corridas}):
            celdas = {(e, i): json.loads((d / "manifiesto.json").read_text(encoding="utf-8"))
                      for (e, i, s), d in corridas.items() if s == sem and i in comparacion.ENTRADAS_MATRIZ}
            try:
                salidas[ev / f"a4_config_semilla{sem}.json"] = _json_texto(exportar.config_a4(celdas, sem))
            except ValueError as exc:
                print(f"AVISO: semilla {sem} sin config a4_factorial_v1 ({exc})")
    print(_json_texto({"corridas": len(corridas), "gold_n": len(gold), "gold_abstenciones": abstenciones,
                       "celdas": {k: round(c["agregado"]["f1_macro"]["media"], 4)
                                  for k, c in comp["celdas"].items()},
                       "archivos": sorted(p.name for p in salidas)}), end="")
    if args.solo_validar:
        print("--solo-validar: no se escribio nada.")
        return 0
    existentes = [p for p in salidas if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    for ruta, contenido in salidas.items():
        _publicar(ruta, contenido)
    print(f"Escrito en {ev}")
    return 0


def _sha_manifiesto(ruta: Path) -> str | None:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8")).get("sha256_manifiesto")
    except (OSError, ValueError):
        return None


def leer_csv_top3(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clasificacion_funcion.cli", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("preparar", help="construye train/val/eval y verifica fugas")
    s.add_argument("--solo-validar", action="store_true", help="valida y no escribe nada")
    s.add_argument("--limite", type=int, default=None, help="primeros N casos por conjunto")
    s.add_argument("--fuente-etiquetas", default="haiku", choices=servicio.FUENTES_ETIQUETAS)
    s.add_argument("--salida", type=Path, default=EVIDENCIAS)
    s.add_argument("--artefactos", type=Path, default=ARTEFACTOS)
    s.set_defaults(accion=preparar)
    t = sub.add_parser("recuperar", help="Top-3 denso (SciBERT base, regla de A1) para todos los conjuntos")
    t.add_argument("--solo-validar", action="store_true", help="solo cobertura de chunks; sin modelo")
    t.add_argument("--limite", type=int, default=None, help="primeros N casos por conjunto")
    t.add_argument("--fuente-etiquetas", default="haiku", choices=servicio.FUENTES_ETIQUETAS)
    t.add_argument("--raw", type=Path, default=ad.RAW)
    t.add_argument("--cache-ocl", type=Path, default=ad.CACHE_OCL)
    t.add_argument("--salida", type=Path, default=EVIDENCIAS)
    t.add_argument("--cache", type=Path, default=CACHE_EMBEDDINGS, help="cache de embeddings")
    t.add_argument("--sin-cache", action="store_true")
    t.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    t.add_argument("--batch-size", type=int, default=16)
    t.add_argument("--max-length", type=int, default=512)
    t.add_argument("--regresion-a1", type=Path, default=TOP3_A1,
                   help="top3.csv de A1: los chunk_id deben coincidir en los contextos compartidos")
    t.add_argument("--manifiesto-modelo", type=Path, default=EVIDENCIAS / "manifiesto_modelo_scibert.json")
    t.add_argument("--manifiesto-ocl", type=Path, default=EVIDENCIAS / "manifiesto_ocl.json")
    t.set_defaults(accion=recuperar)
    e = sub.add_parser("entradas", help="interseccion A/B, hashes y Gold JSONL provisional")
    e.add_argument("--solo-validar", action="store_true", help="solo cobertura; no escribe")
    e.add_argument("--limite", type=int, default=None, help="primeros N casos por conjunto")
    e.add_argument("--fuente-etiquetas", default="haiku", choices=servicio.FUENTES_ETIQUETAS)
    e.add_argument("--raw", type=Path, default=ad.RAW)
    e.add_argument("--cache-ocl", type=Path, default=ad.CACHE_OCL)
    e.add_argument("--salida", type=Path, default=EVIDENCIAS)
    e.add_argument("--top3", type=Path, default=EVIDENCIAS, help="carpeta con top3_*.csv")
    e.add_argument("--artefactos", type=Path, default=ENTRADAS_ART)
    e.add_argument("--max-len", type=int, default=512)
    e.add_argument("--umbral-cobertura", type=float, default=UMBRAL_COBERTURA)
    e.add_argument("--exigir-cobertura", action="store_true",
                   help="termina con codigo 3 si la cobertura queda bajo el umbral")
    e.add_argument("--manifiesto-ocl", type=Path, default=EVIDENCIAS / "manifiesto_ocl.json")
    e.set_defaults(accion=entradas)
    v = sub.add_parser("evaluar", help="puntua predicciones, exporta a4_factorial_v1 y compara")
    v.add_argument("--evidencias", type=Path, default=EVIDENCIAS)
    v.add_argument("--gold", type=Path, default=None, help="Gold JSONL (def.: gold_eval_2015_haiku)")
    v.add_argument("--gold-v2", type=Path, default=None,
                   help="RUTA PRIVADA del Gold v2 (JSONL id/gold): puntua las predicciones ciegas")
    v.add_argument("--solo-validar", action="store_true", help="calcula y muestra; no escribe")
    v.set_defaults(accion=evaluar)
    return p


def main(argv: list[str] | None = None, *, fabrica_codificador: Callable | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.accion is recuperar:
            return recuperar(args, fabrica_codificador)
        return args.accion(args)
    except (ValueError, OSError, RuntimeError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
