"""Una corrida completa del issue #104: casos -> entrenar -> evaluar -> registrar en MLflow.

Importa torch y mlflow (grupos `modelo` + `experimentos`). El notebook solo orquesta."""
import json
import random
import time
from pathlib import Path

import mlflow
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from . import clasificador_torch as ct
from . import dominio, registro_mlflow, revision, seleccion_datos
from .cli import EVIDENCIAS
from .cli_modelo import dispositivo

MODOS_PERDIDA = ("duro", "kd", "ponderado")
ENTRADAS_104 = ("A", "B", "B_barajada")
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
    """Casos de la entrada `A`, `B` o `B_barajada` (esta ultima aun sin barajar: ver `_barajar`)."""
    if entrada not in ENTRADAS_104:
        raise ValueError(f"Entrada no soportada en #104: {entrada!r}")
    if entrada == "A":
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
    de las Partes 1 y 2 de #104; `top3_sha` solo se agrega con B/B_barajada."""
    if entrada != "A" and not top3_sha:
        raise ValueError("Las entradas B requieren `top3_sha` (huella del Top-3 usado).")
    cfg = {**config, "encoder": encoder, "semilla": semilla, "modo_perdida": modo, "entrada": entrada,
           "dry": dry, **{f"hp_{k}": v for k, v in hp.__dict__.items()}}
    return {**cfg, "top3_sha": top3_sha} if entrada != "A" else cfg


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


def entrenar_y_registrar(nombre: str, config: dict, train_filas: list[dict], v_filas: list[dict],
                         f: seleccion_datos.Fuentes, papers: dict, carpeta: Path, *,
                         encoder: str = "scibert", semilla: int = 42, modo: str = "duro",
                         hp: ct.Hiperparametros | None = None, dry: bool = False,
                         manifiesto_datos_sha: str = "", manifiesto_modelo: Path | None = None,
                         entrada: str = "A", entradas_b: dict[str, dict] | None = None,
                         top3_sha: str = "") -> str:
    """Entrena, evalua en V/dev_haiku/ref_gpt y registra todo. Devuelve el run_id (el del run
    FINISHED previo si ya existia: reanudacion). Los checkpoints quedan en `carpeta/<nombre>`, en MLflow solo
    su ruta y sha. `entrada` A (def.), B o B_barajada; las B requieren `entradas_b` y `top3_sha`."""
    hp = hp or ct.Hiperparametros()
    if dry:
        hp = ct.Hiperparametros(**{**hp.__dict__, "epocas": 1})
        train_filas, v_filas = train_filas[:64], v_filas[:64]
    config = config_corrida(config, encoder, semilla, modo, hp, dry, entrada, top3_sha)
    tr_casos, info_tr = casos_entrada(entrada, train_filas, f, papers, entradas_b)
    v_casos, info_v = casos_entrada(entrada, v_filas, f, papers, entradas_b)
    sets = conjuntos_eval(v_filas, f)
    with registro_mlflow.abrir_corrida(nombre, config, {
            "manifiesto_datos_sha": manifiesto_datos_sha, "casos_train": str(info_tr),
            "casos_val": str(info_v), "entrada": entrada,
            **({"top3_sha": top3_sha, "regla_antifuga_b": "L2_citados_citantes+L4_texto+L5_mismos_ids"}
               if entrada != "A" else {})}, ct.hardware()) as run:
        if run is None:  # reanudacion: devuelve el run FINISHED existente
            return registro_mlflow.corrida_terminada(registro_mlflow.sha_config(config))
        ruta = _ruta_encoder(encoder, manifiesto_modelo)
        tok = ct.TokenizadorHF(ruta)
        dev = dispositivo("auto")
        ej_train = ct.preparar_ejemplos(
            _limpio(con_modo_perdida(_barajar(entrada, tr_casos, semilla), modo)), entrada, tok, hp.max_len)
        ej_val = ct.preparar_ejemplos(_limpio(_barajar(entrada, v_casos, semilla)), entrada, tok, hp.max_len)
        ct.fijar_determinismo(semilla)
        modelo = ct.ClasificadorCLS(ruta, semilla, hp.dropout)
        salida = Path(carpeta) / nombre
        resultado = ct.entrenar(modelo, ej_train, ej_val, tok.pad_id, semilla, hp, salida, dev,
                                al_terminar_epoca=registro_mlflow.log_epoca)
        ct.cargar_checkpoint(modelo, salida / "model.safetensors", resultado["checkpoint_sha256"])
        mlflow.set_tags({"checkpoint": str(salida / "model.safetensors"),
                         "checkpoint_sha256": resultado["checkpoint_sha256"],
                         "model_version": revision.modelo(encoder)[1]})
        registro_mlflow.log_dataset("train", [c["context_id"] for c in tr_casos],
                                    [c["_fila"]["etiqueta_entrenamiento"] for c in tr_casos], "training")
        registro_mlflow.log_dataset("val", [c["context_id"] for c in v_casos],
                                    [c["_fila"]["etiqueta_entrenamiento"] for c in v_casos], "validation")
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
    if entrada == "B_barajada":
        raise ValueError("Las predicciones sobre el Gold son solo para A y B.")
    filas = [{"context_id": c, "citing_id": f.contextos[c]["citing_id"]} for c in sorted(ids)]
    return casos_entrada(entrada, filas, f, papers, entradas_b, etiqueta=None)[0]


def predecir_gold(run_dir: Path, encoder: str, casos: list[dict], entrada: str,
                  manifiesto_modelo: Path | None = None) -> list[dict]:
    """Predicciones ciegas de un checkpoint sobre `casos` (de `casos_gold`): una fila
    `{context_id, pred, probs}` por caso. No recibe ni devuelve etiquetas."""
    if entrada not in ("A", "B"):
        raise ValueError("Las predicciones sobre el Gold son solo para A y B.")
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


def leer_predicciones(carpeta: Path) -> dict[str, int]:
    """{context_id: indice predicho} de `predicciones_val.jsonl` de un run."""
    lineas = (Path(carpeta) / "predicciones_val.jsonl").read_text(encoding="utf-8").splitlines()
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
