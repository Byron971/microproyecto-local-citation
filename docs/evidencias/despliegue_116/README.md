# Evidencia de despliegue — Issue #116

Medición: 2026-11-08 20:36:24 (America/La_Paz, UTC−4).

URL: [API y tablero](https://qlipl9bh0i.execute-api.us-east-1.amazonaws.com). Datos originales: [medicion_2026_11_08.json](medicion_2026_11_08.json).

## Funcionamiento verificado

- ECS `ACTIVE`, despliegue `COMPLETED`, una tarea ejecutándose y ninguna pendiente.
- `/`, `/static/top3.html` y `/api/estado`: HTTP 200; el modelo informa `listo: true`.
- 20 peticiones medidas a `/api/recomendar`: 20 respuestas válidas con recomendaciones.
- Prueba adicional de contexto vacío: HTTP 422 con el mensaje «El contexto no puede estar vacío.».

## Latencia desde fuera de AWS

Se utilizó una conexión pública desde el entorno de trabajo del asistente, no desde la red de la universidad. Son 20 consultas secuenciales con un contexto fijo y `top_k=3`, después de tres consultas de calentamiento excluidas. El tiempo incluye conexión TLS, red, API Gateway, ALB y aplicación; no es tiempo exclusivo del modelo.

| Medida | Segundos |
| --- | ---: |
| Mínimo | 0.645 |
| Mediana | 1.107 |
| Promedio | 1.415 |
| P95 (rango más próximo) | 2.808 |
| Máximo | 3.615 |

Es una muestra pequeña, sin concurrencia y con un único contexto. No demuestra capacidad bajo carga, latencia con otros textos ni disponibilidad continua.

## Recursos y memoria observados

Fargate Linux x86, inferencia CPU dentro del contenedor, **0.5 vCPU / 1024 MiB**. Una tarea, sin autoescalado. Las métricas de servicio de CloudWatch usan períodos de 60 segundos. Se recogieron nueve períodos publicados de 20:27 a 20:35 del 8 de noviembre (hora de La Paz); incluyen arranque y actividad anterior a las consultas medidas de 20:36. No representan el consumo aislado de esas consultas ni picos instantáneos.

| Métrica | Promedio de los promedios por minuto | Máximo publicado |
| --- | ---: | ---: |
| CPU | 6.27 % | 95.63 % |
| Memoria | 18.35 % (~188 MiB) | 21.29 % (~218 MiB) |

La memoria en MiB se estima multiplicando el porcentaje de `MemoryUtilization` por los 1024 MiB asignados; no es una medición de RSS del proceso. [Definición de las métricas de ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service_utilization.html).

## Arquitectura, escalabilidad y límites

API Gateway → VPC Link → ALB interno → ECS. La integración usa ALB porque Learner Lab denegó Cloud Map. La entrada a ECS solo se permite desde el ALB.

El tamaño se ajusta con `task_cpu` y `task_memory`; la configuración actual limita el servicio a una tarea y no incluye autoescalado ni alta disponibilidad de la aplicación. No se probó redimensionamiento o carga concurrente. El modelo se carga al iniciar; un reinicio puede interrumpir el servicio. API Gateway tiene un timeout configurado de 30 segundos. Los modelos futuros necesitan medir de nuevo memoria y arranque. El corpus de las rutas `/api/top3-corpus/*` no está incluido y esas rutas pueden responder 503.

El ALB agrega un cargo por hora y uso LCU; la estimación previa de USD 23/mes no lo incluía. La tarifa de referencia publicada para el ALB en us-east-1 es USD 0.0225/h (~USD 16.43 por 730 horas), más LCU. No es el costo total ni una lectura de la factura. [Precios de Elastic Load Balancing](https://aws.amazon.com/elasticloadbalancing/pricing/).

## Repetir las comprobaciones

Con AWS CLI, Python 3 y credenciales vigentes del perfil `maia`, desde la raíz:

```bash
python3 scripts/medir_despliegue.py \
  --url https://qlipl9bh0i.execute-api.us-east-1.amazonaws.com \
  --profile maia \
  --output /tmp/medicion_despliegue.json
```

El script no modifica infraestructura: consulta ECS/CloudWatch y envía 23 recomendaciones (tres de calentamiento y veinte medidas). Guarda tiempos, estados HTTP y métricas disponibles en JSON. Una nueva medición no demuestra que el servicio haya estado disponible entre ambas.

Para repetir la validación de entrada:

```bash
curl -i -H 'Content-Type: application/json' \
  --data '{"contexto":"","top_k":3}' \
  https://qlipl9bh0i.execute-api.us-east-1.amazonaws.com/api/recomendar
```

## Alcance actual y siguiente despliegue

José confirma que el objetivo actual es comprobar el funcionamiento y que la URL definitiva se publicará desde una cuenta personal. El funcionamiento en Learner Lab queda verificado con esta evidencia. Se posponen la prueba de cierre del lab y la coordinación de la franja de evaluación; no se presentan como realizadas.

El siguiente paso es replicar la infraestructura en la cuenta personal, configurar su bucket de estado y un rol ECS con los permisos requeridos, y comprobar tablero, salud y recomendaciones antes de registrar la URL definitiva. Las métricas de este informe pertenecen exclusivamente al despliegue del laboratorio.

Los workflows y el rollback real se siguen en #137; no se presentan como verificados por estas mediciones. No se ha cerrado el issue en GitHub.
