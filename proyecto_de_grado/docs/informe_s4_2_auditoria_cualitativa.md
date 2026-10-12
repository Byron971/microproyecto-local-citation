# S4.2 — Auditoría cualitativa de cambios C1/C2 (exploratoria, no Gold)

**Proyecto:** Recomendación local de citas y clasificación de funciones de cita en artículos académicos.
**Unidad auditada:** únicamente los 12 casos discordantes del piloto de 67 contextos del split `train`.
**Fuente:** `auditoria_transiciones_c1_c2.csv` (12 filas, 11 columnas).
**SHA256 del CSV de entrada:** `f84c0366d7e1abf83865c9cfb9684e8f93f3b67d3ccc46961cca91e047834b29`.
**Carácter:** auditoría interna no ciega orientada a detectar riesgos y priorizar verificaciones. No son etiquetas humanas ni juicios Gold.

## Objetivo y procedimiento

Se contrastaron el texto de cada contexto de cita, las etiquetas automáticas C1 (contexto + título y resumen) y C2 (los mismos datos + evidencia SciBERT Top-3), y el texto de los tres fragmentos recuperados. Se registraron indicios de correspondencia temática, carencias evidenciales y riesgos de atribución para orientar una revisión posterior. **No se adjudicó ninguna función como correcta ni se asignó relevancia binaria a fragmentos.**

## Verificaciones descriptivas

- **12/12** registros discordantes contienen un `TARGETCIT` y tres IDs/textos de fragmentos Top-3 no vacíos.
- **9** artículos citados distintos entre los 12 casos; **7/12** contextos también contienen `OTHERCIT` (58,3 % de este subconjunto seleccionado, no de los 67).
- **7** cambios terminan en `Basis` y **5** parten de `Basis`; saldo neto +2, calculado en este subconjunto.
- `P03-1054` aporta **3/12** discrepancias (25 %); `P03-1021`, **2/12** (16,7 %). Ambos artículos reúnen **5/12** discordancias (41,7 %). Estos porcentajes solo describen las discrepancias, no tasas de error por artículo.
- En `P03-1054`, los tres cambios son `Background → Basis`; en `P03-1021`, los cambios son `Basis → Application` y `Basis → Background`.
- Los contextos presentan recortes y señales de ruido de extracción (por ejemplo, inicios o finales de oración incompletos). La reconstrucción de la oración y la atribución de `TARGETCIT` preceden a cualquier conclusión de función.

## Revisión puntual de P03-1054 (tres discordancias)

### J13-1006_P03-1054_4 — Background → Basis
El contexto cita una estrategia de binarización de árboles. El top1 (`p00031-p00032`) menciona binarización/horizontal markovization y el top2 (`p00033-p00034`) trata propiedades de parsers PCFG. Existe una coincidencia temática visible, pero sin reconstruir el pasaje citante no se puede decidir si el papel de la cita es antecedente, aplicación o fundamento.

### N09-1063_P03-1054_0 — Background → Basis
El contexto describe métodos de búsqueda A* y garantías de optimalidad en parsing; `TARGETCIT` aparece agrupado con `OTHERCIT`. Los pasajes (`p00004-p00005`, `p00001-s001`, `p00031-p00032`) se enfocan en PCFG, anotación, lexicalización y binarización. **No se observa en estos pasajes una explicación directa de A* u optimalidad**. Esto justifica verificar la pertinencia semántica del Top-3 y la atribución exacta del marcador; no demuestra error de clasificación ni recuperación por sí solo.

### W13-1506_P03-1054_0 — Background → Basis
El contexto describe características de complejidad sintáctica obtenidas de Stanford Parser. Los pasajes (`p00001-s001`, `p00019-s001`, `p00029-p00030`) tratan PCFG, categorías y lexicalización, sin explicar de manera clara la extracción de esas características por Stanford Parser. La relación es **indirecta** y amerita verificación del artículo completo.

### Efecto de documentos repetidos
Los contextos de `P03-1054` reutilizan algunos fragmentos: `p00031-p00032` aparece en dos Top-3, así como `p00001-s001` y `p00019-s001` en dos listas cada uno. Esto es esperable al consultar un mismo artículo, pero hace que las observaciones por contexto no puedan suponerse independientes. En `P03-1021`, ambos Top-3 comparten `p00042-p00043` y `p00044-p00044`, y aun así conducen a etiquetas C2 diferentes: **la evidencia compartida no determina por sí sola una función única**.

## Observaciones por los 12 casos (sin adjudicación)

| Context ID | Cambio C1 → C2 | Prioridad | Observación breve |
|---|---|---|---|
| `J12-4005_J91-4003_2` | Gap → Basis | Media | Contexto sobre interpretaciones semánticas de nominalizaciones; los pasajes tratan alternancias semánticas, inferencias y coerción de tipos. Coincidencia temática sin prueba de una función retórica concreta. |
| `J13-1006_P03-1054_4` | Background → Basis | Media | Contexto de binarización de árboles; top1 contiene referencia a binarización y top2 a análisis PCFG. Coherencia temática parcial. |
| `N09-1063_P03-1054_0` | Background → Basis | Alta | Contexto sobre búsqueda A* y optimalidad; los top3 abordan PCFG no lexicalizados, parent-annotation y binarización. No se observa respaldo explícito a la afirmación sobre A*. |
| `P11-2072_J07-2003_0` | Improvement / Modification → Basis | Media | Contexto indica capacidad del decodificador para parsing y cube-pruning; los fragmentos tratan Hiero, extracción de reglas y sistemas de traducción. No evidencian por sí solos una mejora del trabajo citado. |
| `W10-1741_P07-2045_1` | Basis → Application | Media | Contexto declara uso de Moses como sistema base; top1 caracteriza Moses como toolkit de traducción y sus componentes. Relación funcional visible. |
| `W10-3903_N04-1019_0` | Basis → Background | Media | Contexto enumera ROUGE, BE y Pyramid como técnicas previas de evaluación; top1 presenta virtudes del método Pyramid. Hay correspondencia temática, con posible función de antecedente. |
| `W11-2139_P03-1021_1` | Basis → Application | Media | El citante declara usar minimum error rate training para optimizar el sistema; los pasajes incluyen modelos de traducción y optimización. Coherencia metodológica parcial. |
| `W11-2909_P06-1055_0` | Background → Basis | Alta | El contexto agrupa tres referencias sobre métodos para LPCFG; los fragmentos tratan split-merge y estimación gramatical. La atribución específica a TARGETCIT es ambigua sin reconstrucción. |
| `W12-3160_P03-1021_0` | Basis → Background | Media | Contexto presenta MERT como método anterior frente a optimización en línea; la evidencia describe enfoques de entrenamiento y modelos probabilísticos. Hay relación temática. |
| `W13-1506_P03-1054_0` | Background → Basis | Alta | El contexto atribuye características de complejidad sintáctica a la salida de Stanford Parser; los pasajes hablan de PCFG, lexicalización y subcategorización, sin documentación clara del uso específico. |
| `W13-4005_W08-1111_0` | Application → Basis | Alta | El citante agrupa referencias sobre inducción de recursos para NLG; top1 trata inducción de gramáticas y top2 aplicaciones de generación de texto. La atribución individual está confundida. |
| `W13-5002_P98-2127_1` | Basis → Background | Media | El texto citante introduce explícitamente trabajos relacionados; top1 explica una métrica de similitud y top2 compara enfoques previos. El cambio a Background es interpretativamente plausible, no verificado. |

## Hallazgos e interpretación metodológica

1. **Relación temática no equivale a evidencia puntual.** Hay casos donde SciBERT aporta vocabulario o técnica de la misma área que el contexto pero los fragmentos no sustentan de forma explícita la proposición atribuida a `TARGETCIT` (en particular N09-1063 y W13-1506).
2. **Las referencias agrupadas son un confusor importante.** Siete de los doce contextos incluyen `OTHERCIT`. Antes de adjudicar una función retórica se debe verificar qué afirmación corresponde a cada referencia.
3. **Los contextos truncados limitan la atribución.** La reconstrucción de oraciones/citas y la revisión de extracción ACL OCL son acciones metodológicas anteriores al cálculo de calidad.
4. **La concentración en Basis no puede explicarse causalmente a partir de esta auditoría.** Los 12 casos fueron seleccionados por discordancia; no constituyen muestra independiente y no permiten estimar desempeño o prevalencia real por artículo. Que siete cambios terminen en Basis no demuestra sesgo del recuperador.
5. **No hay referencia Gold:** las predicciones C1/C2 son propuestas de un mismo modelo; ni su desacuerdo ni una interpretación semántica preliminar determinan precisión, F1 Macro, Recall@3 o MRR@3.

## Limitaciones y cautelas

- El CSV solo incluye 12 discordancias, no los 55 casos concordantes ni el texto completo de los artículos; esta auditoría no evalúa todos los 67 ni estima una tasa de relevancia representativa.
- Las observaciones son hechas conociendo ambas predicciones y sus rankings (revisión no ciega). **No pueden utilizarse como Gold ni mostrarse como pistas a futuros anotadores ciegos.**
- Un fragmento sin respaldo visible en el Top-3 no demuestra que no exista evidencia pertinente en el resto del artículo citado.
- Varias fuentes presentan errores de extracción, palabras fragmentadas, ecuaciones desordenadas o contextos cortados.
- Estos casos pertenecen a `train`; ninguna conclusión aquí cuantifica la generalización a `val` o `test`.

## Decisiones recomendadas antes de S4.3

1. Conservar **este informe y el CSV de observaciones como auditoría interna de desarrollo**, fuera del conjunto de anotación ciega final.
2. Priorizar inspección documental de `N09-1063_P03-1054_0`, `W13-1506_P03-1054_0`, `W11-2909_P06-1055_0` y `W13-4005_W08-1111_0`, por evidencia indirecta o referencias agrupadas. Esto es prioridad de revisión, **no prioridad de falsos positivos probados**.
3. Preparar S4.3 de manera **separada**: (a) calibración humana sobre train ya excluido del Test Gold; (b) diseño de muestra nueva en val para desarrollo; (c) reserva independiente de test, con exclusiones del piloto histórico y cualquier ejemplo inspeccionado.
4. No publicar Recall@3/MRR@3 sin juicios de relevancia **exhaustivos** para cada consulta y fragmento según G0.5/S2.3; no publicar F1 Macro sin etiquetas de función humanas independientes y adjudicadas.
5. El requisito de validar por humanos ≥15 % del **dataset final** es distinto del tamaño del nuevo Test Gold y sigue pendiente de planificación/ratificación. Una muestra piloto pequeña no lo cumple automáticamente.
6. Mantener la separación del código y resultados de S4 respecto a los PR Draft #84 (S2.8) y #85 (S3).

**Estado S4.2:** auditoría exploratoria concluida; hipótesis y riesgos identificados, sin modificación de etiquetas automáticas y sin adjudicación Gold. Próxima actividad: definir y probar procedimiento de evaluación humana ciega S4.3 antes de medir calidad.
