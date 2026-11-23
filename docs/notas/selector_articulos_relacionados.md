# Selector de artículos relacionados — 22/11/2026

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

La aceptación pública y las revisiones desplegadas se registrarán después de comprobar el servicio real; estas comprobaciones no validan científicamente la relevancia de los candidatos.
