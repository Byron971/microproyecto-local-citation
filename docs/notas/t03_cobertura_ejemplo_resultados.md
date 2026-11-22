# T03 — Cobertura, ejemplo público y resultados

Estado: implementada y aceptada localmente; no publicada en AWS.

## Comportamiento

Al seleccionar un artículo se consulta POST /api/analisis-cita-ms/disponibilidad.
Solo se permite analizar después de confirmar texto disponible para ese ID.
Sin texto, se conserva el contexto y se permite seleccionar otra referencia.
Un error de consulta no se presenta como ausencia de texto: permite reintentar.
Las consultas antiguas se cancelan al cambiar de artículo. Un 404 al analizar
actualiza la cobertura a no disponible. Errores, ocupado y resultados incompletos
conservan las entradas; se comprueban identidad, versión del corpus y tres IDs
únicos antes de presentar el resultado.

El ejemplo precarga W05-0821, «Improved Language Modeling for Statistical Machine
Translation», y un contexto redactado para esta demostración:

“We use the language modeling approach described in TARGETCIT to improve a
statistical machine translation system.”

La referencia visible es [1]. No se extrajeron contextos ni etiquetas TRAIN/Gold.
El ejemplo consulta cobertura del servicio; no presupone que el corpus remoto
coincida con el catálogo de esta entrega.

Se muestran tres fragmentos con sección y enlace a la publicación, la función
predicha con explicación breve y puntuaciones softmax con advertencia explícita.
Las nueve definiciones son consultables. Tokens, revisión, perfiles, coseno y
ajustes técnicos quedan en detalles desplegables. No se inventan puntuaciones.

## Validación

- Build de producción aprobado; 32 pruebas unitarias aprobadas.
- 18 pruebas de recorrido y 14 de cobertura/error en escritorio y móvil aprobadas.
  Incluyen ausencia de inferencia sin cobertura, reintento, consulta antigua,
  404, 429 y salida incompleta/con versión de corpus distinta.
- El ejemplo completó el recorrido desde Chrome contra M/S real, en escritorio
  y móvil, sin mocks del API. Se usó el contenedor ARM64 validado en T01,
  con los pesos y caché SciBERT montados de solo lectura, sin credenciales AWS.
- Verificados los textos de los tres fragmentos contra el corpus local del ID
  W05-0821: p00012-p00012, p00007-s001 y p00002-p00002. M: Background;
  S: Application. No son etiquetas de referencia ni medición de calidad.
- Una llamada HTTP directa tardó 13,255 s; los recorridos de navegador completos
  tardaron aproximadamente 19 s cada uno. Son observaciones, no un benchmark.
- Se revisaron capturas reales de escritorio y móvil; móvil sin sobreancho.

## Límites observados

La primera opción de ejemplo, D15-1167 (37 fragmentos), agotó el timeout de
32 segundos del cliente en este equipo. La web mostró el error y conservó las
entradas. El ejemplo final W05-0821 tiene 12 fragmentos y completó la prueba.
No se amplió el timeout ni se modificó el recuperador para ocultar este problema.
Medir documentos largos, alinear tiempos navegador/proxy/proveedor y decidir
optimizaciones/asincronía quedan para T10/T11 y la evaluación de infraestructura.

Esta aceptación no verifica la URL pública ni asegura compatibilidad con todo
corpus desplegado. El ejemplo es de contenido público, validado con el corpus
local; la aceptación pública queda pendiente de una publicación controlada.
No se desplegó ni se modificaron recursos AWS. Contenedor temporal detenido.
