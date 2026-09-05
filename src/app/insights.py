"""Cálculo de la información que alimenta el tablero.

Reúne en un solo JSON las tres familias de resultados que el proyecto ya
produjo por separado:

1. La exploración de datos del notebook ``01_exploracion_datos.ipynb``.
2. El desempeño de la línea base TF-IDF (Entrega 2).
3. El diagnóstico de muestreo de negativos (``src/evaluation/diagnose_negatives``).

Hasta ahora esos resultados vivían en un notebook, en un reporte LaTeX y en la
salida por consola de un script. El tablero necesita servirlos por HTTP, y para
eso tienen que existir como datos y no como figuras ya dibujadas.

El cálculo completo tarda alrededor de un minuto, sobre todo por el conteo de
bigramas en los 63.768 contextos. Por eso el resultado se guarda en disco y el
backend lo reutiliza: ``load_or_build`` lee el archivo si está y solo recalcula
cuando falta.

Uso:
    python -m src.app.insights
    python -m src.app.insights --force
"""

import argparse
import json
import random
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.data.load_data import load_json
from src.evaluation.diagnose_negatives import (
    hard_negatives_from_ranking,
    random_negatives_by_context,
    separability_auc,
)
from src.evaluation.ranking_metrics import mean_reciprocal_rank, recall_at_k
from src.models.tfidf_baseline import TfidfBaseline, clean_context_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_INSIGHTS_PATH = DEFAULT_PROCESSED_DIR / "dashboard_insights.json"

SPLITS = ("train", "val", "test")

# Profundidades a las que se evalúa la línea base. Se eligen espaciadas de
# forma creciente porque el Recall crece rápido al principio y se aplana
# después: muestrear K de uno en uno no aportaría información nueva.
EVALUATION_DEPTHS = (1, 3, 5, 10, 20, 50, 100)

# Semilla compartida por todos los muestreos de este módulo, para que dos
# ejecuciones del tablero muestren exactamente las mismas cifras.
RANDOM_STATE = 42

TARGETCIT_PATTERN = re.compile(r"\bTARGETCIT\b")
OTHERCIT_PATTERN = re.compile(r"\bOTHERCIT\b")


def _histogram(
    values: Sequence[float] | np.ndarray,
    bins: int,
    upper_quantile: float = 1.0,
) -> dict[str, list[float]]:
    """Resume una distribución en un histograma serializable.

    El frontend dibuja las barras a partir de estos conteos, así que aquí se
    entrega el histograma ya calculado en vez de la lista completa de valores:
    mandar 63.768 longitudes por HTTP para que el navegador las agrupe sería
    desperdiciar ancho de banda.

    Parameters
    ----------
    values:
        Valores de la distribución.
    bins:
        Número de intervalos.
    upper_quantile:
        Cuantil en el que se recorta el eje. Sirve para que unas pocas colas
        muy largas no aplasten visualmente el resto de la distribución.

    Returns
    -------
    dict
        ``bordes`` con los límites de los intervalos y ``conteos`` con la
        frecuencia de cada uno.
    """
    array = np.asarray(values, dtype=float)

    if upper_quantile < 1.0:
        array = array[array <= np.quantile(array, upper_quantile)]

    counts, edges = np.histogram(array, bins=bins)

    return {
        "bordes": [float(edge) for edge in edges],
        "conteos": [int(count) for count in counts],
    }


def _length_stats(values: Sequence[float]) -> dict[str, float]:
    """Calcula mediana, percentil 95 y máximo de una lista de longitudes."""
    array = np.asarray(values, dtype=float)

    return {
        "mediana": float(np.median(array)),
        "percentil_95": float(np.quantile(array, 0.95)),
        "maximo": float(array.max()),
    }


def _fitted_vectorizer(baseline: TfidfBaseline) -> TfidfVectorizer:
    """Devuelve el vectorizador de un modelo ya ajustado.

    ``TfidfBaseline`` lo deja en ``None`` hasta que se llama ``fit``, así que se
    comprueba una vez y se reutiliza en lugar de acceder al atributo opcional
    en cada uso.
    """
    if baseline.vectorizer is None:
        raise RuntimeError("El modelo debe estar ajustado antes de usar su vectorizador.")

    return baseline.vectorizer


def compute_dataset_summary(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    splits: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Tamaños básicos del conjunto de datos."""
    return {
        "contextos": len(contexts),
        "articulos": len(papers),
        "particiones": {name: len(rows) for name, rows in splits.items()},
    }


def compute_quality_checks(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    splits: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Repite las comprobaciones de integridad del análisis exploratorio.

    Cada comprobación cuenta registros defectuosos, de modo que el valor
    esperado es cero en todas. Se recalculan aquí, y no se copian del notebook,
    para que el tablero refleje los datos que hay en disco ahora mismo.

    Returns
    -------
    list[dict]
        Comprobaciones con su nombre y el número de casos encontrados.
    """
    all_rows = [row for rows in splits.values() for row in rows]

    contextos_inexistentes = sum(
        1 for row in all_rows if row["context_id"] not in contexts
    )

    refids_inexistentes = sum(
        1
        for row in all_rows
        if row["context_id"] in contexts
        and contexts[row["context_id"]]["refid"] not in papers
    )

    titulos_vacios = sum(1 for paper in papers.values() if not (paper.get("title") or "").strip())
    resumenes_vacios = sum(
        1 for paper in papers.values() if not (paper.get("abstract") or "").strip()
    )

    sin_targetcit = 0
    targetcit_multiple = 0

    for context in contexts.values():
        marcas = len(TARGETCIT_PATTERN.findall(context["masked_text"]))

        if marcas == 0:
            sin_targetcit += 1
        elif marcas > 1:
            targetcit_multiple += 1

    sin_positivo_unico = sum(1 for row in all_rows if len(row["positive_ids"]) != 1)

    positivo_distinto_refid = sum(
        1
        for row in all_rows
        if row["context_id"] in contexts
        and len(row["positive_ids"]) == 1
        and row["positive_ids"][0] != contexts[row["context_id"]]["refid"]
    )

    textos = Counter(context["masked_text"] for context in contexts.values())
    duplicados = sum(count - 1 for count in textos.values() if count > 1)

    comprobaciones = [
        ("Contextos referenciados inexistentes", contextos_inexistentes),
        ("Artículos citados inexistentes", refids_inexistentes),
        ("Títulos vacíos", titulos_vacios),
        ("Resúmenes vacíos", resumenes_vacios),
        ("Contextos sin TARGETCIT", sin_targetcit),
        ("Contextos con más de un TARGETCIT", targetcit_multiple),
        ("Consultas sin un único positivo", sin_positivo_unico),
        ("Positive ID diferente de refid", positivo_distinto_refid),
        ("Textos de contexto duplicados", duplicados),
    ]

    return [
        {"comprobacion": nombre, "cantidad": int(cantidad)}
        for nombre, cantidad in comprobaciones
    ]


def compute_text_lengths(
    contexts: dict[str, Any],
    papers: dict[str, Any],
) -> dict[str, Any]:
    """Longitudes en palabras de contextos, títulos y resúmenes.

    Estas cifras son las que determinan si hará falta truncar la entrada de un
    modelo con ventana limitada como SciBERT, que es la razón por la que el
    análisis exploratorio las midió.
    """
    context_words = [len(context["masked_text"].split()) for context in contexts.values()]
    title_words = [len((paper.get("title") or "").split()) for paper in papers.values()]
    abstract_words = [len((paper.get("abstract") or "").split()) for paper in papers.values()]

    othercit = [
        len(OTHERCIT_PATTERN.findall(context["masked_text"])) for context in contexts.values()
    ]

    return {
        "resumen": [
            {"texto": "Contexto", **_length_stats(context_words)},
            {"texto": "Título", **_length_stats(title_words)},
            {"texto": "Resumen", **_length_stats(abstract_words)},
        ],
        "histograma_contextos": _histogram(context_words, bins=40),
        "histograma_resumenes": _histogram(abstract_words, bins=45, upper_quantile=0.99),
        "othercit_promedio": float(np.mean(othercit)),
    }


def compute_frequent_terms(
    contexts: dict[str, Any],
    top_n: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    """Unigramas y bigramas más frecuentes de los contextos.

    Se eliminan los marcadores de cita y las palabras vacías del inglés: sin
    eso el resultado estaría dominado por ``TARGETCIT`` y por artículos y
    preposiciones, que aparecen en todos los contextos y no describen el
    dominio.
    """
    textos = [clean_context_text(context["masked_text"]) for context in contexts.values()]

    vectorizer = CountVectorizer(
        lowercase=True,
        stop_words="english",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z-]+\b",
        ngram_range=(1, 2),
        min_df=20,
    )
    matriz: Any = vectorizer.fit_transform(textos)

    frecuencias = np.asarray(matriz.sum(axis=0)).ravel()
    terminos = vectorizer.get_feature_names_out()

    unigramas: list[tuple[str, int]] = []
    bigramas: list[tuple[str, int]] = []

    for termino, frecuencia in zip(terminos, frecuencias, strict=True):
        destino = bigramas if " " in termino else unigramas
        destino.append((termino, int(frecuencia)))

    def top(pares: list[tuple[str, int]]) -> list[dict[str, Any]]:
        ordenados = sorted(pares, key=lambda par: par[1], reverse=True)[:top_n]
        return [{"termino": termino, "frecuencia": frecuencia} for termino, frecuencia in ordenados]

    return {"unigramas": top(unigramas), "bigramas": top(bigramas)}


def compute_similarity_signal(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    splits: dict[str, list[dict[str, Any]]],
    sample_size: int = 4_000,
) -> dict[str, Any]:
    """Compara la similitud del contexto con el artículo citado y con uno al azar.

    Es la comprobación que justificó toda la línea base: si el artículo
    realmente citado no fuera más parecido al contexto que uno cualquiera, no
    habría señal léxica que explotar y TF-IDF sería inútil.

    Returns
    -------
    dict
        Porcentaje de casos en que el positivo gana, medias de cada población y
        los histogramas de ambas distribuciones.
    """
    todas = [row for rows in splits.values() for row in rows]

    rng = random.Random(RANDOM_STATE)
    muestra = rng.sample(todas, min(sample_size, len(todas)))

    paper_ids = list(papers.keys())

    consultas = []
    positivos_texto = []
    negativos_texto = []

    for row in muestra:
        context = contexts[row["context_id"]]
        refid = context["refid"]

        if refid not in papers:
            continue

        # El negativo se re-muestrea si coincide con el positivo: comparar un
        # artículo consigo mismo no mediría nada.
        negativo = rng.choice(paper_ids)
        while negativo == refid:
            negativo = rng.choice(paper_ids)

        consultas.append(clean_context_text(context["masked_text"]))
        positivos_texto.append(f"{papers[refid]['title']} {papers[refid]['abstract']}")
        negativos_texto.append(
            f"{papers[negativo]['title']} {papers[negativo]['abstract']}"
        )

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=3,
        max_df=0.95,
        max_features=20_000,
    )
    vectorizer.fit(consultas + positivos_texto + negativos_texto)

    matriz_consultas = vectorizer.transform(consultas)

    # La similitud se toma par a par (consulta i contra positivo i), no todos
    # contra todos: interesa comparar cada contexto con su propia cita.
    positivos = cosine_similarity(
        matriz_consultas, vectorizer.transform(positivos_texto)
    ).diagonal()
    negativos = cosine_similarity(
        matriz_consultas, vectorizer.transform(negativos_texto)
    ).diagonal()

    return {
        "muestra": len(consultas),
        "porcentaje_positivo_mayor": float((positivos > negativos).mean() * 100),
        "media_positivos": float(positivos.mean()),
        "media_negativos": float(negativos.mean()),
        "histograma_positivos": _histogram(positivos, bins=40),
        "histograma_negativos": _histogram(negativos, bins=40),
    }


def compute_split_integrity(
    contexts: dict[str, Any],
    splits: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Comprueba que las particiones no compartan documentos ni pares.

    Si un mismo artículo citante apareciera en entrenamiento y en prueba, el
    modelo se estaría evaluando sobre documentos que ya vio y las métricas
    estarían infladas.

    Returns
    -------
    list[dict]
        Para cada par de particiones, cuántos citantes y cuántos pares
        citante-citado comparten. Lo esperado es cero.
    """
    citantes: dict[str, set[str]] = {}
    pares: dict[str, set[tuple[str, str]]] = {}

    for nombre, rows in splits.items():
        citantes[nombre] = set()
        pares[nombre] = set()

        for row in rows:
            context = contexts[row["context_id"]]
            citantes[nombre].add(context["citing_id"])
            pares[nombre].add((context["citing_id"], context["refid"]))

    combinaciones = [("train", "val"), ("train", "test"), ("val", "test")]

    return [
        {
            "particiones": f"{a} ∩ {b}",
            "citantes_compartidos": len(citantes[a] & citantes[b]),
            "pares_compartidos": len(pares[a] & pares[b]),
        }
        for a, b in combinaciones
    ]


def compute_most_cited(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Artículos que concentran más contextos de cita.

    Muestra que la distribución de citas está muy sesgada: un puñado de
    artículos muy influyentes aparece cientos de veces mientras la mayoría
    apenas se cita.
    """
    conteo = Counter(context["refid"] for context in contexts.values())

    return [
        {
            "paper_id": paper_id,
            "titulo": (papers[paper_id]["title"] if paper_id in papers else paper_id).strip(),
            "contextos": int(cantidad),
        }
        for paper_id, cantidad in conteo.most_common(top_n)
    ]


def compute_model_performance(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    split: list[dict[str, Any]],
    split_name: str,
) -> dict[str, Any]:
    """Evalúa la línea base TF-IDF a distintas profundidades de ranking.

    El ranking se calcula una sola vez a la profundidad máxima y las métricas
    de cada K se derivan recortándolo. Evaluar K veces desde cero daría los
    mismos números y costaría siete veces más.

    Returns
    -------
    dict
        Curva de Recall@K y MRR@K, más el techo de recuperación que impone la
        primera etapa.
    """
    baseline = TfidfBaseline().fit(papers)
    vectorizer = _fitted_vectorizer(baseline)

    consultas = [contexts[row["context_id"]]["masked_text"] for row in split]
    relevantes = [set(row["positive_ids"]) for row in split]

    profundidad_maxima = max(EVALUATION_DEPTHS)
    rankings = baseline.rank(consultas, top_k=profundidad_maxima)

    curva = []

    for k in EVALUATION_DEPTHS:
        recortados = [ranking[:k] for ranking in rankings]

        recalls = [
            recall_at_k(ranked_ids=ranked, relevant_ids=relevante, k=k)
            for ranked, relevante in zip(recortados, relevantes, strict=True)
        ]

        curva.append(
            {
                "k": k,
                "recall": float(sum(recalls) / len(recalls)),
                "mrr": float(mean_reciprocal_rank(zip(recortados, relevantes, strict=True))),
            }
        )

    return {
        "particion": split_name,
        "consultas": len(split),
        "articulos": len(papers),
        "vocabulario": len(vectorizer.vocabulary_),
        "curva": curva,
        # El Recall a la máxima profundidad es el techo del sistema completo:
        # la segunda etapa solo reordena lo que la primera ya recuperó.
        "techo_recuperacion": curva[-1]["recall"],
    }


def compute_negatives_diagnostic(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    split: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    n_queries: int = 400,
    top_n: int = 100,
) -> dict[str, Any]:
    """Contrasta los negativos aleatorios del pipeline con negativos duros.

    Reproduce el diagnóstico de ``src/evaluation/diagnose_negatives`` en forma
    de datos en vez de texto por consola, para que el tablero pueda mostrar por
    qué el muestreo actual de negativos produce una tarea más fácil que la real.
    """
    baseline = TfidfBaseline().fit(papers)
    vectorizer = _fitted_vectorizer(baseline)
    negativos_aleatorios = random_negatives_by_context(pairs)

    fila_de = {paper_id: i for i, paper_id in enumerate(baseline.paper_ids)}

    rng = random.Random(RANDOM_STATE)
    muestra = rng.sample(split, min(n_queries, len(split)))

    consultas = [
        clean_context_text(contexts[row["context_id"]]["masked_text"]) for row in muestra
    ]

    matriz_consultas = vectorizer.transform(consultas)
    similitudes = (matriz_consultas @ baseline.paper_matrix.T).toarray()

    rankings = baseline.rank(consultas, top_k=top_n)

    positivos: list[float] = []
    aleatorios: list[float] = []
    duros: list[float] = []

    for indice, row in enumerate(muestra):
        puntajes = similitudes[indice]
        ids_positivos = set(row["positive_ids"])

        positivos.extend(
            puntajes[fila_de[paper_id]] for paper_id in ids_positivos if paper_id in fila_de
        )
        aleatorios.extend(
            puntajes[fila_de[paper_id]]
            for paper_id in negativos_aleatorios.get(row["context_id"], [])
            if paper_id in fila_de
        )
        duros.extend(
            puntajes[fila_de[paper_id]]
            for paper_id in hard_negatives_from_ranking(rankings[indice], ids_positivos)
        )

    array_positivos = np.array(positivos)
    array_aleatorios = np.array(aleatorios)
    array_duros = np.array(duros)

    return {
        "consultas": len(muestra),
        "top_n": top_n,
        "similitud_media": {
            "positivos": float(array_positivos.mean()),
            "aleatorios": float(array_aleatorios.mean()),
            "duros": float(array_duros.mean()),
        },
        "auc": {
            "positivos_vs_aleatorios": separability_auc(positivos, aleatorios),
            "positivos_vs_duros": separability_auc(positivos, duros),
        },
        "aleatorios_sin_terminos_comunes": float((array_aleatorios == 0).mean() * 100),
        "aleatorios_bajo_media_positiva": float(
            (array_aleatorios < array_positivos.mean()).mean() * 100
        ),
    }


def compute_examples(
    contexts: dict[str, Any],
    papers: dict[str, Any],
    split: list[dict[str, Any]],
    n_examples: int = 50,
) -> list[dict[str, Any]]:
    """Selecciona contextos reales para probar el recomendador desde el tablero.

    Se guardan junto al resto de la información en vez de exponer
    ``contexts.json`` en el backend: el archivo pesa 39 MB y solo se necesitan
    unas decenas de ejemplos, así que cargarlo entero en memoria por esto sería
    desproporcionado.

    Cada ejemplo trae el artículo que realmente se citó, lo que permite al
    tablero señalar si el modelo lo encontró y en qué posición.

    Parameters
    ----------
    contexts, papers:
        Datos originales.
    split:
        Partición de la que se toman los ejemplos.
    n_examples:
        Cantidad de ejemplos a guardar.

    Returns
    -------
    list[dict]
        Ejemplos con su texto, el identificador de la cita correcta y su título.
    """
    rng = random.Random(RANDOM_STATE)
    muestra = rng.sample(split, min(n_examples, len(split)))

    ejemplos = []

    for row in muestra:
        context = contexts[row["context_id"]]
        refid = context["refid"]

        if refid not in papers:
            continue

        ejemplos.append(
            {
                "context_id": row["context_id"],
                "texto": context["masked_text"].strip(),
                "cita_correcta": refid,
                "titulo_correcto": papers[refid]["title"].strip(),
            }
        )

    return ejemplos


def build_insights(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    processed_dir: str | Path = DEFAULT_PROCESSED_DIR,
    split_name: str = "val",
) -> dict[str, Any]:
    """Calcula el conjunto completo de información del tablero.

    Parameters
    ----------
    raw_dir:
        Carpeta con los cinco JSON originales.
    processed_dir:
        Carpeta con los pares supervisados. Si falta, el diagnóstico de
        negativos se omite y el resto del tablero sigue funcionando.
    split_name:
        Partición sobre la que se evalúa el modelo.

    Returns
    -------
    dict
        Estructura lista para serializar y servir por HTTP.
    """
    raw_path = Path(raw_dir)
    processed_path = Path(processed_dir)

    contexts = load_json(raw_path / "contexts.json")
    papers = load_json(raw_path / "papers.json")
    splits = {name: load_json(raw_path / f"{name}.json") for name in SPLITS}

    insights: dict[str, Any] = {
        "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": compute_dataset_summary(contexts, papers, splits),
        "calidad": compute_quality_checks(contexts, papers, splits),
        "longitudes": compute_text_lengths(contexts, papers),
        "terminos": compute_frequent_terms(contexts),
        "similitud": compute_similarity_signal(contexts, papers, splits),
        "integridad_particiones": compute_split_integrity(contexts, splits),
        "mas_citados": compute_most_cited(contexts, papers),
        "modelo": compute_model_performance(
            contexts, papers, splits[split_name], split_name
        ),
        "ejemplos": compute_examples(contexts, papers, splits[split_name]),
    }

    pairs_path = processed_path / f"{split_name}_pairs.json"

    # El diagnóstico depende de datos derivados que puede no haber generado
    # todavía quien acaba de clonar el repositorio. Se degrada con elegancia:
    # el tablero muestra un aviso en esa sección en lugar de no arrancar.
    if pairs_path.exists():
        insights["negativos"] = compute_negatives_diagnostic(
            contexts, papers, splits[split_name], load_json(pairs_path)
        )
    else:
        insights["negativos"] = None

    return insights


def save_insights(insights: dict[str, Any], path: str | Path) -> Path:
    """Guarda el JSON de insights, creando la carpeta si hace falta."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as file:
        json.dump(insights, file, ensure_ascii=False)

    return output


def load_or_build(
    path: str | Path = DEFAULT_INSIGHTS_PATH,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    processed_dir: str | Path = DEFAULT_PROCESSED_DIR,
    force: bool = False,
) -> dict[str, Any]:
    """Devuelve los insights, calculándolos solo si no están en disco.

    Parameters
    ----------
    path:
        Archivo donde se cachea el resultado.
    raw_dir, processed_dir:
        Carpetas de datos.
    force:
        Recalcula aunque exista el archivo. Es la vía para refrescar el tablero
        después de cambiar los datos o el modelo.

    Returns
    -------
    dict
        Información del tablero.
    """
    cache = Path(path)

    if cache.exists() and not force:
        return load_json(cache)

    insights = build_insights(raw_dir=raw_dir, processed_dir=processed_dir)
    save_insights(insights, cache)

    return insights


def main() -> None:
    """Punto de entrada para precalcular el tablero desde la línea de comandos."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_INSIGHTS_PATH)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalcula aunque el archivo ya exista.",
    )
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"{args.output} ya existe. Use --force para recalcularlo.")
        return

    print("Calculando información del tablero (puede tardar cerca de un minuto)...")

    insights = build_insights(raw_dir=args.raw_dir, processed_dir=args.processed_dir)
    output_path = save_insights(insights, args.output)

    modelo = insights["modelo"]
    recall_10 = next(punto["recall"] for punto in modelo["curva"] if punto["k"] == 10)

    print(f"  {output_path} ({output_path.stat().st_size:,} bytes)")
    print(f"  contextos: {insights['dataset']['contextos']:,}")
    print(f"  Recall@10 ({modelo['particion']}): {recall_10:.4f}")

    if insights["negativos"] is None:
        print("  aviso: sin data/processed, se omitió el diagnóstico de negativos.")


if __name__ == "__main__":
    main()
