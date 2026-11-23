# Flujo de UI por etapas

> Refinamiento posterior: la numeración permanece visible y la carga comienza en el paso 4 al pulsar «Ver resultados». Véase [pasos numerados y espera](pasos_numerados_carga_resultados.md); la evidencia descrita abajo corresponde a la entrega histórica.

> Actualización posterior: por petición explícita del usuario, el paso 2 admite sugerencias SciBERT limitadas a los artículos preparados, con confirmación manual. Véase [selector de artículos relacionados](selector_articulos_relacionados.md); las restricciones anteriores de filtro exclusivamente literal quedan como historial.

Cambio solicitado por el usuario tras la revisión del PRD. Conserva la secuencia
contexto → artículo → clasificador → Top-3 y función, pero muestra una etapa a la vez.

- Inicio: solo contexto. Las tres etapas siguientes están deshabilitadas.
- «Siguiente: artículo» se habilita con contexto no vacío, una marca TARGETCIT y
  hasta 4.000 caracteres. Precargar un ejemplo no salta etapas.
- Artículo: filtro, selector, referencia, fuente y cobertura. El clasificador solo
  se habilita al continuar con un artículo seleccionado y texto disponible.
- Clasificador: modelo, ayuda de entrada, consentimiento comercial y ejecución.
- Resultados: resumen, Top-3 y función; puede presentar Top-3 parcial mientras se
  espera al comercial. Ante fallo comercial se conserva ese resultado parcial.
- «Anterior» y las etapas previas permiten volver conservando los datos. Las
  etapas posteriores vuelven a quedar bloqueadas hasta pulsar «Siguiente».
- La etapa actual tiene fondo azul claro, número destacado y aria-current=step.
- Campos de otras etapas ocultos y deshabilitados. Enviar el formulario en las
  etapas 1 o 2 solo avanza; únicamente la etapa de clasificador puede inferir.
- Los resultados anteriores se descartan al editar contexto, artículo o modelo.
- Mientras una petición está activa no se puede iniciar otra ni navegar atrás.

La UI mantiene la misma página y los contratos existentes. No cambian modelos,
endpoints ni infraestructura; QLoRA continúa suspendido y oculto.

Comprobación local: build correcto, 32 pruebas unitarias y 46 casos distintos
adaptados al recorrido, incluidos bloqueo de pasos, avance, retorno, conservación,
cobertura, errores y consentimiento. Las aserciones afectadas por el cambio de
etapa de resultados se repitieron tras ajustar las pruebas. Capturas de escritorio
y móvil revisadas en artifacts/wizard-stages. Las pruebas comerciales interceptan
la API y no consumen llamadas de OpenAI.

Publicado en https://proyectocitas-grupo19.click mediante make publish-frontend.
Dos pruebas de etapas pasaron sobre la web con API interceptada y dos recorridos
M/S reales completaron los cuatro pasos, uno en escritorio y otro en móvil.
Se contrastaron los textos recuperados con el corpus. make release-confirm
confirmó servicios estables, salud e índice público correspondiente al build.
El mensaje ante pérdida de cobertura se ajustó para pedir volver al artículo;
sus dos casos se repitieron y aprobaron antes de la publicación final.
Evidencia ignorada: artifacts/wizard-*, artifacts/release-web y
artifacts/release-confirmation.json.

Checklist: T01–T03 completas con navegación secuencial; T04 pendiente de cuota;
T05–T06 suspendidas; T07–T08 disponibles para M/S y comercial, QLoRA suspendido;
T09 completa; T10 parcial; T11 M/S y comercial aceptados, QLoRA suspendido;
T12 y cierre de T13 pendientes.

## Actualización de navegación y simplificación

La petición posterior del usuario sustituye el aspecto de pestañas por checks y
permite navegar libremente entre las cuatro etapas después de completar todo
el análisis. Un nuevo contexto o ejemplo reinicia el recorrido; los ejemplos
precargan contexto y artículo. Decisiones por etapa, paginación y evidencia en
[simplificacion_ui_2026_11_22.md](simplificacion_ui_2026_11_22.md).
