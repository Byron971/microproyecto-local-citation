# Auditoría ACL-200 oficial para el Gold candidato — Issue #100

**Estado: auditoría ejecutada por el usuario sobre archivos ACL locales el 8-nov-2026 UTC, pero la versión DVC no se ha verificado ni se ha certificado el Gold.**

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


## Hallazgo real y tratamiento conservador (8 de noviembre de 2026 UTC)

El usuario ejecutó 23 pruebas locales exitosas (antes de la excepción añadida en esta revisión) y el gate ACL-200 sobre los archivos locales. Tras corregir un falso positivo de espacios exteriores, el único bloqueo era **22 anotaciones PR92 fuera de train/val/test**. La inspección independiente de solo lectura confirmó:

- 22 de 22 pertenecen a citantes de **2014** (validación).
- 21 con estado `COMPLETO` / evaluables y 1 `REGISTRADO` / ambiguo.
- 0 IDs pertenecen al manifiesto PR91.
- Las 22 anotaciones están en `contexts.json`, pero no en ninguno de los splits supervisados.
- PR92: 2.700 textos idénticos al original leídos sin `.strip()`; Haiku: 2.264 idénticos y 436 que solo difieren en espacios externos.
- Cruces candidatos Gold/Haiku: cero IDs, cero citantes y cero pares; sin generalizar a entrenamientos ajenos a Haiku.

Se agrega un tratamiento **estrictamente acotado**: un registro histórico de PR92 fuera de los splits se cuenta como `historico_2014_sin_split_no_elegible` en lugar de bloqueo **solo si** (1) es de validación 2014 por ID, (2) existe en `contexts.json`, (3) está ausente del manifiesto PR91 y (4) tiene estado `COMPLETO` o `REGISTRADO`. Se omite de las identidades elegibles utilizadas para controles de intersección. El auditor nunca asigna artificialmente estos ejemplos a `val` ni declara que estén en una partición oficial.

Si el ID está en PR91, corresponde a test 2015, no existe en `contexts.json`, o no tiene el estado esperado, **sigue bloqueando**. Los 5 excluidos históricos son otra categoría, contabilizada independientemente. Se añadieron pruebas sintéticas para los casos de excepción y bloqueo.

**Próxima comprobación obligatoria:** traer el último script/pruebas del PR #146, ejecutar de nuevo Pytest y el comando ACL con los datos locales. Un resultado sin bloqueos solo significa que los controles técnicos pasaron para las fuentes inspeccionadas, no que el Gold tenga revisión humana, independencia documental comprobada para todos los modelos o versión DVC certificada.

**Riesgos restantes:** comprobar SHA/objeto DVC oficial para los cuatro archivos raw; obtener manifiestos de entrenamiento SciBERT/SPECTER/jurado; validar la decisión de un solo Gold canónico con dos revisiones humanas, adjudicaciones y cobertura del 15 %.
