# Ejecución del modelo open-weight para el corte del 20 de septiembre

El repositorio incluye un cliente genérico para cualquier modelo open-weight servido mediante una API compatible con el esquema de chat de OpenAI.

## Configuración

Defina estas variables de entorno en la máquina que ejecutará el modelo:

OPENWEIGHT_BASE_URL=http://localhost:11434/v1
OPENWEIGHT_MODEL=nombre-del-modelo-local
OPENWEIGHT_API_KEY=local

OPENWEIGHT_MODEL debe contener exactamente el identificador que expone el servidor local. La selección concreta del modelo debe quedar documentada en el reporte; la propuesta contempla familias como Llama, Qwen o Mistral, pero el repositorio no inventa una versión si el equipo no la ha acordado.

No versionar llaves, tokens ni credenciales.

## Validar entradas

python -m src.evaluation.commercial.cli --gold ruta/test_gold.jsonl --prompts config/prompts/citation_function_prompts.json --check-only

## Ejecutar open-weight

python -m src.evaluation.commercial.cli --gold ruta/test_gold.jsonl --prompts config/prompts/citation_function_prompts.json --client src.evaluation.commercial.providers_openweight:build_client --parser src.evaluation.commercial.stability:parse_score_array --output-dir artifacts/openweight_eval

El runner registra latencia, tokens cuando el servidor los reporta, reintentos, errores de proveedor, errores de parseo y respuesta cruda.

## Calcular métricas

python -m src.evaluation.commercial.metrics --results artifacts/openweight_eval/results.jsonl --output-dir artifacts/openweight_eval/metrics

La salida incluye evaluation_summary.csv, predictions.csv y matrices de confusión por prompt.

## Comparabilidad

El modelo open-weight y los modelos comerciales deben ejecutarse sobre exactamente el mismo Test Gold y con el mismo orden de las nueve categorías. No se deben reportar Precision, Recall o F1 sobre el piloto con gold nulo.
