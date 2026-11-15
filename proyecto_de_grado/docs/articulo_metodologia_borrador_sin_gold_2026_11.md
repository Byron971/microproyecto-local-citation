# Artículo científico del proyecto de grado — borrador de metodología sin Test Gold

**Estado:** borrador técnico, no artículo final ni manuscrito listo para evaluación.
**Alcance:** secciones verificables con código y manifiestos al 15-nov-2026.
**Control editorial:** issue #112; máximo 12 páginas en versión final, resumen
200–300 palabras, IEEE numérico y autores/afiliaciones por verificar.
**Prohibido** sustituir resultados Gold faltantes por métricas Haiku o simuladas.

## Título de trabajo

Recomendación local de fragmentos y clasificación de la función de cita en
artículos científicos mediante recuperación SciBERT y clasificadores
SciBERT/SPECTER

*Autores, afiliaciones y correos institucionales: pendiente de aprobación
de todos los coautores; no inferirlos a partir de GitHub.*

## Resumen

**POR COMPLETAR PARA EL ARTÍCULO FINAL.** El resumen debe tener entre 200 y
300 palabras y presentar problema, solución, metodología, principales
resultados verificados y conclusiones. No se propone una versión final porque
faltan métricas del Test Gold y acuerdos humanos. La redacción final se
realizará después de completar las tablas de resultados.

**Palabras clave propuestas:** recomendación local de citas; recuperación
semántica; SciBERT; función de cita; reproducibilidad.

## I. Introducción [borrador técnico]

La recomendación local de citas requiere vincular el contexto donde un
autor introduce una referencia con evidencia pertinente de trabajos
anteriores. Recomendar únicamente un artículo no determina qué fragmento
específico lo sustenta ni qué función retórica cumple dentro del texto.
Por eso el proyecto separa dos tareas conectadas: la recuperación de hasta
tres fragmentos del **mismo artículo citado** y la clasificación de su
función en nueve categorías.

La solución distingue entre el sistema heredado del microproyecto, que
recomienda artículos mediante TF-IDF y un reordenador supervisado, y el
estudio de grado, orientado a fragmentos del documento citado y funciones
retóricas. Los resultados del primero no se presentan como resultados del
segundo.

### Objetivo general (un único verbo principal)

Desarrollar un sistema reproducible de recuperación local de fragmentos
y clasificación de la función de cita en artículos científicos.

### Objetivos específicos (un verbo principal por objetivo)

1. **Integrar** contextos ACL-200 con texto completo de artículos citados
   procedente de ACL OCL, bajo particiones y controles de integridad.
2. **Implementar** la recuperación Top-3 de fragmentos del artículo citado
   mediante SciBERT y un baseline léxico BM25.
3. **Comparar** clasificadores SciBERT y SPECTER con entradas A y B,
   manteniendo separada la procedencia de sus etiquetas.
4. **Evaluar** desempeño, reproducibilidad y costos operativos del sistema
   con conjuntos y protocolos diferenciados.

Esta redacción debe cotejarse con los objetivos ya aprobados de la propuesta;
no representa una modificación académica aprobada.

## II. Estado del arte — contenido pendiente de revisión bibliográfica

El estado del arte debe comparar de manera crítica (a) recomendación local
de citas a nivel de artículo, (b) recuperación de evidencia por fragmentos,
(c) representaciones científicas con SciBERT y SPECTER, (d) clasificación
de funciones retóricas y (e) evaluación bajo pseudoetiquetas y Gold humano.
No se incorporan referencias bibliográficas inventadas. Completar las
citas IEEE a partir del gestor bibliográfico y los artículos efectivamente
consultados.

## III. Materiales y métodos [basado en implementaciones versionadas]

### A. Fuentes y unidad de análisis

ACL-200 suministra contextos, identificadores de artículos citantes y
citados, y particiones originales. ACL OCL suministra el texto completo del
citado, cuando existe correspondencia por ID; esta correspondencia es
esencial para impedir recuperar fragmentos de otros artículos.
La partición histórica del corpus original asigna train a citantes de
2009–2013 (30.390 contextos), validación a 2014 (9.381) y test a 2015
(9.585). Estas cantidades caracterizan la fuente, **no** son tamaños
de las intersecciones completas usadas para A4.

En el estudio de enlace sobre 500 contextos se reportó 82,2 % ± 3,4 puntos
porcentuales con texto completo por ACL OCL. Esta tasa es descriptiva de
aquella muestra, no una garantía para cada subconjunto. Las consultas y
documentos se registran con identificadores y hashes de procedencia.
El Test Gold humano debe permanecer fuera de entrenamiento, desarrollo y
elección de hiperparámetros.

### B. Fragmentación del artículo citado

El fragmentador V1 agrupa hasta dos párrafos contiguos de la misma sección,
sin superar 300 palabras por chunk. Rechaza artículos que contienen párrafos
superiores al límite en vez de truncarlos. V2 es una alternativa opt-in que
conserva V1 para párrafos breves y divide párrafos largos en segmentos
de hasta 300 palabras y 5.000 caracteres, conservando índice de párrafo
y sección del origen. Ambas estrategias preservan identificadores
estables y deben auditarse sobre exactamente la misma caché ACL OCL.

La comparación V1/V2 es **técnica** (cobertura, cantidad de chunks,
preservación de texto), no una medición de relevancia ni una justificación
para afirmar mejora de Recall@3 sin anotaciones.

### C. Recuperación Top-3

El baseline léxico BM25 calcula la afinidad entre el contexto de cita y
los fragmentos del artículo citado. El método denso SciBERT emplea
`allenai/scibert_scivocab_uncased`, revisión fija
`24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`.
El codificador construye embeddings mediante mean pooling con máscara,
ventanas de hasta 512 tokens y agregación ponderada por tokens; posteriormente
ordena los chunks por similitud coseno y conserva un máximo de tres.

Este SciBERT es un **encoder base**, no un recuperador optimizado con
etiquetas humanas de relevancia. El ensayo A1 offline registró
603 contextos de TRAIN, 89 artículos citados y 2.574 chunks únicos.
La integridad del ranking exige que los `chunk_id` pertenezcan al
`cited_id` original, que secciones e índices concuerden y que no existan
duplicados. El solape SciBERT/BM25 permite caracterizar diferencias entre
métodos, pero no equivale a precisión ni Recall.

### D. Clasificación de nueve funciones

El estudio A4 utiliza nueve categorías en orden fijo:
Background, Gap, Basis, Comparison, Application,
Improvement / Modification, Evidence,
Identification of the Originator y Further Reading.
Las abstenciones Ambiguo/No evaluable no conforman una décima clase.

Se definen dos entradas distintas:
- **A:** contexto con marcador TARGETCIT, título y abstract del citado.
- **B:** contexto, tres fragmentos Top-3 y perfiles de sección retórica.

Las combinaciones científicas mínimas son SciBERT-A, SciBERT-B,
SPECTER-A y SPECTER-B; la fuente de etiqueta (Haiku o Jurado)
es un factor distinto, nunca el significado de A/B.
El clasificador usa el vector `[CLS]`, dropout 0,1 y una cabeza
lineal de nueve salidas. En el experimento versionado se fijó la longitud
máxima de 512 tokens, contexto de hasta 192, título de hasta 48 en A,
y presupuesto water-filling para tres chunks en B. La selección de
checkpoint depende de F1 macro en validación.

La matriz provisional dispone de las semillas 42, 1234 y 2026 con
etiquetas automáticas Haiku. La intersección comparable A/B reúne
1.241 casos train, 213 de validación y 732 de evaluación 2015.
La cobertura de entrada B es próxima a 54 % por disponibilidad
de fragmentos adecuados, por lo que el conjunto filtrado puede introducir
sesgo de selección. Las métricas frente a Haiku se informan como
**provisionales, no como rendimiento frente a humanos**.

### E. Diseño de evaluación

Para clasificación deberán reportarse F1 macro/micro, precisión,
recall por clase, matriz 9×9, soporte, abstenciones y variación por
semilla sobre un Test Gold congelado y adjudicado. Los contrastes A/B
se realizarán por `example_id` común, conservando encoder y fuente
de etiquetas. Para Top-3 solo pueden calcularse Hit@3, Recall@3 y
MRR@3 tras definir relevancia humana de chunks; antes solo se informan
integridad, solape, distribución de secciones y costos operativos.

Los controles anti-leakage consideran documento citante y par
citante–citado, además del `context_id`. No se debe optimizar
prompts, umbrales o checkpoints con el conjunto final de test.

### F. Arquitectura y reproducibilidad

El repositorio separa el microproyecto (recomendación de artículos)
del código científico en `packages/recuperacion-densa` y
`packages/clasificacion-funcion`. FastAPI expone los baselines y
React ofrece las vistas de consulta. Los adaptadores científicos
opcionales requieren modelos con revisión fija, manifiestos SHA
y checkpoints verificables. El servicio de inferencia debe
**fallar explícitamente** cuando falten pesos o dependencias, sin
sustituir SciBERT por BM25 y sin inventar predicciones.

Las evidencias incluyen Git, DVC, especificaciones de entrada,
manifiestos de corpus y modelos, tests unitarios, pruebas HTTP,
Docker y configuración Terraform. La disponibilidad de infraestructura
no equivale a validación científica.

## IV. Resultados [TABLAS RESERVADAS — NO COMPLETAR SIN EVIDENCIA]

**Tabla 1. Caracterización definitiva del corpus y cobertura humana.**
Pendiente: N aceptado, distribución por nueve clases, abstenciones,
porcentaje humano real, reglas de exclusión y hashes del conjunto congelado.

**Tabla 2. Recuperación Top-3.** Pendiente: relevancia humana,
Hit@3, Recall@3, MRR@3 e intervalos apropiados. Las cifras técnicas
offline A1 se pueden describir sin llamarlas calidad de recuperación.

**Tabla 3. Comparación de clasificadores.** Pendiente: métricas del
mismo Test Gold humano para SciBERT-A/B y SPECTER-A/B,
matrices por clase e intervalos. Los resultados Haiku actuales
solo pueden aparecer en una tabla claramente titulada
*evaluación provisional frente a pseudoetiquetas*.

**Tabla 4. Desempeño de despliegue.** Pendiente:
hardware/software del servidor definitivo, medianas y P95
con igual protocolo, RAM pico, costo por consulta y estado de
inferencia SciBERT/A4 en lugar de TF-IDF/BM25 únicamente.

## V. Discusión [borrador verificable]

La evidencia técnica offline muestra que SciBERT y BM25 seleccionan
fragmentos diferentes; sin juicios humanos no puede afirmarse cuál
recupera evidencia más útil. Además, la alta similitud coseno de
SciBERT puede reflejar anisotropía y hubness en embeddings no ajustados
para recuperación. Es necesario separar capacidad operativa,
coincidencia entre métodos y relevancia científica.

La entrada B altera no solo la información suministrada, sino también
la cobertura muestral y el presupuesto de tokens. Por ello los
contrastes con A deben restringirse a la misma intersección de contextos,
y la interpretación debe reconocer el truncamiento de chunks y la
naturaleza heurística de las secciones.

Los resultados provisionales de clasificación reflejan acuerdo
con etiquetas automáticas. No autorizan conclusiones definitivas
sobre la verdadera función retórica ni cumplimiento de cuotas humanas.
La comparación SciBERT/SPECTER utiliza hiperparámetros compartidos;
no prueba que uno sea intrínsecamente superior para toda configuración.

## VI. Conclusiones y trabajo futuro [RESERVADO]

No redactar conclusiones cuantitativas definitivas hasta disponer
de validación Gold y de la ejecución de inferencia científica
en el entorno final. Completar respuestas a cada objetivo
con evidencia y limitaciones explícitas.

## Declaraciones y referencias

**Uso de IA:** registrar herramientas empleadas para apoyo editorial,
programación y análisis; la responsabilidad de validación,
interpretación, autoría y resultados corresponde a los investigadores.

**Ética y datos:** conservar licencias y permisos de textos ACL,
excluir identificadores y etiquetas de evaluación privada del
demostrador público, y publicar únicamente artefactos autorizados.

**Bibliografía IEEE:** pendiente de importar y verificar desde la
propuesta y el estado del arte aprobados. No se crean referencias
sin fuente comprobada.

## Correspondencia con evidencia ya versionada

| Componente | Evidencia de ingeniería | Límite |
|---|---|---|
| Enlace ACL-200/ACL OCL | `proyecto_de_grado/docs/spike_enlace_datos/` | Tasa estimada en muestra |
| SciBERT Top-3 | `proyecto_de_grado/docs/recuperacion_densa_scibert_a1.md` | Sin relevancia Gold |
| Clasificación 2×2 | `proyecto_de_grado/docs/clasificacion_funcion_a4.md` | Etiquetas Haiku |
| Protocolo A1–A7 | `docs/protocolo_experimental_grado_2026_11.md` | Pendiente cierre Gold |
| Infrastructura | `terraform/`, `.github/workflows/` | No asumir despliegue científico |
| Artículo final | Issue GitHub #112 | Máximo 12 páginas, IEEE |

**Control editorial posterior:** contrastar los objetivos con propuesta V3
aprobada, incorporar bibliografía verificada, completar resultados solo
después de auditoría, redactar resumen final de 200–300 palabras y
maquetar según issue #112 (carta, 2,5 cm, Times New Roman 10,
interlineado sencillo, tablas arriba/figuras abajo, máximo 12 páginas).
