"""Un caso por llamada; proveedor opcional y separado del arranque M/S."""
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.app.commercial_limits import commercial_slot, dynamodb_client

router = APIRouter(tags=['Clasificadores'])
MODEL = 'gpt-6.1-sol'
PROFILE = 'zero_shot_detailed'
CLASSES = ('Background', 'Gap', 'Basis', 'Comparison', 'Application',
           'Improvement / Modification', 'Evidence', 'Identification of the Originator', 'Further Reading')
PROMPTS = Path(__file__).resolve().parents[2] / 'config/prompts/citation_function_prompts.json'


def enabled():
    return (os.environ.get('CITAS_COMMERCIAL_ENABLED') == '1'
            and bool(os.environ.get('OPENAI_API_KEY'))
            and bool(os.environ.get('CITAS_COMMERCIAL_LIMIT_TABLE')))


@router.get('/api/clasificadores')
def catalog():
    models = [{'id': key, 'familia': 'M/S', 'nombre': 'Encoder SciBERT — ' + key} for key in ['M', 'S']]
    if enabled() and os.environ.get('CITAS_COMMERCIAL_VISIBLE') == '1':
        models.append({'id': 'commercial', 'familia': 'Comercial', 'nombre': 'GPT-6.1 Sol',
                       'proveedor': 'OpenAI', 'modelo': MODEL, 'perfil': PROFILE})
    return {'clasificadores': models}


class CommercialQuery(BaseModel):
    contexto: str = Field(min_length=1, max_length=4000)
    paper_id: str = Field(pattern=r'^[A-Z][0-9]{2}-[0-9]{4}$')
    consentimiento: bool = False

    @model_validator(mode='after')
    def target(self):
        if self.contexto.count('TARGETCIT') != 1:
            raise ValueError('Marca exactamente una cita con TARGETCIT')
        return self


def reserve_call():
    """Contador diario global y persistente; cada intento consume una unidad."""
    from botocore.exceptions import ClientError
    now = datetime.now(timezone.utc)
    try:
        limit = int(os.environ.get('CITAS_COMMERCIAL_DAILY_LIMIT', '10'))
    except ValueError:
        raise HTTPException(503, 'Límite comercial no configurado correctamente.') from None
    if not 1 <= limit <= 100:
        raise HTTPException(503, 'Límite comercial no configurado correctamente.')
    try:
        dynamodb_client().update_item(
            TableName=os.environ['CITAS_COMMERCIAL_LIMIT_TABLE'],
            Key={'id': {'S': 'openai:' + now.strftime('%Y-%m-%d')}},
            UpdateExpression='SET expires_at = :ttl ADD #calls :one',
            ExpressionAttributeNames={'#calls': 'calls'},
            ConditionExpression='attribute_not_exists(#calls) OR #calls < :limit',
            ExpressionAttributeValues={':one': {'N': '1'}, ':limit': {'N': str(limit)},
                ':ttl': {'N': str(int((now + timedelta(days=2)).timestamp()))}})
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise HTTPException(429, 'Se alcanzó el límite diario del modelo comercial.') from None
        raise HTTPException(503, 'No se pudo comprobar el límite comercial. Intenta más tarde.') from None
    except Exception:
        raise HTTPException(503, 'No se pudo comprobar el límite comercial. Intenta más tarde.') from None


@router.post('/api/comercial/clasificar')
def classify(query: CommercialQuery):
    if not enabled():
        raise HTTPException(503, 'El modelo comercial todavía no está habilitado.')
    if not query.consentimiento:
        raise HTTPException(422, 'Confirma el envío del contexto, título y resumen a OpenAI.')
    from src.app.article_corpus import corpus, CorpusUnavailable
    try:
        data, version = corpus()
        article = data['documentos'].get(query.paper_id)
    except CorpusUnavailable:
        raise HTTPException(503, 'El artículo preparado no está disponible.') from None
    if article is None:
        raise HTTPException(404, 'Artículo sin texto preparado.')
    raw = PROMPTS.read_bytes()
    template = json.loads(raw)[PROFILE]
    text = f"Citation context: {query.contexto}\nCited paper title: {article['titulo']}\nCited paper abstract: {article['abstract']}"
    prompt = template.replace('{input}', text)
    if len(prompt) > 25000:
        raise HTTPException(422, 'La entrada supera el límite del perfil comercial.')
    with commercial_slot():
        reserve_call()
        from src.evaluation.commercial.providers_openai import OpenAIClient
        from src.evaluation.commercial.stability import parse_score_array
        start = time.monotonic()
        try:
            response = OpenAIClient(MODEL, timeout_seconds=20, max_completion_tokens=1024).generate(prompt)
            scores = parse_score_array(response.text)
            if not response.model or not (response.model == MODEL or response.model.startswith(MODEL + '-')):
                raise ValueError('Identidad del modelo no confirmada')
        except Exception:
            # No exponer excepciones del SDK: pueden incluir detalles del proveedor.
            raise HTTPException(502, 'OpenAI no devolvió una clasificación válida. Los fragmentos se conservan.') from None
    highest = max(scores)
    winner = scores.index(highest) if highest > 0 and scores.count(highest) == 1 else None
    return {'paper_id': query.paper_id, 'version_contenido': version,
            'proveedor': 'OpenAI', 'modelo_solicitado': MODEL, 'modelo_efectivo': response.model,
            'perfil': PROFILE, 'sha256_prompts': hashlib.sha256(raw).hexdigest(),
            'clase': CLASSES[winner] if winner is not None else None,
            'abstencion': None if winner is not None else 'El proveedor no indicó una función única.',
            'puntuaciones': [{'clase': label, 'valor': value} for label, value in zip(CLASSES, scores)],
            'tipo_puntuacion': 'puntajes_generados_no_calibrados',
            'entrada': 'contexto_titulo_resumen', 'latencia_ms': round((time.monotonic() - start) * 1000),
            'tokens_entrada': response.input_tokens, 'tokens_salida': response.output_tokens}
