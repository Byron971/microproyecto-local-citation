# S4.4 — Preselección reproducible y ciega de contextos ACL-200 de `val`

**Estado:** herramienta de **preselección de factibilidad**, no evaluación Gold, sin anotaciones humanas completadas. Depende de S4.3 y de la política G0.5. El incremento se revisará en un PR nuevo, basado en `feature/s4-auditoria-exploratoria`.

## Objetivo y corpus

Automatizar una **preselección de hasta 12 contextos** originales de ACL-200 `val` para evaluar viabilidad de anotación humana ciega de funciones de cita. La muestra **no representa** las nueve categorías por igual y no constituye un Test Gold independiente. **No se accede a predicciones C1/C2, SciBERT, modelos externos ni API**; no se etiquetan los textos.

Se utilizan los archivos ACL-200 existentes del repositorio en `data/raw/`:

- `contexts.json`: `masked_text`, `citing_id`, `refid`;
- `papers.json`: título y resumen del artículo citado;
- `train.json`, `val.json`, `test.json`: particiones originales con `context_id` y `positive_ids`.

El validador ya existente `build_split_index` exige que los IDs, TARGETCIT, citantes, pares y referencias sean coherentes en los **tres splits**. Esto no expone textos de `test` en las hojas de anotación: `test` solo se comprueba para prevenir contaminación.

## Cómo ejecutar (PowerShell, raíz del repositorio)

Antes de empezar, trabajar sobre la rama `feature/s4-4-muestreo-ciego-val` creada desde `feature/s4-auditoria-exploratoria`, con worktree limpio. Confirmar archivos:

```powershell
Test-Path "data/raw/contexts.json"
Test-Path "data/raw/papers.json"
Test-Path "data/raw/train.json"
Test-Path "data/raw/val.json"
Test-Path "data/raw/test.json"
```

Los cinco deben devolver `True`. Si alguno devuelve `False`, detenerse: hay que localizar o restaurar los datos ACL-200 ya versionados antes de ejecutar, sin fabricar una muestra desde los 67 casos de `train`.

Pruebas del incremento:

```powershell
uv run --group research --group dev pytest -q proyecto_de_grado/tests/test_preparar_muestra_ciega_s4_4.py
```

Generación de la preselección (salida nueva):

```powershell
uv run --group research --group dev python -m proyecto_de_grado.src.evaluation.preparar_muestra_ciega_s4_4 `
  --raw "data/raw" `
  --exclude "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt" `
  --exclude-history "proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt" `
  --out "proyecto_de_grado/artifacts/evaluacion_s4/muestra_val_12_v1" `
  --limit 12 `
  --seed 44
```

No borrar ni sobrescribir una carpeta de resultados previa: para una nueva versión cambiar `--out` a `muestra_val_12_v2` y documentar por qué. Si existen exposiciones adicionales de casos de `val`, registrar sus IDs, uno por línea y sin etiquetas, en un archivo local (por ejemplo `proyecto_de_grado/artifacts/evaluacion_s4/ids_expuestos_adicionales.txt`) y añadir el argumento `--extra-exclude <ruta>` antes de generar.

## Salida local e interpretación

Se crean únicamente en `proyecto_de_grado/artifacts/evaluacion_s4/muestra_val_12_v1/`:

| Archivo | Propósito |
|---|---|
| `anotador_a.csv` | Doce contextos en orden aleatorizado para A, `primary_label` y otros juicios **vacíos** |
| `anotador_b.csv` | Mismos IDs, distinto orden para B, juicios **vacíos** |
| `revision_elegibilidad.csv` | Pantalla **previa obligatoria**: integridad de cita, OTHERCIT, truncamiento y atribución; no es Gold |
| `adjudicacion_plantilla.csv` | Registro en blanco para usar **después** de congelar A y B |
| `auditoria_marco_val.csv` | Estados y motivos de exclusión automatizada para **todos** los candidatos `val` |
| `ids_preseleccionados.txt` | Lista estable de IDs elegidos, para congelamiento y exclusiones futuras |
| `manifiesto.json` | Versión, parámetros, selección, SHA-256 de fuentes y archivos, conteos y advertencias |

**No subir a Git** las fichas, textos de corpus, nombres de anotadores o juicios. Todos los datos se mantienen en la carpeta ignorada `artifacts`.

### Proceso obligatorio tras la preselección

1. **Un responsable revisa** `revision_elegibilidad.csv` contra el texto de cita completo cuando sea posible y documenta `revision_contexto` como `apto` o `no_apto`, `motivo` y `revisor`. El script **no puede demostrar** que la cita truncada, agrupada o con OTHERCIT tenga una atribución inequívoca. Para cada `no_apto`, crear una nueva lista local de excluidos y **regenerar** una muestra en carpeta nueva; no eliminar filas a mano de A o B.
2. Antes de distribuir las fichas a los anotadores, **congelar** la muestra revisada, el manifiesto y los SHA. Verificar que los casos expuestos se registren para **excluirlos del futuro Test Gold**. Confirmar con el equipo dos anotadores distintos y posibilidad de adjudicación.
3. A y B trabajan por separado: **una función principal** entre las nueve etiquetas de `docs/guia_anotacion_funcion_cita.md`. `annotation_status` puede registrar duda/no-evaluable con justificación, sin inventar una función. No mostrar etiquetas Qwen, rankings, scores ni respuestas del otro evaluador. No utilizar resultados antiguos del piloto para elegir categorías.
4. **Después** de completar y congelar A/B, documentar desacuerdos y adjudicaciones humanas. Solo en una etapa posterior se calcularán acuerdo y métricas de clasificación apropiadas, indicando clase, soporte y denominadores.

## Controles automáticos y límites

- Un único `TARGETCIT` por contexto; `OTHERCIT` se preserva.
- Validación de splits originales y `positive_ids`; no se admite camuflar `train` o `test` como `val`.
- Unión de las dos listas obligatorias de exclusiones, con lista adicional opcional de IDs ya expuestos.
- Exclusión por coincidencias **textuales exactas normalizadas** con `train`, `test` o dentro de `val` (espacios y mayúsculas); **no** se asegura ausencia de **casi duplicados** semánticos ni de reconstrucciones truncadas.
- Muestreo determinista ordenado por `context_id` antes de mezclar con semilla. Se prioriza diversidad de artículos citantes y citados; si es necesario, se permite repetir `cited_id`, pero nunca el `citing_id` en los seleccionados. **No** es una muestra aleatoria representativa de todas las citas de `val`.
- Si faltan archivos, exclusiones o suficientes contextos válidos se detiene **sin crear la salida**; si la salida ya existe, no sobrescribe.
- Exige revisión humana de elegibilidad antes de entregar hojas, aunque las comprobaciones automáticas pasen.

## Condiciones todavía pendientes

- Ratificación de la guía de anotación y responsables de revisión, de los anotadores A/B y del adjudicador.
- Muestra final de `val` efectivamente revisada y congelada; revisión de casi duplicados y ambigüedades.
- Construcción de un **Test Gold independiente solo de nuevos casos `test`**, con doble anotación y adjudicación, una vez aprobados tamaño y protocolo.
- Evaluación de relevancia BM25/SciBERT Top-3 basada en **todos** los chunks del documento citado. Estas fichas de funciones no contienen juicios de fragmentos ni habilitan Recall@3/MRR@3.
- La política de G0.5 mantiene la validación humana de `ceil(0.15*N)` ejemplos del dataset final y la meta no demostrada de 2.000 por clase. **Doce fichas de calibración no cumplen estas condiciones**.

**Resultado esperado del incremento:** código y pruebas versionados; muestra de factibilidad preseleccionada y manifiesto local verificables; **0 etiquetas Gold creadas**.
