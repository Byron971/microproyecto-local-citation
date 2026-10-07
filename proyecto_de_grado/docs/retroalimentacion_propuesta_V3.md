# Retroalimentación de la docente a la Propuesta V3 (Grupo 19, Tema 1)

Docente: Haydemar Núñez. Total: **86 / 100**.

| # | Criterio | Puntos | Comentario de la docente | Acción |
|---|---|---:|---|---|
| 1 | Contexto y planteamiento del problema | 20/20 | "Bien." | Conservar tal cual. |
| 2 | Objetivos | 10/10 | "En general bien. Incluir un solo verbo de acción en la redacción de los objetivos." | Reescribir los objetivos con un verbo por objetivo (ver abajo). |
| 3 | Estado del arte y bibliografía | 10/10 | "Bien." | Conservar; actualizar si aparece trabajo nuevo. |
| 4 | Metodología propuesta | 12/15 | No es clara la estrategia de homologación de datasets (¿un solo dataset o comparar formas de extraer contextos?). En la 2.ª configuración, agregar la sección puede generar sesgo en la clasificación. | Declarar un dataset integrado (ACL-200 + ACL OCL por ID de ACL). Ablación con/sin sección y control con secciones barajadas. |
| 5 | Recolección, exploración y descripción de datos | 11/20 | Falta mayor descripción del dataset. ¿Todos los contextos tienen su par? ¿Qué consideraciones en el split (¿cuándo se escribió el paper?)? ¿Se llega a la meta de muestra con los datos actuales? ¿Plan si son insuficientes? | Tasa de resolución de pares (82,2 %), split temporal documentado, plan por niveles para clases raras. |
| 6 | Evaluación y métricas | 8/10 | En la recuperación Top-3, ¿cómo se calcula el recall en general? ¿Cuál es el ground truth de referencia? Lo mismo para MRR. | Definir Recall@K y MRR y construir un gold de relevancia por fragmento (decisión pendiente). |
| 7 | Viabilidad y recursos | 5/5 | "Bien el tema ético." | Conservar la sección de ética. |
| 8 | Presentación y redacción | 10/10 | "En general, es un buen documento." | Conservar el nivel de redacción. |

Los 14 puntos perdidos están en los criterios 4, 5 y 6 (3 + 9 + 2).

## Objetivos con más de un verbo (V3, sección 5)

Contados sobre el texto de la V3:

- General: "Diseñar, construir y evaluar…" (3 verbos) y además "comparando… y desplegando".
- Específico 2: "Implementar… y compararla".
- Específico 3: "Construir y curar…".
- Específico 4: "Entrenar y comparar…".
- Específicos 1 y 5 tienen un solo verbo.

Opciones: dejar un verbo por objetivo y mover el resto a objetivos nuevos, o dejar el verbo principal y expresar lo demás como criterio de logro.

## Medido el 2026-10-06 (para el criterio 5)

- Split original de ACL-200 por año del citante, inferido del ID de ACL Anthology: entrenamiento 2009–2013 (30.390), validación 2014 (9.381), prueba 2015 (9.585).
- Citantes compartidos entre particiones: 0. Citados compartidos: 1.518 (entrenamiento–validación), 1.338 (entrenamiento–prueba), 1.305 (validación–prueba).
- Año de los citados: mediana 2007; solo el 0,5 % es de 2015 o posterior.
- Pares completos con texto vía ACL OCL: 82,2 % ± 3,4 pp (`spike_enlace_datos/`, 500 contextos).
