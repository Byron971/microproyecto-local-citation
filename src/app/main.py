"""Backend del tablero: sirve el modelo real y la información del estudio de datos.

Al arrancar carga el modelo empaquetado en la librería ``modelo_citas``, que
recupera candidatos con TF-IDF y los reordena con el modelo lineal supervisado,
y expone los resultados del análisis exploratorio, de la evaluación del modelo y
del diagnóstico de negativos que hasta ahora solo existían en un notebook y en
el reporte.

Para ejecutarlo desde la raíz del proyecto:

    uv run tablero

Después, abrir http://127.0.0.1:8000 en el navegador.
"""

import random
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from src.app.insights import load_insights
from src.app.settings import get_app_settings
from src.app.fragment_retrieval import recuperar_top3
from src.app.corpus_adapter import CorpusError, ejemplos_disponibles, leer_corpus, top3_de_corpus
from src.app.recommender import Recommender
from src.app.scibert_runtime import SciBERTRuntime
from src.app.references import ReferenceUnavailable, fetch_bibtex

STATIC_DIR = Path(__file__).resolve().parent / "static"

# El estado del proceso se guarda en un diccionario poblado durante el arranque.
# El modelo y los insights se cargan una sola vez y se comparten entre
# peticiones porque ambos son de solo lectura y su preparación es lo caro.
state: dict[str, Any] = {"recomendador": None, "insights": None, "config": None, "scibert": None}


class ContextoConsulta(BaseModel):
    """Cuerpo de una petición de recomendación."""

    contexto: str = Field(
        ...,
        description="Texto académico en inglés donde haría falta la cita.",
    )
    modelo: str | None = Field(default=None, max_length=120)
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Cantidad de artículos a devolver.",
    )



class ParrafoCitado(BaseModel):
    """Fragmento proporcionado del articulo citado; no se toma de otros papers."""

    chunk_id: str = Field(..., min_length=1, max_length=120)
    texto: str = Field(..., min_length=1, max_length=5000)
    seccion: str | None = Field(default=None, max_length=200)


# Limite de contenido textual para la ruta manual; no sustituye un limite
# de tamano de peticion a nivel de proxy en despliegue publico.
MAX_CARACTERES_TOP3_MANUAL = 60_000


class ConsultaTop3(BaseModel):
    """Corte vertical inicial; corpus externo aun no enlazado a esta API."""

    contexto: str = Field(..., min_length=1, max_length=4000)
    cited_id: str = Field(..., min_length=1, max_length=120)
    parrafos: list[ParrafoCitado] = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def limitar_texto_total(self) -> "ConsultaTop3":
        total = len(self.contexto) + sum(len(p.texto) for p in self.parrafos)
        if total > MAX_CARACTERES_TOP3_MANUAL:
            raise ValueError(
                f"Texto total supera el maximo de {MAX_CARACTERES_TOP3_MANUAL} caracteres."
            )
        return self


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara el modelo y los insights antes de atender la primera petición.

    Cargarlos aquí y no en la primera consulta evita que quien abra el tablero
    se encuentre con una espera de varios segundos sin explicación: cuando el
    servidor dice estar listo, lo está de verdad.
    """
    config = get_app_settings()  # Validación fail-closed antes de cargar el modelo.
    state["config"] = config

    print("Cargando el modelo empaquetado (TF-IDF + reordenador lineal)...")
    state["recomendador"] = Recommender().load()

    print("Cargando información del tablero...")
    state["insights"] = load_insights(config.insights_path)

    state["scibert"] = None
    if config.scibert_enabled:
        # No fallback a BM25 si falta Torch, snapshot o manifiesto válido.
        state["scibert"] = SciBERTRuntime.load(config.scibert_manifest, config.scibert_device)

    print("Backend listo en http://127.0.0.1:8000")

    yield

    state.clear()


app = FastAPI(
    title="Recomendación local de citas académicas",
    description="Tablero y API del recomendador basado en la línea base TF-IDF.",
    lifespan=lifespan,
)


def _recomendador() -> Recommender:
    """Devuelve el recomendador cargado, o falla si el arranque no terminó."""
    recomendador = state.get("recomendador")

    if recomendador is None:
        raise HTTPException(status_code=503, detail="El modelo aún no está cargado.")

    return recomendador


@app.get("/api/estado")
def estado() -> dict[str, Any]:
    """Informa si el modelo está listo y con qué configuración se cargó."""
    recomendador = _recomendador()

    respuesta = {"listo": recomendador.is_ready, "modelo": recomendador.describe()}
    config = state.get("config")
    if config is not None:
        respuesta["configuracion"] = config.public_info()
    return respuesta


@app.get("/api/capacidades")
def capacidades() -> dict[str, Any]:
    """Estado verificable de cada tarea, sin equiparar salud a cumplimiento de tesis.

    El artefacto de corpus puede faltar en Docker: se valida su contenido,
    no simplemente la existencia del archivo. No lee etiquetas Gold.
    """
    recomendador = state.get("recomendador")
    recomendacion_lista = bool(recomendador is not None and recomendador.is_ready)
    try:
        corpus = leer_corpus()
        corpus_listo, n_train, motivo = True, len(corpus["casos"]), None
    except CorpusError as exc:
        corpus_listo, n_train, motivo = False, 0, str(exc)

    return {
        "servicio": {"listo": recomendacion_lista},
        "tareas": {
            "recomendacion_articulos_tfidf": {
                "disponible": recomendacion_lista,
                "estado": "baseline_legacy",
            },
            "top3_manual_bm25": {
                "disponible": True,
                "estado": "baseline_lexico",
            },
            "top3_corpus_train_bm25": {
                "disponible": corpus_listo,
                "n_casos_train": n_train,
                "motivo": motivo,
                "estado": "desarrollo_no_gold",
            },
            "top3_scibert": {
                "disponible": state.get("scibert") is not None,
                "motivo": None if state.get("scibert") is not None else
                          "SciBERT no está cargado en este proceso.",
                "modelo": getattr(state.get("scibert"), "model", None),
                "revision": getattr(state.get("scibert"), "revision", None),
            },
            "clasificacion_nueve_funciones": {
                "disponible": state.get("a4") is not None,
                "motivo": None if state.get("a4") is not None else
                          "No hay checkpoint A4 cargado en este proceso.",
                "modelo": getattr(state.get("a4"), "model_id", None),
                "validacion": "provisional_no_gold_humano" if state.get("a4") is not None
                              else "no_ejecutada",
            },
        },
        "gold_humano_certificado": False,
        "nota": (
            "Salud de TF-IDF y modelos científicos son aspectos distintos; "
            "ningún modelo queda certificado como Gold por estar disponible."
        ),
    }


# Publicar únicamente el modelo que de verdad está integrado al servicio.
MODELO_PREDETERMINADO = "tfidf_reranker_v1"


@app.get("/api/modelos")
def modelos() -> dict[str, Any]:
    recomendador = state.get("recomendador")
    disponible = bool(recomendador is not None and recomendador.is_ready)
    return {
        "predeterminado": MODELO_PREDETERMINADO,
        "modelos": [{
            "id": MODELO_PREDETERMINADO,
            "nombre": "TF-IDF + reordenador lineal",
            "descripcion": "Recupera artículos y los reordena; no es SciBERT Top-3.",
            "disponible": disponible,
            "motivo": None if disponible else "El modelo aún no está listo.",
            "puntaje": {
                "etiqueta": "Puntaje del reordenador",
                "descripcion": "Puntaje de ordenación, no probabilidad de una referencia correcta.",
            },
            "devuelve_tfidf": True,
        }],
    }


@app.get("/api/referencias/{paper_id}")
def referencia_bibliografica(paper_id: str) -> dict[str, str]:
    """Permitir acceso a ACL Anthology solo para IDs del corpus instalado."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,79}", paper_id) or ".." in paper_id:
        raise HTTPException(status_code=404, detail="Artículo no encontrado.")
    recomendador = _recomendador()
    if recomendador.model is None:
        raise HTTPException(status_code=503, detail="El modelo aún no está disponible.")
    if paper_id not in recomendador.model.papers:
        raise HTTPException(status_code=404, detail="El artículo no pertenece al corpus disponible.")
    try:
        return fetch_bibtex(paper_id)
    except ReferenceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/recomendar")
def recomendar(consulta: ContextoConsulta) -> dict[str, Any]:
    """Devuelve los artículos más pertinentes para un contexto de cita.

    El ranking sale del modelo empaquetado: TF-IDF recupera los candidatos y el
    reordenador lineal los ordena por probabilidad de ser la cita correcta.
    """
    if consulta.modelo is not None:
        if consulta.modelo != MODELO_PREDETERMINADO:
            raise HTTPException(status_code=404, detail="El modelo elegido no existe.")
        actual = state.get("recomendador")
        if actual is None or not actual.is_ready:
            raise HTTPException(status_code=409, detail="El modelo elegido aún no está disponible.")

    texto = consulta.contexto.strip()

    if not texto:
        raise HTTPException(status_code=422, detail="El contexto no puede estar vacío.")

    recomendaciones = _recomendador().recommend(texto, top_k=consulta.top_k)

    return {
        "consulta": texto,
        "modelo": MODELO_PREDETERMINADO,
        "total": len(recomendaciones),
        "recomendaciones": recomendaciones,
    }



@app.post("/api/top3-fragmentos")
def top3_fragmentos(consulta: ConsultaTop3) -> dict[str, Any]:
    """Baseline sin inferencia: BM25 sobre fragmentos de UN articulo citado.

    Los fragmentos se suministran explicitamente en esta primera version.
    La consulta NO estima la funcion retorica ni la calidad del ranking.
    """
    texto = consulta.contexto.strip()
    cited_id = consulta.cited_id.strip()
    if not texto or not cited_id:
        raise HTTPException(status_code=422, detail="Contexto y cited_id son obligatorios.")

    ids = [p.chunk_id.strip() for p in consulta.parrafos]
    if any(not cid for cid in ids) or len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="chunk_id no puede estar vacio ni repetido.")
    if any(not p.texto.strip() for p in consulta.parrafos):
        raise HTTPException(status_code=422, detail="No se admiten fragmentos sin texto.")

    fragmentos = [
        {"chunk_id": p.chunk_id.strip(), "texto": p.texto.strip(),
         "seccion": p.seccion}
        for p in consulta.parrafos
    ]
    ranking = recuperar_top3(texto, fragmentos)
    return {
        "contexto": texto,
        "cited_id": cited_id,
        "metodo": "BM25_lexico_baseline",
        "alcance": "solo_fragmentos_aportados_del_articulo_citado",
        "total_fragmentos_analizados": len(fragmentos),
        "total_resultados": len(ranking),
        "fragmentos": ranking,
        "clasificacion": {
            "estado": "no_ejecutada",
            "motivo": "Aun no se dispone de un clasificador de nueve funciones validado.",
        },
        "aviso": (
            "Puntajes BM25 no son probabilidades ni metricas de calidad; "
            "requieren referencia humana para evaluar relevancia."
        ),
    }



def _scibert() -> SciBERTRuntime:
    instance = state.get("scibert")
    if instance is None:
        raise HTTPException(
            status_code=503,
            detail="SciBERT está desactivado o falta un snapshot verificado. El baseline BM25 sigue disponible.",
        )
    return instance


@app.post("/api/top3-scibert")
def top3_scibert_manual(consulta: ConsultaTop3) -> dict[str, Any]:
    """SciBERT REAL sobre los párrafos aportados, si se habilitó explícitamente."""
    model = _scibert()
    ids = [p.chunk_id.strip() for p in consulta.parrafos]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="chunk_id no puede repetirse.")
    chunks = [
        {"chunk_id": p.chunk_id.strip(), "texto": p.texto.strip(), "seccion": p.seccion}
        for p in consulta.parrafos
    ]
    try:
        ranking = model.top3(consulta.contexto, chunks)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "contexto": consulta.contexto,
        "cited_id": consulta.cited_id,
        "metodo": model.method,
        "modelo": model.model,
        "revision": model.revision,
        "alcance": "solo_fragmentos_aportados_del_articulo_citado",
        "total_fragmentos_analizados": len(chunks),
        "total_resultados": len(ranking),
        "fragmentos": ranking,
        "clasificacion": {"estado": "no_ejecutada"},
        "aviso": "Similitud coseno no es probabilidad ni relevancia Gold.",
    }


@app.get("/api/top3-scibert/corpus/{context_id}")
def top3_scibert_corpus(context_id: str) -> dict[str, Any]:
    """SciBERT sobre el documento citado real, solo en la muestra TRAIN."""
    model = _scibert()
    try:
        data = leer_corpus()
    except CorpusError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if (data.get("resumen") or {}).get("tipo") != "muestra_desarrollo_train_no_gold":
        raise HTTPException(status_code=503, detail="No es un corpus TRAIN aprobado para demostración.")
    caso = next((c for c in data["casos"] if c["context_id"] == context_id), None)
    if caso is None:
        raise HTTPException(status_code=404, detail="Caso no disponible en TRAIN.")
    if any(k in caso for k in ("gold", "label", "labels", "relevantes", "evidencia_top3")):
        raise HTTPException(status_code=503, detail="Caso con datos de anotación no publicables.")
    try:
        ranking = model.top3(caso["citation_context"], caso["chunks"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "context_id": caso["context_id"],
        "contexto": caso["citation_context"],
        "cited_id": caso["cited_id"],
        "cited_title": caso["cited_title"],
        "split": "train",
        "fuente": "ACL-200 + ACL OCL local",
        "sha256_ocl_citado": caso["sha256_ocl_citado"],
        "metodo": model.method,
        "modelo": model.model,
        "revision": model.revision,
        "total_fragmentos_analizados": len(caso["chunks"]),
        "total_resultados": len(ranking),
        "fragmentos": ranking,
        "clasificacion": {"estado": "no_ejecutada"},
        "aviso": "SciBERT base con mean pooling; desarrollo TRAIN, sin Gold ni F1.",
    }


@app.get("/api/top3-corpus/ejemplos")
def ejemplos_corpus_top3() -> dict[str, Any]:
    """Casos reales de desarrollo, disponibles solo si existe artefacto local."""
    try:
        datos = leer_corpus()
    except CorpusError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"total": len(datos["casos"]), "ejemplos": ejemplos_disponibles(datos)}


@app.get("/api/top3-corpus/{context_id}")
def recomendar_top3_corpus(context_id: str) -> dict[str, Any]:
    """Recupera exclusivamente fragmentos documentados del cited_id original."""
    try:
        datos = leer_corpus()
    except CorpusError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    resultado = top3_de_corpus(datos, context_id)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Contexto no incluido en la muestra train.")
    return resultado


@app.get("/api/insights")
def insights() -> dict[str, Any]:
    """Entrega toda la información que dibuja el panel derecho del tablero."""
    datos = state.get("insights")

    if datos is None:
        raise HTTPException(status_code=503, detail="Los insights aún no están listos.")

    return datos


@app.get("/api/ejemplos")
def ejemplos_recomendacion() -> dict[str, Any]:
    """Listado de ejemplos observados del conjunto de validación."""
    datos = state.get("insights")
    if datos is None:
        raise HTTPException(status_code=503, detail="Los ejemplos aún no están listos.")
    ejemplos = datos.get("ejemplos") or []
    return {
        "total": len(ejemplos),
        "particion": (datos.get("modelo") or {}).get("particion"),
        "ejemplos": ejemplos,
    }


@app.get("/api/ejemplo")
def ejemplo() -> dict[str, Any]:
    """Devuelve un contexto real del corpus, con la cita que le corresponde.

    Permite probar el recomendador sin tener que redactar un texto académico en
    inglés, y como se conoce la respuesta correcta el tablero puede indicar si
    el modelo la encontró y en qué posición.
    """
    datos = state.get("insights")

    if datos is None:
        raise HTTPException(status_code=503, detail="Los insights aún no están listos.")

    ejemplos = datos.get("ejemplos") or []

    if not ejemplos:
        raise HTTPException(
            status_code=404,
            detail="No hay ejemplos disponibles. Regenere los insights con --force.",
        )

    return random.choice(ejemplos)


@app.get("/")
def index() -> FileResponse:
    """Sirve el tablero."""
    return FileResponse(STATIC_DIR / "index.html")


# Los archivos estáticos se montan al final para que las rutas declaradas
# arriba tengan prioridad sobre el directorio.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def run_backend() -> None:
    """Inicia el backend con host/puerto/logging validados por entorno."""
    import uvicorn

    config = get_app_settings()
    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level)
