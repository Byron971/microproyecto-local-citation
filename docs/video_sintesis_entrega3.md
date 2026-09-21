# Guion de video de síntesis — Entrega 3

Objetivo interno: 8 a 9 minutos. El límite de la entrega es 10 minutos.

Este guion cubre únicamente resultados y componentes que ya están documentados en el repositorio. La extensión de clasificación de función de cita ya cuenta con Test Gold definitivo y acuerdo interanotador medido, pero debe presentarse como trabajo en curso mientras las corridas de los modelos no se repitan sobre ese conjunto.

## 0:00–0:45 — Problema y objetivo

Pantalla:
- Portada del proyecto.
- Título: Recomendación local de citas académicas mediante aprendizaje automático.

Voz:
"Nuestro proyecto busca apoyar a autores de textos académicos en la búsqueda de referencias relevantes. El sistema recibe un fragmento de texto donde se necesita una cita y devuelve una lista ordenada de artículos candidatos. El objetivo fue construir no solo un modelo, sino una solución reproducible con versionamiento de datos, seguimiento experimental, empaquetamiento, API, tablero, contenedores y despliegue."

## 0:45–1:30 — Datos y reproducibilidad

Pantalla:
- Repositorio.
- data/raw.dvc y data/processed.dvc.
- Breve vista del manual de instalación.

Voz:
"Trabajamos con el conjunto custom ACL-200 del repositorio Local-Citation-Recommendation. Los datos se versionan con DVC para separar los artefactos pesados del código y asegurar reproducibilidad. Git conserva código y configuración, mientras DVC permite recuperar los datos utilizados en entrenamiento y evaluación."

## 1:30–2:50 — Arquitectura y modelos

Pantalla:
- Diagrama: Contexto → TF-IDF → Top-100 → Regresión logística → Top-K.
- Gráficas comparacion_random_hard_recall10.png y comparacion_random_hard_mrr10.png.
- Tabla de resultados del reporte.

Voz:
"La solución tiene dos etapas. Primero, TF-IDF recupera cien artículos candidatos. Después, un reordenador supervisado ajusta el orden. Evaluamos estrategias con negativos aleatorios y negativos difíciles y posteriormente ampliamos el vector de características. La versión 2 con negativos aleatorios fue la seleccionada: alcanzó Recall@10 de 0,3793 y MRR@10 de 0,2166. Recall@100 se mantiene en 0,5160 porque el reordenador no puede recuperar un artículo que no entró en los cien candidatos iniciales."

## 2:50–3:40 — Seguimiento con MLflow

Pantalla:
- mlflow_v2_tabla_corridas.png.
- mlflow_v2_comparacion.png.
- mlflow_conexion_aws_automatica.png.

Voz:
"Los experimentos se registraron con MLflow para comparar configuraciones y conservar parámetros, métricas y evidencia. También se configuró acceso a MLflow en AWS, de manera que las corridas puedan consultarse fuera del entorno local."

## 3:40–4:40 — Empaquetamiento y API

Pantalla:
- model-package.
- issue#14_funcionamiento_API.png.
- Swagger /docs.
- Una petición POST real.

Voz:
"El modelo seleccionado se empaquetó como una librería instalable. FastAPI consume ese paquete y expone el recomendador mediante una interfaz HTTP. Esto desacopla entrenamiento, modelo y aplicación y permite reutilizar el mismo paquete en otros servicios."

## 4:40–5:50 — Demostración del tablero

Pantalla:
- Tablero ejecutándose.
- Botón Usar un ejemplo real.
- Ejecutar una recomendación.
- Mostrar Top-K con título, resumen y puntuaciones.

Voz:
"El tablero permite introducir un contexto académico o cargar un ejemplo real del conjunto de datos. Al ejecutar la consulta, la interfaz llama a la API y presenta los artículos candidatos ordenados. El resultado debe entenderse como apoyo a la búsqueda bibliográfica: el usuario sigue siendo responsable de revisar la pertinencia de la referencia."

## 5:50–6:50 — Docker y despliegue

Pantalla:
- docker-compose.yml.
- issue#15_compose_servicios_activos.png.
- despliegue_aws_postrefactor_tablero.png.
- despliegue_aws_postrefactor_contenedores.png.
- despliegue_aws_postrefactor_consola_ec2.png.

Voz:
"La API y el tablero se dockerizaron y se integraron mediante Docker Compose. Después se desplegaron sobre una instancia EC2 de AWS, donde el tablero responde desde la IP pública y la API reporta estado saludable. La auditoría desde un clon limpio verificó que DVC recupera los datos, el paquete puede entrenarse e instalarse y los contenedores se construyen sin depender del entorno de desarrollo original."

## 6:50–7:30 — Manuales y reproducibilidad

Pantalla:
- docs/manual_usuario.md.
- docs/manual_instalacion.md.
- Pruebas automatizadas.

Voz:
"El repositorio incluye manual de usuario y manual de instalación. La reproducibilidad se apoya en Git, DVC, MLflow, uv, Tox, pytest y Docker. Así, el proyecto puede reconstruirse y ejecutarse siguiendo un procedimiento documentado."

## 7:30–8:20 — Conclusiones y trabajo en equipo

Pantalla:
- Tabla de aportes del reporte.
- Repositorio con issues y pull requests.

Voz:
"El resultado principal es una solución de recomendación local de citas que mejora el ordenamiento de candidatos y queda integrada en un flujo MLOps reproducible. La principal limitación sigue estando en la recuperación inicial: si el artículo correcto no aparece en el Top-100, el reordenador no puede recuperarlo. El trabajo se coordinó mediante issues, ramas, pull requests y revisiones, con aportes diferenciados en recuperación, reordenamiento, empaquetamiento, experimentación, despliegue y documentación."

## 8:20–8:50 — Extensión opcional de función de cita

Mostrar esta parte solo si hay tiempo.

Pantalla:
- docs/evaluacion_comparativa_provisional_20sep.md
- Tabla con Qwen3:8B, Gemini 3.5 Flash-Lite y Cohere Command A+.

Voz:
"Como extensión, evaluamos clasificación de función de cita en nueve categorías usando tres estrategias de prompting sobre veinte casos piloto. En este conjunto provisional, Gemini con few-shot obtuvo F1 Macro de 0,329 y accuracy de 0,65; Cohere alcanzó F1 Macro de 0,261 y Qwen local 0,174 en sus mejores configuraciones comparables. Completamos además una segunda validación humana independiente sobre esos veinte casos, con un acuerdo del sesenta por ciento y un Cohen Kappa de cero coma cuarenta y ocho, que corresponde a un acuerdo moderado. Tras reconciliar los desacuerdos congelamos el Test Gold definitivo. Los resultados de los modelos siguen siendo preliminares por dos razones: se calcularon sobre el conjunto provisional y aún deben repetirse sobre el definitivo, y el conjunto cubre solo cinco de las nueve clases."

## Reparto sugerido

- John: introducción, resultados, MLflow y cierre.
- Carlos Caicedo: datos, línea base y DVC.
- José Zambrana: reordenador, características y resultados.
- Carlos Duque: empaquetamiento, API, Docker y demostración.

El reparto es una propuesta para asegurar participación identificable; puede cambiarse sin alterar el contenido.

## Evidencias que conviene tener abiertas antes de grabar

- reportes/reporte03/comparacion_random_hard_recall10.png
- reportes/reporte03/comparacion_random_hard_mrr10.png
- reportes/reporte03/mlflow_v2_tabla_corridas.png
- reportes/reporte03/issue#14_funcionamiento_API.png
- reportes/reporte03/issue#15_compose_servicios_activos.png
- reportes/reporte03/despliegue_aws_postrefactor_tablero.png
- reportes/reporte03/despliegue_aws_postrefactor_contenedores.png
- reportes/reporte03/despliegue_aws_postrefactor_consola_ec2.png
- docs/manual_usuario.md
- docs/manual_instalacion.md
- docs/evaluacion_comparativa_provisional_20sep.md


## Plan B si los demás integrantes no alcanzan a grabar

La guía oficial exige que el video presente una síntesis del problema, su relevancia, los modelos construidos, la solución, los principales resultados y las conclusiones, con una duración máxima de 10 minutos. No establece de forma explícita que cada integrante deba hablar dentro del video.

Si el equipo no alcanza a coordinar una grabación conjunta, John puede grabar la narración completa siguiendo este mismo guion y mostrar en la sección de trabajo en equipo la tabla de aportes verificables. La contribución individual de cada integrante sigue sustentada en commits, Pull Requests, reporte de trabajo en equipo y la sustentación.

Para este plan, mantenga el video entre 7:30 y 8:30 minutos y elimine el reparto por integrante. Use una sola voz continua y conserve las mismas evidencias de pantalla.
