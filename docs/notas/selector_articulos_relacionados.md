# Selector de artículos relacionados — 22/11/2026

> Registro histórico de esta entrega. La ampliación de texto preparado, el recorte autorizado y las sugerencias automáticas posteriores se siguen en [ampliación de cobertura](ampliacion_cobertura_corpus.md); las restricciones anteriores de 37 artículos y botón manual quedan sustituidas por esa decisión.


## Decisión y relación con el problema

La petición actual sustituye la decisión de utilizar exclusivamente un filtro literal. El problema sigue requiriendo recuperar tres fragmentos del artículo citado y clasificar la función de la cita (propuesta, sección 5). Encontrar candidatos ayuda a identificar ese artículo; no sustituye su confirmación ni demuestra calidad científica del recomendador.

1. Contexto: se mantienen inglés, una marca TARGETCIT y límite de 4.000 caracteres. No se buscan artículos al escribir ni cargar ejemplos.
2. Artículo: búsqueda literal por título/ID y acción opcional «Sugerir según mi contexto». Cinco candidatos por consulta; catálogo manual en páginas de cinco. Tarjetas con título, ID, extracto del resumen y enlace a publicación; selección explícita, confirmación de disponibilidad y opción «Cambiar artículo». Se elimina el desplegable y la repetición del título.
3. Clasificador: conserva M/S y comercial con consentimiento. Las sugerencias usan SciBERT, no OpenAI. La búsqueda y el análisis comparten el bloqueo existente; ocupado devuelve 429, sin reintentos automáticos. El navegador permite cancelar la espera y continuar manualmente; cancelar no garantiza detener un cálculo ya iniciado en servidor.
4. Resultados: el Top-3 continúa restringido al artículo confirmado. Cambiarlo invalida resultados; se conserva el contexto. No se muestran similitudes como probabilidades ni se añaden pantallas independientes.

Se conserva la navegación con checklist, desbloqueada tras completar un análisis, y el modal de ejemplos de diez en diez.

## Reutilización e identidad

`exportar_busqueda_preparada.py` selecciona exactamente las filas existentes para los 37 documentos del corpus. Comprueba hashes de origen, revisión SciBERT, títulos, resúmenes e identidad del catálogo. No genera embeddings nuevos ni modifica pesos. El manifiesto derivado conserva la procedencia del índice original; vectores float32 de 37 × 768, 113.792 bytes incluyendo cabecera NumPy. El arranque valida hashes, forma, normalización e identidad del corpus. La ausencia o corrupción de sugerencias deja operativo M/S y el filtro local.

Se reutilizan `ArticleSearch`, el encoder ya cargado y `/api/analisis-cita-ms/recomendar`. La imagen científica necesita incorporar el índice reducido y el arranque; la imagen API y los manifiestos de modelos/corpus se conservan. Construcción exclusiva M/S mediante `make release-build-ms`, EC2 existente controlada por Terraform, publicación mediante targets de release. No habilitar `MS_ENABLE_GLOBAL_SEARCH`.

## Aceptación comprobada localmente

- 39 pruebas backend aprobadas, una omitida por requerir dependencias de modelos en ese entorno; cubren concurrencia, integridad, arranque y contratos existentes.
- 32 pruebas unitarias frontend aprobadas y build TypeScript/Vite correcto.
- 54 recorridos de regresión de interfaz aprobados en escritorio/móvil; 12 nuevos recorridos verifican petición explícita, paginación, confirmación por teclado, ocupado, indisponibilidad, catálogo incompatible y cancelación.
- Una consulta sintética con SciBERT real en caché devolvió cinco artículos del corpus preparado; no se descargaron modelos.
- Capturas de escritorio y móvil revisadas, sin desbordamiento horizontal; acción explícita de selección visible y foco en el artículo confirmado.
- Las pruebas comerciales de presentación emplean mocks, sin consumo adicional de OpenAI.

## Publicación y aceptación pública

- Código científico: `53a4ab5cb1fbf461aebb9d6bc1c4fbde76d0f188`; ajustes de interfaz y comprobaciones: `ecfdb21`.
- Servicio científico activo: `citas-api-science:5`, digest `sha256:79e9637ec89cea93e24cbaccd9661887c088f1a919bdd94ea48184042f61ff46`.
- API conservada: `citas-api:5`, imagen `release-api-c01b43f04f52806bf5f2948f7b1bd2c56c89dde7`.
- Manifiesto M/S y corpus idénticos a la versión previa; no hay entrenamiento, cambio de pesos ni validación científica nueva.
- `make article-search-check`: respuesta real con cinco IDs únicos del catálogo de 37, títulos y resúmenes contrastados; títulos comparados normalizando saltos de línea heredados.
- `make article-search-web-check`: dos recorridos reales aprobados, escritorio/móvil; candidatos visibles sin selección automática, confirmación de un artículo y disponibilidad antes de avanzar al clasificador.
- `make release-web-check`: dos recorridos M/S reales aprobados; los tres textos recuperados coinciden con el corpus del artículo seleccionado. Capturas públicas de sugerencias revisadas en ambos tamaños.
- `make release-confirm`: servicios estables, imágenes previstas, salud HTTP y HTML público idéntico al build; hash de index `a84c21c3248b03352edcd74034b2065d32ff0e19fc739c4fd518812a54bafe47`.
- EC2 constructora detenida mediante Terraform, sin reemplazar instancia ni borrar disco. Solo se modificaron puntero de imagen científica, definición de tarea y despliegue del mismo servicio; ECS normaliza algunas listas vacías al devolver la definición.
- Publicación frontend mediante `make publish-frontend` y archivo de outputs públicos recién obtenido de `make release-status`; no fue necesario leer directamente el estado S3 en esta entrega.
- No se ejecutaron inferencias comerciales adicionales. Estas comprobaciones acreditan funcionamiento de integración, no relevancia científica de las sugerencias.

## Checklist actualizado

- [x] Paso 2: filtro literal, sugerencias acotadas, tarjetas, selección explícita, paginación del catálogo, disponibilidad y recuperación ante fallos.
- [x] Mantener recorrido único, checklist de pasos, navegación tras completar, reinicio con contexto/ejemplo y ejemplos de diez por página.
- [x] Pruebas locales y aceptación pública, documentación y publicación verificadas; archivos del equipo en `docs/proyecto_final/otros/` conservados sin seguimiento.

| Tarea | Estado real después de esta entrega |
|---|---|
| T01–T03 | Completas y publicadas, con selector de artículo mejorado. |
| T04 | Pendiente por cuota Serverless; ECS se mantiene. |
| T05–T06 | Suspendidas por QLoRA. |
| T07–T08 | Catálogo/selector disponibles para M/S y comercial; parte abierta suspendida. |
| T09 | Completa, publicada y aceptada. |
| T10 | Parcial: secreto, IAM, diez intentos diarios y exclusión comercial global de una solicitud aplicados. Pendiente revisar los demás controles de acceso, retención, escala, alertas y presupuesto de tiempo/costo. |
| T11 | Recorridos públicos M/S y comercial aceptados; QLoRA suspendido. Sugerencias reales y regresión M/S verificadas en esta entrega. |
| T12 | Migración y retirada pendientes; no retirar el servicio actual. |
| T13 | Notas actualizadas; falta cierre de documentación final. |
