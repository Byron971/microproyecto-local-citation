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
