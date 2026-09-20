# Guion literal de video — Entrega 3

Duración objetivo: 7:30–8:30 minutos.
Modalidad: una sola voz. Puede grabarlo John si el resto del equipo no alcanza a participar.
No leer los textos entre corchetes; son instrucciones de pantalla.

## 0:00–0:40 — Introducción

[Mostrar portada del reporte o README]

Hola. En este video presentamos nuestro proyecto de recomendación local de citas académicas mediante aprendizaje automático.

El problema que abordamos es que, durante la escritura de un artículo académico, encontrar una referencia pertinente para respaldar un fragmento concreto puede requerir revisar una gran cantidad de literatura. Nuestro objetivo fue construir un sistema que reciba el contexto donde se necesita una cita y devuelva artículos candidatos ordenados por relevancia.

Además del modelo, buscamos que la solución fuera reproducible y desplegable, incorporando versionamiento de datos, seguimiento de experimentos, empaquetamiento, API, tablero, contenedores y despliegue.

## 0:40–1:20 — Datos y reproducibilidad

[Mostrar repositorio, archivos DVC y manual de instalación]

Trabajamos con el conjunto custom ACL-200 usado en el trabajo de Local Citation Recommendation. Los datos se versionan mediante DVC, mientras que Git y GitHub conservan el código, la configuración y el historial de colaboración.

Esto permite que una persona pueda clonar el repositorio, recuperar los datos y reproducir el flujo documentado sin almacenar los archivos pesados directamente dentro de Git.

## 1:20–2:30 — Arquitectura y modelos

[Mostrar diagrama o sección del reporte y gráficas comparativas]

La solución principal tiene dos etapas.

Primero, un recuperador basado en TF-IDF genera un conjunto de cien artículos candidatos a partir del contexto de la cita.

Después, un reordenador supervisado usa características del par contexto-artículo para reorganizar esos candidatos.

Probamos variantes con negativos aleatorios y negativos difíciles, y posteriormente una versión dos con características adicionales de metadatos.

La configuración seleccionada fue la versión dos con negativos aleatorios. En evaluación obtuvo un Recall arroba diez de 0,3793 y un MRR arroba diez de 0,2166.

También observamos que el Recall arroba cien permanece alrededor de 0,5160. Esto significa que aproximadamente la mitad de las citas correctas no aparecen dentro de los cien candidatos iniciales y, por lo tanto, el reordenador no puede recuperarlas. Esta es una de las principales limitaciones identificadas.

## 2:30–3:15 — MLflow

[Mostrar capturas de MLflow]

Los experimentos se registraron en MLflow para conservar parámetros, métricas y evidencia de cada configuración.

Esto nos permitió comparar las variantes de forma trazable y seleccionar el modelo final con soporte experimental.

También se configuró MLflow en una instancia de AWS y se automatizó la conexión desde el entorno local para manejar cambios en la dirección IP pública de la instancia.

## 3:15–4:00 — Empaquetamiento y API

[Mostrar model-package y Swagger]

El modelo final se empaquetó como una librería Python instalable llamada modelo-citas.

De esta forma, el modelo no depende de ejecutarse únicamente dentro del repositorio original. Puede instalarse como paquete y ser utilizado por otros componentes.

FastAPI consume este paquete y expone la funcionalidad de recomendación mediante un servicio HTTP. En la documentación Swagger se puede ejecutar una consulta y obtener los artículos recomendados con sus puntuaciones.

## 4:00–5:00 — Tablero

[Mostrar tablero y ejecutar ejemplo real]

Sobre la API desarrollamos un tablero que permite escribir un contexto académico o cargar un ejemplo real del conjunto de datos.

Al ejecutar la consulta, el tablero solicita la recomendación a la API y presenta una lista ordenada de artículos candidatos.

Para cada resultado se muestran datos que permiten al usuario revisar la recomendación.

El sistema debe entenderse como una herramienta de apoyo a la búsqueda bibliográfica. La decisión final sobre si una referencia es pertinente sigue correspondiendo al usuario.

## 5:00–5:50 — Docker y despliegue

[Mostrar Docker Compose y evidencias AWS]

La API y el tablero fueron contenerizados con Docker y orquestados mediante Docker Compose.

Posteriormente desplegamos la solución en AWS y verificamos el funcionamiento de los servicios y una recomendación real.

También realizamos una auditoría desde un clon limpio del repositorio. Allí se comprobó la recuperación de datos mediante DVC, la instalación del paquete, la construcción de los contenedores y el funcionamiento de la solución sin depender del entorno de desarrollo original.

## 5:50–6:30 — Manuales y MLOps

[Mostrar manual de usuario y manual de instalación]

El repositorio incluye un manual de usuario y un manual de instalación.

La reproducibilidad se apoya en Git y GitHub para el código, DVC para datos, MLflow para experimentos, uv para dependencias, Tox y pytest para validación y Docker para empaquetamiento y despliegue.

Con esto buscamos que el resultado del proyecto no sea solamente un notebook o un modelo aislado, sino una solución que pueda reconstruirse y utilizarse.

## 6:30–7:10 — Trabajo en equipo

[Mostrar tabla de aportes del reporte e historial de commits]

El trabajo fue organizado mediante issues, ramas, commits y Pull Requests.

Las contribuciones quedan registradas en el repositorio e incluyen la línea base TF-IDF, reordenadores supervisados, experimentación con MLflow, versionamiento con DVC, maqueta, empaquetamiento del modelo, API, tablero, Docker, despliegue y documentación.

El reporte final incluye una tabla con los aportes verificables de cada integrante.

## 7:10–7:45 — Extensión de función de cita

[Opcional: mostrar carpeta annotations o prompts]

Como extensión del trabajo también preparamos un flujo para clasificar la función de una cita en nueve categorías.

Se versionaron tres estrategias de prompting, un parser común, métricas de evaluación y una primera validación manual por parte del equipo sobre veinte casos piloto.

Este resultado todavía se mantiene como provisional, porque falta una segunda validación manual independiente y el cálculo de acuerdo interanotador antes de denominarlo Test Gold definitivo.

## 7:45–8:15 — Cierre

[Mostrar tablero o portada final]

En conclusión, logramos construir una solución de recomendación local de citas que integra recuperación, reordenamiento y una infraestructura MLOps reproducible.

El modelo seleccionado mejora el ordenamiento de candidatos, pero la principal oportunidad de mejora sigue estando en la primera etapa de recuperación.

Como trabajo futuro, resulta especialmente importante incorporar representaciones semánticas más densas para aumentar la probabilidad de que la cita correcta aparezca dentro del conjunto inicial de candidatos.

Gracias.
