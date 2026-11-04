# Benchmark pareado de clasificación — John (#109, #110)

**Estado:** código inicial ejecutable, **solo provisional**. Los tests usan datos sintéticos y no son resultados científicos del proyecto. **No afirma** que exista Test Gold final aprobado.

## Para qué sirve
Compara dos modelos/configuraciones sobre exactamente los mismos `case_id`, verificando que no haya faltantes, duplicados, abstenciones, errores del proveedor ni etiquetas fuera de las nueve clases. Usa el `gold_policy.py` existente y los archivos ACL-200 versionados para verificar pertenencia a test, exclusiones y TARGETCIT. Genera:
- `paired_summary_provisional.json`: métricas fijas sobre nueve clases (P/R/F1 macro, micro, ponderadas, accuracy, soporte y matriz 9×9), exactitud pareada y diferencias, desacuerdos, hashes SHA-256.
- `per_class_a.csv` y `per_class_b.csv`: métricas por cada función.
- Errores por ID en el JSON para revisión local; **no subir resultados con Gold humano o texto confidencial sin revisar permisos y política del proyecto**.

## Diseño experimental: dos factores separados
- `--factor input`: variante A = contexto+título/resumen, B = contexto+Top-3 y/o sección; **fuente de etiquetas fija**. Para sección real vs barajada, elegir nombres explícitos de variantes y controlar el resto del experimento.
- `--factor training_labels`: etiquetas-Haiku vs etiquetas-Jurado; **configuración de entrada fija**.

Esta herramienta hace evaluación y controles básicos, **no entrena SciBERT ni verifica automáticamente que sus hiperparámetros sean idénticos**. Adjuntar manifiesto por cada entrenamiento: modelo, revision, seed, datos, LR, épocas, batch, tokenizer, hardware, git SHA y pesos.

## Formato de entrada
`gold.jsonl`, con exactamente una etiqueta verdadera por cita y el identificador de la pareja documental. **Debe provenir de un Gold realmente adjudicado y custodiado por el equipo; el programa no lo certifica.**

```json
{"id":"C-001","input":"We apply TARGETCIT to this problem.","gold":"Application","citing_id":"P15-0001","cited_id":"P12-0002"}
```

`modelo_a.jsonl` y `modelo_b.jsonl`: cada fila es una predicción sin la etiqueta verdadera y debe corresponder a la misma ID del Gold:

```json
{"case_id":"C-001","status":"ok","pred_label":"Application"}
```

Se acepta alternativamente `pred_index` entero entre 0 y 8. Si están presentes `pred_label` y `pred_index`, deben coincidir. Los scripts de los modelos deben exportar una predicción por ID (incluidos los fallos, con su `status`); fallos explícitos **bloquean** el cómputo para no escoger subconjuntos favorables. Reportarlos por separado en el log operativo.

## Ejecución (desde la raíz)
El grupo `research` proporciona scikit-learn. Primero recuperar datos DVC y auditar test/hashes.

```bash
uv sync --group research --group dev
uv run --group research dvc pull
uv run --group research python -m src.evaluation.commercial.paired_benchmark \
  --gold /ruta/segura/test_gold_adjudicado.jsonl \
  --predictions-a /ruta/segura/predicciones_entrada_A.jsonl \
  --predictions-b /ruta/segura/predicciones_entrada_B.jsonl \
  --name-a entrada_A --name-b entrada_B \
  --factor input --raw-dir data/raw \
  --output-dir artifacts/benchmark_pareado_entrada \
  --provisional
```

**Toda corrida permanece PROVISIONAL:** sin `--provisional` el CLI bloquea cualquier intento de evaluación presentada como final. El chequeo automático de ACL-200 no prueba doble anotación ni adjudicación, y nunca se debe eludir cambiando el nombre de archivos antiguos. Para publicar una evaluación final, se requiere una etapa separada de certificación del Gold y su aprobación documental antes de modificar el protocolo de bloqueo.

### Pruebas
```bash
uv run --group research pytest -q tests/test_paired_benchmark.py
```

La prueba de CI también incorpora el nuevo archivo al workflow `.github/workflows/evaluacion-citas.yml`.

## Limitaciones conocidas / futuros criterios de cierre
1. El programa no convierte automáticamente notebooks/csv de SciBERT y QLoRA a su contrato; requiere un exportador verificado por sus autores.
2. Las métricas son estrictas: se exigen 100% de predicciones válidas para todas las IDs. Registrar coberturas menores como fallos operativos fuera del benchmark y corregirlos antes de comparar; evita cambiar el denominador en silencio.
3. El macro-F1 incluye **las nueve clases aun si alguna tiene soporte cero**. Informar distribución real antes de interpretar ese valor.
4. No se implementan aún bootstrap pareado, inferencia estadística por documento, comparación de latencia ni gráficos del artículo. Se requieren los artefactos reales y el Gold para elegir unidad de remuestreo y controles.
5. El comparador no garantiza por sí solo la ausencia de contaminación en el entrenamiento: hay que cruzar manifiestos completos de train, val y test y hashes de corpus.
6. **Bloqueos P0** siguen vigentes: manifiesto Gold único (#100/#111), 15% de validación humana, 2.000 por cada clase, y acuerdo de relevancia Top-3 por chunks (#127).

## Relación con rúbrica
- Informe de avance: construcción de modelos (35), resultados (10), análisis (20).
- Artículo científico: metodología (30), resultados (15), discusión (15).
- Dependencias: #100, #103, #104, #109, #110, #111, #128.

No se marcarán los issues #109/#110 como terminados hasta disponer de **resultados reales certificados** y revisión cruzada.
