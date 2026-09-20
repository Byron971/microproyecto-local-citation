# Corrida provisional open-weight — corte 20 de septiembre

Este procedimiento permite avanzar aunque la segunda validación manual independiente todavía no esté disponible.

No modifica el reporte final ni convierte el conjunto provisional en Test Gold definitivo.

## Requisito previo

Debe existir un servidor local compatible con OpenAI, por ejemplo Ollama, escuchando en:

```text
http://localhost:11434/v1
```

El modelo debe estar descargado y disponible en ese servidor.

## Paso 1 — Preflight

Desde la raíz del repositorio, en PowerShell:

```powershell
.\scripts\run_provisional_openweight.ps1 -Model "NOMBRE_EXACTO_DEL_MODELO" -CheckOnly
```

El preflight verifica rutas, prompts y configuración sin ejecutar inferencia.

## Paso 2 — Corrida provisional

```powershell
.\scripts\run_provisional_openweight.ps1 -Model "NOMBRE_EXACTO_DEL_MODELO"
```

La corrida usa:

```text
annotations/citation_function/provisional_test_gold.jsonl
```

y marca los artefactos como provisionales.

## Salidas

```text
artifacts/citation_function_eval/openweight_provisional/
  results.jsonl
  summary.csv
  run_metadata.json
  metrics/
    evaluation_summary.csv
    predictions.csv
    confusion_matrices/
```

## Regla de integridad

Estos resultados pueden usarse para avanzar técnicamente en el corte del 20, pero no deben reportarse como resultados definitivos del Test Gold mientras no exista segunda validación manual independiente y reconciliación.
