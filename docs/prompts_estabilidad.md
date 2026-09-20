# Prompts y estabilidad de clasificación de función de cita — issue #43

Este documento cubre el frente del issue #43: diseñar y versionar las
estrategias de *prompting* para clasificación de función de cita (9
categorías) y medir, sin depender todavía de un modelo definitivo, qué tan
estable y bien formateada es la respuesta de un modelo para cada estrategia.

## Prompts

Las tres estrategias están versionadas en
`config/prompts/citation_function_prompts.json`: `zero_shot_generic`,
`zero_shot_detailed` y `few_shot`. Cada plantilla recibe un único campo
`{input}` con el contexto de cita más el título y resumen del artículo
citado, y pide como respuesta un arreglo de 9 flotantes entre 0.0 y 1.0
(uno por categoría) para facilitar el parseo automático.

## Conjunto piloto

`src/data/build_citation_function_pilot.py` genera de forma reproducible
(semilla fija) un conjunto de 20 contextos de cita reales tomados de
`data/raw/`, sin etiqueta de función de cita real (`gold: null` en todos
los casos): sirve solo para medir formato y estabilidad, no accuracy.
Se guarda en `tests/fixtures/citation_function_pilot.jsonl`.

## Metodología de estabilidad

Cada combinación caso+prompt se ejecuta varias veces contra el mismo
modelo. `src/evaluation/commercial/stability.py` agrupa las repeticiones
por `(case_id, prompt_name, provider, model)` y calcula, por cada
combinación prompt+proveedor+modelo:

- `avg_format_error_rate`: fracción de respuestas que no parsean como
  arreglo válido de 9 números entre 0.0 y 1.0 (excluyendo errores de
  proveedor, contados aparte).
- `avg_provider_error_rate`: fracción de ejecuciones que fallaron por
  error del proveedor (reintentos agotados), no por formato.
- `avg_label_stability`: fracción de repeticiones parseables cuyo argmax
  coincide con la moda del caso, promediada sobre los casos con al menos
  una respuesta parseable.
- `n_cases_with_valid_responses`: cuántos de los casos piloto tuvieron al
  menos una respuesta parseable, para no confundir "sin datos" con
  "estable".
- `avg_latency_ms`, `avg_retry_count`: agregados de la telemetría que ya
  registra el runner.

El parser toma la última coincidencia de `[...]` en la respuesta que
valide como arreglo de 9 números — así una respuesta que repite el
ejemplo del propio prompt antes de contestar no se confunde con la
respuesta real.

## Cómo ejecutar

Ejecutar una evaluación (requiere un cliente que implemente el contrato
`CommercialModelClient` de `src/evaluation/commercial/providers.py`):

```bash
uv run python -m src.evaluation.commercial.cli \
  --gold tests/fixtures/citation_function_pilot.jsonl \
  --prompts config/prompts/citation_function_prompts.json \
  --client mi_modulo:build_client \
  --output-dir artifacts/commercial_eval
```

Calcular las métricas de estabilidad sobre los resultados:

```bash
uv run python -m src.evaluation.commercial.stability \
  --results artifacts/commercial_eval/results.jsonl \
  --output artifacts/commercial_eval/stability_summary.csv
```

## Decisión pendiente

No hay todavía un modelo de prueba configurado. `src/evaluation/commercial/providers_local.py`
lanza `LocalProviderNotConfiguredError` en vez de intentar una llamada real,
hasta que el equipo decida entre:

- **Open-weight local vía Ollama**: gratis, sin cuentas ni facturación,
  instalable en minutos.
- **API comercial (OpenAI/Gemini/Anthropic) con cuenta propia**: más
  representativo del modelo final, pero requiere gestionar credenciales y
  posible costo.

## Recomendación de prompt(s) finalista(s)

Pendiente: se completa una vez se resuelva la decisión anterior y se
corran las repeticiones necesarias contra un modelo real. El criterio de
selección es: menor `avg_format_error_rate`, y entre empates, mayor
`avg_label_stability`.
