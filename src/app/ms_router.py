"""Endpoints opt-in de la demostración científica M/S (sin modificar A4)."""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
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
    asincrono: bool = False
    contexto: str = Field(min_length=1, max_length=4000)
    paper_id: str = Field(pattern=r'^[A-Z][0-9]{2}-[0-9]{4}$')


class BusquedaCientifica(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=10, ge=1, le=20)
    modelo: str | None = None


def espera_sugerencias():
    """Segundos que una sugerencia espera al encoder (por debajo de los 30 s del gateway)."""
    try:
        valor = float(os.environ.get('MS_SUGERENCIAS_ESPERA_S', '15'))
    except ValueError:
        valor = 15.0
    return min(max(valor, 0.0), 20.0)


@router.get('/api/analisis-cita-ms/modelos')
def modelos_cientificos(request: Request):
    from src.app.scientific_search import MODEL_ID
    listo = hasattr(request.app.state, 'article_search')
    return {'predeterminado': MODEL_ID, 'modelos': [{
        'id': MODEL_ID, 'nombre': 'SciBERT · búsqueda semántica de artículos',
        'descripcion': 'Sugiere candidatos por título y resumen mediante SciBERT existente. La búsqueda del paso 2 abarca el catálogo completo; M/S clasifican la función después.',
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
    # Espera acotada: el worker M/S libera el encoder entre etapas.
    if not _LOCK.acquire(timeout=espera_sugerencias()):
        raise HTTPException(status_code=429, detail='El buscador está ocupado con otro análisis. Vuelve a intentarlo o elige el artículo manualmente.',
                            headers={'Retry-After': '5'})
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
    try:
        articles = []
        for pid in consulta.paper_ids:
            doc = data['documentos'].get(pid)
            articles.append(dict(paper_id=pid, disponible=doc is not None,
                motivo=None if doc else 'Sin texto completo preparado para M/S.',
                total_fragmentos=len(doc['candidatos']) if doc else 0,
                truncamiento=doc.get('truncamiento') if doc else None))
        return {'version_contenido': version, 'articulos': articles}
    except ValueError:
        raise HTTPException(status_code=503, detail='El artículo preparado no supera la validación.') from None



def _preparar_articulo(contexto, paper_id):
    """Valida artículo y posición de cita; idéntico para modo síncrono y cola."""
    data, version = _corpus_articulos()
    try:
        doc = data['documentos'].get(paper_id)
    except ValueError:
        raise HTTPException(status_code=503, detail='El artículo preparado no supera la validación.') from None
    if doc is None:
        raise HTTPException(status_code=404, detail='Artículo sin texto completo preparado para M/S.')
    try:
        entrada = ConsultaMS(contexto=contexto, titulo=doc['titulo'],
                             abstract=doc['abstract'], candidatos=doc['candidatos'])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='Selecciona una única posición de cita en el contexto.') from exc
    return doc, data, version, entrada


def _metadatos_articulo(paper_id, doc, data, version):
    return {'paper_id': paper_id, 'titulo': doc['titulo'],
            'fuente': doc['fuente'], 'publicacion': doc['publicacion'], 'sha256_ocl': doc['sha256_ocl'],
            'version_contenido': version, 'total_fragmentos': len(doc['candidatos']),
            'licencia': data['licencia'], 'fragmentacion': data['fragmentacion'], 'truncamiento': doc.get('truncamiento')}


def ejecutar_trabajo(trabajo):
    """Inferencia de un trabajo de la cola. Solo la llama el worker, nunca un GET."""
    from src.app.article_corpus import CorpusUnavailable, corpus
    from src.app.ms_lock import LOCK as _LOCK
    from src.app.ms_queue import EntradaInvalida
    from src.app.ms_runtime import obtener_servicio
    solicitud = trabajo['solicitud']
    try:
        data, version = corpus()
    except CorpusUnavailable as exc:
        raise RuntimeError('Corpus no disponible') from exc
    if version != solicitud['version_contenido']:
        raise EntradaInvalida('version')
    doc = data['documentos'].get(solicitud['paper_id'])
    if doc is None:
        raise EntradaInvalida()
    try:
        entrada = ConsultaMS(contexto=solicitud['contexto'], titulo=doc['titulo'],
                             abstract=doc['abstract'], candidatos=doc['candidatos'])
    except ValueError as exc:
        raise EntradaInvalida() from exc

    def por_etapa(funcion):
        # Bloqueo por etapa: las sugerencias pueden intercalarse entre recuperación, M y S.
        with _LOCK:
            return funcion()

    try:
        resultado = obtener_servicio().analizar(
            entrada.contexto, entrada.titulo, entrada.abstract,
            [c.model_dump() for c in entrada.candidatos], por_etapa=por_etapa)
    except ValueError as exc:
        raise EntradaInvalida() from exc
    return {**resultado, 'articulo': _metadatos_articulo(solicitud['paper_id'], doc, data, version)}


def _cola(request):
    servicio = getattr(request.app.state, 'ms_jobs', None)
    if servicio is None:
        raise HTTPException(status_code=503, detail='La cola de análisis no está disponible.')
    return servicio


def _admitir(servicio, clave, consulta, version):
    from src.app.ms_queue import ClaveReutilizada, ColaLlena, ErrorEncolado
    solicitud = {'paper_id': consulta.paper_id, 'contexto': consulta.contexto, 'version_contenido': version}
    try:
        return servicio.admitir(clave, solicitud)
    except ColaLlena:
        raise HTTPException(status_code=429, detail='Hay demasiados análisis en espera. Inténtalo en unos minutos.',
                            headers={'Retry-After': '30'}) from None
    except ClaveReutilizada:
        raise HTTPException(status_code=409, detail='Esta solicitud ya se usó para otro análisis. Vuelve a analizar.') from None
    except ErrorEncolado:
        raise HTTPException(status_code=503, detail='No se pudo poner el análisis en la cola. Inténtalo de nuevo en unos segundos.') from None
    except Exception:
        logging.getLogger(__name__).exception('Fallo al registrar el trabajo M/S')
        raise HTTPException(status_code=503, detail='No se pudo registrar el análisis. Inténtalo de nuevo en unos segundos.') from None


def _leer(servicio, trabajo_id):
    try:
        return servicio.leer(trabajo_id)
    except Exception:
        logging.getLogger(__name__).exception('Fallo al leer el trabajo M/S')
        raise HTTPException(status_code=503, detail='No se pudo consultar el análisis. Se seguirá intentando.') from None


class ConsultaTrabajo(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    paper_id: str = Field(pattern=r'^[A-Z][0-9]{2}-[0-9]{4}$')
    clave_idempotencia: str = Field(pattern=r'^[A-Za-z0-9-]{16,64}$')


NO_DISPONIBLE = 'El análisis no existe o ya no está disponible. Tu contexto se conserva; vuelve a analizar.'


@router.post('/api/analisis-cita-ms/trabajos', status_code=202)
def crear_trabajo(consulta: ConsultaTrabajo, request: Request):
    servicio = _cola(request)
    _, _, version, _ = _preparar_articulo(consulta.contexto, consulta.paper_id)
    vista, _ = _admitir(servicio, consulta.clave_idempotencia, consulta, version)
    return JSONResponse(vista, status_code=202 if vista['estado'] in ('en_cola', 'procesando') else 200)


@router.get('/api/analisis-cita-ms/trabajos/{trabajo_id}')
def leer_trabajo(trabajo_id: str, request: Request):
    vista = _leer(_cola(request), trabajo_id)
    if vista is None:
        raise HTTPException(status_code=404, detail=NO_DISPONIBLE)
    return vista


@router.post('/api/analisis-cita-ms/trabajos/{trabajo_id}/cancelar')
def cancelar_trabajo(trabajo_id: str, request: Request):
    from src.app.ms_queue import TrabajoEnCurso
    servicio = _cola(request)
    try:
        vista = servicio.cancelar(trabajo_id)
    except TrabajoEnCurso:
        raise HTTPException(status_code=409, detail='El análisis ya se está calculando y no se puede detener. El resultado aparecerá al terminar.') from None
    except Exception:
        logging.getLogger(__name__).exception('Fallo al cancelar el trabajo M/S')
        raise HTTPException(status_code=503, detail='No se pudo cancelar el análisis. Inténtalo de nuevo.') from None
    if vista is None:
        raise HTTPException(status_code=404, detail=NO_DISPONIBLE)
    return vista


# Contrato anterior: estado 'procesando' + 202 mientras no termine (bundles web en caché).
CODIGOS_ANTERIORES = {'entrada_invalida': 422, 'version': 409, 'expirado': 504}


@router.post('/api/analisis-cita-ms/articulo')
def analizar_articulo(consulta: ConsultaArticulo, request: Request):
    doc, data, version, entrada = _preparar_articulo(consulta.contexto, consulta.paper_id)
    if consulta.asincrono:
        import uuid
        vista, _ = _admitir(_cola(request), str(uuid.uuid4()), consulta, version)
        return JSONResponse({'estado': 'procesando', 'trabajo_id': vista['trabajo_id']}, status_code=202)
    servicio = getattr(request.app.state, 'ms_jobs', None)
    try:
        ocupado = servicio is not None and servicio.hay_activos()
    except Exception:
        ocupado = True
    if ocupado:
        # El modo síncrono no se adelanta a la cola.
        raise HTTPException(status_code=429, detail='El servicio científico está ocupado', headers={'Retry-After': '5'})
    resultado = analisis_cita_ms(entrada)
    return {**resultado, 'articulo': _metadatos_articulo(consulta.paper_id, doc, data, version)}


@router.get('/api/analisis-cita-ms/articulo/{trabajo_id}')
def consultar_analisis_articulo(trabajo_id: str, request: Request):
    vista = _leer(_cola(request), trabajo_id)
    if vista is None or vista['estado'] == 'cancelado':
        raise HTTPException(status_code=410, detail='El análisis expiró o el servicio se reinició. Vuelve a analizar; tu contexto se conserva.')
    if vista['estado'] in ('en_cola', 'procesando'):
        return JSONResponse({'estado': 'procesando', 'trabajo_id': trabajo_id}, status_code=202)
    if vista['estado'] == 'completado':
        return vista['resultado']
    error = vista.get('error') or {}
    raise HTTPException(status_code=CODIGOS_ANTERIORES.get(error.get('codigo'), 503),
                        detail=error.get('mensaje', 'No se pudo completar el análisis científico.'))


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
        'total_articulos_preparados': getattr(request.app.state, 'total_articulos_preparados', None),
        'version_corpus': getattr(request.app.state, 'version_corpus', None),
        'total_catalogo_cientifico': len(request.app.state.article_search.papers) if hasattr(request.app.state, 'article_search') else 0,
        'cola_trabajos': getattr(request.app.state, 'ms_jobs_backend', None),
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
