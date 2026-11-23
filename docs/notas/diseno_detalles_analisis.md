# Diseño de los detalles del análisis

## Problema y decisión

El panel mostraba párrafos técnicos, identificadores y hashes con la misma jerarquía que el método y los fragmentos. La solicitud posterior del usuario pide mejorar su lectura mediante patrones UI. Se conservan las tres pestañas, Puntuación inicial, el Top-3 y las dos tareas del problema: recuperación dentro del artículo confirmado y clasificación de la cita.

Se utiliza una superficie blanca con secciones y separación discreta. Un resumen distingue recuperación SciBERT y clasificación seleccionada. Una tabla semántica relaciona cada fragmento con la sección real del artículo y su similitud coseno; los enlaces llevan al fragmento correspondiente y permiten enfocarlo. La similitud no se presenta como porcentaje de acierto.

El alcance del recorte permanece visible cuando corresponde. En el comercial se identifican proveedor, modelo efectivo e información enviada. CPU, tokens, revisión completa, método interno, IDs, perfiles, ajuste PH y advertencias originales se conservan en «Ver detalles técnicos», cerrado inicialmente. Esta divulgación progresiva sustituye la decisión anterior de mostrar todos esos datos directamente dentro de la pestaña; no modifica modelos ni respuestas.

Se mantiene la identidad visual. Resumen en dos columnas en escritorio y una en móvil, tabla sin desbordamiento, cadenas técnicas divisibles, encabezados de fila/columna, títulos asociados y controles con teclado/foco visible. No se realiza inferencia al abrir pestañas, desplegar detalles ni seguir enlaces internos.

## Evidencia local

Build TypeScript/Vite correcto y 41 pruebas unitarias aprobadas. La regresión comprende 88 casos de escritorio/móvil: 86 pasaron inicialmente y dos necesitaron precisar un selector que coincidía con el nuevo enlace de fragmento; ambos pasaron al repetirlos con el selector limitado al Top-3. No se modificó el comportamiento asíncrono.

Los seis casos específicos M/S/comercial verifican resumen, tabla, enlace/foco al fragmento, metadatos plegados, teclado y ausencia de inferencias adicionales. Capturas de escritorio y móvil revisadas, incluido recorte de artículo y comercial. Evidencia: `artifacts/friendly-details-final-local/` y `artifacts/friendly-details-selector-correction/`. Todas las respuestas de modelos utilizadas en estas pruebas son mocks.

## Publicación

Pendiente de comprobar y registrar tras publicar exclusivamente el frontend. Las comprobaciones locales no prueban el estado público ni la calidad científica.

## Checklist

- [x] Resumen legible y distinción entre recuperación y clasificación.
- [x] Tabla de fragmentos, secciones y similitudes con enlaces internos.
- [x] Recorte y datos del proveedor conservados; metadatos avanzados plegados.
- [x] Teclado, capturas escritorio/móvil y regresión local con mocks.
- [ ] Publicación frontend y comprobación del HTML y servicios actuales.
- [ ] Recorridos de la UI publicada con mocks y capturas revisadas.

El estado general continúa parcial: T01–T03 disponibles; T04 pendiente de cuota; T05–T06 suspendidas por QLoRA; T07–T09 disponibles para M/S y comercial, familia abierta suspendida; T10 parcial; T11 conserva la aceptación real anterior; T12 migración/retirada pendiente, sin retirar ECS; T13 notas actualizadas y cierre final pendiente. Esta mejora no acredita validación científica adicional.
