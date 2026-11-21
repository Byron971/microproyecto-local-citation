# Resultados Top-3 recalculados — corte para entrega del 23 de noviembre de 2026

**Procedencia:** salida de consola reportada por el investigador tras ejecutar `scripts/recalcular_top3_etiquetas_finales.py` sobre `top3_etiquetas_pareadas_1005.csv` y los rankings originales locales de BM25/SciBERT. El cálculo se ejecutó en su clon `ms-clon-limpio`, no sobre archivos publicados en GitHub. El resultado JSON completo reside en `artifacts/top3_recalculado_1005.json` y no se versiona por privacidad y trazabilidad.

## Denominadores

| Campo | Valor |
| --- | ---: |
| Consultas totales | 30 |
| Consultas con al menos un relevante | 25 |
| Consultas sin relevancias positivas, excluidas del promedio | 5 |
| Juicios binarios consolidados | 1005 |
| Etiquetas positivas (relevante) | 96 |
| Etiquetas negativas | 909 |

## Métricas actuales (prevalecen sobre el corte histórico 99/906)

| Métrica | BM25 | SciBERT | Diferencia BM25 menos SciBERT |
| --- | ---: | ---: | ---: |
| Hit@3 | 0.840000 | 0.520000 | +0.320000 |
| Recall@3 | 0.515051 | 0.211414 | +0.303636 |
| MRR@3 | 0.666667 | 0.433333 | +0.233333 |

La comparación pareada mantiene los mismos signos que el corte anterior:

| Métrica | BM25 mejor | SciBERT mejor | Empates |
| --- | ---: | ---: | ---: |
| Hit@3 | 8 | 0 | 17 |
| Recall@3 | 15 | 0 | 10 |
| MRR@3 | 10 | 3 | 12 |

Estas cifras describen la muestra de 25 consultas elegibles, sin demostrar generalización a todo el universo ACL-200.

## Huellas SHA-256 de la ejecución

- Etiquetas: `e695bd86f481b0784906b47a1de0baec40a9a5063597ea779f388df6dfd07064`.
- Ranking BM25: `25d32d3e560e62f5ee92a8b05a6e81cd99697f3f528fa92b4387f225723f9a0d`.
- Ranking SciBERT: `762b02d5f03d4a5e449edc48a49d85219731b145f0b7d75700598d054ac40222`.

## Pendientes y límites obligatorios

1. **No sustituir el significado de los resultados:** el reporte histórico `docs/resultados_top3_humano_reservado_20261121.md` se calculó con 99 positivos/906 negativos. El presente corte usa 96/909 y debe usarse para la entrega; preservar ambos documentos para la auditoría, identificados por versión.
2. El hecho de que el script haya comprobado que los chunks **recuperados en Top-3** pertenecen al universo etiquetado no demuestra por sí solo que se hayan anotado **todos los chunks disponibles del artículo**. Se necesita auditoría exhaustiva del corpus de 30 casos antes de describir Recall@3 como exhaustivo.
3. El acuerdo A/B en etiquetas consolidadas no demuestra independencia inicial de anotadores; no citar κ = 1 posterior a revisión como κ previo a adjudicación.
4. El conjunto es exploratorio y filtrado; no certificar independencia frente a M/S ni significación ajustada por agrupación documental sin validar procedencia de los contextos.
5. Los conteos por consulta permiten prueba de signos exploratoria (sin empates: Hit@3 8:0, Recall@3 15:0, MRR@3 10:3), pero cualquier interpretación inferencial requiere las cautelas anteriores.

## Estado de la entrega

La **reproducción numérica** de Top-3 sobre la versión final de etiquetas está cerrada. Faltan la verificación de exhaustividad, independencia y consolidación del documento académico con metodología/limitaciones.


## Cierre de auditoría de cobertura, ejecutado localmente el 21-nov-2026

El investigador ejecutó `scripts/auditar_cobertura_top3_1005.py` en
`ms-clon-limpio` sobre el corpus y rankings privados, sin publicar
textos ni etiquetas:

| Control | Resultado |
| --- | ---: |
| Estado | `exhaustivo` |
| Consultas en corpus / etiquetas | 30 / 30 |
| Pares en corpus / etiquetas | 1005 / 1005 |
| Pares sin etiqueta | 0 |
| Etiquetas fuera del corpus | 0 |
| Mínimo/máximo chunks por consulta | 14 / 138 |
| Consultas con / sin positivos | 25 / 5 |
| Total relevantes | 96 |
| Relevancia exhaustiva en corpus | `true` |
| Rankings válidos | `true` |
| BM25: consultas, Top-3 válidos, ajenos | 30, 90, 0 |
| SciBERT: consultas, Top-3 válidos, ajenos | 30, 90, 0 |
| Duplicados en rankings BM25 / SciBERT | 0 / 0 |

Huellas SHA-256 registradas por esta auditoría:

- Corpus: `383475458ecb1d124a8367199e2c66f367e99b480cde4fd9622c420147a427f1`
- Etiquetas: `e695bd86f481b0784906b47a1de0baec40a9a5063597ea779f388df6dfd07064`
- BM25: `25d32d3e560e62f5ee92a8b05a6e81cd99697f3f528fa92b4387f225723f9a0d`
- SciBERT: `762b02d5f03d4a5e449edc48a49d85219731b145f0b7d75700598d054ac40222`

**Conclusión acotada:** las etiquetas cubren **todos los chunks de este corpus
fragmentado** y ambos rankings Top-3 son íntegros respecto de él. Esto
resuelve la duda de completitud *interna* del conjunto de evaluación,
pero no acredita cobertura total del artículo OCL externo, independencia
ciega original de A/B, representatividad poblacional o calidad
semántica de todas las etiquetas. El informe final debe distinguir
claramente estos límites y preservar las evidencias privadas en local.
