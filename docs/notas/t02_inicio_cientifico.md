# T02 — Inicio científico y retiro de rutas públicas heredadas

Estado: implementada y validada localmente; no publicada en AWS.

La portada usa ScientificAnalysis: contexto, selección de referencia en el texto,
artículo preparado identificado por título e ID, y variante M/S. Envía únicamente
contexto e ID a POST /api/analisis-cita-ms/articulo. Reutiliza ScientificResults,
mostrando la variante elegida y aclarando que el backend calcula ambas.

El catálogo articleCatalog.json contiene solo títulos, IDs y enlaces públicos;
version_contenido es el SHA-256 del corpus config/corpus_ms.json de esta entrega.
Debe regenerarse junto con el corpus. No recomienda artículos por similitud.
La disponibilidad real del servicio y los ejemplos públicos corresponden a T03.

Las rutas /datos, /modelo, /negativos, /fragmentos, /funcion, /funcion-b y
/analisis-ms redirigen al inicio con replace. Sus componentes y APIs se conservan
para evidencia/reutilización, sin importarlos en el recorrido público.
Las pruebas previas application.spec.ts se conservaron en application.legacy.ts,
fuera del patrón ejecutable de Playwright. live-api.spec.ts mantiene la comprobación
real de APIs históricas, ajustando su navegación a la redirección vigente.

Aceptación local: npm run build aprobado; 32 pruebas unitarias aprobadas;
18 comprobaciones Playwright en escritorio y móvil aprobadas con Chrome instalado
(PLAYWRIGHT_CHROMIUM_EXECUTABLE). Prueban marcado de cita, envío por artículo,
variante elegida, resultados obsoletos al editar, ausencia de consultas al ranking,
redirecciones y validación de longitud/marcas antes de inferir. El transporte
científico de estas pruebas de UI es simulado; no constituye inferencia pública
real ni aceptación de T03/T11. Capturas de escritorio/móvil revisadas, sin
sobreancho horizontal. No se desplegó ni se modificaron recursos AWS.
