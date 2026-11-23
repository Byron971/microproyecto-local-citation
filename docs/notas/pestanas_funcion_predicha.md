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

Pendiente de publicar exclusivamente frontend con `make publish-frontend`, outputs actuales de `make release-status` y confirmar HTML/bundle y controles publicados. La verificación visual de la web usará respuestas simuladas: no se requieren nuevas inferencias para este cambio de presentación. La aceptación científica real anterior se conserva como evidencia histórica, sin repetirla ni atribuirla a esta tarea.

## Checklist

- [x] Tres pestañas y puntuación inicial en M/S y comercial.
- [x] Ayuda y detalles completos; proveedor integrado y Top-3 conservado.
- [x] Teclado, panel único y cambio sin inferencia comprobados con mocks.
- [x] Capturas locales de escritorio y móvil revisadas.
- [ ] Publicación frontend, HTML público y UI publicada con mocks verificados.

T01–T03 conservan el recorrido publicado; T04 pendiente; T05–T06 suspendidas; T07–T09 M/S/comercial disponibles con familia abierta suspendida; T10 parcial; T11 conserva aceptación real anterior; T12 pendiente; T13 notas actualizadas con cierre final pendiente. El proyecto global sigue parcialmente cumplido.
