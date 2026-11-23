# Pestañas de la función predicha

## Decisión y alcance

Solicitud del usuario: reunir en tres pestañas la puntuación como contenido principal, los detalles del análisis y la ayuda sobre las nueve funciones. Esta organización reemplaza los desplegables de esa sección; no altera la lista de progreso de cuatro etapas ni añade una pantalla.

- **Puntuación**, activa por defecto: función predicha, explicación breve, barras y advertencias de interpretación existentes.
- **Detalles del análisis**: recuperador, revisión, dispositivo, entrada AB, fragmentos, recorte y ajustes existentes. Para el comercial también incluye proveedor, modelo efectivo, perfil y hash de instrucciones, sin otro desplegable.
- **Ayuda**: contenido completo de «Qué significan las nueve funciones».

Los tres fragmentos y sus fuentes permanecen visibles fuera de las pestañas. El cambio es exclusivamente frontend: modelos, corpus, API, inferencia asíncrona, consentimiento y controles de consumo se conservan. No acredita calidad científica ni completa la familia abierta suspendida.

## Accesibilidad y comprobación local

Semántica `tablist`/`tab`/`tabpanel`, relaciones de IDs únicas, estado seleccionado, un único panel visible y foco de teclado itinerante. Flechas izquierda/derecha, Inicio y Fin activan y enfocan; Tab permite entrar al panel. Los controles tienen al menos 48 px de alto y conservan identidad visual y foco visible. No se hacen nuevas solicitudes al cambiar de pestaña.

Build correcto y 41 pruebas unitarias aprobadas. 86 recorridos de regresión de escritorio/móvil aprobados; los seis casos específicos de pestañas M, S y comercial se comprobaron con mocks en ambos tamaños. Se revisaron capturas de puntuación, detalles y ayuda; sin desbordamiento horizontal. Evidencia: `artifacts/result-tabs-local/` y `artifacts/result-tabs-final-local/`. Las llamadas comerciales están simuladas.

## Publicación

Publicación exclusivamente frontend mediante `make publish-frontend`, utilizando los outputs recién obtenidos y contrastados desde `make release-status`. `make release-confirm` comprobó servicios estables, imágenes conservadas, salud, versión del corpus y HTML público idéntico al build. La aceptación científica real anterior se conserva como evidencia histórica, sin repetirla ni atribuirla a esta tarea.

Los seis casos de pestañas M/S/comercial aprobaron sobre la web publicada en escritorio/móvil, con respuestas API simuladas. Se revisaron capturas de esos paneles, foco y ajuste móvil; no hubo solicitudes reales a los modelos. Esto comprueba presentación e interacción del bundle público, no una nueva aceptación de inferencia científica o comercial. Evidencia: `artifacts/result-tabs-public-mocks/`, incluida una copia de la confirmación de despliegue.

Código frontend: `f3d3e72`. SHA256 de `index.html`: `16ef5fb25a6215c292394ecf510573bbc58831aa086b7b86e0cf84528ec39afa`. API conservada en `citas-api:7` (`eb0d14e`), científico en `citas-api-science:9` (`e84fd3a`); no se construyeron imágenes backend ni se encendió la constructora. Los archivos del equipo permanecen sin seguimiento.

## Checklist

- [x] Tres pestañas y puntuación inicial en M/S y comercial.
- [x] Ayuda y detalles completos; proveedor integrado y Top-3 conservado.
- [x] Teclado, panel único y cambio sin inferencia comprobados con mocks.
- [x] Capturas locales de escritorio y móvil revisadas.
- [x] Publicación frontend, HTML público y UI publicada con mocks verificados.

T01–T03 conservan el recorrido publicado; T04 pendiente; T05–T06 suspendidas; T07–T09 M/S/comercial disponibles con familia abierta suspendida; T10 parcial; T11 conserva aceptación real anterior; T12 pendiente; T13 notas actualizadas con cierre final pendiente. El proyecto global sigue parcialmente cumplido.

## Refinamiento posterior

La solicitud posterior de mejorar la lectura introduce resumen, tabla de fragmentos y un desplegable interno para metadatos avanzados. Sustituye la presentación plana descrita arriba; las tres pestañas permanecen. Véase [diseño de los detalles del análisis](diseno_detalles_analisis.md) para implementación y evidencias actuales.
