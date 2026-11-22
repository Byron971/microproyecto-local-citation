# Especificación técnica: diseño de prompts y análisis de estabilidad (issue #43)

## 1. Objetivo

Diseñar y versionar tres estrategias de *prompting* para la tarea de
clasificación de función de cita (9 categorías, definidas en la
[propuesta original](../../propuesta/0102_propuesta_proyecto_pln.md),
sección A5), y producir evidencia reproducible de qué tan estable y bien
formateada es la respuesta de un modelo con cada estrategia.

El entregable responde de manera reproducible:

> De las estrategias de prompting evaluadas (zero-shot genérico, zero-shot
> detallado, few-shot), ¿cuál produce respuestas mejor formateadas y más
> estables ante repeticiones de la misma entrada?

Este issue **no** mide accuracy contra etiquetas reales, no elige el
modelo comercial u open-weight definitivo, y no ejecuta la evaluación
oficial del proyecto. Esas responsabilidades pertenecen a los issues #40
(modelos comerciales), #41 (Test Gold y modelo open-weight) y #42
(pipeline de métricas Precision/Recall/F1 y matrices de confusión).

## 2. Alcance

### 2.1 Incluido

- Tres plantillas de prompt versionadas para las 9 categorías de función
  de cita.
- Un conjunto piloto de ~15-20 casos, construido a partir de contextos de
  cita ya existentes en `data/raw/`, sin etiqueta de función de cita real.
- Ejecución repetida (N=5) de cada combinación caso × prompt contra un
  modelo de prueba, usando el runner ya implementado en el issue #40.
- Cálculo de tasa de error de formato, estabilidad de la etiqueta
  predicha entre repeticiones, y agregación de latencia/reintentos.
- Conclusiones y recomendación de prompt(s) finalista(s).
- Pruebas automatizadas sin llamadas de red.

### 2.2 Fuera del alcance de este issue

- Evaluación de accuracy contra un Test Gold humano-validado (issue #41 /
  #42).
- Selección definitiva del modelo comercial u open-weight (issues #40 /
  #41).
- Anotación humana y acuerdo interanotador (issue #41).
- Cálculo de Precision/Recall/F1/matrices de confusión (issue #42).
- Costos y tarifas de proveedor (issue #40, cuando existan tarifas
  explícitas).

## 3. Insumos disponibles

| Componente | Ubicación | Estado |
|---|---|---|
| Runner de evaluación comercial (caso × prompt × modelo, reintentos, telemetría) | `src/evaluation/commercial/` en la rama `feature/20sep-commercial-eval-john` | Implementado y probado (14 pruebas), sin fusionar a `main` (PR #44, draft) |
| Contrato de proveedor (`generate()`, `ProviderResponse`) | `src/evaluation/commercial/providers.py` (misma rama) | Implementado |
| Formato de Test Gold y prompts (`JSONL` / `JSON` con `{input}`) | `docs/evaluacion_comercial.md` (misma rama) | Documentado |
| Contextos de cita reales sin etiqueta de función | `data/raw/` | Disponibles (corpus ACL-200 ya usado por el modelo de recomendación) |
| Definiciones de las 9 categorías de función de cita | `docs/propuesta/0102_propuesta_proyecto_pln.md`, sección "Esquema de Clasificación de Funciones de Cita" | Disponibles |

El trabajo de este issue se apoya en la infraestructura ya construida
para #40; no la duplica.

## 4. Decisión obligatoria pendiente (bloqueante para ejecutar corridas reales)

**No hay ningún modelo ni credencial configurados en el proyecto.** Se
verificó `pyproject.toml` y `uv.lock`: no existe ninguna dependencia de
SDK de LLM (`openai`, `anthropic`, `ollama`, `transformers`, etc.), ni
archivo `.env` con credenciales.

El equipo debe decidir, antes de poder ejecutar corridas reales de
estabilidad (no antes de escribir este spec ni el código):

| Opción | Costo/tiempo de arranque | Riesgo |
|---|---|---|
| Modelo open-weight local vía Ollama | Gratis; instalación en minutos (`brew install ollama` + `ollama pull <modelo>`) | Requiere recursos de cómputo local; resultados no necesariamente representativos de un modelo comercial |
| API comercial (OpenAI / Gemini / Anthropic) con cuenta propia | Requiere crear cuenta, posiblemente configurar facturación | Más representativo de lo que evaluará #40, pero más lento de arrancar y con costo asociado |

Esta especificación **no fija esa decisión**. El código se escribe con un
cliente placeholder (`providers_local.py`, sección 6.3) que cumple el
contrato esperado pero falla explícitamente con un mensaje claro
("configura el proveedor antes de ejecutar corridas reales") hasta que el
equipo decida. Esto permite que prompts, datos piloto, script de
estabilidad, CLI y pruebas queden completos y verificados sin bloquearse
en esta decisión.

## 5. Los tres prompts

Formato común: cada plantilla recibe un único campo `{input}` (para
cumplir el contrato ya definido por #40), que contiene el contexto de
cita junto con el título y resumen del artículo citado, en el siguiente
formato de texto:

```text
Citation context: <context>

Cited paper title: <title>
Cited paper abstract: <abstract>
```

Las 9 categorías (definiciones abreviadas, ver propuesta para el detalle
completo):

1. **Background** — contextualiza o resume el estado del arte.
2. **Gap** — identifica un vacío de investigación.
3. **Basis** — sirve de punto de partida intelectual del trabajo actual.
4. **Comparison** — compara el trabajo actual con el citado.
5. **Application** — usa un método/herramienta del citado sin modificarlo.
6. **Improvement / Modification** — adapta o extiende un método del citado.
7. **Evidence** — respalda una afirmación o hallazgo.
8. **Identification of the Originator** — reconoce el origen de una idea.
9. **Further Reading** — remite a literatura adicional.

Todas las plantillas piden la respuesta como un arreglo de 9 flotantes
entre 0.0 y 1.0 (uno por categoría, en el orden de la lista anterior)
para facilitar el parseo automático, siguiendo la convención ya definida
en la propuesta original.

### 5.1 Zero-shot genérico

```text
Classify the following citation context into one or more of these 9
citation function categories: Background, Gap, Basis, Comparison,
Application, Improvement/Modification, Evidence, Identification of the
Originator, Further Reading.

{input}

Respond ONLY with a JSON array of 9 floats between 0.0 and 1.0, one per
category in the order listed above. Example format:
[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

### 5.2 Zero-shot detallado

Igual que el genérico, pero antes del bloque `{input}` incluye la
definición y criterios completos de cada una de las 9 categorías
(tomados literalmente de la tabla de la propuesta), para reducir la
ambigüedad de la tarea sin ejemplos resueltos.

### 5.3 Few-shot

Igual que el detallado, más un bloque de 2-3 ejemplos resueltos
(contexto real + arreglo de 9 scores esperado, construidos a mano por el
equipo a partir de casos claros) antes del bloque `{input}` final.

Las tres plantillas completas se versionan en
`config/prompts/citation_function_prompts.json` con el formato:

```json
{
  "zero_shot_generic": "...",
  "zero_shot_detailed": "...",
  "few_shot": "..."
}
```

## 6. Diseño concreto de la implementación

### 6.1 Test Gold piloto

Archivo: `tests/fixtures/citation_function_pilot.jsonl`

- 15-20 casos tomados de contextos de cita reales en `data/raw/`.
- Formato JSONL, un caso por línea, compatible con el loader de #40:

```json
{"id": "case-001", "input": "Citation context: ...\n\nCited paper title: ...\nCited paper abstract: ...", "gold": null}
```

- `gold` se deja en `null` explícitamente: este conjunto no tiene
  etiqueta de función de cita validada; solo sirve para medir formato y
  estabilidad, no accuracy.
- No vive en `data/` ni se versiona con DVC, porque es una muestra
  pequeña construida a mano para pruebas, no parte del corpus ACL-200.

### 6.2 Script de análisis de estabilidad

Archivo: `src/evaluation/commercial/stability.py`

Responsabilidades:

- Leer un `results.jsonl` producido por el runner de #40 (múltiples
  registros por combinación caso+prompt, uno por repetición).
- Agrupar registros por `(case_id, prompt_name)`.
- Calcular por grupo:
  - `format_error_rate`: fracción de respuestas que no parsean como
    arreglo válido de 9 floats.
  - `label_stability`: entre las respuestas parseables, fracción cuyo
    argmax coincide con la moda del grupo.
  - `avg_latency_ms`, `avg_retry_count`: agregados directos de los
    campos ya presentes en `results.jsonl`.
- Agregar además por `prompt_name` (promedio sobre todos los casos), para
  comparar las tres estrategias entre sí.
- Escribir `stability_summary.csv` con una fila por prompt.

Interfaz:

```bash
uv run python -m src.evaluation.commercial.stability \
  --results artifacts/commercial_eval/results.jsonl \
  --output artifacts/commercial_eval/stability_summary.csv
```

### 6.3 Cliente de proveedor (placeholder documentado)

Archivo: `src/evaluation/commercial/providers_local.py`

Implementa el contrato `provider`, `model`, `generate(prompt: str) ->
ProviderResponse` ya definido en `src/evaluation/commercial/providers.py`
(rama de #40). El cuerpo de `generate()` lanza `NotImplementedError` con
un mensaje que remite a la sección 4 de este documento, hasta que el
equipo resuelva la decisión pendiente. Cuando se resuelva, solo este
archivo cambia; el resto del pipeline no se modifica.

### 6.4 Ubicación final de archivos

```text
config/prompts/
    citation_function_prompts.json     # los 3 prompts (sección 5)

tests/fixtures/
    citation_function_pilot.jsonl      # datos piloto (sección 6.1)

src/evaluation/commercial/
    stability.py                       # análisis de estabilidad (sección 6.2)
    providers_local.py                 # cliente placeholder (sección 6.3)

tests/
    test_prompts_format.py
    test_stability.py
    test_providers_local.py

docs/
    evaluacion_comercial.md            # se actualiza con sección "Prompts
                                        # y estabilidad — issue #43"
```

## 7. Coordinación con la rama de #40

`src/evaluation/commercial/` solo existe en `feature/20sep-commercial-eval-john`
(PR #44, draft, sin fusionar a `main`). La implementación de #43 se
ramifica desde esa rama, no desde `main`. El PR de #43 apunta como base a
`feature/20sep-commercial-eval-john`, y se coordina con John para que
ambos se integren juntos a `main` cuando su PR esté listo.

## 8. Pruebas automatizadas

Todas sin llamadas de red, siguiendo la convención ya establecida por el
runner de #40.

### `test_prompts_format.py`

- Las 3 plantillas en `citation_function_prompts.json` contienen
  `{input}`.
- Las 9 categorías aparecen mencionadas en las plantillas detallada y
  few-shot.
- La plantilla few-shot contiene al menos 2 ejemplos resueltos.

### `test_stability.py`

- Con un `results.jsonl` de prueba (fixture local, sin red): un grupo con
  formato consistentemente roto produce `format_error_rate = 1.0`.
- Un grupo con las 5 repeticiones parseables y con el mismo argmax
  produce `label_stability = 1.0`.
- Un grupo con argmax distinto en cada repetición produce
  `label_stability` bajo (≈0.2 con N=5).
- La agregación por `prompt_name` promedia correctamente varios grupos.

### `test_providers_local.py`

- El cliente expone `provider`, `model` y `generate()` con la firma
  esperada.
- Llamar `generate()` sin configuración lanza `NotImplementedError` con
  un mensaje que menciona la decisión pendiente (sección 4), sin
  intentar ninguna conexión de red.

## 9. Contenido que debe incorporarse al reporte y a la documentación

- Sección "Prompts y estabilidad — issue #43" en
  `docs/evaluacion_comercial.md`, con: las 3 plantillas (o referencia al
  archivo versionado), la tabla `stability_summary.csv`, y la
  recomendación de prompt(s) finalista(s) con su justificación.
- En el reporte de Entrega 3: una mención breve (dado el límite de 10
  páginas) del estado de este frente — qué se decidió, qué evidencia
  reproducible existe, y qué depende todavía de la decisión de modelo
  (sección 4) para producir resultados con modelos reales.
- Actualizar la tabla de aportes individuales del reporte de trabajo en
  equipo con la contribución a #43.

## 10. Definición de terminado

- [ ] Las 3 plantillas de prompt están escritas y versionadas en
      `config/prompts/citation_function_prompts.json`.
- [ ] El conjunto piloto de 15-20 casos está construido sin etiquetas
      reales y versionado en `tests/fixtures/`.
- [ ] `stability.py` calcula `format_error_rate`, `label_stability` y
      agregados de latencia/reintentos por prompt.
- [ ] `providers_local.py` expone el contrato esperado y falla
      explícitamente mientras no haya proveedor configurado.
- [ ] Las pruebas de las tres secciones (8) pasan sin llamadas de red.
- [ ] `docs/evaluacion_comercial.md` incluye la sección de prompts y
      estabilidad con conclusiones y recomendación.
- [ ] La decisión pendiente de modelo/proveedor (sección 4) queda
      explícitamente documentada y comunicada al equipo, aunque no esté
      resuelta.
- [ ] El PR de #43 apunta a `feature/20sep-commercial-eval-john`, no a
      `main`.
- [ ] La contribución aparece en el reporte de trabajo en equipo.

## 11. Cómo este issue destraba la cadena #40 → #41 → #42

Una vez `citation_function_prompts.json` esté versionado y las
conclusiones de estabilidad escritas, #40 puede ejecutar corridas contra
modelos comerciales reales usando esos mismos prompts en cuanto existan
credenciales, y #42 puede calcular Precision/Recall/F1/matrices de
confusión reales en cuanto #41 entregue el Test Gold validado. Este
issue deja de ser el bloqueador de esa cadena; la decisión de la sección
4 pasa a ser la responsabilidad compartida siguiente del equipo.
