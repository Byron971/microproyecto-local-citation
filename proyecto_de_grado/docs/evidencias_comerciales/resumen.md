# Resumen de la evaluación de modelos comerciales (1.061 citas con anotación humana)

| Modelo | Prompt | F1 macro (IC 95 %) | Precisión macro | Recall macro | Exactitud | Latencia mediana / p95 (s) | Costo por 1.000 citas (USD) | Errores de formato |
|---|---|---|---|---|---|---|---|---|
| gemini-3.5-flash-lite | Sin ejemplos, instrucción genérica | 0.4124 (0.367 a 0.45) | 0.5194 | 0.4944 | 0.5193 | 0.58 / 0.71 | 0.241 | 0 |
| gemini-3.5-flash-lite | Sin ejemplos, definiciones detalladas | 0.4866 (0.451 a 0.517) | 0.5623 | 0.5501 | 0.573 | 0.59 / 0.71 | 0.299 | 0 |
| gemini-3.5-flash-lite | Con ejemplos | 0.501 (0.464 a 0.535) | 0.549 | 0.553 | 0.6324 | 0.59 / 0.72 | 0.369 | 0 |
| gpt-6.1-sol | Sin ejemplos, instrucción genérica | 0.5505 (0.511 a 0.587) | 0.664 | 0.6216 | 0.656 | 2.18 / 4.23 | 1.502 | 0 |
| gpt-6.1-sol | Sin ejemplos, definiciones detalladas | 0.6124 (0.568 a 0.648) | 0.6737 | 0.6429 | 0.7182 | 2.26 / 4.54 | 1.94 | 0 |
| gpt-6.1-sol | Con ejemplos | 0.6006 (0.556 a 0.64) | 0.6443 | 0.6322 | 0.7238 | 2.02 / 4.44 | 2.436 | 0 |

El costo por 1.000 citas es el de UN prompt (una llamada por cita). Los costos son estimados por el programa con las tarifas de la carpeta `tarifas/`; no son una factura.
