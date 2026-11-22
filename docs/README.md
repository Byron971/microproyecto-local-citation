# Documentación del microproyecto

Este directorio reúne los documentos de referencia utilizados durante el
microproyecto. Los reportes producidos por el equipo se mantienen en
`reportes/`, junto con sus fuentes y figuras.

## Estructura

```text
docs/
├── todo_entrega_02.md # Lista operativa para cerrar la segunda entrega
├── enunciados/       # Instrucciones y entregables oficiales de la materia
├── propuesta/        # Propuesta original que dio origen al proyecto
├── ejemplos/         # Reportes de otros proyectos usados como referencia
├── fundamentos/      # Explicaciones pedagógicas de conceptos
└── specs/            # Especificaciones técnicas de implementación
```

## Enunciados de la materia

| Documento | Descripción | Formatos |
|---|---|---|
| 0101 | Descripción general y cronograma del microproyecto | [PDF](enunciados/0101_microproyecto_general.pdf) · [Texto](enunciados/0101_microproyecto_general.md) |
| 0201 | Requisitos de la primera entrega | [PDF](enunciados/0201_entrega_01.pdf) · [Texto](enunciados/0201_entrega_01.md) |
| 0401 | Requisitos de la segunda entrega | [PDF](enunciados/0401_entrega_02.pdf) |

Las versiones Markdown son extracciones de apoyo para búsqueda y lectura. El
PDF correspondiente continúa siendo la fuente oficial.

## Propuesta

- [Propuesta original del proyecto en PDF](propuesta/0102_propuesta_proyecto_pln.pdf)
- [Extracción de texto de la propuesta](propuesta/0102_propuesta_proyecto_pln.md)

La propuesta original tiene un alcance mayor que el microproyecto actual. La
reducción de alcance fue documentada en la primera entrega del equipo, ubicada
en `reportes/reporte01/`.

## Ejemplos de entregas

Estos documentos pertenecen a otros proyectos y se conservan únicamente como
referencia de estructura y presentación:

- [Entrega de ejemplo: PulmoIA (PDF)](ejemplos/0301_entrega_01_pulmoia.pdf) ·
  [Texto](ejemplos/0301_entrega_01_pulmoia.md)
- [Entrega de ejemplo: detección de ganado (PDF)](ejemplos/0302_entrega_01_ganado.pdf) ·
  [Texto](ejemplos/0302_entrega_01_ganado.md)

## Documentación interna

### Issue #6: modelo supervisado de relevancia

1. [Lista de cierre de la Entrega 2](todo_entrega_02.md)
2. [Índice y ruta de aprendizaje](fundamentos/README.md)
3. [Texto y TF-IDF](fundamentos/01_texto_y_tfidf.md)
4. [Modelo supervisado](fundamentos/02_modelo_supervisado.md)
5. [Ranking y evaluación](fundamentos/03_ranking_y_evaluacion.md)
6. [Herramientas técnicas](fundamentos/herramientas_tecnicas.md)
7. [Especificación técnica](specs/especificacion_tecnica.md)

Los documentos de `fundamentos/` forman un recorrido pedagógico breve. El
documento de herramientas concentra la operación del entorno y MLflow. La
especificación define el trabajo verificable que debe implementarse. La lista
de cierre reúne los pendientes del modelo y de la entrega grupal.

## Convenciones

- Los prefijos numéricos conservan el orden cronológico del material recibido.
- Los nombres de archivos usan minúsculas y guiones bajos, sin espacios.
- Los documentos oficiales se conservan en PDF sin modificaciones.
- Los documentos internos se escriben en Markdown y enlazan la fuente de verdad
  técnica correspondiente.
