# T09: integración comercial preparada

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
  cuenta se comprobará en una llamada real; nunca se asume por documentación.

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

Creación o rotación privada desde la raíz del repositorio, en una terminal:

```sh
make commercial-secret AWS_PROFILE=josezambrana
```

Pide la clave sin mostrarla. El módulo terraform/commercial_secret usa variable
efímera y value_wo: el valor no se escribe al plan ni al estado. Se desactivan
trazas Terraform al ejecutar esa operación. El helper revisa que el plan solo
cree o actualice el parámetro autorizado. El valor nunca se pasa como argumento
CLI ni se guarda en archivos. No pegarlo en el chat, Git o tfvars. El estado del
módulo contiene metadatos y versión de rotación, queda fuera de Git y debe
conservarse para volver a rotar con el mismo comando.

Parámetro: /citas-api/commercial/openai_api_key.
ARN: arn:aws:ssm:us-east-1:646941583111:parameter/citas-api/commercial/openai_api_key.

Crear el secreto NO activa el proveedor en la web. Los valores predeterminados
commercial_enabled y commercial_visible son false. Primero se desplegará la
imagen nueva, el límite y el secreto referenciado con visible=false; después de
una llamada sintética real se mostrará mediante Terraform y se comprobará la web.

## Estado comprobado y pendientes

Comprobado localmente, sin llamadas pagadas:

- Contratos del proveedor, identidad, parser, consentimiento y errores.
- Reserva atómica, agotamiento diario y fallo cerrado ante error de AWS.
- Interfaz de éxito/error en escritorio y móvil, conservando Top-3 y sin mostrar
  una clasificación M/S como resultado comercial.
- Build y configuraciones Terraform válidos.
- El plan de preparación solo añade tabla y dos políticas IAM y actualiza el
  servicio/API ligero; no modifica M/S, red, dominio, QLoRA ni GPU.

No se ha creado el secreto, aplicado este plan, desplegado esta integración ni
realizado una inferencia comercial real. T09 permanece en curso. El plan guardado
es preparatorio y referencia la imagen vigente: regenerarlo después de publicar
la imagen nueva, no aplicarlo directamente.

Seguimiento: T01–T03 publicadas; T04 pendiente; T05–T06 suspendidas; T07–T08 con
contrato/selector comercial preparados y el resto pendiente; T09 en curso;
T10 con mínimos comerciales preparados, pendiente de aplicación y aceptación;
T11 comercial real pendiente; T12 y cierre final T13 pendientes.

Resultados de esta preparación: 120 pruebas de backend y seis subpruebas, 32
pruebas unitarias frontend y 38 recorridos de navegador aprobados. Las cuatro
pruebas que requieren servicios reales permanecieron omitidas; no se presentan
como aceptación del proveedor. Los seis casos comerciales afectados por los
ajustes finales de texto y presentación volvieron a pasar y sus capturas de
escritorio y móvil se revisaron. No se crearon recursos ni se modificó producción.
