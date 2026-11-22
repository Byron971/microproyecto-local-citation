# Publicación del recorrido disponible

Alcance autorizado: publicar la interfaz y servicios actuales, con M/S como
familia disponible. QLoRA queda oculto y suspendido; no se modifican modelos.
El comercial sigue pendiente de integración.

## Seguimiento

- T01–T03: completadas; se publica su código actual.
- T04: pendiente de cuota Serverless; continúa el servicio M/S en ECS.
- T05–T06: suspendidas por decisión del usuario.
- T07–T08: pendientes; parte QLoRA suspendida.
- T09: integración comercial pendiente.
- T10: seguridad y configuración completa pendientes.
- T11: aceptación completa de tres familias pendiente; esta entrega cubre M/S.
- T12: migración pendiente; no se retira el servicio actual.
- T13: documentación final pendiente; este registro cubre esta publicación.

## Operación

La construcción y subida de imágenes se ejecuta en la EC2 existente mediante
`make release-build`, sin trasladar pesos ni imágenes grandes desde el equipo.
Los permisos de publicación se gestionan con Terraform. El despliegue de ECS
se revisa mediante un plan Terraform y conserva los servicios anteriores hasta
que las tareas nuevas estén listas. La web se publica con `make publish-frontend`.
Las rutas públicas y el recorrido artículo → Top-3/función deben comprobarse
antes de declarar publicada la entrega M/S.
