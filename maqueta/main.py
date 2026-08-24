"""Backend mínimo en FastAPI para la maqueta del recomendador local de citas.

Expone un único endpoint:

    POST /predict

Para ejecutarlo desde la raíz del proyecto:

    python -m uvicorn maqueta.main:app --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Local Citation Recommender (maqueta)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CitationContext(BaseModel):
    context: str


HARDCODED_RECOMMENDATIONS = {
    "Paper A": 0.91,
    "Paper B": 0.84,
    "Paper C": 0.76,
}


@app.post("/predict")
def predict(payload: CitationContext) -> dict:
    """Recibe un contexto académico y devuelve recomendaciones de prueba."""
    print(f"Received context ({len(payload.context)} chars): {payload.context!r}")
    return HARDCODED_RECOMMENDATIONS


def run_backend() -> None:
    """Inicia el backend local de la maqueta en el puerto 8000."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
