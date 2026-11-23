# Búsqueda del catálogo completo en el paso 2

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

Pendiente de completar y comprobar públicamente. La evidencia local no se presenta como aceptación del despliegue.

## Checklist del proyecto

- [x] Implementación y comprobación local del catálogo completo en el paso 2.
- [ ] Publicación y aceptación pública de esta ampliación.
- T01–T03: entregas anteriores publicadas; ampliación actual pendiente de aceptación pública.
- T04: pendiente por cuota Serverless. T05–T06: suspendidas por QLoRA.
- T07–T08: M/S y comercial; familia abierta suspendida. T09: publicada y aceptada.
- T10: parcial; no se amplía ni se cierra en esta tarea.
- T11: aceptación histórica M/S y comercial; nueva comprobación pública pendiente.
- T12: migración/retirada pendientes; ECS se conserva. T13: cierre final pendiente.
