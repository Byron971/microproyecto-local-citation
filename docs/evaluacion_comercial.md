# Evaluación de modelos comerciales — corte 20 de septiembre

Este módulo corresponde al frente del issue #40. Su responsabilidad es ejecutar modelos comerciales sobre el mismo Test Gold y los mismos prompts que usa el resto del equipo, registrar latencia, uso, costo cuando exista una tarifa explícita, reintentos y errores, y producir archivos comparables para el pipeline global de métricas.

## Dependencias con el equipo

- Issue #41: entrega el Test Gold definitivo y los resultados del modelo open-weight.
- Issue #43: entrega las estrategias de prompting versionadas.
- Issue #40: ejecuta los modelos comerciales y consolida telemetría/resultados.
- Issue #42: consume las predicciones y calcula Precision, Recall, F1 Macro, F1 Micro y matrices de confusión.

## Configuración segura

Las variables de entorno de ejemplo están en:

config/citation_eval.env.example

Para OpenAI:

OPENAI_API_KEY=...
OPENAI_MODEL=nombre-del-modelo

Para Gemini:

GEMINI_API_KEY=...
GEMINI_MODEL=nombre-del-modelo

Para Cohere:

COHERE_API_KEY=...
COHERE_MODEL=command-a-plus-05-2026

Para open-weight:

OPENWEIGHT_BASE_URL=http://localhost:11434/v1
OPENWEIGHT_MODEL=nombre-del-modelo-local
OPENWEIGHT_API_KEY=local

No se deben versionar credenciales reales. OPENAI_MODEL, GEMINI_MODEL y COHERE_MODEL permiten cambiar los modelos sin modificar código. Gemini y Cohere usan sus capas oficiales de compatibilidad con OpenAI.

## Formato del Test Gold

Archivo JSONL, una observación por línea:

```json
{"id":"case-001","input":"texto de entrada","gold":"Background"}
```

El repositorio mantiene dos estados posibles:

- annotations/citation_function/provisional_test_gold.jsonl: conjunto provisional de 20 casos, construido a partir de la primera validación manual por parte del equipo. Sirve para pruebas técnicas, no para resultados definitivos.
- annotations/citation_function/test_gold.jsonl: nombre reservado para el conjunto definitivo después de la segunda validación manual independiente, acuerdo interanotador y reconciliación.

## Formato de prompts

Los tres prompts versionados viven en:

config/prompts/citation_function_prompts.json

Cada modelo debe devolver un arreglo JSON de nueve puntajes en el mismo orden de categorías.

## Preflight sin consumir APIs

El orquestador valida datos, prompts y variables de entorno antes de llamar proveedores:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode openai \
  --check-only
```

Para verificar Cohere:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode cohere \
  --check-only
```

Para verificar la configuración open-weight:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode openweight \
  --check-only
```

Para verificar ambos modelos comerciales:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode commercial \
  --check-only
```

Para verificar OpenAI, Gemini y open-weight en una sola configuración:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode all \
  --check-only
```

El preflight no realiza llamadas de red.

## Corrida preliminar sobre el gold provisional

Solo para comprobar el pipeline técnico:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode openai \
  --allow-provisional \
  --output-dir artifacts/citation_function_eval/openai_provisional
```

Para una corrida preliminar de Cohere:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode cohere \
  --allow-provisional \
  --output-dir artifacts/citation_function_eval/cohere_provisional
```

El flag --allow-provisional es obligatorio para una corrida real sobre el conjunto provisional. El archivo run_metadata.json queda marcado con provisional_gold=true para evitar que esos resultados se presenten como finales.

## Corrida final

Cuando exista annotations/citation_function/test_gold.jsonl:

```bash
uv run python -m src.evaluation.commercial.orchestrate \
  --mode all \
  --output-dir artifacts/citation_function_eval/final
```

El orquestador usa automáticamente el Test Gold definitivo cuando existe.

## Parser y métricas

Todas las respuestas pasan por el parser común de nueve puntajes. Después se generan automáticamente:

- Precision Macro y Micro
- Recall Macro y Micro
- F1 Macro y Micro
- Accuracy
- cobertura de clasificación
- errores de formato
- errores de proveedor
- latencia media
- reintentos
- tokens de entrada y salida
- costo estimado, solo cuando se suministra pricing explícito
- matrices de confusión 9x9

Las repeticiones de un mismo caso se promedian antes de calcular el argmax, evitando inflar artificialmente el tamaño del Test Gold.

## Tarifas y costo

El repositorio no contiene precios hardcodeados. Para calcular costo se suministra un JSON explícito:

```json
{
  "openai:nombre-del-modelo": {
    "input_usd_per_million": 0.0,
    "output_usd_per_million": 0.0
  }
}
```

Los valores del ejemplo son solo marcadores y deben reemplazarse por la tarifa vigente que el equipo decida documentar. Si no se suministra pricing, estimated_cost_usd queda vacío.

Uso:

```bash
--pricing ruta/pricing.json
```

## Salidas

El directorio de salida contiene:

```text
results.jsonl
summary.csv
run_metadata.json
metrics/
  evaluation_summary.csv
  predictions.csv
  confusion_matrices/
```

results.jsonl conserva cada respuesta cruda y la telemetría. evaluation_summary.csv es la tabla principal para la comparación global.

## Seguridad e integridad

- No versionar API keys, tokens ni cabeceras de autenticación.
- No copiar credenciales en issues, commits o resultados.
- No presentar el gold provisional como Test Gold definitivo.
- No inventar Precision, Recall, F1, costos o acuerdo interanotador.
- Las métricas finales deben provenir del mismo Test Gold para todos los modelos.

## Estado actual

Los prompts, el parser, el runner, el pipeline de métricas, los clientes configurables de OpenAI, Gemini y Cohere, el cliente open-weight y el orquestador de punta a punta están implementados. La corrida definitiva sigue dependiendo de dos insumos externos al código: la segunda validación manual independiente que permita congelar el Test Gold y las credenciales/modelos reales que el equipo use para ejecutar los proveedores.


## Límites de tasa en planes gratuitos

Algunos proveedores gratuitos imponen límites de solicitudes por minuto. El orquestador admite una pausa explícita entre ejecuciones:

```bash
--request-delay-seconds 5
```

Para Gemini Free Tier con un límite observado de 15 solicitudes por minuto, se recomienda usar 5 segundos entre ejecuciones (aprox. 12 solicitudes/minuto) y, si una corrida previa agotó temporalmente la cuota, esperar al menos un minuto antes de reiniciar. Para evitar reintentos inmediatos innecesarios durante la prueba controlada puede combinarse con `--max-retries 0`.
