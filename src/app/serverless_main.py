"""SageMaker adapter only; keeps the public M/S contracts unchanged."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.app.science_main import lifespan
from src.app.ms_router import ConsultaArticulo, ConsultaMS, analizar_articulo, analisis_cita_ms

app = FastAPI(title='Prueba M/S SageMaker Serverless', lifespan=lifespan)


@app.api_route('/ping', methods=['GET', 'POST'])
def ping(request: Request):
    ready = getattr(request.app.state, 'modelos_cargados', False)
    return JSONResponse({'listo': ready}, status_code=200 if ready else 503)


@app.post('/invocations')
def invoke(consulta: ConsultaArticulo | ConsultaMS):
    if isinstance(consulta, ConsultaArticulo):
        return analizar_articulo(consulta)
    return analisis_cita_ms(consulta)
