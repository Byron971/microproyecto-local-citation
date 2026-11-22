# Texto y TF-IDF

## 1. Del lenguaje a los números

Un modelo matemático no recibe directamente el significado de una oración.
Necesita una representación numérica del texto. En este proyecto existen tres
tipos principales de texto:

- **contexto**: fragmento donde falta una cita;
- **título**: descripción breve de un artículo candidato;
- **abstract**: resumen del contenido del artículo.

El conjunto completo de artículos se denomina **corpus**. A partir del corpus
se construye un vocabulario: la lista de términos que el sistema sabe
representar.

### Tokens y n-gramas

Un **token** es una unidad obtenida al dividir el texto, normalmente una
palabra. Por ejemplo:

```text
"Neural models recommend citations"
→ neural, models, recommend, citations
```

Un **unigrama** es un token individual. Un **bigrama** combina dos tokens
consecutivos, como `neural models`. El parámetro `ngram_range=(1, 1)` indica que
el proyecto usa solo unigramas.

Las palabras muy frecuentes y poco informativas, como `the` o `and`, se
denominan **stop words**. El vectorizador elimina stop words en inglés para que
no dominen la comparación.

Los marcadores `TARGETCIT` y `OTHERCIT` también se eliminan: señalan posiciones
de citas, pero no aportan contenido temático.

## 2. Bolsa de palabras

La representación de **bolsa de palabras** asigna una columna a cada término
del vocabulario y cuenta sus apariciones. Ignora el orden general de la frase.

Para el vocabulario:

```text
[citation, model, neural, protein]
```

el texto `neural citation model` podría representarse como:

```text
[1, 1, 1, 0]
```

Los vocabularios reales tienen miles de términos, pero cada documento contiene
solo una pequeña parte. Por eso se utilizan **matrices dispersas**, que guardan
principalmente los valores distintos de cero y reducen el uso de memoria.

Contar palabras no es suficiente: una palabra común en casi todos los artículos
no distingue bien un tema. TF-IDF corrige este problema.

## 3. Qué es TF-IDF

TF-IDF significa **Term Frequency–Inverse Document Frequency**. Su idea es:

> Un término es informativo cuando aparece en el documento actual, pero no en
> demasiados documentos del corpus.

### TF: frecuencia del término

TF mide cuánto aparece un término en un documento. Si `citation` aparece tres
veces, tendrá más presencia que un término que aparece una sola vez.

Una forma simplificada es:

```text
TF(t, d) = apariciones del término t en el documento d
```

### IDF: frecuencia documental inversa

IDF reduce el peso de términos presentes en muchos documentos:

```text
IDF(t) = log(N / DF(t))
```

donde:

- `N` es la cantidad de documentos;
- `DF(t)` es la cantidad de documentos que contienen el término.

En la práctica, scikit-learn agrega suavizado para evitar divisiones problemáticas.

### Peso combinado

```text
TF-IDF(t, d) = TF(t, d) × IDF(t)
```

Ejemplo intuitivo:

- `model` aparece en casi todos los artículos y recibe un IDF bajo;
- `SciBERT` aparece en pocos artículos y recibe un IDF alto;
- un artículo que menciona varias veces `SciBERT` obtiene un peso alto para ese
  término.

TF-IDF produce un vector para cada contexto, título y abstract.

## 4. Parámetros del vectorizador

| Parámetro | Valor principal | Función |
|---|---:|---|
| `max_features` | 50.000 | Límite máximo del vocabulario |
| `min_df` | 2 | Exige que un término aparezca en dos artículos |
| `ngram_range` | `(1, 1)` | Utiliza palabras individuales |
| `stop_words` | `english` | Elimina palabras comunes en inglés |

`max_features` controla memoria y tiempo. `min_df` elimina términos demasiado
raros, aunque un valor excesivo también podría descartar vocabulario científico
útil.

El vectorizador se ajusta sobre los títulos y abstracts del catálogo, no sobre
las etiquetas de validación o prueba.

## 5. Similitud coseno

Después de representar dos textos como vectores, se necesita medir cuánto se
parecen. La similitud coseno compara la dirección de los vectores:

```text
coseno(a, b) = (a · b) / (||a|| × ||b||)
```

Interpretación aproximada para vectores TF-IDF no negativos:

- cerca de `1`: los textos comparten términos importantes;
- cerca de `0`: comparten pocos términos relevantes.

`TfidfVectorizer` normaliza los vectores con norma L2. Por eso, en la
implementación, el producto punto entre dos vectores ya equivale a su similitud
coseno.

El proyecto calcula dos señales diferentes:

```text
similarity_title    = coseno(contexto, título)
similarity_abstract = coseno(contexto, abstract)
```

Separarlas permite que el modelo aprenda si el título o el resumen resulta más
informativo.

## 6. Fortalezas y limitaciones

TF-IDF es rápido, interpretable y funciona sin etiquetas. Por eso es una buena
línea base y una primera etapa eficiente.

Su limitación principal es que mide coincidencia **léxica**, no significado
completo. `car` y `automobile` pueden ser semánticamente similares pero no
comparten la misma palabra. También puede favorecer un artículo que repite los
términos del contexto aunque no sea la cita correcta.

Esta limitación explica por qué los negativos difíciles —artículos con gran
similitud TF-IDF pero incorrectos— son complicados para el modelo actual.

## Error frecuente

Una similitud alta no significa que el artículo sea necesariamente correcto.
Solo indica que comparte vocabulario ponderado con el contexto.

## Ideas clave

- El texto debe transformarse en vectores numéricos.
- TF-IDF aumenta el peso de términos útiles para distinguir documentos.
- La similitud coseno mide cercanía léxica entre vectores.
- Título y abstract generan señales separadas.
- TF-IDF es eficiente, pero no comprende completamente la semántica.

Siguiente lectura: [Modelo supervisado](02_modelo_supervisado.md).
