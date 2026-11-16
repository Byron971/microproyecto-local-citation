"""Anotacion de citas con Sonnet via Claude Code (issue #104, seccion 6 del plan).

  uv run --project packages/clasificacion-funcion python scripts/anotar_sonnet.py <comando> ...

  preparar          lotes de V ∪ D1 (sin etiquetas) en artifacts/anotacion_sonnet/lotes/
  piloto-preparar   ~300 citas con referencia en artifacts/anotacion_sonnet/lotes_piloto/
  anotar            llama a `claude -p --model sonnet` por lote pendiente (reanudable)
  informe-piloto    acuerdo con las referencias y costo extrapolado
  consolidar        une salidas/ en etiquetas_sonnet.csv
  verificar-aislamiento  una llamada minima: costo fijo por llamada y lo que el modelo dice ver

Cada llamada corre aislada (directorio vacio, sin herramientas ni MCP) y no ve pre-etiquetas ni
otras pasadas. Las salidas y el registro quedan versionados en proyecto_de_grado/anotacion/sonnet/."""
import argparse
import json
import sys
from functools import partial
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from clasificacion_funcion import adaptador_proyecto_grado as ad  # noqa: E402
from clasificacion_funcion import dominio  # noqa: E402
from clasificacion_funcion import anotacion_sonnet as an  # noqa: E402
from clasificacion_funcion import seleccion_datos as sd  # noqa: E402

SONNET = REPO / "proyecto_de_grado/anotacion/sonnet"
ARTIFACTS = REPO / "proyecto_de_grado/artifacts/anotacion_sonnet"
PROMPT = SONNET / "prompt_v2.md"
ERRORES = ARTIFACTS / "errores"
ITEMS_TALLER = REPO / "proyecto_de_grado/anotacion/taller/items_meta.json"


def _casos(ids, fuentes, papers):
    """Casos con titulo y abstract (los mismos que usa la entrada A); el resto se omite."""
    casos, omitidos = {}, 0
    for cid in ids:
        ctx = fuentes.contextos[cid]
        p = papers.get(ctx["refid"]) or {}
        titulo, resumen = (p.get("title") or "").strip(), (p.get("abstract") or "").strip()
        if titulo and resumen:
            casos[cid] = {"contexto": ctx["masked_text"], "titulo": titulo, "abstract": resumen}
        else:
            omitidos += 1
    return casos, omitidos


def preparar(args) -> int:
    fuentes, papers = ad.cargar_fuentes_104(), ad.cargar_papers()
    res = sd.construir_todo(fuentes)
    ids = an.seleccionar_para_sonnet(res["v"], res["variantes"]["qlora_p50"])
    casos, omitidos = _casos(ids, fuentes, papers)
    lotes = an.crear_lotes(sorted(casos), args.tam)
    an.escribir_lotes(lotes, casos, ARTIFACTS / "lotes")
    manifiesto = {"semilla": an.SEMILLA, "tam_lote": args.tam, "ids_v_d1": len(ids),
                  "sin_titulo_abstract": omitidos, "ids": len(casos), "lotes": len(lotes),
                  "sha256_ids": dominio.sha_ids(sorted(casos)),
                  "sha256_prompt": an.sha_prompt(PROMPT.read_text(encoding="utf-8")),
                  "sha256_manifiesto_datos": sd.sha_archivo(
                      REPO / "proyecto_de_grado/docs/evidencias_experimentos_104/manifiesto_datos.json")
                  if (REPO / "proyecto_de_grado/docs/evidencias_experimentos_104/manifiesto_datos.json").exists() else None}
    (SONNET / "manifiesto_lotes.json").write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    print(f"{len(casos)} citas ({omitidos} sin titulo/abstract) en {len(lotes)} lotes -> {ARTIFACTS / 'lotes'}")
    return 0


def piloto_preparar(args) -> int:
    fuentes, papers = ad.cargar_fuentes_104(), ad.cargar_papers()
    taller = {x["id"]: x["label"] for x in json.loads(ITEMS_TALLER.read_text(encoding="utf-8"))}
    sel = an.seleccionar_piloto(taller, fuentes.gpt, fuentes.jurado, fuentes.contextos, args.n_jurado)
    casos, omitidos = _casos(sel["ids"], fuentes, papers)
    lotes = an.crear_lotes(sorted(casos), args.tam)
    an.escribir_lotes(lotes, casos, ARTIFACTS / "lotes_piloto")
    refs = {n: {c: e for c, e in r.items() if c in casos} for n, r in sel["referencias"].items()}
    (SONNET / "piloto").mkdir(parents=True, exist_ok=True)
    (SONNET / "piloto/referencias.json").write_text(json.dumps(refs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"piloto: {len(casos)} citas ({omitidos} omitidas) en {len(lotes)} lotes; "
          f"referencias: { {n: len(r) for n, r in refs.items()} }")
    return 0


def anotar(args) -> int:
    base = SONNET / "piloto" if args.piloto else SONNET
    lotes = ARTIFACTS / ("lotes_piloto" if args.piloto else "lotes")
    salidas = base / ({1: "salidas", 2: "salidas_pasada2", 3: "salidas_pasada3"}[args.pasada]
                      if not args.piloto else "salidas")
    plantilla = PROMPT.read_text(encoding="utf-8")
    ejecutar = partial(an.ejecutar_claude, modelo=args.modelo, binario=args.claude, timeout=args.timeout)
    r = an.anotar_pendientes(lotes, salidas, plantilla, ejecutar, base / "registro.jsonl", args.pasada,
                             args.max_lotes, args.paralelo, ERRORES)
    print(r)
    return 1 if r["error"] else 0


def informe(args) -> int:
    base = SONNET / "piloto"
    refs = json.loads((base / "referencias.json").read_text(encoding="utf-8"))
    total = json.loads((SONNET / "manifiesto_lotes.json").read_text(encoding="utf-8"))["lotes"] \
        if (SONNET / "manifiesto_lotes.json").exists() else args.lotes_totales
    rep = an.informe_piloto(base / "salidas", refs, base / "registro.jsonl", total)
    (base / "informe_piloto.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


def consolidar(args) -> int:
    n = an.consolidar(SONNET / "salidas", SONNET / "etiquetas_sonnet.csv")
    print(f"{n} filas -> {SONNET / 'etiquetas_sonnet.csv'}")
    return 0


def verificar_aislamiento(args) -> int:
    ejecutar = partial(an.ejecutar_claude, modelo=args.modelo, binario=args.claude, timeout=args.timeout)
    rep = an.verificar_aislamiento(ejecutar)
    SONNET.mkdir(parents=True, exist_ok=True)
    (SONNET / "verificacion_aislamiento.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("preparar")
    a.add_argument("--tam", type=int, default=an.TAM_LOTE)
    a.set_defaults(f=preparar)
    a = sub.add_parser("piloto-preparar")
    a.add_argument("--tam", type=int, default=an.TAM_LOTE)
    a.add_argument("--n-jurado", type=int, default=110)
    a.set_defaults(f=piloto_preparar)
    a = sub.add_parser("anotar")
    a.add_argument("--piloto", action="store_true")
    a.add_argument("--pasada", type=int, choices=(1, 2, 3), default=1)
    a.add_argument("--max-lotes", type=int, default=None)
    a.add_argument("--paralelo", type=int, default=4)
    a.add_argument("--modelo", default="sonnet")
    a.add_argument("--claude", default="claude")
    a.add_argument("--timeout", type=float, default=900)
    a.set_defaults(f=anotar)
    a = sub.add_parser("informe-piloto")
    a.add_argument("--lotes-totales", type=int, default=167)
    a.set_defaults(f=informe)
    a = sub.add_parser("consolidar")
    a.set_defaults(f=consolidar)
    a = sub.add_parser("verificar-aislamiento")
    a.add_argument("--modelo", default="sonnet")
    a.add_argument("--claude", default="claude")
    a.add_argument("--timeout", type=float, default=300)
    a.set_defaults(f=verificar_aislamiento)
    args = p.parse_args(argv)
    return args.f(args)


if __name__ == "__main__":
    raise SystemExit(main())
