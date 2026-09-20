# Evaluación comparativa provisional — corte 20 de septiembre de 2026

Este documento consolida la evidencia técnica generada para la evaluación de función de cita. No reemplaza el Test Gold definitivo ni el reporte final.

## Condiciones comunes

- Conjunto: `annotations/citation_function/provisional_test_gold.jsonl`.
- Casos: 20.
- Estrategias de prompting: `few_shot`, `zero_shot_detailed` y `zero_shot_generic`.
- Clases definidas por el proyecto: 9.
- Clases presentes en el gold provisional: 5.
- F1 Macro formal: calculado sobre las 9 clases definidas.
- Cada modelo se evaluó sobre los mismos 20 casos y los mismos tres prompts.
- Los resultados son preliminares porque todavía falta la segunda validación manual independiente, el acuerdo entre validadores y la reconciliación del Test Gold.

## Resultados

| Modelo | Prompt | Cobertura | F1 Macro | F1 Micro | Accuracy | Latencia media |
|---|---|---:|---:|---:|---:|---:|
| Qwen3:8B | few_shot | 1.00 | 0.1742 | 0.30 | 0.30 | 56.60 s |
| Qwen3:8B | zero_shot_detailed | 1.00 | 0.1541 | 0.30 | 0.30 | 59.35 s |
| Qwen3:8B | zero_shot_generic | 1.00 | 0.0444 | 0.10 | 0.10 | 64.99 s |
| Gemini 3.5 Flash-Lite | few_shot | 1.00 | 0.3287 | 0.65 | 0.65 | 1.49 s |
| Gemini 3.5 Flash-Lite | zero_shot_detailed | 1.00 | 0.2679 | 0.45 | 0.45 | 1.20 s |
| Gemini 3.5 Flash-Lite | zero_shot_generic | 1.00 | 0.1885 | 0.45 | 0.45 | 1.16 s |
| Cohere Command A+ | few_shot | 1.00 | 0.2606 | 0.50 | 0.50 | 19.96 s |
| Cohere Command A+ | zero_shot_detailed | 1.00 | 0.2614 | 0.45 | 0.45 | 9.27 s |
| Cohere Command A+ | zero_shot_generic | 1.00 | 0.0667 | 0.30 | 0.30 | 10.65 s |

## Calidad operativa

Las corridas finales usadas en la tabla tuvieron cobertura de clasificación del 100 %, sin errores de proveedor ni errores de formato.

Qwen3:8B se ejecutó localmente mediante Ollama. Gemini requirió pacing de 5 segundos por solicitud debido al límite observado de 15 solicitudes por minuto del Free Tier. Cohere se ejecutó con pacing de 4 segundos por solicitud. Las corridas incompletas causadas por rate limiting se conservaron localmente como evidencia técnica, pero no se usan para la comparación principal.

## Lectura provisional

En este piloto, Gemini 3.5 Flash-Lite con few-shot obtuvo el mayor F1 Macro (0.3287) y la mayor accuracy (0.65). Cohere Command A+ quedó en un nivel intermedio: su mayor F1 Macro fue 0.2614 con zero-shot detallado, mientras que few-shot alcanzó la mayor accuracy de Cohere (0.50). Qwen3:8B obtuvo métricas inferiores en este conjunto provisional y una latencia considerablemente mayor al ejecutarse localmente.

Estas diferencias no deben interpretarse como una conclusión definitiva del proyecto. El conjunto contiene únicamente 20 casos y solo 5 de las 9 clases aparecen en las etiquetas gold.

## OpenAI

El cliente OpenAI quedó implementado y el preflight fue exitoso con `gpt-4o-mini`. La corrida real no produjo predicciones porque la cuenta respondió `credit_balance_exhausted`. Por esa razón OpenAI no se incluye en la comparación de desempeño y no se atribuyen métricas al modelo.

## Trazabilidad local

Los artefactos detallados se generan en carpetas ignoradas por Git:

- `artifacts/citation_function_eval/openweight_provisional/`
- `artifacts/citation_function_eval/gemini_provisional_paced/`
- `artifacts/citation_function_eval/cohere_provisional_paced/`
- `artifacts/citation_function_eval/openai_provisional/`

Cada corrida genera `results.jsonl`, `summary.csv`, `run_metadata.json` y la carpeta `metrics/` con el resumen, predicciones y matrices de confusión.

## Pendientes antes de llamar a esto evaluación final

1. Completar la segunda validación manual independiente.
2. Calcular acuerdo entre validadores.
3. Reconciliar desacuerdos y congelar `test_gold.jsonl`.
4. Repetir los modelos seleccionados sobre el Test Gold definitivo.
5. Consolidar la versión final de métricas, eficiencia y conclusiones en el reporte.
