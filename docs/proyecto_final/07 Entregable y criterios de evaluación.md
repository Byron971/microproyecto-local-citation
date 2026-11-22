# Entregable y criterios de evaluación

El objetivo del despliegue es evidenciar que la solución propuesta ha sido integrada en una aplicación funcional y accesible, disponible en una plataforma computacional (por ejemplo, en la nube), y que permite su uso por terceros de manera controlada y reproducible. Se espera que el despliegue refleje buenas prácticas de ingeniería, considerando limitaciones reales como el tamaño del modelo, los recursos computacionales y la escalabilidad de la solución.

**A. Entregable.**

&#x20;Cada grupo deberá entregar un documento breve en formato Word o PDF que incluya:

* &#x20;Enlace al repositorio en GitHub del proyecto.
* &#x20;Enlace a la aplicación funcional desplegada (por ejemplo, API, interfaz web o servicio).

**B. Repositorio del Proyecto**

&#x20;El repositorio compartido debe estar organizado, documentado y ser reproducible. Como mínimo, debe incluir:

&#x20;1\. **Archivo README**, que contenga:

* &#x20;Descripción general del problema y de la solución propuesta.
* &#x20;Instrucciones básicas de uso.
* &#x20;Enlaces relevantes (aplicación desplegada, documentación adicional, datasets si aplica).
* &#x20;Dependencias y entorno de ejecución (por ejemplo, requirements.txt o environment.yml).
* &#x20;Pasos para reproducir el despliegue.
* &#x20;Ejemplos de uso (inputs/outputs esperados).
* &#x20;Consideraciones sobre el modelo (tamaño, requerimientos de hardware, tiempos de inferencia, etc.).
* &#x20;En caso de requerirse, credenciales de ejemplo o instrucciones para su configuración (sin exponer información sensible).

&#x20;2\. **Estructura mínima de carpetas:**

* notebooks/: cuadernos utilizados para análisis, entrenamiento y experimentación.
* modelos/: artefactos del modelo final (por ejemplo, .pkl, .h5, .pt).

**Nota:** Si el modelo es demasiado grande para ser almacenado en el repositorio, se deberá:

* Proporcionar un enlace de descarga (por ejemplo, almacenamiento en la nube).
* Incluir instrucciones claras para su carga o reconstrucción.

3\.  **Código de la aplicación** (por ejemplo, en una carpeta app/ o src/), que permita consumir el modelo (API, servicio o interfaz).

### **C. Consideraciones de despliegue**

Dado que algunos modelos pueden ser de gran tamaño o requerir recursos especializados (GPU, alta memoria), se valorará que los grupos:

* Justifiquen la estrategia de despliegue adoptada (por ejemplo, uso de APIs, servicios externos, o modelos optimizados).
* &#x20;Implementen soluciones que permitan el uso del sistema sin necesidad de cargar el modelo completo en entornos limitados.
* &#x20;Consideren aspectos como tiempos de respuesta, eficiencia y escalabilidad.

**D.  Interfaz de usuario orientada al usuario final.**

La solución desplegada debe contar con una interfaz funcional que permita la interacción con el sistema de manera clara y sencilla. No se requiere un desarrollo visual avanzado ni un diseño sofisticado, pero sí una interfaz pensada para el usuario final, con una organización lógica de los elementos, instrucciones breves de uso, etiquetas claras en entradas y salidas, y una presentación comprensible de los resultados. La interfaz debe facilitar la utilización de la solución y la interpretación de la información generada por el modelo.

### **E. Criterios de evaluación del despliegue**

| Criterio                                    | Descripción                                                                                                                                                                                                                                                                                                                                                                                            | Ponderación |
| :------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------- |
| Funcionamiento                              |  La solución se ejecuta correctamente en el entorno de despliegue y cumple con los requerimientos funcionales definidos. La aplicación permite realizar inferencias o ejecutar el flujo principal sin errores. En caso de modelos de gran tamaño, se implementan estrategias adecuadas (por ejemplo, carga diferida, uso de APIs o servicios externos) que garantizan el funcionamiento del sistema  . | 35          |
| Documentación del despliegue (README)       |  El repositorio incluye un archivo README completo y bien estructurado que describe el proyecto, las dependencias, el entorno de ejecución, los pasos para el despliegue y uso, así como ejemplos de entrada y salida. Se incluyen instrucciones claras para la gestión del modelo, especialmente si no está contenido directamente en el repositorio .                                                | 15          |
| Parametrización                             | El sistema permite ajustar parámetros de funcionamiento de la aplicación mediante archivos de configuración o variables de entorno claramente documentadas y bien organizadas.                                                                                                                                                                                                                         | 15          |
| Usabilidad / Presentación de la información |  La aplicación presenta una interfaz (web, API documentada u otra) clara, intuitiva y coherente. Los resultados son comprensibles para el usuario final, incluyendo explicaciones, visualizaciones o formatos adecuados. Se valora la claridad en la comunicación de los resultados del modelo y la experiencia general de uso.                                                                        | 35          |

**F. Recomendaciones adicionales**

* Asegúrense de que los enlaces funcionen correctamente y estén accesibles al momento de la evaluación. Para realizar esta, se le entregará a cada grupo la hora en la que deberán tener “abierto” el acceso.
* El documento Word o PDF debe incluir los nombres de los integrantes y el nombre del proyecto.
* Si la aplicación tiene acceso restringido, incluyan las credenciales de prueba necesarias.
* El repositorio debe ser público o accesible con permisos.

