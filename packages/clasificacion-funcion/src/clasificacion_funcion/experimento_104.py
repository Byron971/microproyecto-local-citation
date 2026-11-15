"""Una corrida completa del issue #104: casos -> entrenar -> evaluar -> registrar en MLflow.

Importa torch y mlflow (grupos `modelo` + `experimentos`). El notebook solo orquesta."""
import dataclasses
import json
import math
import random
import time
from pathlib import Path

import mlflow
import numpy as np
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from . import clasificador_torch as ct
from . import dominio, registro_mlflow, revision, seleccion_datos
from .cli import EVIDENCIAS
from .cli_modelo import dispositivo

MODOS_PERDIDA = ("duro", "kd", "ponderado")
ENTRADAS_104 = ("A", "B", "B_barajada", "B_sin_seccion", "AB", "B_aleatorio", "AB_aleatorio", "C0")
ENTRADAS_GOLD = ("A", "B", "AB")
CAMPOS_PREDICCION_CIEGA = ("context_id", "pred", "probs")


def _ruta_encoder(encoder: str, manifiesto: Path | None) -> Path:
    return ct.resolver_encoder(encoder, manifiesto or EVIDENCIAS / f"manifiesto_modelo_{encoder}.json")


# ---------------------------------------------------------------- casos de la entrada A
def casos_a(filas: list[dict], f: seleccion_datos.Fuentes, papers: dict,
            etiqueta: str | None = "etiqueta_entrenamiento") -> tuple[list[dict], dict]:
    """Entrada A (contexto + titulo + abstract del citado). Omite citas sin titulo/abstract.
    Con `etiqueta=None` (Gold ciego) los casos no llevan `indice`."""
    casos, omitidas = [], 0
    for x in filas:
        ctx = f.contextos[x["context_id"]]
        paper = papers.get(ctx["refid"]) or {}
        titulo, abstract = (paper.get("title") or "").strip(), (paper.get("abstract") or "").strip()
        if not titulo or not abstract:
            omitidas += 1
            continue
        casos.append({"context_id": x["context_id"], "citing_id": x["citing_id"],
                      "cited_id": ctx["refid"], "citation_context": ctx["masked_text"],
                      "titulo": titulo, "abstract": abstract,
                      "indice": dominio.normalizar_etiqueta(x[etiqueta]) if etiqueta else None,
                      "_fila": x})
    return casos, {"entrada": len(filas), "casos": len(casos), "sin_titulo_abstract": omitidas}


# ---------------------------------------------------------------- casos de la entrada B
def casos_b(filas: list[dict], f: seleccion_datos.Fuentes, papers: dict, entradas_b: dict[str, dict],
            etiqueta: str | None = "etiqueta_entrenamiento") -> tuple[list[dict], dict]:
    """Entrada B: los mismos casos que la A (campos de `casos_a`) mas el `top3` del citado.

    `entradas_b` = {context_id: entrada de `servicio.interseccion`}. Falla cerrado si alguna fila no
    esta en `entradas_b`: A y B deben entrenar exactamente con las mismas citas (el llamador filtra
    antes a la cobertura de B). Conserva `_fila`, asi que `con_modo_perdida` (kd) funciona igual."""
    base, info = casos_a(filas, f, papers, etiqueta)
    faltan = [c["context_id"] for c in base if c["context_id"] not in entradas_b]
    if faltan:
        raise ValueError(f"{len(faltan)} citas sin entrada B (filtre a la cobertura antes): {faltan[:3]}")
    casos = [{**c, "top3": entradas_b[c["context_id"]]["top3"]} for c in base]
    return casos, info


def casos_entrada(entrada: str, filas: list[dict], f: seleccion_datos.Fuentes, papers: dict,
                  entradas_b: dict[str, dict] | None = None,
                  etiqueta: str | None = "etiqueta_entrenamiento") -> tuple[list[dict], dict]:
    """Casos de una entrada de `ENTRADAS_104`. A y C0 usan `casos_a` (C0 ignora titulo y abstract al
    construir los segmentos, pero conserva las mismas citas). Las demas usan `casos_b`, que ya trae
    titulo y abstract (los usan AB y AB_aleatorio). B_aleatorio y AB_aleatorio reciben en
    `entradas_b` las entradas con chunks al azar. B_barajada aun sin barajar: ver `_barajar`."""
    if entrada not in ENTRADAS_104:
        raise ValueError(f"Entrada no soportada en #104: {entrada!r}")
    if entrada in ("A", "C0"):
        return casos_a(filas, f, papers, etiqueta)
    if entradas_b is None:
        raise ValueError(f"La entrada {entrada} requiere `entradas_b`.")
    return casos_b(filas, f, papers, entradas_b, etiqueta)


def _barajar(entrada: str, casos: list[dict], semilla: int) -> list[dict]:
    """`B_barajada`: permutacion sembrada de los perfiles de seccion dentro del conjunto."""
    return dominio.barajar_secciones(casos, semilla)[0] if entrada == "B_barajada" else casos


def config_corrida(config: dict, encoder: str, semilla: int, modo: str, hp: ct.Hiperparametros,
                   dry: bool, entrada: str = "A", top3_sha: str = "") -> dict:
    """Config de un run (base de `config_sha` y de la reanudacion). Con entrada A es identica a la
    de las Partes 1 y 2 de #104; `top3_sha` solo se agrega con las entradas con chunks."""
    con_chunks = entrada in dominio.ENTRADAS_CON_CHUNKS
    if con_chunks and not top3_sha:
        raise ValueError("Las entradas con chunks requieren `top3_sha` (huella de los chunks usados).")
    cfg = {**config, "encoder": encoder, "semilla": semilla, "modo_perdida": modo, "entrada": entrada,
           "dry": dry, **{f"hp_{k}": v for k, v in hp.__dict__.items()}}
    return {**cfg, "top3_sha": top3_sha} if con_chunks else cfg


def nombre_run(encoder: str, entrada: str, pista: str, lr: float, semilla: int, repeticion: int = 0) -> str:
    """`{encoder}-{entrada}-{pista}-lr{lr:g}-s{semilla}`, con `-rep{n}` si `repeticion > 0`."""
    nombre = f"{encoder}-{entrada}-{pista}-lr{float(lr):g}-s{semilla}"
    return f"{nombre}-rep{repeticion}" if repeticion > 0 else nombre


def con_modo_perdida(casos: list[dict], modo: str) -> list[dict]:
    """`kd`: objetivo = dist del QLoRA renormalizada (one-hot si la etiqueta no es del QLoRA).
    `ponderado`: peso por muestra = p del QLoRA (1.0 en etiquetas de Haiku o jurado)."""
    if modo not in MODOS_PERDIDA:
        raise ValueError(f"Modo de perdida desconocido: {modo!r}")
    salida = []
    for c in casos:
        fila, e = c["_fila"], dict(c)
        q = fila["qlora"]
        if modo == "kd" and fila["fuente"] == "qlora" and q:
            e["objetivo"] = seleccion_datos.dist9(q["dist"])
        elif modo == "kd":
            e["objetivo"] = [1.0 if i == c["indice"] else 0.0 for i in range(dominio.N_CLASES)]
        if modo == "ponderado":
            e["peso"] = float(q["p"]) if fila["fuente"] == "qlora" and q else 1.0
        salida.append(e)
    return salida


def conjuntos_eval(v_filas: list[dict], f: seleccion_datos.Fuentes) -> dict[str, list[dict]]:
    """V completa (`val`, con las etiquetas de la pista), `val_mixta` (etiqueta = `etiqueta`),
    `val_sonnet` (etiqueta = Sonnet), `dev_haiku` y `ref_gpt` (subconjuntos de V)."""
    def con(filas, clave):
        return [{**x, "etiqueta_entrenamiento": x[clave]} for x in filas if x.get(clave)]
    con_sonnet = [{**x, "etiqueta_entrenamiento": x["sonnet"]["label"]}
                  for x in v_filas if x.get("sonnet")]
    return {"val": v_filas,
            "val_mixta": con(v_filas, "etiqueta"),
            "val_sonnet": con_sonnet,
            "dev_haiku": con([x for x in v_filas if x["context_id"] in f.haiku_val], "haiku"),
            "ref_gpt": con([x for x in v_filas if x["context_id"] in f.gpt], "gpt")}


def _limpio(casos: list[dict]) -> list[dict]:
    return [{k: v for k, v in c.items() if k != "_fila"} for c in casos]


def _predicciones(modelo, ejemplos, pad_id, dev) -> tuple[list[int], list[list[float]], float]:
    probs, lat = ct.predecir_probabilidades(modelo, ejemplos, pad_id, dev, 16)
    pred = [max(range(dominio.N_CLASES), key=lambda i: (p[i], -i)) for p in probs]
    return pred, probs, sum(lat) / max(1, len(lat))


# ---------------------------------------------------------------- corrida de un encoder
def _evaluar_conjuntos(sets: dict[str, list[dict]], modelo, tok, dev, hp: ct.Hiperparametros,
                       f: seleccion_datos.Fuentes, papers: dict, omitir: set[str] = frozenset(),
                       entrada: str = "A", entradas_b: dict[str, dict] | None = None, semilla: int = 42
                       ) -> dict[str, list[dict]]:
    """Predice y registra (en el run activo) cada conjunto salvo los de `omitir`. Devuelve las
    predicciones de `val` (para `predicciones_val.jsonl`) si se evaluo."""
    salida = {}
    for prefijo, filas in sets.items():
        if prefijo in omitir or not filas:
            continue
        casos, _ = casos_entrada(entrada, filas, f, papers, entradas_b)
        if not casos:
            continue
        ej = ct.preparar_ejemplos(_limpio(_barajar(entrada, casos, semilla)), entrada, tok, hp.max_len)
        pred, probs, lat = _predicciones(modelo, ej, tok.pad_id, dev)
        m = dominio.metricas([e["indice"] for e in ej], pred)
        registro_mlflow.log_metricas(prefijo, m)
        registro_mlflow.log_matriz_confusion(m, prefijo)
        mlflow.log_metric(f"{prefijo}_latencia_ms", lat)
        if prefijo == "val":
            salida["val"] = [{"context_id": e["context_id"], "pred": p, "probs": pr}
                             for e, p, pr in zip(ej, pred, probs)]
    return salida


def _cargar_modelo(run_dir: Path, encoder: str, manifiesto_modelo: Path | None = None) -> tuple:
    """(manifiesto, hp, tokenizador, dispositivo, modelo) desde la carpeta de un run, verificando
    el sha del checkpoint. Camino comun de `smoke_inferencia` y `reevaluar_checkpoint`."""
    man = json.loads((run_dir / "manifiesto_entrenamiento.json").read_text(encoding="utf-8"))
    hp = ct.Hiperparametros(**man["hiperparametros"])
    ruta = _ruta_encoder(encoder, manifiesto_modelo)
    tok = ct.TokenizadorHF(ruta)
    dev = dispositivo("auto")
    modelo = ct.ClasificadorCLS(ruta, man["semilla"], hp.dropout)
    ct.cargar_checkpoint(modelo, run_dir / "model.safetensors", man["checkpoint_sha256"])
    modelo.to(dev)
    return man, hp, tok, dev, modelo


def preparar_corrida(config: dict, train_filas: list[dict], v_filas: list[dict], *, encoder: str,
                     semilla: int, modo: str, hp: ct.Hiperparametros, dry: bool, entrada: str,
                     top3_sha: str, dev_filas: list[dict] | None = None) -> tuple:
    """(config, hp, train, v, dev) de un run: `hp.lr` pasa a `float` (un lr leido de JSON da el mismo
    sha), DRY recorta a 1 epoca y 64 casos por conjunto, y con `dev_filas` el config lleva `dev_sha`."""
    hp = dataclasses.replace(hp, lr=float(hp.lr))
    if dry:
        hp = dataclasses.replace(hp, epocas=1)
        train_filas, v_filas = train_filas[:64], v_filas[:64]
        dev_filas = dev_filas[:64] if dev_filas is not None else None
    config = config_corrida(config, encoder, semilla, modo, hp, dry, entrada, top3_sha)
    if dev_filas is not None:
        if not dev_filas:
            raise ValueError("dev vacio: la parada temprana necesita casos.")
        config["dev_sha"] = dominio.sha_ids(x["context_id"] for x in dev_filas)
    return config, hp, train_filas, v_filas, dev_filas


def _log_epoca_parada(registro: dict) -> None:
    """Metricas por epoca cuando la parada temprana usa dev: prefijo `parada_`."""
    mlflow.log_metrics({"loss_train": registro["loss_train"], "parada_f1_macro_epoca": registro["f1_macro_val"],
                        "parada_accuracy_epoca": registro["accuracy_val"], "segundos_epoca": registro["segundos"]},
                       step=registro["epoca"])


def entrenar_y_registrar(nombre: str, config: dict, train_filas: list[dict], v_filas: list[dict],
                         f: seleccion_datos.Fuentes, papers: dict, carpeta: Path, *,
                         encoder: str = "scibert", semilla: int = 42, modo: str = "duro",
                         hp: ct.Hiperparametros | None = None, dry: bool = False,
                         manifiesto_datos_sha: str = "", manifiesto_modelo: Path | None = None,
                         entrada: str = "A", entradas_b: dict[str, dict] | None = None,
                         top3_sha: str = "", dev_filas: list[dict] | None = None,
                         tags_extra: dict | None = None) -> str:
    """Entrena, evalua en V/dev_haiku/ref_gpt y registra todo. Devuelve el run_id (el del run
    FINISHED previo si ya existia: reanudacion). Los checkpoints quedan en `carpeta/<nombre>`, en MLflow solo
    su ruta y sha. Las entradas con chunks requieren `entradas_b` y `top3_sha`.

    Sin `dev_filas` la parada temprana y la evaluacion usan `v_filas`. Con `dev_filas` la parada usa
    dev (`dev_sha` entra en el config, el manifiesto lleva `conjunto_parada` y `metricas_parada`, MLflow
    `parada_*`) y `v_filas` solo se evalua. `tags_extra` se registran como tags: no cambian el sha."""
    config, hp, train_filas, v_filas, dev_filas = preparar_corrida(
        config, train_filas, v_filas, encoder=encoder, semilla=semilla, modo=modo, hp=hp or ct.Hiperparametros(),
        dry=dry, entrada=entrada, top3_sha=top3_sha, dev_filas=dev_filas)
    tr_casos, info_tr = casos_entrada(entrada, train_filas, f, papers, entradas_b)
    v_casos, info_v = casos_entrada(entrada, v_filas, f, papers, entradas_b)
    dev_casos, info_dev = (casos_entrada(entrada, dev_filas, f, papers, entradas_b) if dev_filas is not None
                           else (None, None))
    sets = conjuntos_eval(v_filas, f)
    tags = {"manifiesto_datos_sha": manifiesto_datos_sha, "casos_train": str(info_tr),
            "casos_val": str(info_v), "entrada": entrada,
            **({"top3_sha": top3_sha, "regla_antifuga_b": "L2_citados_citantes+L4_texto+L5_mismos_ids"}
               if entrada in dominio.ENTRADAS_CON_CHUNKS else {}),
            **({"conjunto_parada": "dev", "casos_dev": str(info_dev)} if dev_casos is not None else {}),
            **{k: str(v) for k, v in (tags_extra or {}).items()}}
    with registro_mlflow.abrir_corrida(nombre, config, tags, ct.hardware()) as run:
        if run is None:  # reanudacion: devuelve el run FINISHED existente
            return registro_mlflow.corrida_terminada(registro_mlflow.sha_config(config))
        ruta = _ruta_encoder(encoder, manifiesto_modelo)
        tok = ct.TokenizadorHF(ruta)
        dev = dispositivo("auto")
        ej_train = ct.preparar_ejemplos(
            _limpio(con_modo_perdida(_barajar(entrada, tr_casos, semilla), modo)), entrada, tok, hp.max_len)
        parada = dev_casos if dev_casos is not None else v_casos
        ej_parada = ct.preparar_ejemplos(_limpio(_barajar(entrada, parada, semilla)), entrada, tok, hp.max_len)
        ct.fijar_determinismo(semilla)
        modelo = ct.ClasificadorCLS(ruta, semilla, hp.dropout)
        salida = Path(carpeta) / nombre
        resultado = ct.entrenar(modelo, ej_train, ej_parada, tok.pad_id, semilla, hp, salida, dev,
                                al_terminar_epoca=(_log_epoca_parada if dev_casos is not None
                                                   else registro_mlflow.log_epoca))
        ct.cargar_checkpoint(modelo, salida / "model.safetensors", resultado["checkpoint_sha256"])
        mlflow.set_tags({"checkpoint": str(salida / "model.safetensors"),
                         "checkpoint_sha256": resultado["checkpoint_sha256"],
                         "model_version": revision.modelo(encoder)[1]})
        registro_mlflow.log_dataset("train", [c["context_id"] for c in tr_casos],
                                    [c["_fila"]["etiqueta_entrenamiento"] for c in tr_casos], "training")
        registro_mlflow.log_dataset("val", [c["context_id"] for c in v_casos],
                                    [c["_fila"]["etiqueta_entrenamiento"] for c in v_casos], "validation")
        if dev_casos is not None:
            registro_mlflow.log_dataset("dev", [c["context_id"] for c in dev_casos],
                                        [c["_fila"]["etiqueta_entrenamiento"] for c in dev_casos], "validation")
            registro_mlflow.log_metricas("parada", resultado["metricas_val"])
        mlflow.log_metric("segundos_entrenamiento", resultado["segundos_entrenamiento"])
        if resultado.get("gpu_mem_pico_gb") is not None:
            mlflow.log_metric("gpu_mem_pico_gb", resultado["gpu_mem_pico_gb"])
        pred_val = _evaluar_conjuntos(sets, modelo, tok, dev, hp, f, papers, entrada=entrada,
                                      entradas_b=entradas_b, semilla=semilla).get("val")
        (salida / "predicciones_val.jsonl").write_text(
            "\n".join(json.dumps(r) for r in pred_val or []) + "\n", encoding="utf-8")
        mlflow.log_artifact(str(salida / "predicciones_val.jsonl"))
        manifiesto = {**resultado, "config": config, "git": registro_mlflow.estado_git(),
                      "estado": registro_mlflow.ESTADO}
        if dev_casos is not None:
            manifiesto = {**{k: v for k, v in manifiesto.items() if k != "metricas_val"},
                          "conjunto_parada": "dev", "metricas_parada": resultado["metricas_val"]}
        (salida / "manifiesto_entrenamiento.json").write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        mlflow.log_artifact(str(salida / "manifiesto_entrenamiento.json"))
        return run.info.run_id


# ---------------------------------------------------------------- linea base TF-IDF + LR
def linea_base_tfidf(nombre: str, config: dict, train_filas: list[dict], v_filas: list[dict],
                     f: seleccion_datos.Fuentes, papers: dict, dry: bool = False) -> str | None:
    if dry:
        train_filas, v_filas = train_filas[:64], v_filas[:64]
    tr, _ = casos_a(train_filas, f, papers)
    sets = conjuntos_eval(v_filas, f)
    config = {**config, "modelo": "tfidf_lr", "entrada": "A", "dry": dry}
    with registro_mlflow.abrir_corrida(nombre, config, {}, ct.hardware()) as run:
        if run is None:  # reanudacion: devuelve el run FINISHED existente
            return registro_mlflow.corrida_terminada(registro_mlflow.sha_config(config))
        texto = lambda c: f"{c['citation_context']} {c['titulo']} {c['abstract']}"  # noqa: E731
        t0 = time.perf_counter()
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=200_000)
        x = vec.fit_transform([texto(c) for c in tr])
        clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(x, [c["indice"] for c in tr])
        mlflow.log_metric("segundos_entrenamiento", time.perf_counter() - t0)
        for prefijo, filas in sets.items():
            casos, _ = casos_a(filas, f, papers)
            if casos:
                pred = [int(i) for i in clf.predict(vec.transform([texto(c) for c in casos]))]
                m = dominio.metricas([c["indice"] for c in casos], pred)
                registro_mlflow.log_metricas(prefijo, m)
        return run.info.run_id


# ---------------------------------------------------------------- smoke test de inferencia
def smoke_inferencia(run_dir: Path, encoder: str, v_filas: list[dict], f: seleccion_datos.Fuentes,
                     papers: dict, n: int = 32, manifiesto_modelo: Path | None = None,
                     entrada: str = "A", entradas_b: dict[str, dict] | None = None) -> dict:
    """Carga el checkpoint verificando su sha, predice `n` casos de V y exige reproducir las
    predicciones registradas al entrenar. `entrada` debe ser la del run."""
    man, hp, tok, dev, modelo = _cargar_modelo(run_dir, encoder, manifiesto_modelo)
    lineas = (run_dir / "predicciones_val.jsonl").read_text(encoding="utf-8").splitlines()
    registradas = {r["context_id"]: r for r in map(json.loads, (l for l in lineas if l.strip()))}
    casos, _ = casos_entrada(entrada, [x for x in v_filas if x["context_id"] in registradas], f, papers,
                             entradas_b)
    # B_barajada: el barajado depende del conjunto completo (como al entrenar), luego se recorta a `n`
    casos = _barajar(entrada, casos, man["semilla"])[:n]
    ej = ct.preparar_ejemplos(_limpio(casos), entrada, tok, hp.max_len)
    pred, probs, lat = _predicciones(modelo, ej, tok.pad_id, dev)
    distintas = [e["context_id"] for e, p in zip(ej, pred) if p != registradas[e["context_id"]]["pred"]]
    dif = max((abs(a - b) for e, pr in zip(ej, probs) for a, b in zip(pr, registradas[e["context_id"]]["probs"])),
              default=0.0)
    ok = bool(ej) and not distintas and dif < 1e-2
    return {"run": run_dir.name, "encoder": encoder, "casos": len(ej), "ok": ok,
            "predicciones_distintas": len(distintas), "max_dif_probabilidad": dif,
            "latencia_ms": lat, "checkpoint_sha256": man["checkpoint_sha256"]}


# ---------------------------------------------------------------- predicciones ciegas (Gold)
def casos_gold(ids: list[str], f: seleccion_datos.Fuentes, papers: dict, entrada: str = "A",
               entradas_b: dict[str, dict] | None = None) -> list[dict]:
    """Casos SIN etiqueta (`indice` None) de los `ids` del Gold, para `predecir_gold`. Con B, solo
    los que tienen entrada B (la interseccion de cobertura la decide el llamador)."""
    if entrada not in ENTRADAS_GOLD:
        raise ValueError("Las predicciones sobre el Gold son solo para A, B y AB.")
    filas = [{"context_id": c, "citing_id": f.contextos[c]["citing_id"]} for c in sorted(ids)]
    return casos_entrada(entrada, filas, f, papers, entradas_b, etiqueta=None)[0]


def predecir_gold(run_dir: Path, encoder: str, casos: list[dict], entrada: str,
                  manifiesto_modelo: Path | None = None) -> list[dict]:
    """Predicciones ciegas de un checkpoint sobre `casos` (de `casos_gold`): una fila
    `{context_id, pred, probs}` por caso. No recibe ni devuelve etiquetas."""
    if entrada not in ENTRADAS_GOLD:
        raise ValueError("Las predicciones sobre el Gold son solo para A, B y AB.")
    if any(c.get("indice") is not None for c in casos):
        raise ValueError("Los casos del Gold deben ir sin etiqueta.")
    _, hp, tok, dev, modelo = _cargar_modelo(Path(run_dir), encoder, manifiesto_modelo)
    ej = ct.preparar_ejemplos(_limpio(casos), entrada, tok, hp.max_len)
    pred, probs, _ = _predicciones(modelo, ej, tok.pad_id, dev)
    return [{"context_id": e["context_id"], "pred": p, "probs": pr} for e, p, pr in zip(ej, pred, probs)]


def escribir_predicciones_ciegas(ruta: Path, filas: list[dict]) -> str:
    """JSONL de predicciones del Gold y su sha256. Falla si una fila lleva algo mas que
    `context_id`, `pred` y `probs` (nunca etiquetas)."""
    for r in filas:
        if tuple(sorted(r)) != tuple(sorted(CAMPOS_PREDICCION_CIEGA)):
            raise ValueError(f"Campos no permitidos en una prediccion ciega: {sorted(r)}")
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("".join(json.dumps(r) + "\n" for r in filas), encoding="utf-8")
    return seleccion_datos.sha_archivo(ruta)


# ---------------------------------------------------------------- reevaluacion y bootstrap
def reevaluar_checkpoint(run_id: str, carpeta: Path, encoder: str, v_filas: list[dict],
                         f: seleccion_datos.Fuentes, papers: dict,
                         manifiesto_modelo: Path | None = None) -> list[str]:
    """Registra en el run EXISTENTE los conjuntos de evaluacion que le faltan (sin reentrenar).

    `carpeta` es la carpeta del run (con `model.safetensors`). Devuelve los conjuntos agregados."""
    sets = conjuntos_eval(v_filas, f)
    previas = mlflow.get_run(run_id).data.metrics
    faltan = {k for k in sets if f"{k}_f1_macro" not in previas}
    if not faltan:
        return []
    _, hp, tok, dev, modelo = _cargar_modelo(Path(carpeta), encoder, manifiesto_modelo)
    with mlflow.start_run(run_id=run_id):
        _evaluar_conjuntos({k: sets[k] for k in sets if k in faltan}, modelo, tok, dev, hp, f, papers)
    return sorted(k for k in faltan if sets[k])


def evaluar_conjunto_extra(run_id: str, carpeta: Path, encoder: str, nombre: str, filas: list[dict],
                           f: seleccion_datos.Fuentes, papers: dict, *, entradas_b: dict[str, dict] | None = None,
                           manifiesto_modelo: Path | None = None) -> dict | None:
    """Evalua el checkpoint de un run sobre `filas` (con `etiqueta_entrenamiento`) y registra
    `{nombre}_*` en el run EXISTENTE, mas `predicciones_{nombre}.jsonl` en `carpeta`. La entrada es
    la del manifiesto del run. No acepta los nombres de `conjuntos_eval` (no pisa `val_*`).
    Devuelve las metricas, o None si el conjunto ya estaba registrado."""
    if nombre == "val" or nombre.startswith("val_") or nombre in ("dev_haiku", "ref_gpt", "parada"):
        raise ValueError(f"El nombre {nombre!r} pisaria metricas del entrenamiento.")
    carpeta = Path(carpeta)
    ruta = carpeta / f"predicciones_{nombre}.jsonl"
    if ruta.is_file() and f"{nombre}_f1_macro" in mlflow.get_run(run_id).data.metrics:
        return None
    man, hp, tok, dev, modelo = _cargar_modelo(carpeta, encoder, manifiesto_modelo)
    entrada = man["config"]["entrada"]
    casos, _ = casos_entrada(entrada, filas, f, papers, entradas_b)
    ej = ct.preparar_ejemplos(_limpio(_barajar(entrada, casos, man["semilla"])), entrada, tok, hp.max_len)
    pred, probs, lat = _predicciones(modelo, ej, tok.pad_id, dev)
    m = dominio.metricas([e["indice"] for e in ej], pred)
    with mlflow.start_run(run_id=run_id):
        registro_mlflow.log_metricas(nombre, m)
        registro_mlflow.log_matriz_confusion(m, nombre)
        mlflow.log_metric(f"{nombre}_latencia_ms", lat)
    ruta.write_text("".join(json.dumps({"context_id": e["context_id"], "pred": p, "probs": pr}) + "\n"
                            for e, p, pr in zip(ej, pred, probs)), encoding="utf-8")
    return m


def leer_predicciones(carpeta: Path, nombre: str = "val") -> dict[str, int]:
    """{context_id: indice predicho} de `predicciones_{nombre}.jsonl` de un run."""
    lineas = (Path(carpeta) / f"predicciones_{nombre}.jsonl").read_text(encoding="utf-8").splitlines()
    return {r["context_id"]: r["pred"] for r in map(json.loads, (l for l in lineas if l.strip()))}


def bootstrap_diferencia(pred_a: list[int], pred_b: list[int], etiquetas: list[int],
                         n: int = 1000, semilla: int = 2026) -> dict:
    """Bootstrap pareado de F1-macro(A) - F1-macro(B): los mismos casos remuestreados para
    ambos. Devuelve la diferencia observada, el IC95% percentil y la fraccion de remuestras con A > B."""
    if not len(pred_a) == len(pred_b) == len(etiquetas):
        raise ValueError("pred_a, pred_b y etiquetas deben tener la misma longitud.")
    if not etiquetas:
        raise ValueError("Se necesita al menos un caso.")
    rng = random.Random(semilla)
    total = len(etiquetas)
    macro = lambda pred, idx: dominio.metricas([etiquetas[i] for i in idx],  # noqa: E731
                                               [pred[i] for i in idx])["f1_macro"]
    todos = range(total)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(total) for _ in todos]
        diffs.append(macro(pred_a, idx) - macro(pred_b, idx))
    diffs.sort()
    return {"diferencia": macro(pred_a, todos) - macro(pred_b, todos),
            "ic95": (diffs[int(0.025 * n)], diffs[min(n - 1, int(0.975 * n))]),
            "prob_a_mayor": sum(d > 0 for d in diffs) / n, "n_remuestras": n, "casos": total}


def bootstrap_diferencia_cluster(preds_a_semillas: list[list[int]], preds_b_semillas: list[list[int]],
                                 etiquetas: list[int], grupos: list[str], n: int = 1000,
                                 semilla: int = 2026) -> dict:
    """Bootstrap por grupos de B - A en F1-macro promediado entre semillas.

    `preds_*_semillas`: una lista de predicciones por semilla, alineadas con `etiquetas` y `grupos`
    (articulo citante de cada caso). Se remuestrean los GRUPOS con reemplazo (las citas de un mismo
    articulo no son independientes) y en cada remuestra se promedia la F1-macro de las semillas de
    cada brazo. Devuelve la diferencia observada, el IC95% percentil, `prob_b_mayor`, la diferencia
    por semilla y `mismo_signo_semillas` (todas las semillas con el mismo signo estricto)."""
    total = len(etiquetas)
    if not total or len(grupos) != total:
        raise ValueError("Se necesitan etiquetas y un grupo por caso.")
    if not preds_a_semillas or len(preds_a_semillas) != len(preds_b_semillas):
        raise ValueError("A y B deben tener el mismo numero (>0) de semillas.")
    if any(len(p) != total for p in (*preds_a_semillas, *preds_b_semillas)):
        raise ValueError("Cada prediccion debe estar alineada con las etiquetas.")
    por_grupo: dict[str, list[int]] = {}
    for i, g in enumerate(grupos):
        por_grupo.setdefault(g, []).append(i)
    claves = sorted(por_grupo)

    def macro(pred: list[int], idx: list[int]) -> float:
        return dominio.metricas([etiquetas[i] for i in idx], [pred[i] for i in idx])["f1_macro"]

    def media(preds: list[list[int]], idx: list[int]) -> float:
        return sum(macro(p, idx) for p in preds) / len(preds)

    todos = list(range(total))
    por_semilla = [macro(b, todos) - macro(a, todos) for a, b in zip(preds_a_semillas, preds_b_semillas)]
    rng = random.Random(semilla)
    diffs = []
    for _ in range(n):
        idx = [i for g in (rng.choice(claves) for _ in claves) for i in por_grupo[g]]
        diffs.append(media(preds_b_semillas, idx) - media(preds_a_semillas, idx))
    diffs.sort()
    return {"diferencia": media(preds_b_semillas, todos) - media(preds_a_semillas, todos),
            "ic95": (diffs[int(0.025 * n)], diffs[min(n - 1, int(0.975 * n))]),
            "prob_b_mayor": sum(d > 0 for d in diffs) / n, "n_remuestras": n, "casos": total,
            "grupos": len(claves), "semillas": len(preds_a_semillas),
            "diferencia_por_semilla": por_semilla,
            "mismo_signo_semillas": all(d > 0 for d in por_semilla) or all(d < 0 for d in por_semilla)}


# ---------------------------------------------------------------- eleccion del lr
def seleccionar_lr(manifiestos: dict[tuple, dict], grilla, semillas,
                   combinaciones=None) -> dict[tuple, dict]:
    """lr por (pista, brazo): la mayor media de `metricas_parada.f1_macro` entre `semillas`; en empate,
    el lr menor. `manifiestos` = {(pista, brazo, lr, semilla): manifiesto_entrenamiento}. Exige la
    grilla completa (cada lr x semilla) para cada (pista, brazo) de `combinaciones` (por defecto, las
    presentes) y que cada manifiesto corresponda a su clave."""
    grilla, semillas = [float(lr) for lr in grilla], list(semillas)
    combinaciones = sorted(set(combinaciones) if combinaciones is not None
                           else {(k, b) for k, b, _, _ in manifiestos})
    faltan = [(k, b, lr, s) for k, b in combinaciones for lr in grilla for s in semillas
              if (k, b, lr, s) not in manifiestos]
    if faltan or not combinaciones:
        raise ValueError(f"grilla de lr incompleta: faltan {faltan}")
    salida = {}
    for k, b in combinaciones:
        por_semilla = {}
        for lr in grilla:
            por_semilla[lr] = {}
            for s in semillas:
                man = manifiestos[(k, b, lr, s)]
                cfg = man["config"]
                if float(cfg["hp_lr"]) != lr or int(cfg["semilla"]) != s or cfg["entrada"] != b:
                    raise ValueError(f"El manifiesto de {(k, b, lr, s)} no corresponde a su clave.")
                por_semilla[lr][s] = float(man["metricas_parada"]["f1_macro"])
        medias = {lr: math.fsum(v.values()) / len(v) for lr, v in por_semilla.items()}
        elegido = max(grilla, key=lambda lr: (medias[lr], -lr))
        salida[(k, b)] = {"lr": elegido, "medias": medias, "por_semilla": por_semilla}
    return salida


# ---------------------------------------------------------------- inferencia entre brazos y semillas
_METRICAS_RAPIDAS = ("f1_macro", "accuracy", "f1_weighted")


def _validar_semillas(preds_x: list[list[int]], preds_a: list[list[int]], etiquetas: list[int],
                      grupos: list[str]) -> None:
    total = len(etiquetas)
    if not total or len(grupos) != total:
        raise ValueError("Se necesitan etiquetas y un grupo por caso.")
    if not preds_x or len(preds_x) != len(preds_a):
        raise ValueError("Los dos brazos deben tener el mismo numero (>0) de semillas.")
    if any(len(p) != total for p in (*preds_x, *preds_a)):
        raise ValueError("Cada prediccion debe estar alineada con las etiquetas.")


def _codigos(etiquetas: list[int], preds: list[list[int]]) -> np.ndarray:
    """Celda de la matriz de confusion (verdad * 9 + pred) por modelo y caso: (modelos, casos)."""
    y = np.asarray(etiquetas, dtype=np.int64)
    return y[None, :] * dominio.N_CLASES + np.asarray(preds, dtype=np.int64)


def _matrices(codigos: np.ndarray, pesos: np.ndarray) -> np.ndarray:
    """Matrices de confusion ponderadas: pesos (replicas, casos) -> (replicas, modelos, 9, 9)."""
    n_mod, n_casos = codigos.shape
    n_cel = dominio.N_CLASES ** 2
    uno = np.zeros((n_casos, n_mod, n_cel))
    np.put_along_axis(uno, codigos.T[..., None], 1.0, axis=2)
    m = pesos @ uno.reshape(n_casos, n_mod * n_cel)
    return m.reshape(pesos.shape[0], n_mod, dominio.N_CLASES, dominio.N_CLASES)


def _f1_por_clase(mat: np.ndarray) -> np.ndarray:
    """F1 por clase con zero_division=0 (la misma convencion que `dominio.metricas`)."""
    tp = np.diagonal(mat, axis1=-2, axis2=-1)
    fn = mat.sum(-1) - tp
    fp = mat.sum(-2) - tp
    den = 2 * tp + fp + fn
    return np.divide(2 * tp, den, out=np.zeros_like(tp), where=den > 0)


def _metrica_vectorial(mat: np.ndarray, metrica: str) -> np.ndarray:
    if metrica == "f1_macro":
        return _f1_por_clase(mat).mean(-1)
    total = mat.sum((-2, -1))
    if metrica == "accuracy":
        return np.diagonal(mat, axis1=-2, axis2=-1).sum(-1) / total
    if metrica == "f1_weighted":
        return (_f1_por_clase(mat) * mat.sum(-1)).sum(-1) / total
    raise ValueError(f"Metrica no soportada: {metrica!r} (use {_METRICAS_RAPIDAS})")


def _pesos_grupos(grupos: list[str], n: int, rng: np.random.Generator, lote: int = 250):
    """Lotes de pesos por caso de un bootstrap por grupos: cada replica remuestrea los grupos con
    reemplazo y cada caso pesa las veces que salio su grupo."""
    posicion = {g: i for i, g in enumerate(sorted(set(grupos)))}
    idx = np.asarray([posicion[g] for g in grupos])
    n_grupos = len(posicion)
    hechos = 0
    while hechos < n:
        b = min(lote, n - hechos)
        conteo = rng.multinomial(n_grupos, np.full(n_grupos, 1 / n_grupos), size=b)
        yield conteo[:, idx].astype(float)
        hechos += b


def _metricas_bootstrap(etiquetas, preds, grupos, n, semilla, metrica=None) -> np.ndarray:
    """Metrica (o F1 por clase si `metrica` es None) de cada modelo en cada replica del bootstrap
    por grupos, con la MISMA remuestra para todos los modelos: (replicas, modelos[, 9])."""
    codigos = _codigos(etiquetas, preds)
    rng = np.random.default_rng(semilla)
    partes = []
    for pesos in _pesos_grupos(grupos, n, rng):
        mat = _matrices(codigos, pesos)
        partes.append(_f1_por_clase(mat) if metrica is None else _metrica_vectorial(mat, metrica))
    return np.concatenate(partes, axis=0)


def _metrica_observada(etiquetas, preds, metrica=None) -> np.ndarray:
    mat = _matrices(_codigos(etiquetas, preds), np.ones((1, len(etiquetas))))[0]
    return _f1_por_clase(mat) if metrica is None else _metrica_vectorial(mat, metrica)


def _cdf_t(x: float, gl: float) -> float:
    return float(stats.norm.cdf(x) if math.isinf(gl) else stats.t.cdf(x, gl))


def _cuantil_t(q: float, gl: float) -> float:
    return float(stats.norm.ppf(q) if math.isinf(gl) else stats.t.ppf(q, gl))


def prueba_combinada(preds_x_semillas: list[list[int]], preds_a_semillas: list[list[int]],
                     etiquetas: list[int], grupos: list[str], n: int = 5000, semilla: int = 2026,
                     metrica: str = "f1_macro", delta: float = 0.02) -> dict:
    """Prueba t de X - A con varianza combinada de semillas y de articulos.

    d_j = M(X_j) - M(A_j) por semilla pareada j; d = media de d_j. v_sem = s^2(d_j) / n_semillas;
    v_art = varianza de d en un bootstrap por articulo citante con las semillas fijas (una sola
    remuestra por replica, compartida por semillas y brazos). SE = sqrt(v_sem + v_art) y
    gl = (v_sem + v_art)^2 / (v_sem^2 / (n_semillas - 1)) (Satterthwaite; infinito si v_sem = 0).
    Devuelve p bilateral, IC95, el TOST con margen `delta` (p de cada cola y el maximo) e IC90."""
    _validar_semillas(preds_x_semillas, preds_a_semillas, etiquetas, grupos)
    k = len(preds_x_semillas)
    preds = [*preds_x_semillas, *preds_a_semillas]
    obs = _metrica_observada(etiquetas, preds, metrica)
    d_j = [float(obs[j] - obs[k + j]) for j in range(k)]
    d = math.fsum(d_j) / k
    s_d = _sd(d_j)
    v_sem = s_d ** 2 / k
    boot = _metricas_bootstrap(etiquetas, preds, grupos, n, semilla, metrica)
    d_boot = (boot[:, :k] - boot[:, k:]).mean(1)
    v_art = float(d_boot.var(ddof=1)) if n > 1 else 0.0
    se = math.sqrt(v_sem + v_art)
    gl = math.inf if v_sem == 0 or k < 2 else (v_sem + v_art) ** 2 / (v_sem ** 2 / (k - 1))
    if se == 0:
        p = 1.0 if d == 0 else 0.0
        p_inf = 0.0 if d > -delta else 1.0
        p_sup = 0.0 if d < delta else 1.0
        ic95 = ic90 = (d, d)
    else:
        p = 2 * (1 - _cdf_t(abs(d) / se, gl))
        p_inf = 1 - _cdf_t((d + delta) / se, gl)   # H0: d <= -delta
        p_sup = _cdf_t((d - delta) / se, gl)       # H0: d >= +delta
        t95, t90 = _cuantil_t(0.975, gl), _cuantil_t(0.95, gl)
        ic95, ic90 = (d - t95 * se, d + t95 * se), (d - t90 * se, d + t90 * se)
    return {"metrica": metrica, "diferencia": d, "diferencia_por_semilla": d_j, "sd_semillas": s_d,
            "v_sem": v_sem, "v_art": v_art, "se": se, "gl": gl, "p": float(p), "ic95": ic95,
            "delta": delta, "p_tost_inferior": float(p_inf), "p_tost_superior": float(p_sup),
            "p_tost": float(max(p_inf, p_sup)), "ic90": ic90, "semillas": k, "casos": len(etiquetas),
            "grupos": len(set(grupos)), "n_remuestras": n, "semilla_bootstrap": semilla}


def _sd(valores: list[float]) -> float:
    """Desviacion estandar muestral (ddof=1); 0.0 con menos de dos valores."""
    if len(valores) < 2:
        return 0.0
    m = math.fsum(valores) / len(valores)
    return math.sqrt(math.fsum((v - m) ** 2 for v in valores) / (len(valores) - 1))


def bootstrap_jerarquico(preds_x_semillas: list[list[int]], preds_a_semillas: list[list[int]],
                         etiquetas: list[int], grupos: list[str], n: int = 5000,
                         semilla: int = 2026) -> dict:
    """IC95 percentil descriptivo de X - A en F1-macro con un bootstrap jerarquico: en cada replica se
    remuestrean las PAREJAS de semillas con reemplazo y luego los articulos citantes (remuestra
    compartida). Incluye la F1 por clase de cada brazo (media de semillas), su diferencia con IC95 y
    la contribucion de cada clase a la diferencia de F1-macro (diferencia de la clase / 9)."""
    _validar_semillas(preds_x_semillas, preds_a_semillas, etiquetas, grupos)
    k = len(preds_x_semillas)
    preds = [*preds_x_semillas, *preds_a_semillas]
    obs = _metrica_observada(etiquetas, preds)            # (modelos, 9)
    dif_clase = (obs[:k] - obs[k:]).mean(0)               # (9,)
    boot = _metricas_bootstrap(etiquetas, preds, grupos, n, semilla)   # (replicas, modelos, 9)
    rng = np.random.default_rng(semilla + 1)
    elegidas = rng.integers(0, k, size=(boot.shape[0], k))
    dif_rep = boot[:, :k] - boot[:, k:]                   # (replicas, k, 9)
    dif_rep = np.take_along_axis(dif_rep, elegidas[..., None], axis=1).mean(1)   # (replicas, 9)
    macro_rep = dif_rep.mean(-1)
    soporte = [sum(1 for e in etiquetas if e == c) for c in range(dominio.N_CLASES)]

    def ic(v):
        return (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))

    return {"diferencia": float(dif_clase.mean()), "ic95": ic(macro_rep), "n_remuestras": n,
            "semillas": k, "casos": len(etiquetas), "grupos": len(set(grupos)),
            "por_clase": [{"clase": dominio.CATEGORIAS[c], "soporte": soporte[c],
                           "f1_a": float(obs[k:, c].mean()), "f1_x": float(obs[:k, c].mean()),
                           "diferencia": float(dif_clase[c]), "ic95": ic(dif_rep[:, c]),
                           "contribucion_macro": float(dif_clase[c] / dominio.N_CLASES)}
                          for c in range(dominio.N_CLASES)]}


def holm(pvalores: dict) -> dict:
    """Ajuste de Holm por pasos: p_(i) * (m - i + 1), con maximo acumulado y tope 1."""
    orden = sorted(pvalores, key=lambda k: (pvalores[k], str(k)))
    m, previo, salida = len(orden), 0.0, {}
    for i, clave in enumerate(orden):
        previo = max(previo, min(1.0, (m - i) * pvalores[clave]))
        salida[clave] = previo
    return {k: salida[k] for k in pvalores}


def veredicto(r: dict, p_holm: float, p_tost_holm: float, alfa: float = 0.05, min_signo: int = 4,
              n_semillas: int = 5) -> str:
    """`incompleto` (faltan semillas) > `mejora`/`empeora` (p Holm < alfa y al menos `min_signo` d_j
    con el signo de la media; un d_j = 0 no cuenta) > `equivalente` (TOST Holm < alfa) >
    `no_concluyente`."""
    d_j = r["diferencia_por_semilla"]
    if len(d_j) < n_semillas:
        return "incompleto"
    d = r["diferencia"]
    signo = (d > 0) - (d < 0)
    concordantes = sum(1 for x in d_j if signo and ((x > 0) - (x < 0)) == signo)
    if signo and p_holm < alfa and concordantes >= min_signo:
        return "mejora" if signo > 0 else "empeora"
    if p_tost_holm < alfa:
        return "equivalente"
    return "no_concluyente"
