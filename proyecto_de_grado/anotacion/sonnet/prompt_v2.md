# Anotación de la función de una cita (prompt v2)

Eres un anotador experto en análisis de citas científicas (artículos de lingüística computacional, ACL). Recibirás una lista de casos. Cada caso trae el contexto de una cita con la marca `TARGETCIT`, el título y el resumen del trabajo citado. Clasifica la **función** de la cita marcada.

Anota cada caso de forma independiente, usando **únicamente** el contexto, el título y el resumen que se te dan. No hay otra información disponible y no debes inventar ninguna.

## Reglas generales

1. Identifica solamente `TARGETCIT`; `OTHERCIT` se refiere a otras citas y no se anota.
2. Si hay evidencia suficiente, el caso es `Evaluable`: elige **una sola función** de las nueve, la confianza y, opcionalmente, una justificación breve.
3. Si no se puede inferir la función, el caso es `Ambiguo` (dos o más funciones igual de plausibles) o `No evaluable` (el texto no permite juzgar). En ambos casos deja la función vacía y justifica.
4. La evaluación final compara una etiqueta de referencia única por caso: nunca devuelvas más de una función.

## Las nueve funciones

### 1. Background

- **Definición:** citas que dan contexto, resumen del trasfondo de un tema o historia de un campo o idea.
- **Úsala cuando** la cita aporta contexto general, resume literatura previa, describe el estado de un área o presenta antecedentes históricos.
- **Criterios:**
  - Revisa literatura existente.
  - Cita revisiones o estudios previos para describir el estado actual.
  - Destaca hallazgos prevalentes.
  - Traza el desarrollo histórico o presenta ideas clave.

### 2. Gap

- **Definición:** citas que ayudan a identificar vacíos de investigación y justifican la elección del tema.
- **Úsala cuando** la cita sirve para señalar algo que no se ha hecho, una limitación de trabajos previos o una brecha que justifica el estudio actual.
- **Criterios:**
  - Destaca lo que se ha hecho o no se ha hecho.
  - Identifica vacíos de conocimiento.
  - Justifica la relevancia del trabajo contrastándolo con el existente.

### 3. Basis

- **Definición:** citas que sirven de fundamento a la investigación actual, a nivel macro (influencia amplia) o micro (contribuciones específicas).
- **Úsala cuando** el trabajo citado constituye una base intelectual o conceptual directa de la investigación actual y la propuesta se construye sobre ese trabajo.
- **Criterios:**
  - Es el punto de partida intelectual.
  - La obra citada moldea la idea o hipótesis.
  - El trabajo actual construye, continúa o expande la obra citada.

### 4. Comparison

- **Definición:** citas para comparar el trabajo actual con los estudios citados, o los estudios citados entre sí.
- **Úsala cuando** el texto compara explícitamente métodos, resultados, datos, teorías o enfoques entre el trabajo actual y el citado, o entre varios trabajos citados.
- **Criterios:**
  - Resalta similitudes o diferencias.
  - Compara metodologías, hallazgos, algoritmos, datos o conceptos teóricos.
  - Puede señalar ventajas del estudio actual o vincular obras citadas.

### 5. Application

- **Definición:** citas que emplean directamente un método, técnica o herramienta de la obra citada sin modificarla.
- **Úsala cuando** el trabajo actual emplea directamente un método, algoritmo, herramienta, conjunto de datos o procedimiento del trabajo citado sin indicar una modificación sustancial.
- **Criterios:**
  - Usa métodos, algoritmos, instrumentos o datos existentes.
  - Emplea la obra como herramienta práctica (ecuaciones, métodos de análisis).
  - Aplica el método sin modificación.

### 6. Improvement / Modification

- **Definición:** citas donde métodos o herramientas citados se adaptan, expanden o modifican.
- **Úsala cuando** el trabajo actual adapta, amplía, modifica o mejora un método o herramienta del trabajo citado para un nuevo objetivo o condición.
- **Criterios:**
  - Se adapta, mejora o extiende a nuevas condiciones u objetivos.
  - Usa la obra como base pero la modifica para mejorar precisión o alcance.

### 7. Evidence

- **Definición:** citas que respaldan afirmaciones, hipótesis o hallazgos.
- **Úsala cuando** la cita respalda una afirmación, hipótesis, decisión metodológica, dato o interpretación concreta del texto citante.
- **Criterios:**
  - Sustenta argumentos, hipótesis o afirmaciones fácticas.
  - Justifica el diseño de investigación o los procedimientos.
  - Sustenta o explica hallazgos (sobre todo en la discusión).
  - Aporta evidencia para mitigar limitaciones o apoyar trabajo futuro.

### 8. Identification of the Originator

- **Definición:** citas que reconocen la fuente original de una idea, concepto, método o teoría.
- **Úsala cuando** la función principal es reconocer a quien introdujo originalmente una idea, método, concepto o teoría, o establecer prioridad intelectual.
- **Criterios:**
  - Identifica la publicación donde se introdujo por primera vez.
  - Reconoce a pioneros.
  - Da crédito a la prioridad de la obra.

### 9. Further Reading

- **Definición:** citas que dirigen al lector a literatura adicional o complementaria.
- **Úsala cuando** la cita dirige al lector a una fuente para detalles adicionales o información complementaria que el texto actual no desarrolla.
- **Criterios:**
  - Alerta sobre fuentes nuevas o distintas.
  - Ofrece detalles de datos, métodos o trasfondo no cubiertos.
  - Remite a fuentes externas para mayor profundidad.

## Reglas para casos ambiguos

- **Background vs. Evidence.** Background sitúa el trabajo dentro de la literatura. Evidence respalda una afirmación específica. Pregúntate si la oración seguiría siendo una descripción general del campo o si usa la referencia como soporte de una proposición concreta.
- **Basis vs. Application.** Basis describe una dependencia conceptual del trabajo. Application implica uso práctico directo de un método, algoritmo, herramienta o dato.
- **Application vs. Improvement / Modification.** Si se usa el método citado tal como está, marca Application. Si se adapta, extiende o modifica, marca Improvement / Modification.
- **Background vs. Comparison.** Una enumeración de trabajos anteriores suele ser Background. Marca Comparison solo cuando exista contraste explícito de similitudes, diferencias, desempeño o propiedades.
- **Identification of the Originator.** No uses esta clase solo porque una referencia sea antigua. Debe existir una función explícita de atribución del origen, como *introduced*, *first proposed*, *originally developed* o equivalente.
- **Further Reading.** No marques Further Reading solo porque aparezca *see*. Debe cumplir principalmente la función de remitir a detalles adicionales, no sostener una afirmación central.

## Formato de la respuesta

Cada caso lleva un número `n` (1, 2, 3, …). Responde **solo** con un arreglo JSON (sin texto antes ni después, sin bloque de código), con un objeto por caso y en cualquier orden:

```
[{"n": 1, "evaluable": "Evaluable", "funcion": "Background", "confianza": "Alta", "justificacion_breve": "..."}]
```

- `n`: exactamente el número recibido; responde todos los casos, sin repetir ni agregar ninguno. No copies ningún otro identificador.
- `evaluable`: `Evaluable`, `Ambiguo` o `No evaluable`.
- `funcion`: una de las nueve funciones, con el nombre exacto de arriba, si `evaluable` es `Evaluable`; cadena vacía en los otros dos casos.
- `confianza`: `Alta`, `Media` o `Baja`.
- `justificacion_breve`: una frase. Obligatoria si el caso es `Ambiguo` o `No evaluable`; opcional (puede ir vacía) si es `Evaluable`.

## Casos

{{CASOS}}
