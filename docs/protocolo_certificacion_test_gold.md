# Protocolo para certificar el Test Gold y reportar métricas finales

**Estado:** en ejecución; ningún resultado del Test Gold consolidado se declara certificado por la mera existencia del archivo o por pasar CI. Este protocolo separa auditoría estructural, adjudicación humana y evaluación ciega.

## 1. Universo y trazabilidad

Archivo consolidado: `proyecto_de_grado/anotacion/test_gold_final/test_gold_final.csv`.
El algoritmo actual de consolidación (`scripts/consolidar_test_gold.py`)
combina cuatro fuentes disjuntas con etiqueta principal:
`concordancia`, `una_anotacion`, `discrepancia_opus`,
`solo_opus`. El nombre de fuente no equivale a certificación.
La auditoría `scripts/auditar_certificacion_gold.py` coteja
`context_id`, fuente, etiqueta, estado de evaluabilidad y SHA-256
sin adjudicar casos ni cambiar datos. El paso exitoso de este auditor
**solo acredita consistencia estructural**.

## 2. Criterios de certificación humana

Se necesita fijar antes de calcular métricas finales:

- Dos anotadores humanos independientes por caso, salvo excepción
  documentada explícitamente en un protocolo aprobado.
- Evaluable/no evaluable y una de las nueve etiquetas según
  definiciones operativas congeladas; conservar comentarios y
  justificación de selección cuando exista duda.
- Resolver desacuerdos por adjudicación humana registrada, indicando
  fecha, rol, anotadores, criterio y etiqueta final.
- Para casos que solo cuentan con una anotación, completar la segunda;
  para casos derivados de Opus, obtener revisión humana independiente.
  La concordancia con una propuesta automatizada no sustituye
  independencia humana.
- Para declarar cobertura total, todos los IDs evaluables deben contar
  con estados suficientes para el criterio aprobado; los casos no
  evaluables conservan su abstención. Informar tasas por origen.
- Calcular acuerdo interanotador sobre las parejas de anotaciones
  humanas elegibles **antes** de la adjudicación; documentar n, κ
  de Cohen y/o α de Krippendorff con denominador explícito.
  El acuerdo no se calcula entre humanos y Opus como equivalente.

No inferir etiquetas, no sustituir decisiones del equipo por LLM,
no sobrescribir las hojas originales de los anotadores ni
`test_gold_final.csv` mientras la revisión sigue abierta.

## 3. Congelar el conjunto final

Al completar la adjudicación:

1. Conservar originales, un registro de adjudicación y un CSV
   certificado **nuevo** con versión y SHA-256; nunca sobreescribir
   las fuentes sin historial.
2. Verificar unicidad de `context_id`, cobertura del universo,
   vocabulario de nueve clases, clases ausentes, evaluabilidad,
   trazabilidad por fuente y hashes de entradas.
3. Comprobar independencia por `citing_id`, `cited_id` y par
   citante-citado contra TRAIN y VALIDACIÓN; documentar el criterio
   de no leakage. No asumir independencia a partir del nombre `test`.
4. Congelar modelos, hiperparámetros, checkpoints y scripts de
   predicción **antes** de evaluar sobre etiquetas Gold.
5. Mantener acceso a Gold y textos originales restringido a las
   personas autorizadas.

## 4. Métricas a reportar

**Clasificación de nueve funciones:** accuracy, macro-F1,
weighted-F1 y precision/recall/F1/soporte por clase; matriz de
confusión y denominador de casos evaluables. Describir política para
abstenciones y casos no evaluables, separando cobertura y calidad.

**Recuperación local Top-3:** Recall@3 y MRR@3 (y opcional nDCG@3)
**solo** si hay anotaciones independientes de relevancia de
fragmentos del mismo documento citado; el Gold de nueve funciones
**no es por sí solo** un Gold de fragmentos relevantes.
Reportar n de consultas, docs citados distintos, disponibilidad
de candidatos, exclusiones y baselines BM25/SciBERT.

**Comparaciones M/S:** reportar métricas por modelo en el mismo
subconjunto, con predicciones pareadas, criterios de agregación
documentados y sin elegir el mejor modelo usando TEST.

Los resultados previos de un caso TRAIN, incluida la
demostración `D09-1001_D08-1068_0`, no son parte de la
estimación final de desempeño.

## 5. Salidas de cierre

- Reporte estructural de auditoría y SHA-256.
- Matriz de pendientes de segunda anotación/adjudicación en acceso
  controlado, con comentarios humanos, fechas y estado.
- Dataset certificado con versión y firma del equipo.
- Manifiesto de splits, exclusiones y no-leakage.
- Predicciones congeladas y evaluación reproducible.
- Informe científico que diferencia métricas finales de
  resultados provisionales y demostraciones funcionales.

**Regla de publicación:** no subir pesos de modelos, textos completos,
matrices de adjudicación privada o credenciales a la PR pública.
