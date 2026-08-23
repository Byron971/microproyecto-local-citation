"""Minimal FastAPI backend for the Local Citation Recommender mock-up.

Single endpoint: POST /predict

Run with:
    uvicorn main:app --reload --port 8000
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
    # The real context sent by the frontend arrives here...
    print(f"Received context ({len(payload.context)} chars): {payload.context!r}")
    return HARDCODED_RECOMMENDATIONS


def run_backend() -> None:
    """Entry point for `uv run maqueta-back` — starts the API on port 8000."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
