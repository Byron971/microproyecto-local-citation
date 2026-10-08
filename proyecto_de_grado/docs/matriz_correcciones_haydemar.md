
# Matriz de correcciones - Propuesta V4

Proyecto: Recomendación local de citas y clasificación de su función en artículos académicos.

Docente: Haydemar Núñez
Calificación anterior: 86/100
Fecha de revisión: 8 de octubre de 2026

## Objetivo

Resolver las observaciones recibidas en las rúbricas 4, 5 y 6 mediante correcciones metodológicas, implementación reproducible y evidencia verificable.

## Rúbrica 4 - Metodología (12/15)

### R4.1. Homologación de datasets

Observación:
No se explicó claramente cómo se combinarían los datasets ni si se utilizaría un único conjunto integrado.

Corrección:
Integrar ACL-200 y ACL OCL utilizando los identificadores de ACL Anthology. ACL-200 proporciona los contextos y pares de artículos; ACL OCL, el texto completo.

Evidencia disponible:
docs/spike_enlace_datos/README.md

Pendiente:
Implementar y validar el pipeline de integración completo.

Estado: PARCIAL

### R4.2. Sesgo por secciones

Observación:
Incorporar la sección del documento puede introducir sesgo en la clasificación.

Corrección:
Comparar configuraciones sin secciones, con secciones y con secciones permutadas. Diferenciar la sección del artículo citante de la sección del fragmento citado.

Pendiente:
Definir las configuraciones definitivas y ejecutar los experimentos de ablación.

Estado: PENDIENTE

## Rúbrica 5 - Datos (11/20)

### R5.1. Caracterización del dataset

Corrección:
Documentar tamaño, estructura, campos disponibles, distribución temporal, contextos truncados y calidad del texto.

Estado: PARCIAL

### R5.2. Disponibilidad de pares

Corrección:
Medir cuántos contextos pueden relacionarse con artículos citantes y citados que tengan texto completo utilizable.

Evidencia:
Estudio de 500 contextos con 82,2 % de pares completos mediante ACL OCL.

Pendiente:
Medir la cobertura real del corpus procesado.

Estado: PARCIAL

### R5.3. Particiones y no-leakage

Corrección:
Conservar la división temporal y verificar el aislamiento de documentos citantes y pares citante-citado entre entrenamiento, validación y prueba.

Pendiente:
Automatizar las verificaciones e investigar los artículos citados compartidos.

Estado: PARCIAL

### R5.4. Viabilidad de 2.000 ejemplos por clase

Corrección:
Medir la distribución de las nueve funciones y comprobar si pueden reunirse al menos 2.000 ejemplos por categoría.

Pendiente:
Ejecutar el pre-etiquetado a escala y verificar los conteos por clase.

Estado: PENDIENTE

### R5.5. Datos insuficientes

Corrección:
Definir ampliación de fuentes, estrategias para clases escasas y criterios de aceptación académica si no se alcanzan las cuotas.

Estado: PARCIAL

## Rúbrica 6 - Evaluación (8/10)

### R6.1. Ground truth para Top-3

Corrección:
Construir un conjunto curado de contextos y fragmentos relevantes mediante anotación humana independiente.

Pendiente:
Definir el protocolo, reservar los casos de evaluación y realizar la curaduría.

Estado: PENDIENTE

### R6.2. Recall@3 y MRR@3

Corrección:
Definir Recall@3, Hit@3 y MRR@3 sobre fragmentos, con fórmulas y ejemplos comprobables.

Evaluación principal:
Comparar F1 Macro de la clasificación con y sin fragmentos recuperados.

Pendiente:
Implementar pruebas, generar resultados y documentar las limitaciones.

Estado: PENDIENTE

## Decisiones académicas por confirmar

1. Tamaño definitivo del Test Gold: propuesta original del 15 % frente a alternativa de 450 casos.
2. Clasificación de función principal única frente a posibles etiquetas múltiples.
3. Protocolo de validación de fragmentos relevantes.

## Condición de cierre

Cada observación se considerará resuelta únicamente cuando tenga:

- Corrección documentada.
- Evidencia reproducible, si corresponde.
- Pruebas aprobadas para los cambios de código.
- Resultados verificados o limitaciones explícitas.
- Aprobación académica cuando se cambien compromisos de la propuesta.
