# Auditoría ACL-200 oficial para el Gold candidato — Issue #100

**Estado: implementación propuesta para revisión; no se ha ejecutado contra DVC real ni certificado el Gold.**

## Objetivo

Auditar los candidatos PR #91 y PR #92 y los ejemplos de entrenamiento Haiku contra `contexts.json` y las particiones `train.json`, `val.json`, `test.json` oficiales, usando el validador preexistente `proyecto_de_grado/src/data/validar_splits.py`.

El nuevo comando `src/evaluation/commercial/acl200_gold_split_gate.py` calcula únicamente resúmenes agregados, hashes y bloqueos; no cambia datasets ni exporta contexto, IDs de cita o etiquetas humanas.

## Ejecución

Desde la raíz del repositorio:

```powershell
uv sync --group dev
uv run pytest -q tests/test_acl200_gold_split_gate.py proyecto_de_grado/tests/test_validar_splits.py
uv run dvc pull data/raw
uv run python -m src.evaluation.commercial.acl200_gold_split_gate --raw-dir data/raw --output-dir artifacts/auditoria_splits_acl200
```

`data/raw` debe contener los cuatro archivos oficiales `contexts.json`, `train.json`, `val.json` y `test.json`. Si no están, el comando falla: **no se sustituye con años inferidos ni con datos sintéticos**.

Salida: `artifacts/auditoria_splits_acl200/resumen_acl200.json`. No subir el resultado sin revisarlo primero según política de acceso del equipo; solo contiene totales y SHA-256, no IDs ni etiquetas individuales.

## Alcance

- Comprueba existencia de cada `context_id` en la partición oficial: PR91 testgold -> test; PR91 calibración -> val; PR92 año 2014 -> val y año 2015 -> test; Haiku -> train.
- Valida coherencia de `citing_id`, `refid` y el texto `TARGETCIT` con ACL-200.
- Bloquea solapamiento de IDs, documentos citantes o pares citante–citado entre fuentes Gold candidatas y Haiku. Los documentos **citados** compartidos se informan pero no se presumen fuga por sí solos.
- Aplica exclusiones históricas sin modificar los CSV, y señala las exclusiones de PR91 como bloqueo.
- Registra hashes de los cuatro archivos originales ACL y de los tres archivos auditados.
- No demuestra que los corpus completos del jurado/SciBERT/SPECTER estén libres de fuga: faltan sus manifiestos de entrenamiento y checkpoints.
- No valida anotación humana independiente, adjudicación, cobertura 15%, balance 2.000/clase ni decisión de manifiesto único. Las banderas `gold_human_certified` y `final_benchmark_allowed` permanecen `false`.

## Estado de las pruebas

Se agregaron pruebas sintéticas en `tests/test_acl200_gold_split_gate.py` para: splits válidos, cruce Gold-train, año/grupo equivocado, texto distinto, exclusiones sin borrado, duplicados, datos DVC ausentes y formato de salida. **No se reportan como aprobadas hasta ejecutar CI o pytest y comprobar el resultado.**

La edición automática del workflow `.github/workflows/evaluacion-citas.yml` fue bloqueada. Como alternativa se añadió una prueba de integración a `proyecto_de_grado/tests/test_validar_splits.py`, que el workflow **sí incluye** a través de `proyecto_de_grado/tests`. Las ocho pruebas específicas en `tests/test_acl200_gold_split_gate.py` todavía requieren ejecución directa o incorporación posterior al workflow. No reportar ejecución exitosa hasta verificar el run de GitHub Actions.

## Dependencias

- PR #143: conciliación por IDs de PR #91 y #92; esta auditoría no depende de fusionarlo.
- PR #145: acta de decisión de Gold, pendiente.
- Issue #100: permanece abierto y el benchmark final bloqueado.
