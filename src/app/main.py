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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.app.insights import load_insights
from src.app.fragment_retrieval import recuperar_top3
from src.app.corpus_adapter import CorpusError, ejemplos_disponibles, leer_corpus, top3_de_corpus
from src.app.recommender import Recommender

STATIC_DIR = Path(__file__).resolve().parent / "static"

# El estado del proceso se guarda en un diccionario poblado durante el arranque.
# El modelo y los insights se cargan una sola vez y se comparten entre
# peticiones porque ambos son de solo lectura y su preparación es lo caro.
state: dict[str, Any] = {"recomendador": None, "insights": None}


class ContextoConsulta(BaseModel):
    """Cuerpo de una petición de recomendación."""

    contexto: str = Field(
        ...,
        description="Texto académico en inglés donde haría falta la cita.",
    )
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


class ConsultaTop3(BaseModel):
    """Corte vertical inicial; corpus externo aun no enlazado a esta API."""

    contexto: str = Field(..., min_length=1, max_length=4000)
    cited_id: str = Field(..., min_length=1, max_length=120)
    parrafos: list[ParrafoCitado] = Field(..., min_length=1, max_length=100)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara el modelo y los insights antes de atender la primera petición.

    Cargarlos aquí y no en la primera consulta evita que quien abra el tablero
    se encuentre con una espera de varios segundos sin explicación: cuando el
    servidor dice estar listo, lo está de verdad.
    """
    print("Cargando el modelo empaquetado (TF-IDF + reordenador lineal)...")
    state["recomendador"] = Recommender().load()

    print("Cargando información del tablero...")
    state["insights"] = load_insights()

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

    return {"listo": recomendador.is_ready, "modelo": recomendador.describe()}


@app.post("/api/recomendar")
def recomendar(consulta: ContextoConsulta) -> dict[str, Any]:
    """Devuelve los artículos más pertinentes para un contexto de cita.

    El ranking sale del modelo empaquetado: TF-IDF recupera los candidatos y el
    reordenador lineal los ordena por probabilidad de ser la cita correcta.
    """
    texto = consulta.contexto.strip()

    if not texto:
        raise HTTPException(status_code=422, detail="El contexto no puede estar vacío.")

    recomendaciones = _recomendador().recommend(texto, top_k=consulta.top_k)

    return {
        "consulta": texto,
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
    """Inicia el backend del tablero en el puerto 8000."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
