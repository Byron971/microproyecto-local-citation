# Búsqueda del catálogo completo en el paso 2

> Registro histórico de esta entrega. La ampliación de texto preparado, el recorte autorizado y las sugerencias automáticas posteriores se siguen en [ampliación de cobertura](ampliacion_cobertura_corpus.md); las restricciones anteriores de 37 artículos y botón manual quedan sustituidas por esa decisión.


## Decisión y alcance

El usuario solicita ampliar la búsqueda a todos los artículos disponibles, dentro del paso 2. Esta decisión sustituye el límite de 37 documentos del selector anterior; no crea una pantalla independiente ni recupera fragmentos de otro artículo.

- Filtro literal por título/ID sobre los 19.776 artículos del índice local existente.
- Sugerencias explícitas SciBERT sobre título/resumen de ese catálogo, cinco candidatos y selección manual. Ninguna inferencia automática al escribir o entrar a la etapa.
- Catálogo en páginas de cinco; ejemplos conservan diez por página.
- Las tarjetas distinguen texto preparado y pendiente. La disponibilidad se confirma con el servicio al seleccionar. Un artículo sin texto no habilita clasificación; se conserva el contexto.
- Continúan 37 artículos con texto preparado. Solo se prepararon 38, no se auditó la cobertura de texto completo de los otros miles. No se promete Top-3 para todo el catálogo.

## Implementación y reproducibilidad

`scripts/exportar_catalogo_completo.py` verifica el hash de los metadatos del índice ya calculado y genera `frontend/src/fullArticleCatalog.json`. Incluye títulos, IDs, enlaces, estado preparado y resúmenes del subconjunto preparado; los resúmenes de las sugerencias llegan en su respuesta. El JSON se descarga solo al entrar al paso 2 y se conserva en memoria. Si falla permite reintentar y conserva el catálogo preparado.

`catalog_article_search` reutiliza `ArticleSearch`, la matriz existente de 19.776 × 768 y el encoder cargado. Valida integridad y coincidencia de los 37 documentos preparados con el corpus. La respuesta identifica tanto el corpus como el hash del catálogo; la web rechaza versiones distintas e IDs desconocidos.

El índice completo se distribuye mediante el publicador existente y el nuevo target `make catalog-index-release AWS_PROFILE=josezambrana`. El inventario fijado es `config/catalog_search_release.json`. No se habilita `MS_ENABLE_GLOBAL_SEARCH`. El arranque descarga y verifica el índice; un fallo deja M/S y la búsqueda literal operativos, con sugerencias no disponibles. Se requiere una nueva imagen científica para este cambio; API comercial, pesos y corpus se conservan.

## Comprobaciones locales

- Build TypeScript/Vite correcto, 38 pruebas unitarias frontend aprobadas.
- 45 pruebas backend aprobadas en los entornos existentes (18 científicas/arranque/corpus/concurrencia y 27 API/comercial).
- 70 recorridos completos de regresión aprobados; los 20 casos del selector final se repitieron y aprobaron tras los últimos ajustes. Cobertura total: 74 recorridos distintos de escritorio/móvil.
- Filtro y sugerencias con artículos fuera de los 37, falta de texto, selección manual, cancelación, ocupado, versiones, IDs desconocidos y recuperación de carga del catálogo.
- Capturas de escritorio/móvil revisadas en `artifacts/full-catalog-final/` y siguientes carpetas del selector. Sin desbordamiento horizontal.
- Una consulta local real con SciBERT en caché, sin red ni descargas, devolvió cinco candidatos del catálogo completo. Evidencia: `artifacts/full-catalog-local-real.json`. No demuestra relevancia científica.
- No se ejecutaron llamadas comerciales reales.

## Publicación

Publicada y aceptada en https://proyectocitas-grupo19.click.

- Código científico/frontend: `3d055edeb407560c07e34817cb2f91fb83c2f508`.
- Imagen científica: `sha256:5b1520a91ac3be8db5d783488cb9fe23812f48759362792575cb99809984879d`; ECS `citas-api-science:6` estable.
- API conservada en `citas-api:5`, código `c01b43f04f52806bf5f2948f7b1bd2c56c89dde7`. Pesos y corpus sin cambios.
- Índice `search-scibert-994412ffe3a831d3`: 85.443.204 bytes publicados y contrastados desde S3 mediante `make catalog-index-release`, sin recalcular embeddings. No se habilitó `MS_ENABLE_GLOBAL_SEARCH`.
- Plan Terraform revisado: solo puntero de imagen científica, definición de tarea y servicio científico. En el contenedor solo cambió la imagen; ECS normalizó listas vacías. Punteros previos guardados para reversión.
- `make article-search-check`: una consulta real devolvió cinco candidatos del catálogo de 19.776; IDs, títulos, resúmenes y versiones contrastados con el índice existente. Evidencia nueva: `artifacts/full-catalog-public.json`.
- `make article-search-web-check`: cuatro recorridos públicos reales aprobados, escritorio/móvil; sugerencias sin selección automática y búsqueda/selección fuera de los 37, con disponibilidad real y bloqueo del clasificador sin texto. Capturas revisadas en `artifacts/full-catalog-live/`.
- Dos casos públicos adicionales con API simulada comprobaron fallo/reintento de carga del catálogo y conservación de los preparados. Evidencia: `artifacts/full-catalog-retry-public/`; no son inferencias reales.
- `make release-web-check`: dos recorridos M/S reales aprobados, escritorio/móvil; textos Top-3 contrastados con el corpus del artículo confirmado. Evidencia nueva: `artifacts/full-catalog-ms-web/`.
- `make release-confirm`: API y científico estables, salud HTTP correcta y HTML público idéntico al build. SHA-256 de index: `ae25c08fee87b4f7d06495e6b933e1302c09f93a097f92330cc4bc42b1f6e65a`. Copia de la confirmación: `artifacts/full-catalog-release-confirmation.json`.
- Frontend publicado mediante Make usando outputs actuales de `make release-status`. Los targets permiten elegir nuevas carpetas de evidencia para conservar las anteriores.
- EC2 `i-03c35e1f2d0597f9f` encendida y detenida mediante Terraform/targets `builder-power-*`; estado final `stopped` comprobado. Instancia y disco conservados.
- No se ejecutaron llamadas comerciales reales. Esta aceptación acredita integración y funcionamiento, no relevancia científica de las sugerencias.

## Checklist del proyecto

- [x] Implementación y comprobación local del catálogo completo en el paso 2.
- [x] Publicación y aceptación pública de esta ampliación.
- T01–T03: publicadas y aceptadas, incluida esta ampliación del paso 2.
- T04: pendiente por cuota Serverless. T05–T06: suspendidas por QLoRA.
- T07–T08: M/S y comercial; familia abierta suspendida. T09: publicada y aceptada.
- T10: parcial; no se amplía ni se cierra en esta tarea.
- T11: M/S y comercial aceptados; selector completo y regresión M/S comprobados públicamente. Familia abierta suspendida.
- T12: migración/retirada pendientes; ECS se conserva. T13: cierre final pendiente.
