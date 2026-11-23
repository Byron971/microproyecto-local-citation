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

Publicado únicamente el frontend del commit `d8ac7d6` mediante `make publish-frontend`, con outputs actualizados y verificados desde `make release-status`. `make release-confirm` comprobó servicios estables, imágenes previstas, salud HTTP, identidad del corpus y HTML público idéntico al build. SHA256 de `index.html`: `9ecbe806e575de98508b0e6ddc6e9fb08de21735293e3e55cb90fa09c4349563`. API conservada en `citas-api:7`; científico en `citas-api-science:9`. No se construyeron imágenes backend ni se encendió la constructora.

Los seis recorridos M/S/comercial de escritorio/móvil aprobaron sobre la web publicada, con respuestas API simuladas. Se revisaron capturas públicas del panel en escritorio/móvil; se conservan las capturas de puntuación, ayuda y detalles técnicos abiertos. Esto comprueba UI e interacción del bundle público; no es una nueva ejecución ni aceptación científica o comercial real. No se consumió cuota de inferencia. Evidencia: `artifacts/friendly-details-public-mocks/`, incluida copia de la confirmación de despliegue.

## Checklist

- [x] Resumen legible y distinción entre recuperación y clasificación.
- [x] Tabla de fragmentos, secciones y similitudes con enlaces internos.
- [x] Recorte y datos del proveedor conservados; metadatos avanzados plegados.
- [x] Teclado, capturas escritorio/móvil y regresión local con mocks.
- [x] Publicación frontend y comprobación del HTML y servicios actuales.
- [x] Recorridos de la UI publicada con mocks y capturas revisadas.

El estado general continúa parcial: T01–T03 disponibles; T04 pendiente de cuota; T05–T06 suspendidas por QLoRA; T07–T09 disponibles para M/S y comercial, familia abierta suspendida; T10 parcial; T11 conserva la aceptación real anterior; T12 migración/retirada pendiente, sin retirar ECS; T13 notas actualizadas y cierre final pendiente. Esta mejora no acredita validación científica adicional.

## Homogeneización posterior

La pestaña Ayuda pasa a llamarse «Funciones de cita» y reutiliza la superficie visual de Detalles. Véase [guía de funciones](guia_funciones_cita.md) para el alcance y la evidencia correspondiente a esa entrega.
