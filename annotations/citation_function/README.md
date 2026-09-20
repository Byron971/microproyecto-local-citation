# Validación manual por parte del equipo del piloto de función de cita

Este directorio conserva los artefactos de validación manual usados para preparar el corte del 20 de septiembre.

Archivos:
- annotator_a.csv: primera validación manual por parte del equipo, 20 de 20 casos.
- annotator_b_blank.csv: formulario sin etiquetas para una segunda validación manual independiente.
- provisional_test_gold.jsonl: versión provisional construida únicamente a partir de annotator_a.csv.

Estado:
- 20 de 20 casos revisados en la primera validación.
- Una sola etiqueta por caso, usando las nueve categorías definidas en el proyecto.
- La primera validación fue asistida con explicaciones de cada caso y no debe describirse como una anotación ciega o independiente.
- provisional_test_gold.jsonl puede usarse para pruebas técnicas y corridas preliminares, pero no debe presentarse como Test Gold definitivo.
- Para calcular el acuerdo interanotador se requiere completar annotator_b_blank.csv de forma independiente.
- Después se deben calcular acuerdo, reconciliar desacuerdos y generar el Test Gold final.

Las etiquetas de annotator_a.csv fueron confirmadas durante la primera validación manual por parte del equipo y no deben confundirse con las sugerencias automáticas almacenadas en tests/fixtures/citation_function_prelabels.jsonl.
