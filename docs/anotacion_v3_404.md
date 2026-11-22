# Etiquetado de las 404 entradas nuevas de v3

El flujo usa `TestGold_v3_Zambrana__rellenado.xlsx` como base. Conserva las 207 respuestas trasladadas y etiqueta solo las 404 filas sin respuestas en I–L.

1. GPT-6 Sol y Claude Opus 5.5 etiquetan cada contexto independientemente, con la misma guía. Reciben contexto inglés, título y resumen; no reciben propuestas del jurado, respuestas ajenas ni las anotaciones de la Tanda 1.
2. Si coinciden **evaluabilidad y función**, se acepta la respuesta de Opus. La confianza y la justificación pueden diferir sin activar arbitraje.
3. En los desacuerdos, GPT-6 Luna recibe el contexto y las dos respuestas anónimas A/B en orden reproducible y balanceado. Elige una de ellas; no introduce una tercera función. Se conserva la respuesta original seleccionada y se registra por separado la explicación del arbitraje.

No se cambia ningún `context_id`, texto, columna del jurado, hoja ni formato. Las decisiones son automáticas y no se registran como revisión humana.

## Ejecutar o reanudar

```bash
.venv/bin/python notebooks/anotacion_v3_dos_jueces.py
```

Las claves se cargan del `.env` sin imprimirlas. Se comparte el ledger existente de presupuesto, con límite local de 18 USD y 2 USD de margen respecto al máximo solicitado de 20 USD. No es una garantía de facturación: depende de las tarifas configuradas y no cubre gastos de otras aplicaciones. Cada intento reserva costo y ajusta con los tokens informados; los fallos sin uso conocido conservan su reserva.

Cada fase procesa hasta cuatro solicitudes concurrentes, con escritura de registros y presupuesto serializadas dentro del proceso. No lanzar dos ejecuciones simultáneas del flujo ni otros scripts que escriban en el mismo ledger.

Los checkpoints se guardan en `artifacts/anotacion_v3_404/`:

- `manifest.json`: fuente y hash, IDs incluidos, modelos y criterio.
- Carpetas `gpt-6-sol/` y `claude-opus-5-5/`: intentos y respuestas originales.
- `gpt-6-sol.predicciones.json` y `claude-opus-5-5.predicciones.json`: decisiones válidas por ID.
- `gpt-6-luna/arbitraje.jsonl`: elecciones, explicaciones y tokens del árbitro.
- `decisiones_nuevas.json`: respuesta aceptada y regla aplicada por contexto.
- `resumen.json`: cobertura, coincidencias, arbitrajes y presupuesto local.

El resultado se escribe en `notebooks/anotaciones/TestGold_v3_Zambrana__resultado_final.xlsx`. Si una fase primaria no completa sus 404 respuestas, el proceso se detiene y conserva los registros para reanudar. Las decisiones de arbitraje válidas también se recuperan por ID y hash de las propuestas. No se vuelven a pagar respuestas ya guardadas bajo la misma configuración.

Las cinco decisiones humanas ambiguas de la Tanda 1 conservan su función vacía: la fórmula v3 las puede mostrar como INCOMPLETO. No se inventa una función para resolver esa diferencia de plantilla. Excel recalcula Estado y Control al abrir.
