# Evaluación de modelos comerciales sobre el Test Gold (21 de noviembre de 2026)

**Qué es.** Primera evaluación de modelos comerciales contra las citas del Test Gold congelado que tienen anotación humana (actividades A5 y A7 del enunciado del Tema 1). Antes solo existía un piloto de 20 citas del 20-sep (Gemini, Cohere y Qwen local) y OpenAI no tenía resultados por falta de saldo.

## Qué se evaluó

| Modelo | Proveedor y conexión | Fecha y hora (Colombia) |
|---|---|---|
| gemini-3.5-flash-lite | Google, API compatible con OpenAI (`generativelanguage.googleapis.com/v1beta/openai/`) | 21-nov-2026, 01:30 a 02:55 |
| gpt-6.1-sol | OpenAI API | 21-nov-2026, 01:56 a 02:30 |

- **Citas:** 1.061 = las del subconjunto «humano» de las métricas (186 con dos anotadores de acuerdo + 818 con una anotación + 57 con desacuerdo resuelto por Claude Opus 5.5). Excluye las 470 etiquetadas solo por Opus y 2 no evaluables. Origen: `proyecto_de_grado/anotacion/test_gold_final/test_gold_final.csv` (SHA-256 80e4d9a6a72bd36913548bef897ad8212178797e181bb7893f7be2aad66b83c7). Se mezclaron con semilla 2026 y se partieron en 4 archivos (`entradas/completo_1..4.jsonl`; 266, 266, 266 y 263 citas).
- **Entrada de cada llamada:** contexto de la cita en inglés (TARGETCIT marcada), título y resumen del artículo citado (de `data/raw/papers.json`).
- **Prompts** (`config/prompts/citation_function_prompts.json`, SHA-256 d23edde112b19c8d453999676e654786fcb7ac5b651765d01971c1b5507a3b83): `zero_shot_generic` (instrucción genérica), `zero_shot_detailed` (definiciones de las 9 funciones) y `few_shot` (con ejemplos). Cada uno pide un arreglo de 9 puntajes entre 0 y 1; la predicción es el mayor.
- **3.183 llamadas por modelo** (1.061 citas × 3 prompts). Parámetros del modelo por defecto del proveedor, una sola corrida por prompt.
- **Código:** módulo `src/evaluation/commercial` del repositorio, rama `feature/evaluar-anotaciones-llm`, commit `6d0d631` en el equipo donde se corrió.

## Resultados principales

Ver `resumen.md` (tabla completa), `metricas/por_clase.csv` y `metricas/matrices_de_confusion/`. Las métricas se calcularon con el programa del repositorio y de forma independiente con `scripts/analizar.py`; coinciden (diferencia 0,000000). Intervalos de confianza al 95 % del F1 macro por bootstrap de las 1.061 citas (1.000 remuestreos, semilla 2026; `scripts/bootstrap_ic95.py`).

## Tarifas usadas para estimar el costo

| Modelo | Entrada (USD por millón de tokens) | Salida (USD por millón de tokens) | Fuente |
|---|---|---|---|
| gemini-3.5-flash-lite | 0,30 | 2,50 | Varias páginas de precios coinciden; la página de Google lista 0,30 de entrada. Consultado el 21-nov-2026. Verificar en ai.google.dev/gemini-api/docs/pricing |
| gpt-6.1-sol | 2,00 | 10,00 | Fuentes secundarias citan la lista de OpenAI del 17-oct-2026. Verificar en developers.openai.com/api/docs/pricing |

**Los costos del resumen son estimaciones** (tokens medidos por la API × tarifa). En una prueba de 9 llamadas con Gemini el programa estimó US$0,0027 y la consola mostró unos 9 COP, que son del mismo orden. La comparación con el cobro de cada consola está en `costos_cobrados.md`: OpenAI cobró US$6,98 (estimado US$6,88) y Gemini COP 3.138, cerca de US$0,80 (estimado US$0,97).

**Costo estimado total (3 prompts × 1.061 citas):** Gemini 3.5 Flash-Lite US$0,96; GPT-6.1 Sol US$6,24. A eso se suman las pruebas previas (unos US$0,64 de OpenAI y centavos de Gemini).

## Cómo reproducir

1. Definir las claves en variables de entorno de la sesión (`GEMINI_API_KEY`, `OPENAI_API_KEY`); **nunca guardarlas en archivos ni pegarlas en el chat**. Las que se usaron se revocaron.
2. Definir `GEMINI_MODEL=gemini-3.5-flash-lite` y `OPENAI_MODEL=gpt-6.1-sol`.
3. Por cada tanda: `uv run python -m src.evaluation.commercial.orchestrate --mode gemini|openai --gold entradas/completo_N.jsonl --allow-provisional --pricing tarifas/tarifas_<proveedor>.json --request-delay-seconds 1 --output-dir <salida>` (OpenAI se corrió con pausa 0 y las 4 tandas en paralelo). Los scripts `scripts/correr_*.ps1` lo automatizan.
4. Unir los `results.jsonl` y correr `python -m src.evaluation.commercial.metrics --results <unido> --output-dir <metricas>`, y luego `scripts/analizar.py`.

## Límites que hay que declarar

- Es evaluación **provisional**: se corrió con `--allow-provisional` porque el Test Gold no está certificado.
- Las 1.061 citas incluyen 57 cuya etiqueta decidió Claude Opus 5.5 y 818 con una sola anotación humana; la validación humana no llega al 15 % por clase.
- Los anotadores vieron la propuesta del jurado (sesgo de anclaje).
- Un modelo por proveedor, una corrida por prompt y parámetros por defecto: no se midió la variación entre corridas.
- Los modelos de proveedores pueden cambiar de versión sin aviso; estos resultados valen para la fecha indicada.
- Las citas y resúmenes son del corpus público ACL-200; los archivos no contienen claves (se buscó en todos los archivos antes de copiarlos).

## Qué está en el repositorio y qué no

Aquí están los archivos pequeños (resumen, métricas, metadatos de cada tanda, tarifas y scripts). Los resultados completos de cada llamada (`results.jsonl`, 11 MB por modelo), las entradas y las pruebas previas están en la carpeta compartida del grupo en SharePoint, `Proyecto de Grado/datos y resultados/Evaluacion_comerciales_21nov/`, con los mismos hashes.

## Contenido y verificación

`SHA256SUMS.txt` lista el hash de cada archivo de esta carpeta.
