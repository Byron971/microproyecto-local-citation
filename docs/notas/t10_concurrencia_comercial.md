# T10: concurrencia comercial global

Se incorpora una reserva compartida en DynamoDB antes de consumir cuota diaria.
La clave `openai:inflight` admite un propietario mediante UpdateItem condicional.
Una solicitud ocupada recibe 429 con Retry-After: 5, sin reservar cuota ni llamar
al proveedor. El contador de diez intentos por día UTC sigue siendo independiente.
Los errores posteriores a reservar cuota siguen consumiendo el intento.

La reserva se libera en finally ante éxito, error de proveedor, parseo o cuota.
La liberación exige el mismo propietario: una petición antigua nunca libera
la reserva de una nueva. Si AWS impide liberar, se conserva el resultado original
y se registra un aviso genérico, sin texto, clave ni detalles de la excepción.

Una reserva abandonada se puede recuperar a los 120 segundos; se compara
lease_until de forma atómica y no se espera el borrado asíncrono de DynamoDB TTL.
El TTL de dos días solo limpia registros. Las operaciones del contador y la reserva
usan conexión/lectura AWS de dos segundos y un único intento. El proveedor conserva
20 segundos de timeout por operación de transporte, 1.024 tokens y cero reintentos.
La caducidad es recuperación operativa: no puede cancelar trabajo que el proveedor
ya haya recibido ni impedir que este siga procesando tras una desconexión.

No se añaden recursos, permisos ni secretos. Reutiliza la tabla existente y su
permiso UpdateItem. Solo requiere publicar una imagen nueva del API; M/S permanece
con su imagen actual. Durante el reemplazo puede coexistir la revisión anterior,
que no conoce esta reserva: el control se considera publicado al estabilizar ECS.

## Aceptación

- Pruebas sin red: solicitudes concurrentes, liberación y recuperación, propietario
  antiguo, error AWS cerrado y errores HTTP sin detalles privados.
- `make commercial-concurrency-check AWS_PROFILE=josezambrana`: comprueba contra
  DynamoDB real una clave aleatoria `concurrency-check:*`, sin usar `openai:inflight`,
  sin tocar el contador diario y sin llamar a OpenAI. Conserva un registro vacío
  de reserva con TTL para limpieza automática. Evidencia ignorada en
  artifacts/t10-concurrency-check.json.
- 42 pruebas aprobadas y una omitida en los contratos comercial, proveedor,
  corpus y concurrencia M/S. DynamoDB real confirmó rechazo de ocupados,
  liberación y recuperación de reserva vencida, sin llamadas comerciales.
- `make commercial-concurrency-public-check AWS_PROFILE=josezambrana`, solo tras
  estabilizar la nueva imagen: retiene brevemente la reserva real y exige 429
  de la API pública con cuota diaria inalterada. Usa GetItem para comprobar
  el contador con las credenciales del operador; no amplía permisos de la app.

## Publicación y aceptación comprobadas

- Código publicado: c01b43f04f52806bf5f2948f7b1bd2c56c89dde7.
- API construido desde EC2 mediante make release-build-api; digest:
  sha256:5a21c97f625e22f88913dd9c7f8f3359dedf19190051a6c7c39e53b2bf86d16b.
- Plan revisado y aplicado con make release-prepare/plan/apply: solo referencia
  SSM de imagen, revisión de tarea API y servicio API. La revisión anterior se
  conserva con skip_destroy. No cambian recursos, permisos ni secreto comercial.
- API citas-api:5 estable, una tarea; M/S permanece en citas-api-science:4 con
  digest sha256:36b2c122407da337ade64f73448ede02553a2b793484c18f0e1d9e41f26ba21c.
- make commercial-concurrency-public-check pasó: API pública devuelve 429 y
  Retry-After: 5 al retener la reserva; contador diario idéntico antes/después.
  No se efectuaron llamadas a OpenAI. Evidencia ignorada:
  artifacts/t10-concurrency-public-check.json.
- make release-confirm pasó: servicios estables, salud HTTP y HTML público igual
  al build. Evidencia ignorada: artifacts/release-confirmation.json.
- Constructora i-03c35e1f2d0597f9f encendida y detenida mediante Terraform y targets
  builder-power-*. make builder-power-status confirmó stopped; disco conservado.
- Archivos del equipo en docs/proyecto_final/otros/ conservados sin seguimiento.
- No se modifican modelos ni pesos, ni se retoma QLoRA.

La concurrencia comercial queda publicada y aceptada. Esto no cierra T10 completa.

## Checklist

T01–T03 publicadas; T04 pendiente por cuota; T05–T06 suspendidas por QLoRA;
T07–T08 y T11 aceptadas para M/S y comercial, parte abierta suspendida;
T09 aceptada; T10 parcial, con concurrencia comercial publicada y aceptada;
T12 pendiente sin retirar servicio actual; T13 pendiente de cierre.

T10 aún requiere revisar aislamiento de roles, protección de imágenes de reversión,
retención de otros datos, alertas, presupuesto de costo y plazos de ejecución.
