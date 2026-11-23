# T09: integración comercial y publicación

Decisión del usuario: GPT-6.1 Sol. Reutilizar el cliente OpenAI, el parser de nueve
puntajes y el prompt zero_shot_detailed de la evaluación comercial existente.
No cambiar modelos ni entrenar. QLoRA sigue suspendido y oculto.

## Comportamiento implementado

- GET /api/clasificadores anuncia M/S y añade el comercial únicamente si está
  configurado, habilitado y marcado como visible. Nunca anuncia QLoRA.
- POST /api/comercial/clasificar recibe contexto con una marca TARGETCIT, ID del
  artículo preparado y consentimiento explícito. El servidor obtiene título y
  resumen del corpus, no del navegador, y hace una sola llamada al proveedor.
- Se fija gpt-6.1-sol; no usa el default histórico gpt-4o-mini del evaluador ni
  otro modelo de respaldo. Devuelve modelo efectivo, perfil y hash del archivo
  de prompts; no registra clave, entrada ni respuesta cruda en logs.
- Perfil de servicio: timeout del proveedor 20 s, máximo 1.024 tokens de salida,
  cero reintentos automáticos. Son límites operativos; no se presentan como una
  reproducción idéntica de las condiciones del benchmark.
- El frontend conserva el POST M/S existente para recuperar Top-3 y luego llama
  al comercial en otra petición. M y S se calculan en esa primera petición, pero
  no se presentan como sustitución si se eligió el comercial. Cada petición
  conserva el timeout de 32 s del navegador; no acumula ambos pasos en un único
  request de API Gateway. Un error comercial conserva los fragmentos.
- Presenta puntajes generados, sin normalizarlos ni llamarlos probabilidades
  softmax. Máximos empatados o todos en cero producen abstención explícita.
- La identidad efectiva debe corresponder al modelo pedido; si falta o cambia
  a otro modelo, la respuesta se rechaza. La disponibilidad del alias para la
  cuenta se comprobó con llamadas reales; no se asumió por documentación.

Contrato de referencia: https://developers.openai.com/api/docs/models/gpt-6.1-sol
API: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

## Secreto y límite de consumo

La clave llega como variable de entorno solo al API ligero mediante la inyección
SSM de ECS. El servicio M/S no recibe la clave. Terraform añade permisos de
lectura del ARN concreto al rol de ejecución. El contador diario usa DynamoDB
con actualización condicional atómica; el rol del API solo puede UpdateItem
sobre esa tabla. Si falla la reserva, no llama a OpenAI. Un intento fallido también
consume cuota. Por defecto son diez intentos globales por día UTC, compartidos
entre tareas y conservados tras reinicios. El contador expira a los dos días.
No es un límite de facturación de la cuenta ni una garantía sobre tarifas.

El 22 de noviembre de 2026 se creó el parámetro SecureString versión 1 desde
OPENAI_API_KEY de .env mediante AWS CLI, como excepción puntual solicitada por
el usuario. No se imprimió la clave ni se guardó en Git, argumentos o archivos
intermedios. El parámetro está fuera del estado de terraform/commercial_secret;
no ejecutar make commercial-secret sobre él sin resolver antes esa propiedad.

Parámetro: /citas-api/commercial/openai_api_key.
ARN: arn:aws:ssm:us-east-1:646941583111:parameter/citas-api/commercial/openai_api_key.

La infraestructura de servicio, permisos, tabla y visibilidad se aplicó mediante
Terraform. Los tfvars de producción permanecen ignorados y habilitan el comercial,
referencian solo el ARN y fijan diez intentos globales por día UTC.

## Estado comprobado y pendientes

Comprobado localmente, sin llamadas pagadas:

- Contratos del proveedor, identidad, parser, consentimiento y errores.
- Reserva atómica, agotamiento diario y fallo cerrado ante error de AWS.
- Interfaz de éxito/error en escritorio y móvil, conservando Top-3 y sin mostrar
  una clasificación M/S como resultado comercial.
- Build y configuraciones Terraform válidos.
- El plan de preparación solo añade tabla y dos políticas IAM y actualiza el
  servicio/API ligero; no modifica M/S, red, dominio, QLoRA ni GPU.

## Publicación del 22 de noviembre de 2026

- Imagen del API construida y publicada en ECR desde la EC2 existente, sin subir
  capas desde el equipo local. Código: 43f405236f07fb0e320f1aa377c5622f014d7d39.
- Digest API: sha256:108ffd091a16912d7d0f3352d9bdafc561bc8b9e9935fe33402d66138076309a.
- M/S conserva citas-api-science:4 y su digest
  sha256:36b2c122407da337ade64f73448ede02553a2b793484c18f0e1d9e41f26ba21c.
- EC2 detenida mediante Terraform después del build; disco y archivos conservados.
- Primera aceptación real con el proveedor aún oculto: gpt-6.1-sol,
  zero_shot_detailed, clase Application, nueve puntajes válidos y 7,271 segundos
  totales. Una llamada con contexto inventado y artículo público W05-0821.
- Evidencia local ignorada: artifacts/t09-aceptacion-real.json.
- Frontend publicado en https://proyectocitas-grupo19.click.
- Recorrido comercial público aceptado en escritorio y móvil: consentimiento
  obligatorio, tres fragmentos contrastados con el corpus y función Application.
  Dos pruebas aprobadas; capturas revisadas sin desbordamiento horizontal.
- Tres llamadas comerciales en total durante esta aceptación: una directa y una
  por navegador. No se ejecutó una evaluación del modelo ni se modificaron pesos.
- API citas-api:4 y M/S citas-api-science:4 estables. Salud pública y HTML de
  CloudFront iguales al build local, confirmado por make release-confirm.
- Evidencia adicional ignorada: artifacts/release-confirmation.json y
  frontend/test-results/commercial-real-*/aceptacion-comercial.json.
- make commercial-smoke está diseñado para la fase previa con proveedor oculto;
  no repetirlo ahora que es visible. make commercial-web-check hace dos llamadas
  reales y consume la cuota del día.

Seguimiento: T01–T03 publicadas; T04 pendiente por cuota; T05–T06 suspendidas;
T07–T08 con catálogo y selector M/S y comercial aceptados, parte QLoRA suspendida;
T09 completada; T10 con secreto, IAM y límite comercial aplicados, resto pendiente;
T11 con recorridos públicos M/S y comercial aceptados, parte QLoRA suspendida;
T12 y cierre T13 pendientes. No se cambiaron pesos ni se entrenaron modelos.

Resultados de esta preparación: 120 pruebas de backend y seis subpruebas, 32
pruebas unitarias frontend y 38 recorridos de navegador aprobados. Las cuatro
pruebas que requieren servicios reales permanecieron omitidas; no se presentan
como aceptación del proveedor. Los seis casos comerciales afectados por los
ajustes finales de texto y presentación volvieron a pasar y sus capturas de
escritorio y móvil se revisaron. Esos resultados locales preceden al despliegue descrito arriba.

## Continuación de T10

Se publicó el control de concurrencia comercial global en citas-api:5, con
rechazo público 429 y cuota diaria inalterada comprobados sin llamar a OpenAI.
M/S permanece en citas-api-science:4. Evidencia, límites y checklist vigente en
[t10_concurrencia_comercial.md](t10_concurrencia_comercial.md). T10 sigue parcial.
