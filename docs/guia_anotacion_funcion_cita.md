# Guía de anotación de función de cita

Esta guía operacionaliza las nueve funciones de cita definidas en la propuesta del proyecto. Su propósito es que dos anotadores humanos clasifiquen independientemente el mismo conjunto y que los desacuerdos se reconcilien después.

## Categorías

1. Background
Use esta clase cuando la cita aporta contexto general, resume literatura previa, describe el estado de un área o presenta antecedentes históricos.

2. Gap
Use esta clase cuando la cita sirve para señalar algo que no se ha hecho, una limitación de trabajos previos o una brecha que justifica el estudio actual.

3. Basis
Use esta clase cuando el trabajo citado constituye una base intelectual o conceptual directa de la investigación actual y la propuesta se construye sobre ese trabajo.

4. Comparison
Use esta clase cuando el texto compara explícitamente métodos, resultados, datos, teorías o enfoques entre el trabajo actual y el citado, o entre varios trabajos citados.

5. Application
Use esta clase cuando el trabajo actual emplea directamente un método, algoritmo, herramienta, conjunto de datos o procedimiento del trabajo citado sin indicar una modificación sustancial.

6. Improvement / Modification
Use esta clase cuando el trabajo actual adapta, amplía, modifica o mejora un método o herramienta del trabajo citado para un nuevo objetivo o condición.

7. Evidence
Use esta clase cuando la cita respalda una afirmación, hipótesis, decisión metodológica, dato o interpretación concreta del texto citante.

8. Identification of the Originator
Use esta clase cuando la función principal es reconocer a quien introdujo originalmente una idea, método, concepto o teoría, o establecer prioridad intelectual.

9. Further Reading
Use esta clase cuando la cita dirige al lector a una fuente para detalles adicionales o información complementaria que el texto actual no desarrolla.

## Reglas para casos ambiguos

Background vs Evidence:
Background sitúa el trabajo dentro de la literatura. Evidence respalda una afirmación específica. Pregunte si la oración seguiría siendo una descripción general del campo o si está usando la referencia como soporte de una proposición concreta.

Basis vs Application:
Basis describe una dependencia conceptual del trabajo. Application implica uso práctico directo de un método, algoritmo, herramienta o dato.

Application vs Improvement / Modification:
Si se usa el método citado tal como está, marque Application. Si se adapta, extiende o modifica, marque Improvement / Modification.

Background vs Comparison:
Una enumeración de trabajos anteriores suele ser Background. Marque Comparison solo cuando exista contraste explícito de similitudes, diferencias, desempeño o propiedades.

Identification of the Originator:
No use esta clase solo porque una referencia sea antigua. Debe existir una función explícita de atribución del origen, como introduced, first proposed, originally developed o equivalente.

Further Reading:
No marque Further Reading solo porque aparezca see. Debe cumplir principalmente la función de remitir a detalles adicionales, no sostener una afirmación central.

## Procedimiento

Cada anotador debe trabajar sobre su hoja sin consultar la del otro. Se debe asignar una sola categoría por caso porque la evaluación final compara el argmax de nueve puntajes contra una etiqueta de referencia única.

Después de completar ambas hojas, ejecutar el módulo src.evaluation.annotation con el comando agreement. El script calcula Cohen Kappa, tasa de acuerdo y genera un archivo de desacuerdos y una hoja de reconciliación.

Los desacuerdos deben revisarse usando únicamente el contexto de cita, título y resumen disponibles. La etiqueta final debe quedar en final_label. Solo después de completar todos los final_label se genera el Test Gold definitivo.

## Integridad de la evidencia

Los pre-etiquetados automáticos pueden acelerar la búsqueda de candidatos, pero no deben registrarse como validación humana. Si se usa un archivo de sugerencias, el anotador debe tomar su decisión de forma independiente antes de verlo o usarlo únicamente durante la etapa de reconciliación.
