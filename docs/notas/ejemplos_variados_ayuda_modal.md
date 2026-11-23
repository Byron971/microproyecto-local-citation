# Ejemplos variados y ayuda en modal

## Hallazgo y decisión actual

El usuario pide variar los ejemplos, unificar sus acciones, situar «Explorar ejemplos» junto a «Siguiente: artículo», revisar la instrucción del campo y abrir la ayuda desde la cabecera en un modal.

La selección anterior tenía 33 contextos para nueve artículos, todavía limitada al catálogo inicial de 37: 16 contextos correspondían a un mismo artículo y la ordenación alfabética agrupaba repeticiones. La comprobación actual sobre el catálogo ampliado encontró 9.357 contextos elegibles de validación en 2.196 artículos preparados, después de excluir train, test y los IDs reservados en los archivos Gold disponibles. Es un universo de selección de ejemplos, no un nuevo conjunto científico ni una medida de calidad.

Se publica una selección editorial acotada de **40 contextos de 40 artículos**, un contexto por artículo, intercalando ocho subtemas de PLN: sentimientos, resumen, preguntas/diálogo, sintaxis/morfología, semántica, extracción de información, recursos/evaluación y traducción. La primera página contiene los ocho subtemas. Son áreas del corpus ACL-200; no se afirma cobertura de disciplinas ajenas a PLN. Los temas orientan la lectura y búsqueda; no son funciones predichas ni acreditan balance científico.

`config/ui_example_articles.json` identifica los artículos elegidos. `scripts/exportar_ejemplos_cientificos.py` usa ahora el catálogo completo, exige texto preparado y mantiene las exclusiones existentes. Prefiere prosa con menos caracteres de extracción no habituales y conserva literalmente `masked_text`, IDs, título y citante. No reescribe ni corrige los textos: siguen siendo extractos originales y pueden empezar/terminar a mitad de una oración. Exporta hashes de fuentes, catálogo, selección y archivos de exclusión. No incluye etiquetas de función, predicciones ni fragmentos calculados.

## UI y patrones

- Se elimina «Usar ejemplo público» y su estado asociado del producto. La única acción es «Explorar ejemplos», secundaria y alineada con la acción principal, también en móvil. Las pruebas de integración conservan un contexto sintético como fixture escrito en el campo, no como acción de usuario.
- El modal conserva búsqueda y diez ejemplos por página: **10/10/10/10**. El tema, artículo y procedencia ACL-200/validación son visibles. Cargar un ejemplo solo carga contexto, reinicia recorrido/modelo/consentimiento y exige confirmar artículo después; no infiere.
- La instrucción cambia a «Pega el párrafo que contiene la cita». Aclara que se necesita contexto y evita repetir los formatos de referencia ya ilustrados en el placeholder. Se conservan selección de referencia y mensajes de validación.
- «Ayuda» pasa de ancla a botón de apertura de `HelpDialog`. Se retira el desplegable aislado al final. El modal usa la superficie, cabecera, bordes, fondo atenuado y cierre de los ejemplos, y organiza el recorrido en cuatro pasos, marcado de cita e interpretación.
- Patrón [modal W3C](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/): diálogo nativo con `showModal`, contenido exterior inerte, título asociado y enfocado al abrir, foco contenido con Tab/Mayús+Tab, Escape y botón de cierre de 44 px. Devuelve el foco a Ayuda. No aplica `aria-describedby` a todo el contenido estructurado. La cabecera y cierre se conservan visibles mientras el cuerpo se desplaza en pantallas pequeñas.
- Abrir/cerrar ayuda conserva contexto, etapa, modelo y consentimiento; no inicia solicitudes. Se mantiene la identidad visual. Se ajustó el cierre para ignorar el evento de un cierre anterior si el diálogo ya fue reabierto durante el montaje de desarrollo.

## Comprobación local

Build TypeScript/Vite aprobado, 41 pruebas unitarias frontend y dos pruebas Python de integridad de ejemplos aprobadas. Estas contrastan textos originales, val, exclusiones train/test/Gold, títulos, cobertura preparada, artículo único y huellas de selección. La exportación se regeneró tras dar formato al manifiesto para que su hash refleje los bytes definitivos.

92 recorridos de interfaz distintos en escritorio/móvil: 90 aprobaron en la ejecución completa y dos aserciones esperaban todavía la instrucción anterior. Se actualizaron al texto solicitado; los diez recorridos afectados de usabilidad, ejemplos y ayuda se repitieron y aprobaron tras el refinamiento final. Se comprobó búsqueda, paginación, carga solo de contexto, reinicio, navegación, espera/resultados, errores y consentimiento. Las dos pruebas reales se adaptaron a introducir el fixture y a la selección manual, sin ejecutarlas.

Capturas de acciones alineadas, ejemplos variados, ayuda y su parte inferior revisadas en escritorio/móvil. Se amplió la altura máxima de la ayuda y se quitó su subtítulo redundante para facilitar la lectura. Evidencia local separada: `artifacts/context-help-final-local/` y `artifacts/context-help-acceptance-local/`. Los intentos previos de ajuste del modal no son aceptación. Todas las respuestas de modelos en estas pruebas son simuladas; no se consumió inferencia comercial.

## Publicación y checklist

Pendiente de publicar y registrar comprobación pública. Las pruebas locales no prueban el estado público actual. Una consulta real de metadatos, en dos lotes de veinte IDs, confirmó disponibilidad de los 40 artículos con la misma versión de corpus, sin inferencias. Evidencia: `artifacts/context-help-availability-public.json`. La aceptación del nuevo frontend sigue pendiente de publicar.

- [x] 40 contextos originales, 40 artículos y ocho subtemas intercalados.
- [x] Exclusiones y procedencia contrastadas; sin cambio de modelos, corpus ni particiones.
- [x] Una acción «Explorar ejemplos», junto a Siguiente; paginación de diez.
- [x] Instrucción breve orientada al párrafo de contexto.
- [x] Ayuda modal con teclado/foco, conservación de datos y capturas locales.
- [x] Build, 41 pruebas unitarias, dos comprobaciones de integridad y 92 recorridos locales distintos.
- [ ] Publicación frontend y confirmación de HTML, salud y servicios actuales.
- [ ] Recorridos públicos con mocks y capturas revisadas.

Estado general: T01–T03 disponibles; T04 pendiente por cuota; T05–T06 suspendidas por QLoRA; T07–T09 disponibles para M/S y comercial, familia abierta suspendida; T10 parcial; T11 conserva la aceptación real anterior; T12 migración/retirada pendiente sin retirar ECS; T13 notas actualizadas y cierre final pendiente. El proyecto global continúa parcialmente cumplido.
