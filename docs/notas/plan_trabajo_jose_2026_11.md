# Plan de trabajo de José María — Noviembre 2026

Actualizado: 2026-11-09.

Este documento reúne mis siete issues asignados y sirve para seguir lo implementado y lo que falta completar. La verificación del despliegue corresponde al 8 de noviembre; los estados de anotación, revisión y ensayos deben confirmarse con el equipo antes de cerrarlos en GitHub.

## Tareas y pendientes

| Issue | Estado | Qué incluye | Qué falta completar |
| --- | --- | --- | --- |
| [#116](https://github.com/Byron971/microproyecto-local-citation/issues/116) Despliegue público | Funcionamiento verificado en el lab; migración pendiente | Publicar el API y el tablero con inferencia real y acceso externo. | Replicar el despliegue en la cuenta personal, comprobar el flujo y registrar la nueva URL. URL del lab, estabilidad, latencia, CPU y memoria ya tienen evidencia; la franja de evaluación queda pospuesta por decisión de José. |
| [#137](https://github.com/Byron971/microproyecto-local-citation/issues/137) Terraform y GitHub Actions | Infraestructura desplegada; CI pendiente de verificar | Crear infraestructura reproducible y automatizar publicación y despliegue desde main. | Integrar el PR #155, que ya contiene el ajuste a ALB interno publicado; configurar secrets y probar ambos workflows, comentarios del plan y credenciales vencidas; probar rollback real; confirmar protección de main y aceptación del uso de secrets temporales sin OIDC ni environments. |
| [#107](https://github.com/Byron971/microproyecto-local-citation/issues/107) Interfaz final | React publicado en rama; integración y despliegue pendientes | Unir recomendaciones, Top-3 y clasificación de nueve funciones en una demo. | Integrar la rama feature/interfaz-react-107; desplegar el API actualizado y React en S3/CloudFront, aplicar CORS y verificar el flujo público. Terraform y pruebas locales listos. Integrar los modelos pendientes y la clasificación de nueve funciones según #102/#103/#105. |
| [#127](https://github.com/Byron971/microproyecto-local-citation/issues/127) Gold de relevancia Top-3 | Pendiente | Construir una referencia humana para evaluar los fragmentos recuperados. | Seleccionar unas 100 consultas con manifiesto; repartir anotación ciega entre los cinco; adjudicar desacuerdos y calcular Hit@3, Recall@3 y MRR@3 para BM25 y SciBERT, junto con Carlos Caicedo. |
| [#98](https://github.com/Byron971/microproyecto-local-citation/issues/98) Anotación humana | En progreso | Mantener la guía y obtener etiquetas humanas independientes. | Revisar casos frontera, especialmente Basis; completar dos etiquetas por cita y registrar decisiones, en coordinación con Carlos Caicedo. |
| [#99](https://github.com/Byron971/microproyecto-local-citation/issues/99) Acuerdo humano | En revisión; estado por confirmar | Medir el acuerdo entre anotadores y resolver la calibración 3. | Revisar el PR #141 de Carlos Caicedo y sus resultados; documentar la decisión de calibración antes de dar la tarea por terminada. |
| [#123](https://github.com/Byron971/microproyecto-local-citation/issues/123) Ensayos | Pendiente | Preparar al equipo para la sustentación y la demostración. | Realizar dos ensayos de 15 minutos; preparar 15–20 preguntas con responsables; definir quién opera la demo y probar conexión y respaldo. |

## Avance de la interfaz (#107)

La rama `feature/interfaz-react-107` está publicada y parte de `feature/despliegue-aws-ecs-137`. Incluye:

- Aplicación React con la identidad visual acordada, navegación y adaptación a móvil.
- Recomendaciones conectadas al API, selector de modelos con ayuda y mensajes de error. El catálogo muestra únicamente el TF-IDF con reordenador realmente integrado.
- Modal para elegir entre 50 ejemplos reales de ACL-200, con título y vista previa. Los resultados no muestran avisos de «cita correcta».
- Copia de referencias en APA 7 con metadatos oficiales de ACL Anthology y alternativa de copia manual.
- Vistas de datos, desempeño, negativos y Top-3 experimental. La clasificación de nueve funciones se muestra como no integrada.
- Terraform para S3 privado y CloudFront, configuración de CORS, script de publicación y workflows de validación y publicación.

Validación local: 16 pruebas de frontend, 11 del API, dos de rutas de CloudFront y dos pruebas de navegador (escritorio y móvil) pasan. La compilación, los workflows y ambos stacks de Terraform están validados. Las pruebas de navegador usan respuestas controladas; no sustituyen la comprobación del despliegue público ni de CORS.

El código está publicado hasta el commit `46434cf`. Los cambios de `docs/` se retiraron del alcance del PR y se conservan localmente. No se aplicaron los recursos del frontend ni se publicó React en AWS. El ticket #107 sigue abierto por integración, despliegue y modelos pendientes.

## Despliegue comprobado (8 de noviembre)

URL pública: [API y tablero](https://qlipl9bh0i.execute-api.us-east-1.amazonaws.com/).

Infraestructura: API Gateway → VPC Link → ALB interno → ECS Fargate, con 0.5 vCPU y 1 GB de memoria. ECS confirma `COMPLETED`, una tarea en ejecución y ninguna pendiente. El tablero, Top-3 y salud responden 200; las recomendaciones funcionan y una entrada vacía devuelve 422.

En 20 recomendaciones secuenciales, la mediana fue 1.107 s y el P95 2.808 s. CloudWatch registró memoria media de ~188 MiB y máxima de ~218 MiB en los períodos disponibles, que incluyen arranque y actividad anterior a la medición HTTP. No son resultados de una prueba de carga.

Los comandos, datos originales, métricas de CPU/memoria y límites están en [la evidencia de #116](../evidencias/despliegue_116/README.md). El funcionamiento en Learner Lab queda validado para el alcance actual. Por decisión de José, no se realizará ahora la prueba de cierre del lab ni se coordinará la franja de evaluación: la URL definitiva se publicará desde una cuenta personal. Esa cuenta aún no se ha desplegado ni verificado.

## Próximos pasos

1. #116: replicar el despliegue en la cuenta personal y registrar su URL tras comprobar tablero, salud y recomendaciones. Configurar credenciales, bucket propio y un rol ECS existente con los permisos necesarios; `LabRole` pertenece al laboratorio.
2. Integrar el PR #155 y comprobar los workflows de #137 con credenciales vigentes.
3. #137: probar rollback real y guardar evidencia, sin mezclarlo con la verificación de disponibilidad de #116.
4. #107: integrar la rama React después de su base de despliegue; actualizar el API con los endpoints de modelos, ejemplos y referencias; aplicar Terraform de frontend y CORS, publicar el sitio y verificar recomendaciones, ejemplos y copia APA 7 desde CloudFront. Integrar el clasificador cuando esté disponible.
5. Coordinar la anotación de #98/#127 y revisar #99.
6. Preparar los ensayos de #123 con la demo validada.
