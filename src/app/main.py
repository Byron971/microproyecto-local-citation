"""Backend del tablero: sirve el modelo real y la información del estudio de datos.

Al arrancar carga la línea base TF-IDF sobre los 19.776 artículos del corpus y
responde cada consulta ordenándolos de verdad, y expone los resultados del
análisis exploratorio, de la evaluación del modelo y del diagnóstico de
negativos que hasta ahora solo existían en un notebook y en el reporte.

Para ejecutarlo desde la raíz del proyecto:

    python -m uvicorn src.app.main:app --host 127.0.0.1 --port 8000

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

from src.app.insights import load_or_build
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara el modelo y los insights antes de atender la primera petición.

    Cargarlos aquí y no en la primera consulta evita que quien abra el tablero
    se encuentre con una espera de varios segundos sin explicación: cuando el
    servidor dice estar listo, lo está de verdad.
    """
    print("Cargando modelo TF-IDF sobre el corpus de artículos...")
    state["recomendador"] = Recommender().load()

    print("Cargando información del tablero...")
    state["insights"] = load_or_build()

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

    A diferencia de la maqueta, el ranking sale del modelo: se vectoriza el
    contexto con el mismo TF-IDF ajustado sobre el corpus y se ordenan los
    artículos por similitud coseno.
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
