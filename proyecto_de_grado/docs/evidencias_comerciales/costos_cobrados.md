# Costo estimado frente a costo cobrado (consulta del 21-nov-2026)

Incluye la corrida completa (3.183 llamadas por modelo) y las pruebas previas (mini y piloto).

| Proveedor | Llamadas | Tokens de entrada | Tokens de salida | Estimado por el programa | Cobrado en la consola | Diferencia |
|---|---|---|---|---|---|---|
| OpenAI (gpt-6.1-sol) | 3.501 | 2.218.728 | 244.363 | US$6,88 | US$6,98 | +1,5 % |
| Google (gemini-3.5-flash-lite) | 3.192 | 2.024.987 | 143.640 | US$0,97 | COP 3.137,96 (cerca de US$0,80) | cerca de −18 % |

- **Estimado:** tokens que reporta la API en cada llamada (`input_tokens`, `output_tokens` en `results.jsonl`) multiplicados por las tarifas de `tarifas/`.
- **Cobrado:** valor que mostró la consola de cada proveedor el 21-nov-2026, consultado por Carlos Caicedo. Gemini factura en pesos colombianos; la conversión a dólares es aproximada (unos 3.900 a 4.000 COP por dólar).
- **Lectura:** en OpenAI el estimado y el cobro son prácticamente iguales, lo que confirma los tokens medidos y la tarifa usada. En Gemini el cobro fue menor; puede deberse a que la consola aún no reflejaba todo el uso (puede tardar hasta un día) o a una tarifa real más baja. En los dos casos el orden de magnitud del costo por 1.000 citas se mantiene, por lo que el estimado sirve como base de comparación.
