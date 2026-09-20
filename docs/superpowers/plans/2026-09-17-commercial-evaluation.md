# Commercial Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar un pipeline reproducible para ejecutar modelos comerciales sobre un Test Gold común, registrar telemetría y producir resultados reutilizables por el pipeline global de métricas.

**Architecture:** Se añadirá un paquete aislado `src/evaluation/commercial/` con esquemas, I/O, contrato de proveedor y runner. El runner no calculará F1/Precision/Recall; conservará la respuesta cruda, telemetría y salida parseada opcional para que el issue #42 haga la evaluación final.

**Tech Stack:** Python estándar, dataclasses, pathlib, json, csv, time, pytest.

**Spec:** `docs/superpowers/specs/2026-09-17-commercial-evaluation-design.md`

## Global Constraints

- No versionar claves API.
- Las pruebas no pueden realizar llamadas de red.
- No fijar nombres de modelos comerciales que el equipo aún no haya versionado.
- El costo solo se calcula cuando existe una tarifa explícita para el modelo.
- El formato de salida debe conservar la respuesta cruda aunque falle el parseo.

---

### Task 1: Esquemas y validación de entradas

**Files:**
- Create: `src/evaluation/commercial/__init__.py`
- Create: `src/evaluation/commercial/schema.py`
- Create: `tests/test_commercial_schema.py`

**Interfaces:**
- Produces: `EvaluationCase`, `PromptTemplate`, `ProviderResponse`, `RunRecord`.

- [ ] Escribir pruebas que validen IDs/inputs no vacíos, plantillas con `{input}` y serialización de registros.
- [ ] Ejecutar `pytest tests/test_commercial_schema.py -v` y comprobar que falla por módulo inexistente.
- [ ] Implementar dataclasses y validaciones mínimas.
- [ ] Repetir la prueba hasta obtener PASS.

### Task 2: Carga y persistencia reproducible

**Files:**
- Create: `src/evaluation/commercial/io.py`
- Create: `tests/test_commercial_io.py`

**Interfaces:**
- Consumes: tipos de `schema.py`.
- Produces: `load_gold_jsonl(path)`, `load_prompts_json(path)`, `write_results_jsonl(path, records)`, `write_summary_csv(path, records)`.

- [ ] Escribir pruebas con `tmp_path` para Test Gold válido/inválido, prompts y salidas JSONL/CSV.
- [ ] Verificar RED.
- [ ] Implementar únicamente I/O local con `pathlib`, `json` y `csv`.
- [ ] Verificar GREEN.

### Task 3: Contrato de proveedor y runner con reintentos

**Files:**
- Create: `src/evaluation/commercial/providers.py`
- Create: `src/evaluation/commercial/runner.py`
- Create: `tests/test_commercial_runner.py`

**Interfaces:**
- Produces: `CommercialModelClient` protocol, `ProviderCallError`, `run_evaluation(cases, prompts, clients, max_retries=2, parser=None, pricing=None)`.

- [ ] Escribir clientes falsos en tests: éxito, fallo transitorio seguido de éxito y fallo permanente.
- [ ] Verificar RED.
- [ ] Implementar medición de latencia, `retry_count`, estados `ok/provider_error/parse_error` y costo opcional.
- [ ] Verificar GREEN.
- [ ] Añadir prueba de parser inválido que preserve `raw_response`.

### Task 4: CLI de preparación y documentación

**Files:**
- Create: `src/evaluation/commercial/cli.py`
- Create: `docs/evaluacion_comercial.md`
- Modify: `README.md`
- Test: `tests/test_commercial_cli.py`

**Interfaces:**
- Produces: validación de entradas y comando para ejecutar el pipeline cuando exista un adaptador registrado.

- [ ] Escribir prueba de ayuda/validación del CLI sin llamadas externas.
- [ ] Verificar RED.
- [ ] Implementar CLI con `argparse` para rutas de gold/prompts/salida y parámetros de reintentos.
- [ ] Documentar formatos, variables de entorno y dependencia de #41/#43.
- [ ] Verificar GREEN.

### Task 5: Verificación y PR

**Files:**
- Verify all files above.

- [ ] Ejecutar pruebas comerciales aisladas.
- [ ] Ejecutar la suite completa cuando el entorno del repositorio esté disponible.
- [ ] Revisar que no haya secretos o precios inventados.
- [ ] Crear PR contra `main` enlazando el issue #40 y explicando que la ejecución real queda condicionada a Test Gold, prompts, modelos y credenciales.
