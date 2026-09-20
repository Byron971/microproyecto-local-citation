# Cierre de Entrega 3

Este documento concentra lo que ya está disponible en el repositorio y lo que todavía debe completarse antes de la entrega.

## Requisitos principales

| Requisito | Evidencia en el repositorio | Estado |
| --- | --- | --- |
| Repositorio Git con código | raíz del repositorio, src/, model-package/ | Listo |
| Datos versionados | data/raw.dvc, data/processed.dvc | Listo |
| Modelos y entrenamiento | src/, model-package/ | Listo |
| Seguimiento experimental | MLflow + evidencias en reportes/reporte03/ | Listo |
| Modelo empaquetado | model-package/ | Listo |
| API | FastAPI y evidencias issue #14 | Listo |
| Tablero | src/app + evidencias de recomendación real | Listo |
| Contenedores | Dockerfile, Dockerfile.dashboard, docker-compose.yml | Listo |
| Despliegue | evidencias issue #31 y auditoría de entorno limpio | Listo |
| Manual de usuario | docs/manual_usuario.md | Listo |
| Manual de instalación | docs/manual_instalacion.md | Listo |
| Fuente del reporte | reportes/reporte03/main.tex | Listo, en actualización |
| PDF final del reporte | debe generarse desde main.tex | Pendiente |
| Reporte de trabajo en equipo | sección Trabajo en equipo de main.tex | En actualización |
| Video de síntesis | docs/video_sintesis_entrega3.md contiene el guion | Pendiente de grabación |

## Correcciones aplicadas al reporte

Se corrigió la conclusión para que use las métricas del modelo finalmente seleccionado, versión 2 con negativos aleatorios:

- Recall@10: 0,3793
- MRR@10: 0,2166
- Recall@100: 0,5160

También se corrigió la sintaxis LaTeX de la sección añadida para la evaluación de función de cita y se aclaró que esa extensión aún tiene resultados provisionales.

## Evaluación de función de cita

Este frente adicional ya tiene:

- tres prompts versionados;
- parser común de nueve puntajes;
- métricas Precision, Recall y F1 Macro/Micro;
- matrices de confusión;
- clientes para OpenAI, Gemini y un modelo open-weight;
- orquestador de punta a punta;
- primera validación manual por parte del equipo sobre 20 casos;
- formulario vacío para una segunda validación independiente;
- gold provisional protegido para evitar reportarlo como definitivo.

Todavía falta completar la segunda validación manual independiente, calcular acuerdo interanotador, reconciliar desacuerdos y ejecutar corridas reales con los modelos configurados.

## Orden de cierre recomendado

1. Obtener annotator_b_blank.csv completado por un segundo validador.
2. Ejecutar el cálculo de acuerdo y reconciliar desacuerdos.
3. Generar annotations/citation_function/test_gold.jsonl.
4. Configurar modelos y credenciales localmente; nunca versionarlas.
5. Ejecutar el orquestador sobre el Test Gold definitivo.
6. Incorporar resultados definitivos al reporte si entran dentro del alcance de la entrega.
7. Generar y revisar el PDF final, verificando que no supere 10 páginas.
8. Grabar el video usando docs/video_sintesis_entrega3.md.
9. Añadir el enlace del video y cerrar los issues pendientes.
