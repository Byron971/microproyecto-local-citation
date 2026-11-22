

<!-- Start of picture text -->
e<br>i Proyecto:<br>e Desarrollo de soluciones<br><!-- End of picture text -->

|**Título**|**Recomendación local de citas y clasificación de su**<br>**función en artículos académicos (**_Improving local Citation_<br>_recommendation dataset incorporating citation function in_<br>_academic papers)_|
|---|---|
|Organización/Grupo de<br>investigación|Grupo de investigación FLAG<sup>1</sup>– TICsW. Departamento de<br>Ingeniería de Sistemas y Computación. Universidad de los Andes.|
||PhD. Juan Camilo Sanguino. Machine Learning Engineer and AI|
|Experto|Researcher. Departamento de Ingeniería de Sistemas y<br>Computación Uniandes.|



# 1. Descripción

El acelerado crecimiento de la literatura académica en formato digital ha intensificado la necesidad de herramientas automáticas capaces de asistir en la navegación, comprensión y contextualización de la evidencia científica. En el ámbito del Procesamiento del Lenguaje Natural (PLN) aplicado a textos académicos, la recomendación local de citas ( _Local Citation Recommendation_ ) y la caracterización discursiva de las referencias _(Citation Function Classification_ ) son tareas fundamentales para optimizar procesos como la revisión automática de literatura, el análisis de impacto bibliométrico y la verificación de afirmaciones científicas.

El idioma inglés constituye la lengua predominantemente utilizada en la producción y divulgación científica global. A pesar de la abundancia de corpus académicos en este idioma, la identificación precisa de la función retórica que cumple una cita dentro de un documento (por ejemplo, fundamentar un método, comparar un resultado o señalar una limitación) presenta retos metodológicos complejos. Los contextos de cita _(citation context_ ) suelen ser breves o ambiguos, y

1 https://flaglab.github.io/index.html

la información semántica relevante dentro del documento citado (cited paper) suele encontrarse distribuida en párrafos específicos y secciones retóricas particulares.

Este proyecto aborda la comprensión automática de citas académicas en inglés a través de dos tareas interconectadas. La primera tarea consiste en la recuperación y alineación de fragmentos textuales (chunks), cuyo objetivo es identificar, para un contexto de cita, los fragmentos más similares semánticamente dentro del artículo citado y determinar la sección discursiva a la que pertenecen. La segunda tarea es la clasificación de la función de cita ( _citation function classification_ ), orientada a categorizar el propósito específico del uso de la fuente bibliográfica en el texto.



<!-- Start of picture text -->
Citation Mark<br>Content Content<br>Lorem ipsum door st Lorem ipsum dolor sit amet,<br>amet, consectetur Citation context consectetur adipiscing elt,<br>adipisieng et, sed do elusmod tempor<br>[CITATION_REF] sed do incididunt ut labore et dolore<br>euusmod tempor inci magna aliqua<br>Utlabore et dolore magna<br>aiiqua<br>References: References:<br>ICITATION_REF] ipsum. ICITATION_REF_2}lorem ipsum<br>Citing paper Cited paper<br><!-- End of picture text -->

Figura ilustrativa de los conceptos relacionados

Al integrar la recuperación semántica de fragmentos con la clasificación de funciones de cita, este estudio evalúa cómo la información contextual y la aproximación a nivel de párrafo mejoran la capacidad de predicción de modelos supervisados y arquitecturas basadas en modelos de lenguaje.

# 2. Objetivos principales del proyecto

Extraer y procesar un corpus de documentos científicos en inglés a partir del repositorio arXiv (formatos PDF/LaTeX). Especialmente del área de computación.

- Implementar una estrategia de recuperación densa basada en SciBERT para extraer el Top 3 de párrafos más similares dentro del artículo citado para cada contexto de cita.

- Construir y curar, apoyándose en un pre-etiquetado automático con modelos de pesos abiertos, un dataset balanceado con al menos 2.000 ejemplos por cada etiqueta de función de cita, definiendo una guía de anotación para medir el acuerdo interanotador sobre un subconjunto validado por humanos (15%).

- Ajustar (fine-tuning) clasificadores supervisados basados en encoders especializados para literatura científica en inglés (como SciBERT).

- Evaluar modelos de lenguaje de gran escala comerciales vía API (GPT-4o/5, Gemini) en modo inferencia, comparando diversas estrategias de _prompting_ ( _zero-shot_ , _few-shot_ , _prompts_ específicos vs. genéricos).

- Desarrollar un demostrador interactivo que integre el flujo completo de recuperación de fragmentos y clasificación de funciones de cita sobre entradas textuales en tiempo real.

# 2. Esquema de Clasificación de Funciones de Cita ( _Citation Functions_ )

A continuación se detallan las 9 categorías de funciones de cita adaptadas del marco conceptual de referencia, junto con sus definiciones operativas y los criterios de anotación que deben regir el proceso de construcción del dataset y entrenamiento de los modelos:

|Citation<br>Function|Definition|Criteria|
|---|---|---|
|Background|Citations<br>used<br>to<br>provide<br>context, summarize the general<br>background of a research topic,<br>or trace the history of a field or<br>idea. These citations lay the<br>foundation for understanding<br>the focal study.|Reviews existing literature to ensure<br>comprehensiveness.<br>Cites review papers or relevant previous<br>studies to depict the current state of the<br>field.<br>Highlights<br>important<br>or<br>prevailing<br>findings in the field.<br>Traces the historical development or<br>presents key ideas in the subject area.|
|Gap|Citations that help identify<br>research gaps or unexplored<br>areas, justifying the author’s<br>choice of research topic.|Highlights what has or has not been done<br>in the research area.<br>Identifies gaps in knowledge or areas for<br>further study.<br>Justifies the relevance and importance of<br>the current research by contrasting it<br>with existing work.|



|Citation<br>Function|Definition|Criteria|
|---|---|---|
|Basis|Citations<br>that<br>provide<br>a<br>foundation for the current<br>research. This can operate at a<br>macro level (broad influence)<br>or a micro level (specific key<br>contributions).|Serves as the intellectual starting point<br>for the focal research.<br>The cited work significantly shapes the<br>research idea or hypothesis.<br>The<br>focal<br>research<br>builds<br>upon,<br>continues, or expands on the cited work.|
|Comparison|Citations used to compare the<br>current work with cited studies<br>or<br>to<br>draw<br>comparisons<br>between cited studies.|Highlights similarities or differences<br>between the current research and cited<br>works.<br>Compares<br>methodologies,<br>findings,<br>algorithms, data, or theoretical concepts.<br>May point out advantages of the current<br>study over previous ones or establish<br>links among different cited works.|
|Application|Citations that directly employ a<br>method, technique, or tool<br>from the cited work without<br>modification.|Utilizes existing methods, algorithms,<br>instruments, or data for the current<br>research.<br>Employs the cited work as a practical tool<br>(e.g., equations, analysis methods) for<br>calculation or experimentation.<br>Applies the cited method without<br>modification.|
|Improvement /<br>Modification|<br>Citations in which methods or<br>tools from the cited work are<br>adapted,<br>expanded,<br>or<br>modified<br>for<br>the<br>current<br>research.|The cited method is adapted, improved,<br>or extended to fit new experimental<br>conditions or research objectives.|



|Citation<br>Function|Definition|Criteria|
|---|---|---|
|||Uses the cited work as a foundation but<br>modifies it to enhance precision or<br>scope.|
|Evidence|Citations<br>used<br>to<br>support<br>claims, hypotheses, or findings<br>in the current research.|Supports arguments, hypotheses, or<br>factual statements.<br>Justifies research design, methodologies,<br>or experimental procedures.<br>Substantiates<br>or<br>explains<br>findings,<br>especially in the discussion section.<br>Provides evidence to mitigate limitations<br>or support further research suggestions.|
|Identification of<br>the Originator|Citations used to acknowledge<br>the original source of an idea,<br>concept, method, or theory.|Identifies the original publication where<br>a key idea or method was first<br>introduced.<br>Acknowledges pioneers in the field.<br>Gives credit to the priority of a cited<br>work,<br>demonstrating<br>intellectual<br>indebtedness.|
|Further Reading|Citations that direct readers to<br>additional or supplementary<br>literature for more detailed<br>information or context.|Alerts readers to new, different, or<br>relevant sources of information.<br>Provides more complete details on data,<br>methods, or background not fully<br>covered in the current work.<br>Often used to refer readers to external<br>sources for deeper insights.|



# 3. Conjunto de Datos (Dataset)

## **Procesamiento de Chunks y Búsqueda del Top 3**

Para cada _citation context_ identificado en el texto citante:

- Se segmentará el documento citado ( _cited paper_ ) en unidades textuales o _chunks_ que no superen los 2 párrafos o las 300 palabras, respetando el límite natural de las oraciones. Y la finalización de sesiones dentro el documento

- Se implementará una aproximación densa para seleccionar los 3 párrafos más cercanos semánticamente: representación de texto y cálculo de similitud entre el _citation context_ y los _chunks_ mediante embeddings generados por _SciBERT_ .

- Se registrará la posición y la sección retórica de origen dentro del documento citado para cada uno de los _chunks_ recuperados.

## **Escala y Balance del Dataset**

- **Volumen:** El dataset final para la clasificación de funciones de cita debe contar con al menos 2.000 ejemplos por cada categoría/etiqueta considerada dentro del esquema de función de citas definido (9 categorías en total).

- **Validación Humana (Test Set):** Al menos el 15% del dataset total será validado manualmente por los integrantes del grupo de trabajo siguiendo una guía de anotación previa.

- Las muestras validadas por humanos se reservarán exclusivamente como conjunto de evaluación final (test set), garantizando que el entrenamiento y la validación interna se realicen sobre los datos restantes.

## **Acuerdo Interanotador y Garantía de No-Solapamiento**

- **Métricas de Acuerdo:** Para evaluar la consistencia del proceso de anotación, las muestras reservadas para el test set serán anotadas de forma independiente por al menos dos evaluadores, reportando métricas estándar como _Cohen’s Kappa, Fleiss’ Kappa o Krippendorff’s Alpha_ .

- **Aislamiento por Documento (** **_No-Leakage Guarantee_ ):** Las particiones de entrenamiento, validación y prueba deberán respetar estrictamente el criterio de no solapamiento a nivel de documento. Si un par de artículos (citante – citado) es asignado al conjunto de entrenamiento, ningún contexto de cita ni fragmento asociado a ese par podrá formar parte de los conjuntos de prueba o validación.

# 4. Actividades del Proyecto

**A1. Extracción de PDFs, Segmentación y Búsqueda de Chunks**

Procesar el conjunto de datos de arXiv para extraer el texto plano de los artículos en inglés. Puede utilizar dataset utilizados en estuidos previos basados también en arxiv. Identificar los marcadores y contextos de cita ( _citation contexts_ ) y segmentar los documentos citados en _chunks_ (máximo 300 palabras). Utilizar _SciBERT_ para asociar a cada contexto de cita los 3 párrafos con mayor similitud semántica, identificando la sección de origen dentro del _cited paper_ .

## **A2. Pre-etiquetado Asistido por Modelos Comerciales (Sistema de Jueces)**

Antes de estructurar el dataset balanceado (A3), se utilizarán modelos abiertos de lenguaje de gran escala (ej. Llama 3 8B, Qwen 2.5 7B, Mistral) como una primera instancia de clasificación sobre el conjunto de contextos de cita extraído en A1. Mediante _prompts_ básicos, se le pedirá a estos modelos que asignen a cada contexto de cita la(s) categoría(s) de función de cita a la(s) que pertenece. Se implementará un esquema de _jueces_ (más de un modelo evaluando el mismo ejemplo, contrastando sus respuestas) para obtener una pre-etiqueta de mayor confianza sobre los candidatos. Este pre-etiquetado automático permitirá identificar de forma más rápida y efectiva los candidatos necesarios para completar el mínimo de 2.000 ejemplos por categoría solicitado en A3, reduciendo el esfuerzo de búsqueda y curaduría manual. Sobre el conjunto pre-etiquetado se seleccionará aleatoriamente el 15% de las muestras (Por categoría) que posteriormente se someterá a la validación humana descrita en A3, en lugar de partir de una selección completamente manual. Este pre-etiquetado es exploratorio y no reemplaza la evaluación formal de _prompting_ que se realizará más adelante en A5 y A6 sobre el conjunto de prueba ya validado por humanos.

## **A3. Construcción del Dataset y Validación Humana**

A partir de los candidatos pre-etiquetados en A2, estructurar el dataset balanceado con 2.000 instancias por clase. Sobre el 15% de las muestras seleccionadas aleatoriamente en A2, realizar la validación manual por parte del equipo, confirmando o corrigiendo la etiqueta sugerida por los modelos comerciales. Construir la guía de anotación, realizar la revisión independiente y reportar el coeficiente de acuerdo interanotador (Kappa/Alpha). Dividir el dataset en los subconjuntos de _train_ , _validation_ y _test_ , asegurando el aislamiento estricto por documento.

## **A4. Clasificadores Supervisados Basados en Encoders (Fine-Tuning)**

Entrenar y ajustar clasificadores supervisados utilizando arquitecturas preentrenadas en inglés científico (ej. _SciBERT_ , _SPECTER_ ). Probar distintas configuraciones en la entrada del modelo:

- Clasificación utilizando _el abstract y el titulo del paper_

- Clasificación concatenando la información de la sección retórica y los _chunks_ recuperados del Top 3.

En ambas configuraciones, la entrada se construirá concatenando el _citation context_ con la información del documento citado mediante un token especial de separación, y se añadirá una

cabeza de clasificación entrenada con función de pérdida de entropía cruzada para producir un puntaje por cada una de las 9 categorías de función de cita.

## **A5. Evaluación con Modelos comerciales**

Evaluar modelos de lenguaje (ej. _GPT-4o/5, Gemini Pro_ ) en modo inferencia (sin reentrenamiento). Diseñar y comparar distintas estrategias de _prompting_ :

- Enfoques _Zero-Shot_ vs. _Few-Shot_ .

- Formulación de prompts específicos por categoría frente a prompts genéricos de clasificación estructurada.

Como referencia metodológica, la plantilla base de prompt entregará al modelo el _citation context_ y la información del documento citado (título y resumen), junto con la lista de las 9 categorías de función de cita. Se le pedirá al modelo un puntaje entre 0.0 y 1.0 por categoría (formato tipo _[0.0, 0.0, …, 0.0]_ ), con el fin de facilitar el parseo automático de las respuestas. Sobre esta plantilla base se compararán variantes de _zero-shot_ y _few-shot_ , así como la inclusión opcional de un bloque de criterios detallados y/o un bloque de ejemplos resueltos, evaluando su efecto sobre la alineación entre el puntaje más alto generado y la etiqueta de referencia.

## **A6. Evaluación Comparativa y Análisis de Desempeño**

Comparar de forma cuantitativa todos los modelos sobre el conjunto de evaluación validado por humanos (15%). Calcular métricas de _Precision, Recall y F1-Score_ (Macro y Micro). Generar y analizar las matrices de confusión para identificar qué funciones de cita presentan mayor ambigüedad o confusión entre clases.

## **A7. Análisis de Eficiencia, Latencia y Costos**

Llevar a cabo un análisis comparativo multidimensional que incluya:

- Costos de entrenamiento computacional ( _fine-tuning_ ) frente al costo financiero por consumo de tokens vía API.

- Latencia promedio por inferencia (segundos/ejemplo) entre los _encoders_ y los servicios API.

- Estabilidad y consistencia en el formato de respuesta de los modelos evaluados.

- Tasa de errores de formato (respuestas incompletas o no parseables) por modelo y variante de prompt

# 5. Despliegue y Demostrador Interactivo

Como entrega final del proyecto, se desarrollará un demostrador interactivo (aplicación web) que permita explorar el flujo completo de recomendación local y clasificación de citas.

**Requerimientos de la Interfaz:**

1. **Entrada de Usuario:** Permitir el ingreso de un texto o párrafo académico en inglés que

contenga un contexto de cita ( _citation context_ ).

2. **Recuperación de Chunks:** Calcular y desplegar, mediante _SciBERT_ , los Top 3 párrafos más similares del documento citado, junto con la sección retórica a la que corresponden.

3. **Selección del Modelo Clasificador:** Permitir seleccionar el modelo a ejecutar para la predicción de la función de cita entre tres opciones:

   - Encoder _fine-tuned_ (ej. SciBERT).

   - Modelo _Open-Weight_ (1–8B).

   - Modelo Comercial vía API (GPT / Gemini).

4. **Visualización de Resultados:** Presentar de manera clara y gráfica la función de cita predicha, la puntuación de confianza asociada (cuando el modelo lo proporcione) y la distribución visual de los _chunks_ candidatos recuperados.
