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

## Publicación realizada

Web: https://proyectocitas-grupo19.click
API: https://api.proyectocitas-grupo19.click

Código de las imágenes: 314f48885398beac629fee166e91a0660ebb3b08.
API: revisión ECS citas-api:2; M/S: citas-api-science:4. Ambos servicios
quedaron con una tarea, despliegue COMPLETED y las imágenes previstas, sin
reversión automática. Los parámetros SSM existentes se importaron a Terraform
para actualizar los punteros y los servicios en el mismo plan. No se crearon
recursos QLoRA ni se cambiaron pesos, ajustes o entrenamiento.

La publicación encontró un error previo en Makefile: las variables de shell
usaban un solo dólar y Make alteraba el bucket y la URL del API. Se corrigió
el escape; el segundo intento publicó assets antes del index en el bucket
correcto e invalidó index.html en CloudFront. Se confirmó que el index público
coincide con el compilado local.

Comprobaciones terminadas:

- Terraform válido y plan limitado a punteros, revisiones ECS y ruta científica.
- 15 pruebas de contratos/API/despliegue, con seis subpruebas, aprobadas.
- 32 pruebas unitarias de frontend aprobadas; build de producción aprobado.
- 32 pruebas de recorrido y errores en escritorio/móvil aprobadas.
- Dos recorridos reales contra la web publicada, sin mocks: escritorio y móvil.
- El ejemplo W05-0821 muestra tres fragmentos, función y enlaces; QLoRA no aparece.
- El POST público de artículo respondió en 9,542 s para el contexto sintético de
  la comprobación de API. Los tiempos de los casos completos de navegador fueron
  15,2 s y 28,8 s; incluyen navegación y controles, no son latencias del modelo.
- Capturas de ambas pantallas revisadas, sin sobreancho horizontal.

La comprobación antigua de integración exigía búsqueda global, retirada del
recorrido en T01. Se actualizó para consultar disponibilidad y analizar el
artículo conocido. No se habilitó la búsqueda global para hacer pasar la prueba.
Los informes detallados quedan en artifacts/ (fuera de Git). No son evaluación
académica ni certificación de calidad. Los límites para artículos largos de T03
siguen pendientes de T10/T11. Esta publicación no completa la entrega de tres
familias ni la migración de infraestructura.

## Comandos de la publicación

1. `make release-build AWS_PROFILE=josezambrana` y `make release-build-result`.
2. `make release-prepare AWS_PROFILE=josezambrana`.
3. `make release-plan AWS_PROFILE=josezambrana RELEASE_VARS=artifacts/release.tfvars.json`.
4. Revisar plan; `make release-apply AWS_PROFILE=josezambrana` y `make release-wait AWS_PROFILE=josezambrana`.
5. `make release-check AWS_PROFILE=josezambrana`.
6. `make publish-frontend AWS_PROFILE=josezambrana`.
7. `make release-confirm AWS_PROFILE=josezambrana`.
8. `make release-web-check` con Chromium disponible para Playwright.

Para reversión, generar y revisar otro plan mediante release-plan usando
artifacts/release-rollback.tfvars.json, y aplicarlo mediante release-apply.
No reutilizar un plan anterior ni actualizar ECS manualmente.
