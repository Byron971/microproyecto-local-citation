# Revisión del flujo y la UI — 22 de noviembre de 2026

> Actualización posterior: por petición explícita del usuario, el paso 2 admite sugerencias SciBERT limitadas a los artículos preparados, con confirmación manual. Véase [selector de artículos relacionados](selector_articulos_relacionados.md); las restricciones anteriores de filtro exclusivamente literal quedan como historial.

## Fuentes y alcance

- docs/propuesta/0102_propuesta_proyecto_pln.md:14: descripción del problema.
- La misma propuesta, línea 35: objetivos; línea 156: demostrador interactivo.
- docs/specs/prd_aplicacion_cientifica_citas.md:79: recorrido; línea 91:
  aceptación RF01–RF14; línea 184: organización de la página.
- docs/proyecto_final/07 Entregable y criterios de evaluación.md: sección D,
  instrucciones breves, etiquetas claras y resultados comprensibles.

La propuesta describe dos tareas: recuperar fragmentos semánticamente cercanos
DENTRO del artículo citado y clasificar la función de esa cita. La UI no debe
convertirse en un buscador global de referencias ni afirmar que verifica una
cita. La aplicación actual resuelve ese recorrido en el catálogo preparado con
M/S y GPT-6.1 Sol. No es todavía la entrega completa de tres familias: QLoRA
permanece oculto y suspendido por decisión posterior del usuario. Esta revisión
no acredita balance del dataset, validación humana, ausencia de leakage, métricas
científicas ni comparación de calidad de modelos. Esos objetivos requieren su
propia evidencia; una UI funcional no demuestra que se hayan cumplido.

## Contraste de requisitos

| Requisito | Observación y resultado de esta revisión |
|---|---|
| RF01–RF02 | Flujo único sin ranking global ni JSON. Se añade filtro local por título/ID, conservando la selección explícita. |
| RF03 | Ya existían validaciones; faltaban orientación inmediata y foco. Se añaden contador, estado de marca, aria-invalid y foco en contexto/consentimiento. |
| RF04 | Consulta real de cobertura, error separado de ausencia, reintento y conservación de entradas. Continúa sin inferir si falta texto. |
| RF05 | Top-3 con tres fragmentos, secciones y fuentes. Se añaden enlaces a las secciones recuperadas; no se inventan posiciones físicas ni relevancia validada. |
| RF06 | Se conserva contrato M/S y se muestra la variante elegida. Ningún peso, endpoint o configuración de modelo cambia. |
| RF07 | No cumplido en web: abierto suspendido. No se vuelve a anunciar como disponible. |
| RF08 | Comercial previamente aceptado con inferencia real en T09. En esta revisión se comprueba la nueva presentación con API interceptada, sin nuevas llamadas pagadas. |
| RF09 | Solo se ofrecen modelos operativos; M/S agrupados. El fallo de catálogo deja de ser silencioso: se explica y permite reintentar. |
| RF10 | M/S ya tenía explicación y barras. Se añaden explicación y barras al comercial, con sus valores originales 0–1 y aviso de no calibración. No se normalizan puntajes ni se fabrican probabilidades. |
| RF11 | Se distinguen recuperación y espera comercial usando el estado real de las peticiones. Se conservan Top-3 ante fallo comercial y se descartan resultados al editar. |
| RF12 | AB y softmax dejan de encabezar instrucciones de uso. Se conservan en detalles técnicos. Tiempo total del navegador visible en resumen. |
| RF13 | Se conserva ejemplo público sintético. El modal de 33 ejemplos de validación identifica su procedencia y no dispara inferencias por selección. |
| RF14 | Las siete rutas heredadas siguen redirigiendo al flujo principal; sin paneles ni experimentos públicos. |

## Cambios de experiencia

Se conserva la paleta azul existente (#2f4be0), superficies blancas, fondo
#f3f5fa, texto #121826, tipografía Outfit/DM Sans. La orientación por pasos se
corresponde con etapas reales, no con un porcentaje simulado. Se mantiene la
misma página y los mismos campos; en móvil los pasos se apilan en dos columnas.

Se aplican orientación de tarea, prevención de errores, visibilidad del estado,
detalle progresivo y acceso por teclado. El filtro no recomienda artículos: solo
busca literalmente dentro del catálogo, sin inferencia y sin borrar la referencia.
La selección de clasificador conserva contexto y artículo. Al completar el
análisis se enfoca el resultado; ante fallo remoto se enfoca el mensaje.

Referencias de accesibilidad consultadas:
https://www.w3.org/WAI/tutorials/forms/instructions/
https://www.w3.org/WAI/tutorials/forms/notifications/

## Evidencia y límites

- Build TypeScript/Vite correcto y 32 pruebas unitarias aprobadas.
- 40 casos existentes de navegación, cobertura, ejemplos y comercial aprobados.
- Cuatro nuevos casos de filtro/foco y reintento del catálogo aprobados en
  escritorio y móvil. En total: 44 casos de interfaz distintos aprobados; los
  dos casos de reintento se repitieron tras ajustar la simulación a StrictMode.
- Prueba comercial con respuesta retenida: el Top-3 se presenta durante la espera,
  el botón evita duplicados y después aparecen explicación, nueve barras y valores.
- Capturas de formulario preparado y resultados comerciales revisadas.
- Las pruebas de comercial usan respuestas simuladas: no son evaluación de calidad
  ni sustituyen la evidencia real de T09 en docs/notas/t09_integracion_comercial.md.
- Publicado mediante make publish-frontend en https://proyectocitas-grupo19.click.
- Cuatro casos de usabilidad aprobados sobre el frontend público con API
  interceptada, más dos recorridos reales M/S en escritorio y móvil. Los tres
  textos recuperados coinciden con el corpus: p00012-p00012, p00007-s001 y
  p00002-p00002 para W05-0821. No se usaron TRAIN/Gold en esas inferencias.
- make release-confirm confirmó salud HTTP, servicios estables y HTML público
  igual al build. Índice SHA-256:
  21acc1a9736926e725ea45a133fbecc3f71ced8c9316bcf11fbc8295a164dd3d.
- No cambian imágenes, pesos, endpoints, recursos ni secretos. EC2 no se inicia.
- Evidencia ignorada en artifacts/ui-review-*, artifacts/release-web y
  artifacts/release-confirmation.json.

## Checklist vigente

T01–T03 completas, con mejora de UI; T04 pendiente por cuota; T05–T06 suspendidas;
T07–T08 disponibles para M/S y comercial, parte QLoRA suspendida; T09 completa;
T10 parcial; T11 M/S y comercial aceptados, parte QLoRA suspendida; T12 y cierre
T13 pendientes. Esta revisión no cierra los objetivos científicos ni cambia el PRD.
