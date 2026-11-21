# Evaluación humana reservada Top-3: BM25 frente a SciBERT (corte local)

**Estado:** resultados agregados extraídos de `proyecto_de_grado/artifacts/top3_test_preparacion/evaluacion_modelos_reservada/resultados_humanos_revision_independiente/evaluacion_top3_humana_revision_independiente.json` por el investigador en PowerShell, 21-nov-2026. No se ha copiado ni publicado el JSON privado de origen. La auditoría de juicios originales y ranking consulta a consulta sigue pendiente.

## Denominador y juicios humanos

- `estado`: `evaluacion_con_etiquetas_revisadas_independientemente`.
- `metodologia`: «Cada par (context_id,chunk_id) evaluado por dos anotadores. Se verifican etiquetas revisadas, no acuerdo ciego inicial».
- 30 consultas totales, 25 consultas con al menos un fragmento relevante y 5 sin positivos; los promedios reportados se calculan **solo en las 25 elegibles**.
- Acuerdo posterior a revisión: 1.0. κ de Cohen posterior a revisión: 1.0.
- κ en primera pasada: **no calculado**, porque se requieren los archivos originales sin revisar. No atribuir acuerdo ciego inicial perfecto ni independencia de un consenso posterior.

## Resultados reportados

| Métrica | BM25 | SciBERT | Diferencia SciBERT menos BM25 |
| --- | ---: | ---: | ---: |
| Hit@3 | 0.840000 | 0.520000 | -0.320000 |
| Recall@3 | 0.514909 | 0.210606 | -0.304303 |
| MRR@3 | 0.686667 | 0.433333 | -0.253333 |

En esta submuestra filtrada, BM25 alcanzó una mayor tasa de consultas con al menos un relevante en Top-3, mayor proporción de fragmentos relevantes recuperados y mayor rango recíproco promedio. La interpretación es **descriptiva y condicionada** al conjunto de relevancias revisado; no representa ventaja universal ni resultado definitivo sobre todo ACL-200 TEST.

Las cantidades de Hit@3 concuerdan aritméticamente con 21/25 (BM25) y 13/25 (SciBERT). No se pueden inferir automáticamente los casos pareados en que cada sistema acertó de forma exclusiva, ni demostrar significación estadística, sin inspeccionar los datos por consulta.

## Limitaciones declaradas en el propio archivo

1. «Submuestra filtrada no necesariamente representativa de ACL-200 TEST».
2. «Concordancia de la revision independiente distinta a primera pasada».
3. «Independencia frente a fuentes efectivas M/S y similitud textual no certificada».
4. «No equivale a validacion humana del 15% de las nueve funciones de cita».

## Revisión técnica adicional antes de afirmar recuperación científica final

- Inspeccionar los campos estructurados `comparacion_consulta_a_consulta`, `etiquetas` y `hashes` **sin publicar contextos ni juicios privados**.
- Comprobar que ambos recuperadores compararon exactamente las mismas 30 consultas, el mismo universo de chunks del artículo citado y los mismos juicios de relevancia.
- Verificar si todos los chunks candidatos fueron revisados. Según `proyecto_de_grado/docs/protocolo_top3_s2_3.md`, un pool solo de Top-3 no permite tratar Recall@3 como exhaustivo del artículo.
- Identificar naturaleza de la selección de 30 consultas y posibles exposiciones previas a rankings.
- Mantener separados estos resultados del experimento técnico de TRAIN en 603 consultas que **no** tenía Gold de fragmentos, y de la evaluación M/S de nueve funciones.

## Relación con el clasificador de funciones

El experimento de clasificación M/S **sí fue recalculado** con predicciones individuales sobre 1530 casos evaluables emparejados; macro-F1 M 0.551217 y S 0.604604 sobre etiquetas consolidadas provisionales. Este resultado es diferente de la evaluación de Top-3. Ninguno certifica por sí mismo el 15% de anotación humana de las funciones.

**Estado final del informe:** análisis cuantitativo exploratorio con juicio humano revisado; evidencia prometedora para la sección de resultados, no validación ciega ni representatividad certificada.


## Auditoría complementaria de estructura (salida local)

La inspección de las propiedades del JSON aporta los siguientes agregados, reportados por el investigador:

- `etiquetas.total`: **1005** pares `(context_id,chunk_id)` etiquetados.
- `etiquetas.relevantes`: **99** (9.85 %).
- `etiquetas.no_relevantes`: **906** (90.15 %).
- `etiquetas.desacuerdos_post_revision`: **0**.
- Las métricas `hit_at_3`, `recall_at_3` y `mrr_at_3` de
  `comparacion_consulta_a_consulta` contienen conteos agregados
  `SciBERT_mejor`, `empates`, `BM25_mejor`.
- Los hashes `corpus`, `anotador_A_normalizado`, `anotador_B_normalizado`,
  `anotador_A_original_vacio`, `anotador_B_original_vacio`, `BM25` y
  `SciBERT` tienen valores no vacíos. **Presencia de hashes no equivale
  a verificar su correspondencia con los archivos.**

No se infiere, solo por contabilizar 1005 pares sobre 30 consultas, que
se anotó exhaustivamente el conjunto de chunks de cada artículo citado.
Para afirmar Recall@3 exhaustivo se debe comprobar la cobertura de los
chunks del corpus por contexto; de lo contrario, la métrica depende del
pool anotado. Los conteos de victorias/empates por consulta siguen
pendientes de lectura. El resultado de κ posterior a revisión no sustituye
κ de primera pasada.

## Comparación pareada por consulta y prueba exacta de signos

Los agregados `comparacion_consulta_a_consulta` reportados por el investigador fueron:

| Métrica | SciBERT mejor | Empates | BM25 mejor | n sin empate | p bilateral exacta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hit@3 | 0 | 17 | 8 | 8 | 0.0078125 |
| Recall@3 | 0 | 10 | 15 | 15 | 0.0000610352 |
| MRR@3 | 3 | 12 | 10 | 13 | 0.0922852 |

Para cada métrica, la prueba de signos exacta bilateral elimina empates y supone bajo la hipótesis nula la misma probabilidad de mejora para ambos recuperadores. Con `b` victorias BM25 y `s` victorias SciBERT, `n=b+s`, se calcula `p = min(1, 2*sum(comb(n,k) for k in range(min(b,s)+1))/2**n)`. Estos conteos son compatibles con las 25 consultas elegibles en cada métrica.

Ajuste Holm para las tres pruebas exploratorias: Recall@3 **0.0001831**, Hit@3 **0.0156250**, MRR@3 **0.0922852**. Se rechaza la hipótesis de simetría de signos al 5% en las dos primeras, no en MRR@3. La prueba contrasta direcciones de diferencias, **no** estima el tamaño de una mejora en la población, ni demuestra representatividad o generalización; además, la dependencia entre consultas del mismo artículo puede afectar la inferencia. Los datos individuales por consulta no se han examinado para controlar dependencia documental o calcular intervalos de confianza sobre las magnitudes.

**Precaución imprescindible:** las etiquetas son posteriores a revisión, sin κ original; se requiere verificar cobertura exhaustiva de chunks y comparabilidad del universo de candidatos BM25/SciBERT antes de presentar Recall@3 como exhaustivo o causalizar las diferencias.
