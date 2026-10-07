---
title: "Recomendación local de citas y clasificación de funciones en artículos científicos con modelos de lenguaje"
subtitle: "Informe de avance — borrador de secciones ajustadas según la retroalimentación de la propuesta"
---

**Integrantes:** Carlos Eduardo Duque Lugo, John Byron Arias Sanz, Gabriel Gustavo Pinzón Páez, José María Zambrana Arze, Carlos Alfredo Caicedo Bermúdez.

> **Nota para el equipo (borrar antes de entregar).** Este borrador reúne los ajustes a los criterios donde la propuesta V3 perdió puntos (metodología, datos y evaluación) y la corrección de los objetivos. Las marcas **[PENDIENTE: …]** indican lo que falta medir o confirmar. Todas las cifras se recalcularon el 6 de octubre de 2026 desde los datos de ACL-200 y desde los resultados del estudio de enlace de datos (`Proyecto_de_grado/spike_enlace_datos/`).

# 1. Descripción breve de la propuesta de solución

El proyecto aborda dos tareas conectadas sobre artículos científicos en inglés del área de *Computer Science*: la recuperación de la evidencia que respalda una cita dentro del artículo citado y la clasificación de la función retórica de esa cita en nueve categorías (*Background*, *Gap*, *Basis*, *Comparison*, *Application*, *Improvement / Modification*, *Evidence*, *Identification of the Originator* y *Further Reading*). Frente a la propuesta, este avance precisa la fuente de texto completo, el protocolo de anotación humana y la definición operativa de las métricas de recuperación.

**Objetivo general.** Desarrollar, en seis semanas, un sistema reproducible de PLN que integre la recuperación local de evidencia y la clasificación de nueve funciones de cita en artículos científicos en inglés, desplegado como demostrador interactivo.

**Objetivos específicos** (un verbo de acción por objetivo):

1. Construir, antes de finalizar la semana 2, un corpus integrado de ACL-200 y ACL OCL enlazado por el identificador de ACL Anthology, con secciones del documento y particiones sin fuga de información.
2. Implementar, antes de finalizar la semana 2, un recuperador denso basado en SciBERT que obtenga los tres fragmentos más cercanos del artículo citado, con Recall@K y MRR reportados frente a BM25.
3. Generar, antes de finalizar la semana 3, un conjunto de entrenamiento pre-etiquetado por jueces *open-weight*, con meta de 2.000 ejemplos por clase y la cantidad lograda documentada en las clases escasas.
4. Validar, antes de finalizar la semana 4, un conjunto de prueba humano (*Test Gold*) de 450 casos, 50 por clase, con doble anotación independiente y α de Krippendorff ≥ 0,70. **[DECISIÓN DEL EQUIPO: tamaño del Test Gold; la propuesta V3 planteaba el 15 % de 18.000.]**
5. Comparar, durante la semana 5, un encoder científico ajustado, un modelo *open-weight* de 1–8B y un modelo comercial sobre el mismo Test Gold, con F1 Macro como métrica principal.
6. Implementar, al finalizar la semana 6, un demostrador web que muestre los fragmentos recuperados con su sección, la función predicha con su confianza y las métricas operativas de latencia, costo y errores de formato.

# 2. Recolección y preparación de los datos

## 2.1 Fuentes y estrategia de homologación

El proyecto construye **un único conjunto de datos integrado**; no compara conjuntos de datos entre sí. ACL-200 aporta los contextos de cita y los pares artículo citante–artículo citado; ACL OCL (Rohatgi et al., 2023) aporta el texto completo de ambos artículos. Las dos fuentes comparten el identificador de ACL Anthology (por ejemplo, P15-2138), de modo que el enlace es directo y no requiere emparejamiento difuso. MultiCite e ILCiteR no se fusionan con el corpus: se usan solo como referencia externa para contrastar la taxonomía y los casos ambiguos.

Esta decisión corrige la propuesta, que planteaba el enlace con unarXive por identificador de arXiv. Un estudio sobre 500 contextos aleatorios de ACL-200 (semilla 42) mostró que esa ruta no es viable: solo el 0,2 % de los pares tendría ambos artículos en arXiv, porque el 99,5 % de los artículos citados es anterior a 2015 y fue publicado en ACL Anthology. Con ACL OCL, en cambio, el 82,2 % de los pares queda completo. **[PENDIENTE: confirmación del experto de dominio sobre el uso de ACL OCL.]**

El texto de ACL OCL proviene de PDF y fue extraído con GROBID, no de fuentes LaTeX como preveía la propuesta: para los artículos de ACL anteriores a 2015 no existe fuente LaTeX. Esto introduce ruido de extracción en algunos caracteres, que se trata en la limpieza (sección 2.4).

## 2.2 Descripción del conjunto de datos

ACL-200 contiene 63.768 contextos de cita y 19.776 artículos, de los cuales solo se dispone de título y resumen. De los contextos, 49.356 están en particiones supervisadas (30.390 de entrenamiento, 9.381 de validación y 9.585 de prueba). Cada contexto marca la cita objetivo con el símbolo TARGETCIT y las demás citas con OTHERCIT. Los contextos vienen recortados por una ventana fija y no por límites de oración: el 87,9 % empieza en minúscula, el 98,3 % no termina en punto y la longitud es muy homogénea (mediana de 63 palabras; p10 = 56; p90 = 70).

**¿Todos los contextos tienen su par?** No. La Tabla 1 muestra el embudo medido sobre la muestra de 500 contextos. Los pares incompletos se descartan y la tasa de resolución se reporta como parte del conjunto de datos.

*Tabla 1. Embudo de resolución de pares con texto completo (muestra de 500 contextos de ACL-200).*

| Etapa | Casos | % |
|---|---:|---:|
| Contextos en la muestra | 500 | 100,0 |
| Artículo citado presente en ACL OCL | 499 | 99,8 |
| Artículo citado con texto usable para fragmentar (≥ 500 palabras y ≥ 3 secciones) | 490 | 98,0 |
| Contexto ubicado en el texto del artículo citante (reconstruible a oración completa) | 421 | 84,2 |
| **Par completo (citado usable y contexto reconstruible)** | **411** | **82,2** |

Extrapolado a los 63.768 contextos, el 82,2 % equivale a unos 52.400 pares con texto completo (intervalo de ±3,4 puntos porcentuales por el tamaño de la muestra). Los artículos citados con texto en ACL OCL tienen una mediana de 4.258 palabras, 13 secciones y 34 fragmentos según la regla de la propuesta (dos párrafos o 300 palabras); el 96 % de los párrafos tiene su sección asignada, lo que permite registrar la sección de cada fragmento recuperado.

## 2.3 Partición de los datos

**¿Se tiene en cuenta cuándo se escribió el artículo?** Sí. Las particiones originales de ACL-200 ya son temporales por año del artículo citante: entrenamiento con artículos de 2009 a 2013, validación con los de 2014 y prueba con los de 2015. El proyecto conserva esta partición por dos razones: refleja el uso real (recomendar para artículos nuevos a partir de literatura anterior) y evita que el modelo vea en entrenamiento el estilo de los artículos de prueba.

Ningún artículo citante aparece en dos particiones. Sí hay artículos citados compartidos (1.338 entre entrenamiento y prueba), lo que es esperable porque los trabajos influyentes se citan cada año. Para la clasificación con fragmentos del artículo citado se reportará el desempeño por separado en los casos de prueba cuyo artículo citado también aparece en entrenamiento, para medir si el modelo memoriza artículos.

## 2.4 Preparación

- Reconstrucción de cada contexto hasta la oración completa, localizando el fragmento truncado en el texto del artículo citante en ACL OCL.
- Fragmentación del artículo citado en bloques de máximo dos párrafos o 300 palabras, con partición por oración cuando un párrafo supera ese límite (175 de 398 artículos citados de la muestra tienen al menos un párrafo así).
- Limpieza del ruido de extracción del PDF y de los restos de tablas y figuras. Los contextos que vienen de tablas se marcan como «No válido» y se excluyen.
- La cita objetivo se muestra marcada en todas las hojas de anotación. En el piloto esa marca se había eliminado, de modo que los anotadores no podían saber cuál de las citas del fragmento debían clasificar.

## 2.5 Conjunto de entrenamiento y conjunto de prueba humano

El proyecto separa dos conjuntos con propósitos distintos:

- **Conjunto de entrenamiento pre-etiquetado.** Lo etiquetan al menos dos jueces *open-weight* y se audita una muestra con anotación humana para estimar su nivel de ruido. La meta es de 2.000 ejemplos por clase.
- **Test Gold humano.** Lo anotan únicamente personas, con doble anotación independiente y sin ver las sugerencias de los modelos. Es el único conjunto que se usa para evaluar y no se re-muestrea después de conocer los resultados.

**¿Alcanzan los datos para la meta de muestra?** En volumen sí: unos 52.400 pares completos frente a una meta de 18.000. El riesgo está en las clases escasas (*Further Reading* e *Identification of the Originator*), cuya frecuencia natural se conocerá con el pre-etiquetado. El plan si no se alcanza la meta es escalonado:

1. Ampliar con contextos adicionales extraídos de la bibliografía enlazada de los artículos de ACL OCL fuera de ACL-200.
2. Compartir etiquetas con los otros grupos del Tema 1, como propuso el experto, si usan la misma taxonomía y guía.
3. Conservar la cantidad disponible, aplicar ponderación de clases en el entrenamiento y reportar el volumen alcanzado por clase.

# 3. Descripción del proceso de construcción de la solución

## 3.1 Protocolo de anotación humana

La anotación sigue cuatro pasos:

1. Entrenamiento con una guía de las nueve funciones y 41 casos de práctica con explicación.
2. Ronda de calibración: todos los anotadores etiquetan por separado los mismos 36 casos nuevos. Se calcula el α de Krippendorff y se discuten los desacuerdos; la ronda se repite con casos nuevos hasta alcanzar α ≥ 0,70.
3. Anotación del Test Gold por parejas rotativas, sin acceso a las sugerencias de los modelos.
4. Resolución de desacuerdos por una tercera persona que no anotó el caso.

Los casos de práctica y de calibración quedan excluidos del Test Gold. Se usa el α de Krippendorff (Krippendorff, 2004) porque admite más de dos anotadores y casos sin todas las respuestas; el κ de Cohen se reporta para cada pareja.

## 3.2 Configuraciones de entrada y control del sesgo de la sección

Incluir la sección del texto puede introducir un sesgo: la sección donde está la cita se asocia con su función (por ejemplo, *Related Work* con *Background*), y en la literatura incluso se usa como señal auxiliar (Cohan et al., 2019). El riesgo es que el clasificador aprenda ese atajo en lugar de interpretar el contexto. Para medirlo se comparan cinco configuraciones de entrada (Tabla 2).

*Tabla 2. Configuraciones de entrada del clasificador.*

| Configuración | Entrada |
|---|---|
| C0 | Solo el contexto de cita |
| C1 | Contexto, título y resumen del artículo citado |
| C2 | Contexto y los tres fragmentos recuperados |
| C3 | C2 más la sección de cada fragmento |
| C3-barajada | C3 con las secciones permutadas al azar entre ejemplos |

Si C3 supera a C2 y C3-barajada no, la sección aporta información real. Si ambas mejoran por igual, la mejora proviene de un atajo y no se atribuye a la sección. Además se reportan la asociación entre sección y etiqueta en el Test Gold (V de Cramér) y los resultados por clase.

## 3.3 Modelos

- **Recuperación:** embeddings de SciBERT con similitud coseno, frente a BM25 como línea base dispersa y a dos líneas base triviales (tres fragmentos al azar y los tres primeros fragmentos del artículo).
- **Clasificación:** clase mayoritaria y TF-IDF con regresión logística como líneas base; un encoder científico ajustado (SciBERT o SPECTER); un modelo *open-weight* de 1–8B y un modelo comercial en *zero-shot* y *few-shot*.

**[PENDIENTE: describir el entrenamiento de la primera versión (TF-IDF con regresión logística sobre el pre-etiquetado) y del recuperador.]**

## 3.4 Definición de las métricas de recuperación

Sea $Q$ el conjunto de contextos evaluados y, para cada contexto $q$, sea $G(q)$ el conjunto de fragmentos del artículo citado que respaldan la afirmación (la referencia). Entonces:

$$\mathrm{Recall}@K = \frac{1}{|Q|}\sum_{q \in Q} \mathbf{1}\left[\mathrm{Top}_K(q) \cap G(q) \neq \emptyset\right]$$

$$\mathrm{MRR} = \frac{1}{|Q|}\sum_{q \in Q} \frac{1}{r_q}$$

donde $\mathbf{1}[\cdot]$ vale 1 si la condición se cumple y 0 si no, $\mathrm{Top}_K(q)$ son los $K$ fragmentos mejor puntuados y $r_q$ es la posición del primer fragmento relevante en la lista ordenada (el término $1/r_q$ vale 0 si ninguno aparece).

**Referencia (*ground truth*).** ACL-200 no indica qué fragmento del artículo citado respalda cada cita, así que la referencia se construye. Se toman 200 contextos del conjunto de prueba; para cada uno se juntan los diez mejores fragmentos de BM25 y de SciBERT, y dos anotadores marcan cuáles respaldan la afirmación. Juntar los candidatos de ambos sistemas evita que la referencia favorezca a uno de ellos. Los desacuerdos los resuelve un tercero y se reporta el acuerdo. **[PENDIENTE: confirmación del experto sobre esta referencia.]** Las diferencias entre sistemas se reportan con intervalos de confianza por *bootstrap*.

# 4. Resultados obtenidos

- **Enlace de datos:** 82,2 % de pares completos con ACL OCL frente a 0,2 % con unarXive (Tabla 1).
- **Partición temporal:** verificada (2009–2013 / 2014 / 2015), sin artículos citantes compartidos.
- **Piloto de anotación:** 20 casos con dos anotadores: 60 % de acuerdo y κ de Cohen = 0,48, por debajo de la meta de 0,70. La primera anotación fue asistida con explicaciones y no fue ciega, y los 20 casos solo cubrieron 5 de las 9 clases.
- **[PENDIENTE: α de la ronda de calibración y tiempo mediano por caso.]**
- **[PENDIENTE: primeras cifras de Recall@K y MRR, y F1 Macro de la línea base de clasificación.]**

# 5. Análisis de los resultados obtenidos

**Calidad de la anotación.** El κ de 0,48 del piloto tiene tres causas identificadas:

- La marca de la cita objetivo estaba ausente en las hojas.
- No había un orden de decisión para los casos ambiguos.
- Faltaban ejemplos de cuatro clases.

Las tres se corrigieron con la guía ampliada, los casos de práctica y la ronda de calibración. Si la calibración no alcanza 0,70, se ajustará la guía en los pares de clases con más confusión y se repetirá la ronda antes de anotar el Test Gold.

**Riesgos que se mantienen:**

- **Memorización.** Los artículos de ACL anteriores a 2015 son públicos y probablemente forman parte del preentrenamiento de los modelos de lenguaje, lo que puede inflar su desempeño en *zero-shot*. Se reporta como limitación.
- **Ruido de extracción.** El texto de los PDF degrada la reconstrucción de algunos contextos (el 15,8 % no se ubicó en el artículo citante). La tasa de 84,2 % es un piso, porque usar coincidencia difusa la subiría.
- **Licencias.** Los artículos de ACL Anthology anteriores a 2016 tienen licencia CC BY-NC-SA 3.0, lo que limita la redistribución del conjunto de datos.

**Próximos pasos:**

1. Correr la ronda de calibración con los cinco integrantes.
2. Entrenar la línea base de clasificación sobre el pre-etiquetado.
3. Construir el índice de recuperación sobre los artículos citados.
4. Anotar la referencia de recuperación.

# Referencias (adiciones a las de la propuesta)

- Cohan, A., Ammar, W., van Zuylen, M., & Cady, F. (2019). Structural Scaffolds for Citation Intent Classification in Scientific Publications. *Proceedings of NAACL-HLT 2019*.
- Krippendorff, K. (2004). *Content Analysis: An Introduction to Its Methodology* (2.ª ed.). Sage.
- Rohatgi, S., Qin, Y., Aw, B., Unnithan, N., & Kan, M.-Y. (2023). The ACL OCL Corpus: Advancing Open Science in Computational Linguistics. *Proceedings of EMNLP 2023*.

**[PENDIENTE: verificar páginas y DOI de estas tres referencias antes de entregar.]**
