# Matriz de correcciones - Propuesta V4

**Proyecto:** Recomendación local de citas y clasificación de su función en artículos académicos.

**Docente:** Haydemar Núñez  
**Calificación de la propuesta V3:** 86/100  
**Fecha de revisión:** 8 de octubre de 2026  
**Repositorio:** Byron971/microproyecto-local-citation  
**Rama de trabajo:** docs/correcciones-haydemar-v4

## 1. Objetivo

Resolver las observaciones recibidas en las rúbricas 4, 5 y 6 mediante correcciones metodológicas, análisis de datos, implementación reproducible y evidencia verificable.

El documento permite identificar los problemas observados, las decisiones adoptadas por el equipo, las evidencias disponibles y las actividades pendientes.

La corrección de las observaciones no implica modificar automáticamente la calificación anterior. Su propósito es mejorar la calidad científica y técnica de las siguientes entregas.

## 2. Resumen de la evaluación

| Criterio | Calificación | Puntos perdidos |
|---|---:|---:|
| Rúbrica 4 - Metodología propuesta | 12/15 | 3 |
| Rúbrica 5 - Recolección, exploración y descripción de datos | 11/20 | 9 |
| Rúbrica 6 - Evaluación y métricas | 8/10 | 2 |
| **Total de los criterios observados** | **31/45** | **14** |

Las demás rúbricas obtuvieron la puntuación máxima.

La mayor prioridad es la Rúbrica 5, responsable de nueve de los catorce puntos perdidos.

## 3. Rúbrica 4 - Metodología propuesta (12/15)

### R4.1. Estrategia de homologación de datasets

**Observación de Haydemar:**

Se mencionan diferentes datasets, pero no es clara la estrategia de homologación, si se piensa armar un solo dataset o si se planea comparar los datasets mediante diferentes formas de extracción de contextos de cita.

**Problema identificado:**

La propuesta V3 consideraba combinar ACL-200 con unarXive utilizando identificadores de arXiv, sin demostrar que existiera suficiente correspondencia entre ambos conjuntos.

**Corrección adoptada:**

Construir un único dataset integrado utilizando dos fuentes complementarias:

- ACL-200: proporciona los contextos de cita, los identificadores de los artículos citantes y citados, los títulos, los resúmenes y las particiones originales.
- ACL OCL: proporciona el texto completo de artículos de ACL Anthology, incluyendo párrafos, secciones, citas y referencias bibliográficas.

La homologación se realiza mediante identificadores de ACL Anthology.

MultiCite e ILCiteR se utilizarán como referencias metodológicas externas, sin fusionarlos automáticamente con el dataset principal.

El estudio técnico del equipo encontró una cobertura estimada de pares completos del 82,2 % con ACL OCL, frente a una cota superior del 0,2 % mediante la ruta de unarXive evaluada.

El experto de dominio confirmó que pueden combinarse fuentes siempre que cumplan las características del proyecto y las cuotas establecidas o se aproximen justificadamente a ellas.

**Implementación disponible:**

- Integración individual de contextos con artículos citados.
- Verificación de identificadores ACL Anthology.
- Conservación del marcador TARGETCIT.
- Recuperación de párrafos y secciones.
- Integración por lotes.
- Auditoría automática del corpus.
- Registro de documentos faltantes, referencias candidatas y posibles problemas de alineación textual.

**Evidencias técnicas:**

- proyecto_de_grado/docs/spike_enlace_datos/README.md
- proyecto_de_grado/scripts/spike_enlace_datos/medir_enlace.py
- proyecto_de_grado/src/data/integrar_acl.py
- proyecto_de_grado/src/data/integrar_lote.py
- proyecto_de_grado/src/data/auditar_corpus.py
- proyecto_de_grado/tests/test_integrar_acl.py
- proyecto_de_grado/tests/test_integrar_lote.py
- proyecto_de_grado/tests/test_auditar_corpus.py

**Pendiente:**

- Integrar el corpus objetivo completo.
- Incorporar la recuperación y validación de artículos citantes.
- Reconstruir las oraciones de cita mediante un procedimiento verificable.
- Registrar las causas de exclusión.
- Generar el dataset final versionado y reproducible.

**Estado: PARCIAL - ESTRATEGIA DEFINIDA E IMPLEMENTACIÓN INICIAL VALIDADA.**

### R4.2. Posible sesgo producido por las secciones

**Observación de Haydemar:**

Agregar la sección del documento dentro de la segunda configuración de clasificación de citas puede generar un sesgo en la clasificación.

**Problema identificado:**

El clasificador podría aprender asociaciones superficiales entre el nombre de una sección y una función retórica.

Por ejemplo, podría relacionar automáticamente Related Work con Background, sin analizar suficientemente el significado del contexto.

También es necesario distinguir entre:

- Sección del artículo citante donde aparece la cita.
- Sección del artículo citado de donde proviene un fragmento recuperado.

Estas variables representan información diferente.

**Corrección propuesta:**

Realizar experimentos de ablación con las siguientes configuraciones:

| Configuración | Información de entrada |
|---|---|
| C0 | Contexto de cita |
| C1 | Contexto, título y resumen del artículo citado |
| C2 | Contexto y Top-3 fragmentos recuperados |
| C3 | C2 más secciones de los fragmentos recuperados |
| C3-barajada | C3 con las etiquetas de sección permutadas como control |

Se comparará F1 Macro entre configuraciones para determinar si incorporar las secciones produce una mejora real.

También se evaluará la asociación entre las secciones y las funciones de cita, incluyendo resultados por categoría.

La interpretación de las ablaciones deberá considerar posibles factores de confusión. Una mejora aislada no demuestra automáticamente ausencia de sesgo.

**Pendiente:**

- Definir formalmente las variables de sección.
- Implementar las configuraciones experimentales.
- Ejecutar los experimentos.
- Reportar F1 Macro, diferencias por clase y resultados de los controles.
- Documentar si resulta conveniente incorporar las secciones al modelo definitivo.

**Estado: PENDIENTE - DISEÑO EXPERIMENTAL DOCUMENTADO.**

## 4. Rúbrica 5 - Recolección, exploración y descripción de los datos (11/20)

### R5.1. Caracterización detallada del dataset

**Observación de Haydemar:**

Falta una mayor descripción del dataset utilizado y de sus características.

**Corrección:**

Se documentan las características verificadas de ACL-200:

- 63.768 contextos de cita.
- 19.776 artículos científicos registrados.
- 49.356 contextos incluidos en las particiones supervisadas.
- Marcador TARGETCIT para la cita objetivo.
- Marcador OTHERCIT para otras citas.
- Metadatos de artículos que incluyen título y resumen.

Los contextos originales están truncados mediante ventanas de texto.

El análisis del equipo identificó:

- 87,9 % de contextos que comienzan en minúscula.
- 98,3 % que no terminan en punto.
- Mediana de 63 palabras por contexto.

Esto demuestra la necesidad de reconstruir las oraciones antes de utilizar los contextos en tareas que requieran sus límites completos.

ACL OCL aporta el texto extraído de PDF mediante GROBID. Esta fuente puede presentar ruido de extracción, errores de caracteres y fragmentación de párrafos.

**Evidencia:**

- proyecto_de_grado/scripts/cifras_informe.py
- proyecto_de_grado/docs/informe_avance/borrador_ajustes_informe_avance.md

**Pendiente:**

Completar la caracterización del corpus integrado definitivo, incluyendo distribución de longitud, secciones, documentos disponibles, incidencias de extracción y registros excluidos.

**Estado: PARCIAL - CARACTERIZACIÓN DE ACL-200 DISPONIBLE.**

### R5.2. Disponibilidad de pares y cobertura documental

**Observación de Haydemar:**

Aclarar si todos los contextos de cita tienen su correspondiente par y qué consideraciones deben tenerse en cuenta para dividir y utilizar el dataset.

**Corrección:**

Se establece una estrategia de homologación entre ACL-200 y ACL OCL utilizando identificadores ACL Anthology.

El estudio reproducible del equipo sobre 500 contextos aleatorios, con semilla 42, encontró:

| Etapa | Casos | Porcentaje |
|---|---:|---:|
| Contextos examinados | 500 | 100 % |
| Artículos citados disponibles en ACL OCL | 499 | 99,8 % |
| Artículos citados con texto utilizable | 490 | 98,0 % |
| Contextos localizados en artículos citantes | 421 | 84,2 % |
| Pares que cumplen ambos criterios | 411 | 82,2 % |

El criterio inicial de texto utilizable exige al menos 500 palabras de cuerpo y tres secciones distintas.

El 82,2 % es una estimación obtenida sobre una muestra y no equivale a la cobertura verificada del corpus completo.

La localización textual tampoco constituye por sí sola una validación definitiva de la cita objetivo.

**Auditoría técnica adicional:**

Se implementó una herramienta de auditoría automática que examinó 141 contextos supervisados cuyos artículos citados estaban descargados localmente.

Distribución:

- Entrenamiento: 70.
- Validación: 45.
- Prueba: 26.

Resultados:

- 5 alineaciones candidatas.
- 1 referencia bibliográfica localizada.
- 2 contextos localizados mediante coincidencia textual.
- 133 registros cuyos artículos citantes no estaban descargados localmente.

Los 133 casos sin citante descargado no deben contabilizarse como documentos ausentes de ACL OCL ni como fallos de integración.

La auditoría local no constituye una muestra representativa del corpus.

**Evidencias:**

- proyecto_de_grado/docs/spike_enlace_datos/README.md
- proyecto_de_grado/scripts/spike_enlace_datos/medir_enlace.py
- proyecto_de_grado/src/data/auditar_corpus.py

**Pendiente:**

- Ejecutar la integración sobre el corpus objetivo.
- Separar disponibilidad documental de reconstrucción validada.
- Reportar las pérdidas en cada etapa.
- Verificar las cuotas reales por función de cita después del pre-etiquetado.

**Estado: PARCIAL - COBERTURA MUESTRAL Y AUDITORÍA LOCAL DOCUMENTADAS.**

### R5.3. Particiones temporales y control de fuga de información

**Observación de Haydemar:**

¿Qué consideraciones se tienen en cuenta al momento de hacer el split del dataset? ¿Se tiene en cuenta cuándo se escribió el artículo?

**Corrección:**

Se conservarán inicialmente las particiones temporales de ACL-200:

| Partición | Año del artículo citante | Contextos |
|---|---|---:|
| Train | 2009–2013 | 30.390 |
| Val | 2014 | 9.381 |
| Test | 2015 | 9.585 |

Se verificó que no existen artículos citantes compartidos entre entrenamiento y prueba.

Sin embargo, existen 1.338 artículos citados compartidos entre estas dos particiones.

Esto no implica automáticamente fuga de información, pero requiere controles adicionales.

Para la nueva tarea de clasificación se documentará el grado de solapamiento a nivel de documento y de par citante-citado.

También se analizará por separado el rendimiento sobre artículos citados vistos y no vistos durante el entrenamiento.

**Pendiente:**

- Automatizar los controles de solapamiento.
- Verificar los pares citante-citado entre particiones.
- Comprobar posibles duplicados textuales.
- Documentar la política definitiva de separación.
- Garantizar que los casos del Test Gold no participen en entrenamiento ni selección de modelos.

**Estado: PARCIAL - ESTRUCTURA TEMPORAL VERIFICADA.**

### R5.4. Viabilidad de 2.000 ejemplos por función de cita

**Observación de Haydemar:**

Con la cantidad actual de datos, ¿es posible llegar a la meta de muestra propuesta?

**Problema identificado:**

El volumen de contextos disponibles no garantiza que podamos construir un conjunto balanceado de nueve funciones de cita.

La propuesta contempla al menos 2.000 ejemplos por categoría, equivalentes a 18.000 ejemplos en total.

Las funciones minoritarias pueden tener frecuencias naturales insuficientes.

**Corrección propuesta:**

Ejecutar un proceso de pre-etiquetado con modelos open-weight y auditoría humana para estimar las frecuencias por clase.

Las nueve categorías son:

1. Background.
2. Gap.
3. Basis.
4. Comparison.
5. Application.
6. Improvement / Modification.
7. Evidence.
8. Identification of the Originator.
9. Further Reading.

Se generará un reporte que incluya:

- Cantidad de ejemplos por clase.
- Proporción de ejemplos por categoría.
- Confianza y desacuerdo entre jueces automáticos.
- Cantidad de ejemplos revisados por humanos.
- Número de ejemplos válidos después de los controles de calidad.
- Déficit respecto a la cuota de 2.000 ejemplos por categoría.

No se afirmará que las cuotas se cumplieron hasta disponer de conteos reproducibles.

**Pendiente:**

- Definir el esquema de etiqueta principal y casos ambiguos.
- Ejecutar el pre-etiquetado.
- Calcular las frecuencias reales.
- Verificar la calidad de las etiquetas.
- Construir el dataset final.

**Estado: PENDIENTE - CUOTAS TODAVÍA NO DEMOSTRADAS.**

### R5.5. Plan de contingencia ante datos insuficientes

**Observación de Haydemar:**

¿Qué plan se propone en caso de que los datos actuales sean insuficientes?

**Corrección:**

Se establece una estrategia escalonada:

1. Utilizar los contextos elegibles de ACL-200 y el texto completo de ACL OCL.
2. Identificar clases minoritarias mediante pre-etiquetado.
3. Evaluar la extracción de contextos adicionales desde las referencias bibliográficas de ACL OCL.
4. Consultar la posibilidad de colaboración con otros grupos que utilicen la misma taxonomía y criterios de anotación.
5. Aplicar estrategias de entrenamiento para clases desbalanceadas, sin presentar el balance artificial como aumento de ejemplos independientes.
6. Reportar de manera transparente las cuotas alcanzadas y las limitaciones.
7. Solicitar aprobación académica si resulta necesario modificar compromisos de la propuesta.

No se incorporarán etiquetas externas sin verificar su calidad y compatibilidad metodológica.

**Estado: PARCIAL - CONTINGENCIA DEFINIDA, AÚN NO EJECUTADA.**

## 5. Rúbrica 6 - Evaluación y métricas (8/10)

### R6.1. Ground truth para recuperación Top-3

**Observación de Haydemar:**

¿En recuperación del Top-3 cómo se calcula el Recall en general? ¿Cuál es el ground truth de referencia, lo mismo para MRR?

**Problema identificado:**

ACL-200 identifica el artículo citado, pero no los fragmentos concretos de ese artículo que respaldan la afirmación del contexto.

Las métricas de recomendación de artículos del MVP no pueden utilizarse directamente como evaluación de relevancia de fragmentos.

**Corrección propuesta:**

Construir un conjunto curado de aproximadamente 100 contextos de cita para evaluar la recuperación de evidencia.

Para cada contexto se identificarán los fragmentos del artículo citado considerados relevantes.

Se propondrá el siguiente protocolo:

1. Seleccionar contextos con criterios predefinidos.
2. Generar candidatos mediante BM25 y SciBERT.
3. Incorporar controles para evaluar posibles fragmentos relevantes no recuperados por ninguno de los sistemas.
4. Realizar anotación humana independiente.
5. Resolver desacuerdos mediante adjudicación.
6. Registrar identificadores de fragmentos, etiquetas de relevancia y procedencia de las decisiones.
7. Mantener separados los casos utilizados para ajustar el recuperador y los reservados para su evaluación final.

El ground truth deberá identificar explícitamente qué fragmentos son relevantes para cada consulta.

El conjunto curado no se considerará exhaustivo si solamente se anotan candidatos sugeridos por los recuperadores.

**Estado: PENDIENTE - PROTOCOLO DEFINIDO, GROUND TRUTH NO CONSTRUIDO.**

### R6.2. Definición de Recall@3, Hit@3 y MRR@3

**Corrección:**

Para cada contexto q se definirá:

- G(q): conjunto de fragmentos relevantes.
- Top3(q): los tres fragmentos mejor puntuados por el recuperador.
- r(q): posición del primer fragmento relevante, si aparece entre los tres primeros.

**Hit@3:**

Promedio del indicador de que al menos un fragmento relevante aparece entre los tres primeros.

**Recall@3:**

Promedio de la proporción de fragmentos relevantes recuperados entre los tres primeros, respecto al total de fragmentos relevantes por consulta.

**MRR@3:**

Promedio del inverso de la posición del primer fragmento relevante entre los tres primeros. Cuando ninguno aparece, el valor de esa consulta es cero.

Las consultas sin fragmentos relevantes identificados deberán tratarse mediante una política predefinida para evitar métricas ambiguas.

Estas métricas se reportarán de manera complementaria.

**Evaluación principal:**

Siguiendo la orientación del experto de dominio, el Top-3 se evaluará principalmente por su contribución al clasificador.

Se comparará F1 Macro bajo entradas equivalentes, con y sin fragmentos recuperados, utilizando el mismo conjunto de evaluación.

También se compararán fragmentos obtenidos con BM25 y SciBERT.

**Pendiente:**

- Implementar las métricas sobre fragmentos.
- Crear pruebas unitarias.
- Construir la referencia humana.
- Ejecutar la comparación entre recuperadores.
- Medir el efecto de Top-3 sobre F1 Macro.
- Reportar incertidumbre y limitaciones de evaluación.

**Estado: PARCIAL - MÉTRICAS DEFINIDAS, IMPLEMENTACIÓN FINAL PENDIENTE.**

## 6. Decisiones académicas pendientes

### D1. Tamaño del Test Gold humano

La propuesta V3 contempla validar humanamente el 15 % de un conjunto de 18.000 ejemplos, equivalente a 2.700 casos.

El borrador de avance propone alternativamente 450 casos, 50 por categoría.

La reducción no se considerará aprobada hasta obtener la conformidad académica correspondiente.

También deberá definirse si el requisito del 15 % aplica sobre el conjunto definitivo cuando su tamaño cambie.

**Estado: PENDIENTE DE CONFIRMACIÓN.**

### D2. Esquema de clasificación

Se debe confirmar si el objetivo principal será clasificar una única función por cita o admitir múltiples etiquetas.

El esquema debe coincidir entre la guía de anotación, los prompts, el entrenamiento y las métricas.

**Estado: PENDIENTE DE DEFINICIÓN FINAL.**

### D3. Organización de las anotaciones humanas

El equipo debe organizar la carga de trabajo, el entrenamiento de anotadores, las rondas de calibración y la adjudicación de desacuerdos.

La colaboración con otros grupos puede evaluarse siempre que exista una guía común y trazabilidad de las anotaciones.

Se mantiene como referencia de calibración el objetivo de α de Krippendorff ≥ 0,70 contemplado en el borrador.

**Estado: EN COORDINACIÓN CON EL EQUIPO.**

### D4. Evaluación complementaria del Top-3

Confirmar el procedimiento de curaduría de los 100 casos y la separación entre desarrollo y evaluación final.

**Estado: PROTOCOLO EN DEFINICIÓN.**

## 7. Avances técnicos realizados

### Integración de datos

Se desarrollaron los siguientes módulos:

- integrar_acl.py: integración individual.
- integrar_lote.py: integración de múltiples contextos.
- auditar_corpus.py: auditoría automática y generación de reportes.

Se verificó la integración de 66 contextos relacionados con un artículo citado y la disponibilidad de seis artículos adicionales.

Se ejecutaron doce pruebas automáticas de integración individual y por lotes con resultados aprobados.

Se incorporaron cuatro pruebas adicionales del auditor automático. Su resultado conjunto debe verificarse y registrarse explícitamente.

### Auditoría local

La herramienta de auditoría genera un reporte y registros detallados sin modificar los datos originales.

Los resultados se guardan localmente en:

proyecto_de_grado/artifacts/auditoria_acl_ocl/

La auditoría diferencia estados de procesamiento y evita confundir documentos no descargados con documentos inexistentes.

### Control de versiones

Los desarrollos se registraron mediante commits en la rama:

docs/correcciones-haydemar-v4

El MVP original se conserva sin modificaciones en esta etapa.

## 8. Próximas actividades prioritarias

### Prioridad 1 - Consolidar calidad y caracterización de datos

- Integrar el corpus objetivo.
- Registrar disponibilidad y causas de exclusión.
- Verificar particiones y duplicados.
- Generar el informe definitivo de calidad.

### Prioridad 2 - Verificar las cuotas por función de cita

- Ejecutar pre-etiquetado.
- Analizar distribución de nueve clases.
- Identificar clases escasas.
- Definir medidas de ampliación.

### Prioridad 3 - Consolidar protocolo de anotación

- Calibrar anotadores.
- Confirmar tamaño del Test Gold.
- Organizar doble anotación independiente.
- Registrar acuerdo y adjudicaciones.

### Prioridad 4 - Evaluación del Top-3 y sesgo por secciones

- Construir referencia humana de fragmentos.
- Implementar métricas.
- Ejecutar experimentos de ablación.
- Comparar F1 Macro con y sin evidencia recuperada.

### Prioridad 5 - Actualizar la propuesta e informe de avance

Consolidar los resultados, las decisiones aprobadas, las limitaciones y las evidencias reproducibles.

No deben presentarse como completadas las actividades cuyos experimentos todavía no se han ejecutado.

## 9. Condiciones de cierre

Una observación solamente se considerará resuelta cuando tenga:

- Respuesta metodológica clara.
- Evidencia técnica o documental verificable.
- Resultados reproducibles cuando corresponda.
- Pruebas automatizadas aprobadas para los cambios de código.
- Limitaciones y criterios de exclusión explícitos.
- Coherencia entre la propuesta, el código y los informes.
- Aprobación académica cuando se modifiquen compromisos importantes.

## 10. Estado general

| Observación | Estado |
|---|---|
| R4.1. Homologación de datasets | Parcial: estrategia y módulos iniciales disponibles |
| R4.2. Sesgo por secciones | Pendiente: experimentos no ejecutados |
| R5.1. Caracterización del dataset | Parcial: estadísticas originales disponibles |
| R5.2. Disponibilidad de pares | Parcial: cobertura muestral documentada |
| R5.3. Particiones temporales | Parcial: faltan controles definitivos |
| R5.4. Cuotas por función de cita | Pendiente: sin conteos reales por clase |
| R5.5. Contingencia por datos insuficientes | Parcial: estrategia documentada |
| R6.1. Ground truth Top-3 | Pendiente: referencia humana no construida |
| R6.2. Métricas de recuperación | Parcial: definidas, sin evaluación definitiva |

**Conclusión:**

El equipo cuenta con una estrategia de homologación justificada, herramientas iniciales de integración y auditoría, estadísticas del corpus original y un protocolo experimental en preparación.

Las actividades prioritarias restantes son completar el corpus integrado, demostrar las cuotas por función de cita, validar las anotaciones humanas y ejecutar la evaluación de recuperación y clasificación.

Esta matriz se mantendrá actualizada durante el desarrollo del proyecto de grado.