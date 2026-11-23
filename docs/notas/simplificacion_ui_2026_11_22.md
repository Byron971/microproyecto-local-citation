# Simplificación de la experiencia de análisis de citas

> Actualización posterior: por petición explícita del usuario, el paso 2 admite sugerencias SciBERT limitadas a los artículos preparados, con confirmación manual. Véase [selector de artículos relacionados](selector_articulos_relacionados.md); las restricciones anteriores de filtro exclusivamente literal quedan como historial.

## Alineación con el problema, etapa por etapa

Fuentes: docs/propuesta/0102_propuesta_proyecto_pln.md, descripción y sección 5;
docs/specs/prd_aplicacion_cientifica_citas.md, recorrido y RF01–RF14.
La petición del usuario actualiza la navegación descrita en flujo_ui_por_etapas.md.

| Etapa | Se requiere y se conserva | Simplificación aplicada |
|---|---|---|
| Contexto | Texto en inglés, una TARGETCIT, máximo 4.000 caracteres, marcado y ejemplos. | Un título de campo, una instrucción y un contador. Se eliminan número/título repetidos, límite repetido y mensajes de listo/vacío redundantes. Procedencia breve del ejemplo. |
| Artículo | Selección explícita por título/ID, fuente, consulta de cobertura y recuperación ante errores. | Se elimina el aviso de listo duplicado. Filtro literal, selección y disponibilidad siguen visibles en su etapa. |
| Clasificador | Identidad M/S o comercial, perfil de entrada comprensible y consentimiento obligatorio de OpenAI. | Se elimina el mensaje de listo. Al regresar tras completar, Ver resultados consulta lo calculado sin otra inferencia. Cambiar modelo descarta resultados. |
| Resultados | Artículo, modelo, tiempo total, tres fragmentos con sección y fuente, función y puntuaciones interpretadas correctamente. | Se quitan el contador Paso 4 de 4 y los accesos a secciones duplicados sobre los tres fragmentos. Se conservan las secciones en cada fragmento, las nueve funciones y los detalles técnicos plegados. |

No se añaden tareas científicas, rankings globales, formularios JSON ni nuevas
familias. La UI no acredita calidad científica, balance o independencia del test.
QLoRA sigue suspendido y oculto.

## Patrones y decisiones

- Progreso como lista ordenada con números/checks, sin fondos ni bordes de pestaña.
  Se conserva aria-current y foco visible por teclado. Al cambiar de etapa se
  enfoca su título, evitando dibujar un marco sobre el indicador al iniciar.
- Se conserva la paleta y tipografía existentes: azul #2f4be0, fondo #f3f5fa,
  superficie #fff, texto #121826 y secundario #4a5568; Outfit y DM Sans.
- Divulgación progresiva: solo se muestra la etapa actual. Instrucciones junto
  al campo, errores accionables y detalles técnicos secundarios.
- Los checks conservan los avances al regresar a una etapa anterior.
- Solo después de terminar correctamente todo el análisis se permite ir a
  cualquiera de las cuatro etapas. Navegar conserva datos/resultados y no infiere.
- Un resultado comercial parcial o fallido no equivale a análisis completado.
  Durante una petición se impiden navegación y ejecuciones simultáneas.
- Editar el contexto o marcar otra cita reinicia progreso, artículo, modelo M,
  consentimiento y resultados. Seleccionar cualquier ejemplo también reinicia,
  pero precarga su contexto y artículo; no ejecuta inferencia ni salta etapas.
- Cambiar artículo/modelo conserva contexto e invalida resultados y finalización.
- Modal con diez ejemplos por página: 10/10/10/3 para el catálogo actual de 33.
  Búsqueda sobre todos los ejemplos y reinicio de página al buscar. Anterior y
  Siguiente respetan límites. Al reabrir se muestra la página del ejemplo en uso.
  La lista desplaza su contenido; búsqueda, cierre y paginación siguen visibles.

## Verificación

- Build TypeScript/Vite correcto; 32 pruebas unitarias aprobadas.
- 54 recorridos de interfaz distintos aprobados en escritorio y móvil. Los 18
  afectados por el ajuste final de foco/Ver resultados se repitieron y pasaron.
  Los seis casos comerciales se repitieron con comprobación explícita de que
  una clasificación fallida no desbloquea el recorrido.
- Navegación sin inferencia extra, reinicios por contexto/ambos tipos de ejemplo,
  paginación y búsqueda, cobertura, consentimiento, errores, teclado y foco.
- Capturas de escritorio/móvil revisadas, incluidos formulario y modal.
- Todas las pruebas comerciales usan API simulada; no consumen OpenAI.
- Publicado en https://proyectocitas-grupo19.click mediante make publish-frontend.
- Doce comprobaciones públicas con API interceptada aprobadas, en escritorio y
  móvil: navegación, reinicios, ejemplos y paginación. Capturas/evidencia ignoradas
  en artifacts/ui-simplification-public/.
- Dos recorridos públicos M/S reales aprobados mediante make release-web-check,
  uno por tamaño. Los tres fragmentos de W05-0821 se contrastaron con el corpus.
  Evidencia ignorada en artifacts/release-web/.
- Confirmación final: API citas-api:5 y M/S citas-api-science:4 estables, salud HTTP
  correcta y HTML público idéntico al build. Índice SHA-256:
  49d7ee8857b5934d9af8e4fbf92839c5b0fdf1765a5b44a23fe1a5ca959a4d35.
- No se reconstruyen imágenes, modifican modelos, secretos ni infraestructura.
  No se inicia la constructora. Archivos del equipo conservados sin seguimiento.

## Lectura de outputs durante la publicación

Terraform CLI quedó detenido repetidamente al leer el estado S3. Se cancelaron
solo esos procesos de lectura, antes de subir archivos. El target publish-frontend
ahora consulta los outputs una sola vez, en JSON, en lugar de cuatro consultas.
También admite FRONTEND_OUTPUTS_FILE para un JSON de outputs actual ya verificado.

Para esta publicación se obtuvo el estado real de S3 mediante una consulta de
lectura con tiempos acotados, sin guardar ni mostrar el estado completo. Se
contrastaron los cuatro destinos públicos con bucket, distribución y URLs reales;
se guardaron solo esos outputs en artifacts/frontend-live-outputs.json (ignorado).
Se publicó con make publish-frontend AWS_PROFILE=josezambrana
FRONTEND_OUTPUTS_FILE=artifacts/frontend-live-outputs.json.

La confirmación se ejecutó con make -o release-status release-confirm después de
obtener nuevamente del estado real S3 sus outputs no sensibles (serial 26) en
artifacts/release-outputs.json. Así se evita repetir la lectura CLI bloqueada;
confirm_release.py sí comprueba ECS, imágenes, salud y el HTML público. No se
omiten sus comprobaciones ni se modifica el estado Terraform. El archivo opcional
debe provenir siempre del estado actual verificado, no de una copia desactualizada.

## Checklist vigente

- T01–T03: publicadas, con esta simplificación publicada y verificada.
- T04: pendiente por cuota Serverless.
- T05–T06: suspendidas por QLoRA.
- T07–T08: M/S y comercial disponibles; parte abierta suspendida.
- T09: publicada y aceptada.
- T10: parcial, concurrencia comercial publicada; resto de controles pendiente.
- T11: M/S y comercial aceptados; parte abierta suspendida.
- T12: pendiente; conservar servicio actual.
- T13: notas actualizadas; cierre final pendiente.
