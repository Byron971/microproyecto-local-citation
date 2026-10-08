
### R5.2. Disponibilidad de pares

Observación:
Haydemar solicita aclarar cuántos contextos disponen de sus artículos correspondientes y si el volumen es suficiente.

Corrección:
Se establece una estrategia de homologación entre ACL-200 y ACL OCL utilizando identificadores ACL Anthology.

Evidencia:
El estudio reproducible del equipo sobre 500 contextos aleatorios (semilla 42) encontró:

- 499 artículos citados disponibles en ACL OCL.
- 490 artículos citados con texto utilizable.
- 421 contextos localizados en su artículo citante.
- 411 pares que cumplen simultáneamente los criterios de texto citado utilizable y localización del contexto.
- Cobertura estimada: 82,2 %.

El pipeline adicional de auditoría local examinó 141 contextos cuyos artículos citados estaban en caché. De ellos, 133 no tenían descargado el artículo citante, por lo que su estado de reconstrucción continúa sin evaluarse.

Limitaciones:
El 82,2 % es una estimación muestral, no la cobertura verificada de todo el corpus. Tampoco garantiza disponibilidad de 2.000 ejemplos por cada función de cita.

Evidencias técnicas:
- proyecto_de_grado/docs/spike_enlace_datos/README.md
- proyecto_de_grado/scripts/spike_enlace_datos/medir_enlace.py
- proyecto_de_grado/src/data/auditar_corpus.py

Pendiente:
Verificar las cuotas reales por función de cita durante el pre-etiquetado y documentar las clases insuficientes.

Estado: PARCIAL - EVIDENCIA DE COBERTURA DOCUMENTADA
