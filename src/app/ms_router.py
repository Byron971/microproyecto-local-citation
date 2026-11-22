"""Endpoints opt-in de la demostración científica M/S (sin modificar A4)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

router = APIRouter(tags=["Ciencia M/S"])


class FragmentoMS(BaseModel):
    chunk_id: str = Field(min_length=1, max_length=120)
    texto: str = Field(min_length=1, max_length=5000)
    seccion: str | None = Field(default=None, max_length=200)


class ConsultaMS(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    titulo: str = Field(min_length=1, max_length=600)
    abstract: str = Field(min_length=1, max_length=12000)
    candidatos: list[FragmentoMS] = Field(min_length=3, max_length=100)

    @model_validator(mode="after")
    def validar(self):
        if self.contexto.count("TARGETCIT") != 1:
            raise ValueError("El contexto debe contener TARGETCIT exactamente una vez")
        if not self.titulo.strip() or not self.abstract.strip():
            raise ValueError("Titulo y abstract no pueden estar vacios")
        ids = [c.chunk_id.strip() for c in self.candidatos]
        if not all(ids) or len(ids) != len(set(ids)) or any(not c.texto.strip() for c in self.candidatos):
            raise ValueError("IDs duplicados/vacios o fragmentos sin texto")
        total = len(self.contexto) + len(self.titulo) + len(self.abstract) + sum(len(c.texto) for c in self.candidatos)
        if total > 60000:
            raise ValueError("El texto de la solicitud supera 60000 caracteres")
        return self


class DisponibilidadArticulos(BaseModel):
    paper_ids: list[str] = Field(min_length=1, max_length=20)


class ConsultaArticulo(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    paper_id: str = Field(pattern=r'^[A-Z][0-9]{2}-[0-9]{4}$')


class BusquedaCientifica(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=10, ge=1, le=20)
    modelo: str | None = None


@router.get('/api/analisis-cita-ms/modelos')
def modelos_cientificos(request: Request):
    from src.app.scientific_search import MODEL_ID
    listo = hasattr(request.app.state, 'article_search')
    return {'predeterminado': MODEL_ID, 'modelos': [{
        'id': MODEL_ID, 'nombre': 'SciBERT · búsqueda semántica de artículos',
        'descripcion': 'Compara el contexto con títulos y resúmenes de todo el catálogo mediante SciBERT base. Extensión experimental; M/S se aplican después a la función de cita.',
        'disponible': listo, 'motivo': None if listo else 'Índice científico no disponible.',
        'puntaje': {'etiqueta': 'Similitud SciBERT', 'descripcion': 'Similitud coseno entre contexto y título + resumen. No es probabilidad de una referencia correcta.'},
        'devuelve_tfidf': False}]}


@router.post('/api/analisis-cita-ms/recomendar')
def recomendar_cientifico(consulta: BusquedaCientifica, request: Request):
    from src.app.scientific_search import MODEL_ID
    from src.app.ms_lock import LOCK as _LOCK
    if consulta.modelo not in (None, MODEL_ID):
        raise HTTPException(status_code=404, detail='Modelo científico desconocido')
    search = getattr(request.app.state, 'article_search', None)
    if search is None:
        raise HTTPException(status_code=503, detail='Índice científico no disponible')
    if not _LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail='El servicio científico está ocupado', headers={'Retry-After': '5'})
    try:
        return search.recommend(consulta.contexto.strip(), consulta.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        import logging
        logging.getLogger(__name__).exception('Error de recuperación científica')
        raise HTTPException(status_code=503, detail='Búsqueda científica no disponible; revisar registro del servidor') from exc
    finally:
        _LOCK.release()


def _corpus_articulos():
    from src.app.article_corpus import CorpusUnavailable, corpus
    try:
        return corpus()
    except CorpusUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post('/api/analisis-cita-ms/disponibilidad')
def disponibilidad_articulos(consulta: DisponibilidadArticulos):
    data, version = _corpus_articulos()
    return {'version_contenido': version, 'articulos': [
        {'paper_id': pid, 'disponible': pid in data['documentos'],
         'motivo': None if pid in data['documentos'] else 'Sin texto completo preparado para M/S.',
         'total_fragmentos': len(data['documentos'][pid]['candidatos']) if pid in data['documentos'] else 0}
        for pid in consulta.paper_ids
    ]}


@router.post('/api/analisis-cita-ms/articulo')
def analizar_articulo(consulta: ConsultaArticulo):
    data, version = _corpus_articulos()
    doc = data['documentos'].get(consulta.paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail='Artículo sin texto completo preparado para M/S.')
    try:
        entrada = ConsultaMS(contexto=consulta.contexto, titulo=doc['titulo'],
                             abstract=doc['abstract'], candidatos=doc['candidatos'])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='Selecciona una única posición de cita en el contexto.') from exc
    resultado = analisis_cita_ms(entrada)
    return {**resultado, 'articulo': {'paper_id': consulta.paper_id, 'titulo': doc['titulo'],
            'fuente': doc['fuente'], 'publicacion': doc['publicacion'], 'sha256_ocl': doc['sha256_ocl'],
            'version_contenido': version, 'total_fragmentos': len(doc['candidatos']),
            'licencia': data['licencia'], 'fragmentacion': data['fragmentacion']}}


@router.get("/api/analisis-cita-ms/estado")
def estado_ms(request: Request):
    from src.app.ms_config import ARTIFACTS, MANIFEST_SCIBERT
    manifest_scibert_existe = MANIFEST_SCIBERT.is_file()
    checkpoint_m_existe = (ARTIFACTS / "M/model.safetensors").is_file()
    checkpoint_s_existe = (ARTIFACTS / "S/model.safetensors").is_file()
    manifiesto_m_existe = (ARTIFACTS / "M/manifiesto_entrenamiento.json").is_file()
    manifiesto_s_existe = (ARTIFACTS / "S/manifiesto_entrenamiento.json").is_file()
    artefactos_presentes = all((
        manifest_scibert_existe, checkpoint_m_existe, checkpoint_s_existe,
        manifiesto_m_existe, manifiesto_s_existe,
    ))
    import os
    return {
        "modelos_cargados": getattr(request.app.state, "modelos_cargados", False),
        'busqueda_cientifica_disponible': hasattr(request.app.state, 'article_search'),
        'total_catalogo_cientifico': len(request.app.state.article_search.papers) if hasattr(request.app.state, 'article_search') else 0,
        'version_indice_cientifico': request.app.state.article_search.version if hasattr(request.app.state, 'article_search') else None,
        "release": os.environ.get("MS_RELEASE_ID"),
        "revision_codigo": os.environ.get("MS_CODE_SHA"),
        "habilitado": True,  # La ruta HTTP esta publicada, no es un chequeo de inferencia.
        "artefactos_locales_presentes": artefactos_presentes,
        "inferencia_verificada_por_estado": False,  # Este GET no ejecuta modelos.
        "manifest_scibert_existe": manifest_scibert_existe,
        "checkpoint_m_existe": checkpoint_m_existe,
        "checkpoint_s_existe": checkpoint_s_existe,
        "manifiesto_m_existe": manifiesto_m_existe,
        "manifiesto_s_existe": manifiesto_s_existe,
        "nota": (
            "La ruta esta habilitada, pero no se ha verificado carga ni inferencia en "
            "esta consulta. Compruebe la carga real con POST; los archivos por si "
            "solos no garantizan que los modelos funcionen."
        ),
    }


@router.post("/api/analisis-cita-ms")
def analisis_cita_ms(consulta: ConsultaMS):
    from src.app.ms_runtime import analizar_seguro, ServicioOcupado
    try:
        return analizar_seguro(
            consulta.contexto, consulta.titulo, consulta.abstract,
            [c.model_dump() for c in consulta.candidatos],
        )
    except ServicioOcupado as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "5"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        # Evitar exponer rutas internas y trazas en HTTP; ver error en log del servidor.
        import logging
        logging.getLogger(__name__).exception("Error al cargar o ejecutar M/S")
        raise HTTPException(status_code=503, detail="Modelos científicos no disponibles; revisar registro del servidor") from exc
