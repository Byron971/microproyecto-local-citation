# Evaluación de modelos comerciales — corte 20 de septiembre

Este módulo corresponde al frente del issue #40. Su responsabilidad es ejecutar modelos comerciales sobre el mismo Test Gold y los mismos prompts que usa el resto del equipo, registrar latencia, uso, costo cuando exista una tarifa explícita, reintentos y errores, y producir archivos comparables para el pipeline global de métricas.

## Dependencias con el equipo

- Issue #41: entrega el Test Gold definitivo y los resultados del modelo open-weight.
- Issue #43: entrega las estrategias de prompting versionadas.
- Issue #40: ejecuta los modelos comerciales y consolida telemetría/resultados.
- Issue #42: consume las predicciones y calcula Precision, Recall, F1 Macro, F1 Micro y matrices de confusión.

El runner no duplica las métricas del issue #42.

## Formato del Test Gold

Archivo JSONL, una observación por línea:

```json
{"id":"case-001","input":"texto de entrada","gold":"etiqueta_objetivo"}
```

Cualquier campo adicional se conserva como metadata.

## Formato de prompts

Archivo JSON con nombre de estrategia y plantilla. Todas las plantillas deben incluir `{input}`:

```json
{
  "zero_shot": "Clasifique el siguiente texto: {input}",
  "few_shot": "Ejemplos... Ahora clasifique: {input}"
}
```

## Validar entradas sin consumir APIs

```bash
uv run python -m src.evaluation.commercial.cli \
  --gold ruta/test_gold.jsonl \
  --prompts ruta/prompts.json \
  --check-only
```

Este comando no realiza llamadas de red.

## Contrato de un cliente comercial

Los proveedores se conectan mediante una clase u objeto con dos atributos y un método:

```python
from src.evaluation.commercial.schema import ProviderResponse

class MiCliente:
    provider = "proveedor"
    model = "modelo-versionado"

    def generate(self, prompt: str) -> ProviderResponse:
        # La implementación concreta usa el SDK oficial y lee la clave
        # desde una variable de entorno. Nunca debe incluir la clave en Git.
        return ProviderResponse(
            text="respuesta cruda",
            input_tokens=100,
            output_tokens=20,
        )


def build_client():
    return MiCliente()
```

El CLI carga la factory con `module:factory`. Ejemplo:

```bash
uv run python -m src.evaluation.commercial.cli \
  --gold ruta/test_gold.jsonl \
  --prompts ruta/prompts.json \
  --client mi_modulo:build_client \
  --output-dir artifacts/commercial_eval
```

Se pueden repetir varios `--client` para evaluar varios modelos en la misma corrida.

## Parser de respuestas

Si el equipo define un parser común, puede pasarse como `module:function`:

```bash
--parser mi_modulo:parse_label
```

Si el parser falla, el registro queda con `status=parse_error`, pero la respuesta original se conserva en `raw_response` para poder auditarla y contabilizar errores de formato.

## Tarifas y costo

El runner no contiene precios hardcodeados. Para estimar costo debe suministrarse un JSON explícito:

```json
{
  "proveedor:modelo-versionado": {
    "input_usd_per_million": 2.0,
    "output_usd_per_million": 10.0
  }
}
```

Uso:

```bash
--pricing ruta/pricing.json
```

Si no existe una tarifa para un modelo o el proveedor no entrega conteo de tokens, `estimated_cost_usd` queda vacío.

## Reintentos

El valor predeterminado es `--max-retries 2`, es decir, hasta dos reintentos después del primer intento. Solo se reintentan errores que el adaptador marque como transitorios mediante `ProviderCallError(..., transient=True)`.

## Salidas

El directorio de salida contiene:

```text
results.jsonl
summary.csv
```

Cada registro contiene:

- case_id
- provider
- model
- prompt_name
- prompt_text
- raw_response
- parsed_output
- latency_ms
- input_tokens
- output_tokens
- estimated_cost_usd
- retry_count
- status
- error
- started_at
- gold

`results.jsonl` es la fuente detallada y auditable. `summary.csv` facilita la consolidación para el reporte.

## Seguridad

- No versionar API keys, tokens ni cabeceras de autenticación.
- Leer credenciales desde variables de entorno.
- No guardar secretos en `results.jsonl` ni `summary.csv`.
- Las pruebas automatizadas usan clientes falsos y no consumen APIs ni saldo.

## Estado actual

La infraestructura de evaluación está lista y probada. La ejecución real de modelos comerciales depende de que el equipo entregue el Test Gold definitivo (#41), los prompts finalistas (#43), la lista/versiones de modelos comerciales y las credenciales de los proveedores. El repositorio no define todavía esos nombres de modelo, por lo que no se inventan ni se fijan en código.
