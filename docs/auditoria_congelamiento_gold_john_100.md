# John — Issue #100: puerta de auditoría para congelar Test Gold

**Estado:** herramienta de auditoría implementada para candidato Gold, **NO certifica Gold humano**. Separa evidencia científica de validaciones técnicas. Revisión cruzada pendiente con José María, Caicedo y Duque. No subir Gold, datos humanos identificables, texto con derechos ni credenciales al PR.

## 1. Requisitos que controla el script

Módulo: `src/evaluation/commercial/gold_freeze_audit.py`.

- IDs únicos presentes en una lista explícita de **todos los ejemplos del dataset final** (denominador real del 15 %).
- Etiquetas finales de una de las **nueve funciones**; prohíbe usar una distribución de scores o la pseudo-etiqueta de un LLM como etiqueta humana.
- `TARGETCIT` único y exclusión de casos usados en práctica/calibración con `gold_policy.py`.
- Particiones oficiales ACL-200 de `data/raw` mediante `validar_splits.py`; Gold debe pertenecer a test.
- Comparación contra **manifiestos reales de train y validation**; revisa solapes de `id`, documento citante, par citante–citado y contexto textual normalizado. Compartir solo el artículo *citado* no prueba fuga por sí mismo.
- Al menos **dos anotaciones humanas primarias con IDs de anotador diferentes** para **cada ejemplo Gold**. Un acuerdo debe corresponder a la etiqueta final; si hay desacuerdo, exige una decisión registrada y razonada por un adjudicador **distinto de los dos anotadores primarios**.
- Cuenta IDs con anotación humana presentada en `reviews.jsonl` (no preetiquetas Haiku/jurado) y exige una fracción de al menos **15 % de los IDs del dataset final**. Si el dataset final tiene 18.000 casos, el mínimo equivalente es 2.700 IDs revisados; no inferir cobertura a partir de muestra.
- Genera reporte compacto con cantidades por clase, bloqueos, advertencias y SHA-256 de seis archivos de entrada (sin copiar el texto de anotaciones al reporte).

### Límite fundamental

**Ningún script puede garantizar que un ID de anotador corresponda a una persona real, que haya actuado a ciegas, que no existan anotaciones copiadas, que los modelos no hayan visto el Gold durante selección de prompts, o que el dataset final tenga efectivamente la procedencia declarada.** Estos requisitos se verifican documentalmente por José, Caicedo y John; luego se registra aprobación explícita y firmas/fecha por el proceso acordado. El auditor deja siempre:
- `gold_human_certified=false`
- `ready_for_final_benchmark=false`
- Si no hay bloqueos: `CANDIDATO_PARA_REVISION_HUMANA_NO_CERTIFICADO`
- Si faltan evidencias o hay incompatibilidades: `BLOQUEADO`

El benchmark actual `paired_benchmark.py` sigue en **modo provisional** hasta la certificación externa. No retirar la barrera `--provisional` sin PR, revisión de otros y manifiesto canónico aprobado.

## 2. Contratos de datos — archivos locales, NO añadir al Git público

Los archivos pueden permanecer en almacenamiento restringido con control de versiones (DVC/objeto S3 aprobado); el reporte solo incluye hashes de entradas.

**`gold_candidate.jsonl`**, una fila por ejemplo final propuesto:

```json
{"id":"C-001","input":"We apply TARGETCIT to this method.","gold":"Application","citing_id":"P15-0001","cited_id":"P12-0002"}
```

**`human_independent_reviews.jsonl`**, una fila por anotación *primaria*, todas las revisiones humanas del dataset (incluidas al menos dos por caso Gold):

```json
{"case_id":"C-001","annotator_id":"reviewer-1","label":"Application"}
```

**`adjudications.jsonl`**, obligatorio como archivo pero puede estar vacío cuando no haya discrepancias, una fila por desacuerdo resuelto:

```json
{"case_id":"C-001","adjudicator_id":"reviewer-3","label":"Application","reason":"El trabajo cita un método que utiliza."}
```

En este ejemplo habría también una anotación primaria de `reviewer-2` con etiqueta diferente que requiera la decisión del tercero; no es un registro completo ni un Gold real.

**`dataset_final_ids.txt`**: un ID de caso por línea, de **todo** el dataset final (no solamente casos de test). Se rechazan IDs repetidos. Las anotaciones humanas revisadas se cuentan exclusivamente sobre esta lista.

**`train_manifest.jsonl`** y **`validation_manifest.jsonl`**: una fila por caso de ambos conjuntos utilizados para entrenamiento/ajuste, con `id`, `input`, `citing_id` y `cited_id`. Se comprueban contra ACL-200. **No inventar** manifiestos vacíos para evitar los controles; incluir también cualquier otra fuente/ejemplos de desarrollo que hayan podido contaminar Gold y excluirlos correctamente.

Los archivos deben usar los IDs de contexto de `contexts.json`; si la propuesta final incorpora datos externos al ACL-200, **adaptar y aprobar primero** el contrato de procedencia/particiones y la política de pruebas, sin omitir silenciosamente casos por procedencia distinta.

## 3. Ejecución

```bash
uv sync --group dev
uv run python -m src.evaluation.commercial.gold_freeze_audit \
  --gold /ruta-restringida/gold_candidate.jsonl \
  --reviews /ruta-restringida/human_independent_reviews.jsonl \
  --adjudications /ruta-restringida/adjudications.jsonl \
  --dataset-ids /ruta-restringida/dataset_final_ids.txt \
  --train /ruta-restringida/train_manifest.jsonl \
  --validation /ruta-restringida/validation_manifest.jsonl \
  --raw-dir data/raw \
  --output-dir artifacts/auditoria_gold_candidato
```

Primero recuperar los datos ACL-200 del remoto DVC de confianza si no están locales. Los comandos **no ejecutan modelos, no envían tokens a proveedores, no modifican datasets**. Los parámetros `--gold`, `--reviews` y `--dataset-ids` deben apuntar a artefactos reales, con permisos apropiados.

El resultado es `artifacts/auditoria_gold_candidato/gold_audit.json` con resumen, bloqueo y hashes. Código `0` significa **que el candidato superó controles automáticos** y **debe entrar a revisión humana**, no que ya esté certificado; código `2` indica bloqueos o entrada incompleta.

### Pruebas sintéticas (sin Gold real ni S3)

```bash
uv run pytest -q tests/test_gold_freeze_audit.py tests/test_commercial_gold_policy.py tests/test_paired_benchmark.py
```

## 4. Cierre real de #100 — responsabilidades y evidencias

1. **Caicedo:** entrega dataset final versionado, manifest de todos los IDs, etiqueta original/consenso y tabla de cobertura; coordina #97 y PR #134. Validación de 15 % con trazabilidad de anotadores. Confirmar números reales y fecha de cierre.
2. **José María:** guía de anotación, evidencia de doble anotación ciega, acuerdo interanotador y decisiones independientes de adjudicación. Continúa en #98/#99/#127 y debe distribuir carga entre cinco mientras coordina despliegue.
3. **John:** ejecuta el gate sobre artefactos versionados, revisa exclusiones, relaciones train/val/test e incompatibilidad de manifiestos PR #91/#92; conserva SHA-256 y fallo/éxito verificable en la bitácora privada.
4. **Carlos Duque:** confirma que ningún ejemplo del Gold estuvo en el entrenamiento, selección de checkpoints/prompts o ajuste de SciBERT/SPECTER, y que están identificadas las variantes A/B y su procedencia de etiquetas.
5. **Gabriel:** verifica que tabla final/explicación de Gold y limitaciones queden coherentes en artículo y demo, sin publicar las etiquetas humanas del test a la interfaz.

**Evidencias finales para #100:** manifiesto canónico único con huellas/versión; política de privacidad y acceso; denominador N dataset y numerador N revisado; acuerdo y adjudicación; informe leakage 0 o excepciones documentadas y excluidas; revisión fechada de otros integrantes. **Ninguna evidencia se presume disponible por crear este código.**

La auditoría de chunk relevance del issue #127 es **otro Gold distinto**, y no puede sustituirse por el Gold de función de cita de nueve clases.
