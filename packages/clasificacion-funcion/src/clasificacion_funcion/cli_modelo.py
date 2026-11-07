"""Punto de entrada con modelo real (torch).

  PYTHONPATH=. uv run --project packages/clasificacion-funcion --group modelo \\
      python -m clasificacion_funcion.cli_modelo recuperar|entrenar|predecir ...

- `recuperar`: Top-3 con SciBERT base (revision de A1), un recuperador unico para ambos encoders.
- `entrenar`: ajusta el clasificador [CLS] de un encoder con una entrada; guarda el mejor
  checkpoint (gitignored) y el manifiesto de entrenamiento.
- `predecir`: puntua eval_2015 (etiquetas Haiku, PROVISIONAL) y el Gold v2 ciego con el mejor
  checkpoint y escribe las evidencias versionables. No reentrena nunca.
"""
import argparse
import json
import sys
from pathlib import Path

from recuperacion_densa.codificador_torch import TorchSciBERTEncoder

from . import adaptador_proyecto_grado as ad
from . import clasificador_torch as ct
from . import cli, dominio, exportar, revision, servicio

CORRIDAS = ad.REPO / "proyecto_de_grado/artifacts/clasificacion_a4/corridas"
MANIFIESTO_ENTRADAS = cli.EVIDENCIAS / "manifiesto_entradas.json"
ENTRADAS_ENTRENABLES = ("A", "B", "B_sin_seccion", "B_barajada")
COMANDOS_MODELO = ("entrenar", "predecir")


def fabrica_recuperador(args) -> TorchSciBERTEncoder:
    """Recuperador unico para ambos encoders: SciBERT base en la revision de A1."""
    model_id, rev = revision.modelo("scibert")
    return TorchSciBERTEncoder(rev, model_id, args.device, args.batch_size, args.max_length,
                               manifiesto=args.manifiesto_modelo)


# ---------------------------------------------------------------- utilidades
def nombre_corrida(encoder: str, entrada: str, semilla: int) -> str:
    return f"{encoder}_{entrada}_{semilla}"


def leer_entradas(carpeta: Path, nombre: str) -> list[dict]:
    ruta = Path(carpeta) / f"entradas_{nombre}.jsonl"
    if not ruta.is_file():
        raise FileNotFoundError(f"Falta {ruta}: ejecute `cli entradas` primero.")
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def leer_manifiesto(ruta: Path) -> dict | None:
    return json.loads(Path(ruta).read_text(encoding="utf-8")) if Path(ruta).is_file() else None


def verificar_entradas(manifiesto: dict | None, nombre: str, entradas: list[dict], tipo: str) -> None:
    """Las entradas en disco deben ser exactamente las que declaro `cli entradas`."""
    if manifiesto is None:
        raise FileNotFoundError(f"Falta {MANIFIESTO_ENTRADAS}: ejecute `cli entradas`.")
    esperado = manifiesto["hashes"][nombre]
    if dominio.sha_ids(e["context_id"] for e in entradas) != esperado["ids_sha256"]:
        raise ValueError(f"Los ids de entradas_{nombre} no coinciden con el manifiesto.")
    if "labels_sha256" in esperado and dominio.sha_etiquetas(
            {e["context_id"]: e["indice"] for e in entradas}) != esperado["labels_sha256"]:
        raise ValueError(f"Las etiquetas de entradas_{nombre} no coinciden con el manifiesto.")
    if tipo != "B_barajada" and servicio.huella_entradas(entradas, tipo) != \
            manifiesto["texto_sha256"][tipo][nombre]:
        raise ValueError(f"El texto de entradas_{nombre} ({tipo}) no coincide con el manifiesto.")


def preparar_conjunto(entradas: list[dict], tipo: str, semilla: int) -> tuple[list[dict], str | None]:
    """B_barajada: permutacion sembrada de los perfiles DENTRO de cada conjunto."""
    if tipo != "B_barajada":
        return entradas, None
    return dominio.barajar_secciones(entradas, semilla)


def dispositivo(nombre: str):
    if nombre == "auto":
        nombre = "cuda" if ct.torch.cuda.is_available() else "cpu"
    if nombre == "cuda" and not ct.torch.cuda.is_available():
        raise RuntimeError("CUDA solicitado pero no esta disponible.")
    return ct.torch.device(nombre)


def cargar_base(args, encoder: str):
    ruta = (Path(args.encoder_ruta) if args.encoder_ruta
            else ct.resolver_encoder(encoder, args.manifiesto_modelo
                                     or cli.EVIDENCIAS / f"manifiesto_modelo_{encoder}.json"))
    return ruta, ct.TokenizadorHF(ruta)


# ---------------------------------------------------------------- entrenar
def entrenar(args) -> int:
    manifiesto = leer_manifiesto(args.manifiesto_entradas)
    train = leer_entradas(args.entradas, "train")
    val = leer_entradas(args.entradas, "val")
    if not args.limite:
        verificar_entradas(manifiesto, "train", train, args.entrada)
        verificar_entradas(manifiesto, "val", val, args.entrada)
    else:
        train, val = train[:args.limite], val[:max(1, args.limite // 4)]
    run = args.corridas / nombre_corrida(args.encoder, args.entrada, args.semilla)
    if run.exists() and any(run.iterdir()):
        raise FileExistsError(f"No se sobrescribe: {run}")
    train, sha_perm_train = preparar_conjunto(train, args.entrada, args.semilla)
    val, sha_perm_val = preparar_conjunto(val, args.entrada, args.semilla)
    ruta, tok = cargar_base(args, args.encoder)
    hp = ct.Hiperparametros(epocas=args.epocas, pesos_clase=not args.sin_pesos)
    ej_train = ct.preparar_ejemplos(train, args.entrada, tok, hp.max_len)
    ej_val = ct.preparar_ejemplos(val, args.entrada, tok, hp.max_len)
    dev = dispositivo(args.device)
    ct.fijar_determinismo(args.semilla)
    modelo = ct.ClasificadorCLS(ruta, args.semilla, hp.dropout)
    resultado = ct.entrenar(modelo, ej_train, ej_val, tok.pad_id, args.semilla, hp, run, dev)
    model_id, rev = (("local", "local") if args.encoder_ruta else revision.modelo(args.encoder))
    resultado.update({
        "estado": servicio.ESTADO, "data_use": "provisional_only", "training_labels": "Haiku",
        "encoder": args.encoder, "model_id": model_id, "model_version": rev,
        "entrada": args.entrada, "experiment_id": nombre_corrida(args.encoder, args.entrada, args.semilla),
        "limite": args.limite, "tokenizer": tok.info(), "git": cli._git(),
        "input_spec_sha256": dominio.sha_especificacion(dominio.especificacion_entrada(
            args.entrada, hp.max_len, args.semilla if args.entrada == "B_barajada" else None)),
        "sha256_permutacion": {"train": sha_perm_train, "val": sha_perm_val}
        if args.entrada == "B_barajada" else None,
        "truncamiento": {"train": ct.resumen_truncamiento(ej_train),
                         "val": ct.resumen_truncamiento(ej_val)},
        "entradas": {"manifiesto_entradas": cli._sha_archivo(args.manifiesto_entradas),
                     "train_ids_sha256": manifiesto["train_ids_sha256"] if manifiesto else None,
                     "train_labels_sha256": manifiesto["train_labels_sha256"] if manifiesto else None},
    })
    (run / "manifiesto_entrenamiento.json").write_text(cli._json_texto(resultado), encoding="utf-8")
    (run / "metricas_val.json").write_text(cli._json_texto(
        {"estado": servicio.ESTADO, **resultado["metricas_val"]}), encoding="utf-8")
    h = resultado["historial"]
    print(f"{run.name}: {resultado['epocas_ejecutadas']} epocas (mejor {resultado['mejor_epoca']}) | "
          f"F1 macro val {resultado['metricas_val']['f1_macro']:.4f} | "
          f"{resultado['segundos_entrenamiento']} s | {h[-1]['loss_train']:.4f} loss final")
    return 0


# ---------------------------------------------------------------- predecir
def predecir(args) -> int:
    run = Path(args.corrida)
    entrenado = json.loads((run / "manifiesto_entrenamiento.json").read_text(encoding="utf-8"))
    entrada_eval = args.entrada_eval or entrenado["entrada"]
    sufijo = "" if entrada_eval == entrenado["entrada"] else f"_{entrada_eval}"
    salida = args.salida or cli.EVIDENCIAS / run.name
    manifiesto = leer_manifiesto(args.manifiesto_entradas)
    semilla, hp = entrenado["semilla"], ct.Hiperparametros(**entrenado["hiperparametros"])
    eval_, gold = leer_entradas(args.entradas, "eval_2015"), leer_entradas(args.entradas, "gold_v2")
    if not args.limite:
        verificar_entradas(manifiesto, "eval_2015", eval_, entrada_eval)
        verificar_entradas(manifiesto, "gold_v2", gold, entrada_eval)
    else:
        eval_, gold = eval_[:args.limite], gold[:args.limite]
    destinos = [salida / f"{n}{sufijo}{e}" for n, e in (
        ("manifiesto", ".json"), ("metricas_eval", ".json"),
        ("predicciones_eval", ".jsonl"), ("predicciones_gold_v2", ".jsonl"))]
    if not sufijo:
        destinos.append(salida / "metricas_val.json")
    existentes = [p for p in destinos if p.exists()]
    if existentes:
        raise FileExistsError(f"No se sobrescribe: {', '.join(str(p) for p in existentes)}")
    eval_, sha_perm_eval = preparar_conjunto(eval_, entrada_eval, semilla)
    gold, sha_perm_gold = preparar_conjunto(gold, entrada_eval, semilla)
    encoder = entrenado["encoder"]
    ruta, tok = cargar_base(args, encoder)
    if tok.info() != entrenado["tokenizer"]:
        raise RuntimeError("La huella del tokenizer difiere de la usada al entrenar.")
    dev = dispositivo(args.device)
    modelo = ct.ClasificadorCLS(ruta, semilla, hp.dropout)
    ct.cargar_checkpoint(modelo, run / "model.safetensors", entrenado["checkpoint_sha256"])
    modelo.to(dev)
    ej_eval = ct.preparar_ejemplos(eval_, entrada_eval, tok, hp.max_len)
    ej_gold = ct.preparar_ejemplos(gold, entrada_eval, tok, hp.max_len)
    p_eval, l_eval = ct.predecir_probabilidades(modelo, ej_eval, tok.pad_id, dev, args.batch_size)
    p_gold, l_gold = ct.predecir_probabilidades(modelo, ej_gold, tok.pad_id, dev, args.batch_size)
    comun = {"model_id": entrenado["model_id"], "model_version": entrenado["model_version"],
             "experiment_id": entrenado["experiment_id"] + sufijo}
    sha_gold_eval = manifiesto and manifiesto.get("gold_eval_2015_haiku_sha256")
    sha_gold_v2 = manifiesto and manifiesto["hashes"]["gold_v2"]["ids_sha256"]
    f_eval = ct.filas_prediccion(ej_eval, p_eval, l_eval, gold_manifest_sha256=sha_gold_eval, **comun)
    f_gold = ct.filas_prediccion(ej_gold, p_gold, l_gold, gold_manifest_sha256=sha_gold_v2, **comun)
    metricas = dominio.metricas([e["indice"] for e in ej_eval], [f["pred_index"] for f in f_eval])
    salida.mkdir(parents=True, exist_ok=True)
    final = {k: v for k, v in entrenado.items() if k != "historial"}
    final.update({
        "entrada_eval": entrada_eval, "git_prediccion": cli._git(),
        "sha256_permutacion_eval": {"eval_2015": sha_perm_eval, "gold_v2": sha_perm_gold}
        if entrada_eval == "B_barajada" else None,
        "truncamiento_eval": {"eval_2015": ct.resumen_truncamiento(ej_eval),
                              "gold_v2": ct.resumen_truncamiento(ej_gold)},
        "casos": {**entrenado["casos"], "eval_2015": len(ej_eval), "gold_v2": len(ej_gold)},
        "latencia_ms_media": sum(l_eval + l_gold) / max(1, len(l_eval) + len(l_gold)),
    })
    cli._publicar(salida / f"manifiesto{sufijo}.json", cli._json_texto(final))
    cli._publicar(salida / f"metricas_eval{sufijo}.json", cli._json_texto(
        {"estado": servicio.ESTADO, "entrada_eval": entrada_eval, **metricas}))
    cli._publicar(salida / f"predicciones_eval{sufijo}.jsonl", exportar.jsonl_texto(f_eval))
    cli._publicar(salida / f"predicciones_gold_v2{sufijo}.jsonl", exportar.jsonl_texto(f_gold))
    if not sufijo:
        cli._publicar(salida / "metricas_val.json",
                      (run / "metricas_val.json").read_text(encoding="utf-8"))
    print(f"{run.name}{sufijo}: F1 macro eval (PROVISIONAL, Haiku) {metricas['f1_macro']:.4f} | "
          f"accuracy {metricas['accuracy']:.4f} | n={metricas['n']} | gold_v2 n={len(f_gold)} | {salida}")
    return 0


# ---------------------------------------------------------------- CLI
def parser_modelo() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clasificacion_funcion.cli_modelo", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="comando", required=True)

    def comunes(s):
        s.add_argument("--entradas", type=Path, default=cli.ENTRADAS_ART)
        s.add_argument("--manifiesto-entradas", type=Path, default=MANIFIESTO_ENTRADAS)
        s.add_argument("--manifiesto-modelo", type=Path, default=None)
        s.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
        s.add_argument("--encoder-ruta", type=Path, default=None,
                       help="SOLO PRUEBAS: carpeta local del encoder (omite la verificacion SHA)")
        s.add_argument("--limite", type=int, default=None, help="dry-run: primeros N casos")

    e = sub.add_parser("entrenar", help="entrena un encoder con una entrada")
    comunes(e)
    e.add_argument("--encoder", required=True, choices=revision.ENCODERS)
    e.add_argument("--entrada", required=True, choices=ENTRADAS_ENTRENABLES)
    e.add_argument("--semilla", type=int, required=True)
    e.add_argument("--epocas", type=int, default=ct.Hiperparametros.epocas)
    e.add_argument("--sin-pesos", action="store_true", help="CE sin pesos inversos a la frecuencia")
    e.add_argument("--corridas", type=Path, default=CORRIDAS)
    e.set_defaults(accion=entrenar)

    q = sub.add_parser("predecir", help="predice eval_2015 y Gold v2 con el mejor checkpoint")
    comunes(q)
    q.add_argument("--corrida", type=Path, required=True)
    q.add_argument("--salida", type=Path, default=None)
    q.add_argument("--entrada-eval", choices=ENTRADAS_ENTRENABLES, default=None,
                   help="entrada con la que se evalua (def.: la del entrenamiento); "
                        "B_barajada sobre un modelo B es el sondeo de secciones")
    q.add_argument("--batch-size", type=int, default=16)
    q.set_defaults(accion=predecir)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMANDOS_MODELO:
        return cli.main(argv, fabrica_codificador=fabrica_recuperador)
    args = parser_modelo().parse_args(argv)
    try:
        return args.accion(args)
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
