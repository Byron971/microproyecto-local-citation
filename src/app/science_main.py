"""Servicio científico independiente; falla al arrancar si no puede cargar M/S."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.ms_router import router, recomendar_cientifico, modelos_cientificos


@asynccontextmanager
async def lifespan(app):
    from src.app.ms_runtime import obtener_servicio
    from src.app.article_corpus import corpus
    corpus()  # Validate identity and the complete M/S input budget before readiness.
    servicio = obtener_servicio()
    # Experimental global search is opt-in; it must not block article analysis.
    if os.environ.get('MS_ENABLE_GLOBAL_SEARCH') == '1':
        from src.app.scientific_search import ArticleSearch
        app.state.article_search = ArticleSearch(
            os.environ.get('MS_SEARCH_DIR', 'artifacts/scientific_search'), servicio.recuperador.encoder)
    else:
        # Sugerencias del paso 2: solo documentos del corpus preparado, sin otro modelo.
        try:
            from src.app.scientific_search import prepared_article_search
            app.state.article_search = prepared_article_search(servicio.recuperador.encoder)
        except (OSError, ValueError, KeyError, TypeError):
            import logging
            logging.getLogger(__name__).warning('Sugerencias no disponibles; el análisis M/S continúa.')
    app.state.modelos_cargados = True
    try:
        yield
    finally:
        app.state.modelos_cargados = False
        if hasattr(app.state, 'article_search'):
            del app.state.article_search


app = FastAPI(title="API científica M/S", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("MS_CORS_ORIGINS", "https://proyectocitas-grupo19.click").split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)
app.include_router(router)
app.add_api_route('/api/recomendar', recomendar_cientifico, methods=['POST'])
app.add_api_route('/api/modelos', modelos_cientificos, methods=['GET'])


@app.get("/health/ready")
def ready():
    from fastapi.responses import JSONResponse
    loaded = getattr(app.state, "modelos_cargados", False)
    return JSONResponse({"listo": loaded, "release": os.environ.get("MS_RELEASE_ID", "local")},
                        status_code=200 if loaded else 503)
