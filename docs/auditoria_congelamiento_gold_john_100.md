# Issue #100 — Auditoría del Test Gold existente, sin repetir anotaciones

Responsable: John Byron (@Byron971). Revisión conjunta: José María (@josezambrana), Carlos Caicedo (@CaicedoBz) y Carlos Duque (@CarlosEdDL).  
**Estado:** comprobación automática de integridad; **NO** es certificación final del Gold, ni solicitud de anotar nuevamente 2.700 citas.

## 1. Lo que realmente existe en `main` (revisión 5-nov-2026)

La rama `main` ya contiene los tres CSV necesarios:

| Archivo versionado | Total | Resultado verificable |
|---|---:|---|
| `proyecto_de_grado/anotacion/test_gold/TEST_GOLD_2700_ANOTADO.csv` | 2.700 `context_id` únicos | 2.672 `COMPLETO / Evaluable`, 25 `Ambiguo`, 3 `No evaluable` |
| `notebooks/qlora-training/ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv` | 2.700 `context_id` únicos | 2.642 completos, 58 ambiguos o no evaluables |
| `proyecto_de_grado/anotacion/test_gold/TEST_GOLD_2700_MANIFIESTO.csv` | 2.700 `context_id` | Muestreo, año citante y preetiqueta QLoRA; **no prueba validación humana** |

Los IDs del primer conjunto y del conjunto de Haiku son **disjuntos (intersección 0)**. La comprobación con listas de exclusión históricas detectó **cinco IDs previamente usados (uno de 2014 y cuatro de 2015)** dentro del archivo de anotaciones. **No se eliminan ni alteran esas cinco filas**: se conservan en el histórico y se descartan solo de los candidatos al Test Gold. Por tanto, de los **1.379 registros de 2015**, quedan **1.375 elegibles por el filtro de exclusiones**, ANTES de validar particiones oficiales, adjudicaciones y demás condiciones científicas. Según PR #92, el segundo CSV contiene **pre-etiquetas automáticas Haiku**, no 2.700 decisiones de anotadores humanos. El primer CSV está diligenciado, pero **carece de campos de identidad del anotador y fecha/bitácora**, así que no se certificará de manera automática la revisión humana. El usuario/equipo confirma que una persona realizó las revisiones: **no se rehacen**; se adjunta su evidencia de procedencia si la universidad la exige.

El archivo de 2.700 anotaciones contiene **1.321 casos citantes de 2014** y **1.379 casos de 2015**. En el protocolo ACL-200, los de 2014 corresponden a **validación** y los de 2015 a **test candidato**, sujeto a corroboración contra particiones oficiales con DVC. Los 2.700 **no pueden reportarse como Test Gold final sin separar particiones**.

El PR #91 documenta otro muestreo de **1.533 casos (519 + 441 + 573)** y doble revisión distribuida entre los cinco. Es un flujo adicional, con resultados privados en Drive; hasta cruzar IDs no se puede afirmar que esos 1.533 coincidan con el CSV de 2.700, ni descartarlos. No solicitar 1.533 anotaciones nuevas sin conciliar el trabajo previo.

## 2. Ruta principal para auditar los CSV que ya están

`src/evaluation/commercial/gold_existing_csv_audit.py` lee directamente los tres CSV del repositorio, **sin modificarlos ni crear nuevas etiquetas**.

```bash
uv sync --group dev
uv run python -m src.evaluation.commercial.gold_existing_csv_audit \
  --output-dir artifacts/auditoria_gold_existente
```

El informe `gold_existing_audit.json` conserva solo cantidades globales, año, clases, bloqueos, advertencias y SHA-256; **no contiene texto de citas, respuestas por fila, identificadores de cada ejemplo o credenciales**.

Comprueba: 2.700 IDs únicos por archivo; alineación exacta con el manifiesto; formato de `TARGETCIT`, estados y nueve funciones; exclusiones de prácticas **para definir elegibilidad del Gold sin borrar anotaciones**; intersección de IDs, citantes y pares con entrenamiento Haiku; y repartición 2014/2015. La validación contra las **particiones oficiales** de ACL-200 se habilita opcionalmente indicando `--raw-dir data/raw` una vez ejecutado `dvc pull data/raw`; **sin ese argumento el reporte lo advierte expresamente**.

La cobertura de revisión humana se calcula **solo si** se introduce un denominador real documentado del dataset final con `--dataset-final-total N`; el reporte lo denomina `annotation_file_fraction_if_all_human`, **no valida la identidad humana**. Si el conjunto final fuera exactamente 18.000, 2.700/18.000 = 15 % en cantidad documental, aunque la cobertura adjudicada puede diferir; no asumir que 18.000 es el tamaño final si se depuraron casos o hay clases no evaluables.

El comando no convierte el resultado en “Gold certificado”: los campos `scientific_gold_certified`, `human_provenance_verified`, `double_annotation_verified` y `ready_for_final_benchmark` permanecen `false`. Si los controles técnicos pasan, el estado es `INTEGRIDAD_CSV_OK_CERTIFICACION_HUMANA_PENDIENTE`.

## 3. Ruta opcional para doble anotación / adjudicación

El módulo previo `src/evaluation/commercial/gold_freeze_audit.py` fue diseñado como **gate estricto opcional** para un futuro conjunto Gold que *sí tenga dos evaluaciones independientes y una adjudicación registrada*. Exige archivos **JSONL** separados (`gold`, `reviews`, `adjudications`, `dataset-ids`, `train`, `validation`) y splits ACL-200. **NO ES requisito para ejecutar la auditoría de los 2.700 CSV actuales.**

El script estricto no puede utilizarse sobre los CSV actuales sin un proceso de mapeo explícito ni se debe invocar para justificar que “hay que revisar las 2.700 otra vez”. Si la política docente exige doble anotación de un subconjunto del Gold y los 1.533 casos ya cuentan con esas hojas, **reutilizar dichas hojas** y verificar su correspondencia; solamente las faltantes, si las hubiera, serían una acción legítima adicional. No duplicar anotadores ni mezclar selección de validación y test.

## 4. QA y criterios de aceptación

```bash
uv run pytest -q tests/test_gold_existing_csv_audit.py tests/test_gold_freeze_audit.py \
  tests/test_commercial_gold_policy.py tests/test_paired_benchmark.py
```

El workflow `.github/workflows/evaluacion-citas.yml` ejecuta pruebas sintéticas más una prueba de lectura de **los archivos reales** y la auditoría de su integridad. Archiva solo el JSON de resumen. **Que CI pase demuestra compatibilidad y controles técnicos, no revisión humana ni acuerdo interanotador.**

Checklist para cerrar realmente #100:

- [ ] Registrar quién revisó los 2.700 ejemplos y cómo (fecha/protocolo), sin publicar datos personales/hojas privadas; confirmado por Caicedo/José.
- [ ] Documentar denominador real del dataset depurado y numerador validado (2.700 registros diligenciados ≠ 2.700 clasificaciones evaluables).
- [ ] Reconstruir la relación exacta entre los **2.700 revisados**, los **2.700 Haiku** y los **1.533 doblemente revisados** con los manifiestos y las hojas originales; confirmar intersecciones/citas excluidas.
- [ ] Verificar ACL-200 `train`/`val`/`test` y anti-leakage a nivel de documentos y pares, con evidencia de versión y hash.
- [ ] Comprobar ceguera, acuerdo humano, adjudicación de desacuerdos y reglas de abstención; no presumir los datos que no estén documentados.
- [ ] Separar los casos de **validación 2014** de **prueba 2015** y congelar Gold de test con etiqueta humana adjudicada.
- [ ] Obtener aprobación explícita del equipo para el manifiesto final y actualizar el benchmark #110 para consumirlo, sin mirar el test durante ajuste.

## 5. Alcance del PR #142

Este PR completa la **infraestructura de auditoría reproducible** y conserva los datos del equipo intactos. No se deben adjudicar 15/15, Gold final ni métricas científicas hasta disponer de evidencia independiente. Se puede fusionar el código de QA tras revisión y CI, pero **no cerrar #100 automáticamente**: depende de la documentación y consenso humano.

Ningún procedimiento de este PR puede sustituir la tarea de clasificación SciBERT/SPECTER del #103 o el Gold de relevancia de chunks del #127, que es otro conjunto distinto.
