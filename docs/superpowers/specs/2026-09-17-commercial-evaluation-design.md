# Diseño: evaluación de modelos comerciales para el 20 de septiembre

## Objetivo

Cerrar el frente asignado a Byron971 en el issue #40 sin duplicar el trabajo de los issues #41, #42 y #43. El código debe ejecutar modelos comerciales sobre un Test Gold común y prompts versionados, registrar costo/latencia/errores y producir resultados consumibles por el pipeline global de métricas.

## Alcance

Este frente implementará la orquestación de evaluaciones comerciales y la captura de telemetría. No calculará Precision, Recall, F1 ni matrices de confusión, porque esas responsabilidades pertenecen al issue #42. Tampoco definirá el Test Gold (#41) ni las estrategias finales de prompting (#43).

## Arquitectura

Se añadirá un módulo independiente bajo `src/evaluation/commercial/` con cuatro responsabilidades separadas:

1. `schema.py`: tipos de datos para casos de evaluación, prompts, respuestas y registros de ejecución.
2. `runner.py`: orquestación de ejecuciones, medición de latencia, reintentos y captura de errores.
3. `io.py`: lectura del Test Gold/prompts y escritura de resultados JSONL/CSV.
4. `providers.py`: interfaz mínima de cliente comercial. Los proveedores concretos se conectan mediante implementaciones que respeten el mismo contrato.

La primera versión será deliberadamente agnóstica al proveedor. Esto evita fijar nombres de modelos o SDKs que todavía no están versionados en el repositorio y permite que OpenAI, Anthropic, Google u otro proveedor se conecte sin cambiar el pipeline de evaluación.

## Contratos de entrada

### Test Gold

Formato JSONL. Cada línea debe contener:

```json
{"id":"case-001","input":"texto de entrada","gold":"etiqueta_objetivo"}
```

Los campos extra se preservarán en `metadata` cuando existan.

### Prompts

Formato JSON. Cada estrategia se identifica por nombre y debe contener una plantilla con `{input}`:

```json
{
  "zero_shot": "Clasifique el siguiente texto: {input}",
  "few_shot": "... {input}"
}
```

## Salida de cada ejecución

Cada combinación caso × modelo × prompt genera un registro con:

- `case_id`
- `provider`
- `model`
- `prompt_name`
- `prompt_text`
- `raw_response`
- `parsed_output` opcional
- `latency_ms`
- `input_tokens` opcional
- `output_tokens` opcional
- `estimated_cost_usd` opcional
- `retry_count`
- `status`: `ok`, `provider_error` o `parse_error`
- `error` opcional
- `started_at`

Los resultados detallados se guardan como JSONL. Un CSV de resumen contendrá una fila por ejecución y columnas planas para facilitar la consolidación del reporte.

## Costos

El runner no inventará precios. El costo se calculará únicamente si el adaptador del proveedor entrega información de uso y se suministra una tabla de precios explícita para ese modelo. Si no hay precio configurado, `estimated_cost_usd` queda vacío.

## Reintentos

Por defecto habrá hasta 2 reintentos después del intento inicial para errores transitorios reportados por el adaptador. Cada reintento se contabiliza. Los errores permanentes se registran sin ocultarlos ni descartar el caso.

## Seguridad

- Ninguna clave API se versiona.
- Los adaptadores concretos leerán credenciales desde variables de entorno.
- Las pruebas usarán clientes falsos y nunca llamarán servicios externos.
- Los resultados no incluirán secretos ni cabeceras HTTP.

## Integración con el trabajo del equipo

- #41 produce el Test Gold definitivo.
- #43 produce los prompts versionados.
- Este frente (#40) ejecuta modelos comerciales y genera telemetría/resultados.
- #42 consume `parsed_output` y `gold` para calcular las métricas finales.

## Pruebas

Se cubrirán como mínimo:

- carga válida e inválida de Test Gold;
- validación de plantillas de prompt;
- medición de latencia;
- reintentos y conteo correcto;
- persistencia JSONL/CSV;
- costo ausente cuando no exista tabla de precios;
- propagación de respuestas no parseables sin perder la respuesta cruda;
- aislamiento completo de red mediante clientes falsos.

## Criterios de aceptación

1. La rama contiene un pipeline reproducible de evaluación comercial.
2. El pipeline no depende de un proveedor concreto para funcionar.
3. Todos los resultados conservan respuesta cruda y telemetría suficiente para el reporte.
4. El formato de salida puede ser consumido por el pipeline del issue #42.
5. No se versionan credenciales.
6. Las pruebas automatizadas no realizan llamadas externas.
7. La documentación explica cómo conectar un proveedor y cómo ejecutar la evaluación cuando estén disponibles Test Gold, prompts, modelos y credenciales.
