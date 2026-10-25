# S4.5 — Segunda auditoría de alineaciones de la muestra VAL

**Alcance:** 12 contextos `val` ya preseleccionados y expuestos durante S4.4. No es Test Gold ni validación humana. No se entrena ni se repiten inferencias.

## Hallazgos del JSONL S4.5

Se recibieron 12 resultados de `reconstrucciones_preliminares_s4_5.jsonl`:

- 1 `reconstruccion_candidata_revision_humana`: `W14-2710_D13-1010_0`, párrafo 0, score textual 1.0 y BIBREF16. La oración reconstruida conserva las citas no objetivo; falta confirmar identidad en bibliografía y PDF.
- 6 `TARGETCIT_cerca_de_OTHERCIT_grupo_potencial`: la heurística de 38 caracteres es conservadora; **no equivale** a demostrar que hay múltiples citas dentro del mismo paréntesis.
- 4 `bibliografia_candidata_sin_cita_en_parrafo`: existe bibliografía candidata por metadatos, pero no un `cite_span` correspondiente en el párrafo seleccionado. La coincidencia textual del párrafo no valida por sí sola el enlace de cita.
- 1 `referencia_candidata_no_unica_en_parrafo`: no escoger la primera referencia arbitrariamente.

## Propósito del nuevo diagnóstico

El módulo `proyecto_de_grado.src.evaluation.diagnosticar_enlaces_s4_5` compara, **sin alterar documentos**, las referencias bibliográficas candidatas, los `cite_spans` del párrafo previamente alineado y los `cite_spans` de esas referencias en todo el artículo **citante**. Distingue entre proximidad heurística de `OTHERCIT` y presencia visible dentro del mismo grupo parentético; si los paréntesis están truncados registra incertidumbre.

La presencia de un `cite_span` coincidente **no confirma** por sí sola que la referencia exacta sea `TARGETCIT` en ACL-200; debe revisarse identidad bibliográfica, offsets y contexto textual. Este paso **no acepta nuevos casos** ni cambia la guía de anotación.

## Instrucciones PowerShell (desde raíz de repo)

```powershell
uv run --group research --group dev pytest -q proyecto_de_grado/tests/test_diagnosticar_enlaces_s4_5.py

uv run --group research --group dev python -m proyecto_de_grado.src.evaluation.diagnosticar_enlaces_s4_5 --base "proyecto_de_grado/artifacts/evaluacion_s4/muestra_val_12_v1" --raw "data/raw" --cache "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl" --out "proyecto_de_grado/artifacts/evaluacion_s4/muestra_val_12_v1/diagnostico_spans_s4_5_v1.csv"
```

**Nota:** el comando de diagnóstico se entrega en una sola línea compatible con PowerShell.

El resultado `diagnostico_spans_s4_5_v1.csv` se guarda en `artifacts`, ignorado por Git. Si ya existe, el programa se detiene para evitar sobrescribir evidencia. Compartir este CSV para evaluación de causas técnicas; no subir la caché, corpus crudo ni anotaciones a GitHub.

## Criterios para continuar

1. Una persona comprueba el texto original, la bibliografía y los offsets de cada cita antes de aceptar una oración reconstruida.
2. Los grupos genuinamente ambiguos permanecen pendientes o se sustituyen por nuevos contextos `val` de manera documentada.
3. La validación humana de **función** es un paso posterior y diferente de la validación de reconstrucción.
4. Mantener la unión de exclusiones históricas e incluir los IDs expuestos de S4.4 en el registro de contaminación de futuros ensayos.
