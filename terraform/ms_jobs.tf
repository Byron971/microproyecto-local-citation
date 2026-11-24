# Cola duradera M/S: SQS entrega trabajos y DynamoDB guarda estado, resultados e idempotencia.
# El worker vive en la tarea científica existente (el modelo ya está cargado allí): no hay
# servicio ECS nuevo. Los recursos se crean con el servicio científico; la tarea solo los usa
# cuando ms_queue_enabled = true (segunda fase, junto con la imagen que contiene el worker).
variable "ms_queue_enabled" {
  description = "Inyecta tabla, cola y límites en la tarea científica. Requiere la imagen con el worker."
  type        = bool
  default     = false
  validation {
    condition     = !var.ms_queue_enabled || var.scientific_api_enabled
    error_message = "La cola M/S requiere el servicio científico."
  }
}
variable "ms_queue_limits" {
  description = "Límites explícitos de la cola (segundos salvo max_activos/max_intentos)."
  type = object({
    max_activos          = number
    espera_max_s         = number
    lease_s              = number
    max_intentos         = number
    retencion_s          = number
    sugerencias_espera_s = number
  })
  default = {
    max_activos          = 10
    espera_max_s         = 900
    lease_s              = 120
    max_intentos         = 2
    retencion_s          = 3600
    sugerencias_espera_s = 15
  }
  validation {
    condition = (
      var.ms_queue_limits.max_activos >= 1 && var.ms_queue_limits.max_activos <= 100 &&
      var.ms_queue_limits.espera_max_s >= 60 && var.ms_queue_limits.espera_max_s <= 3600 &&
      var.ms_queue_limits.lease_s >= 30 && var.ms_queue_limits.lease_s <= 900 &&
      var.ms_queue_limits.max_intentos >= 1 && var.ms_queue_limits.max_intentos <= 3 &&
      var.ms_queue_limits.retencion_s >= 60 && var.ms_queue_limits.retencion_s <= 86400 &&
      var.ms_queue_limits.sugerencias_espera_s >= 0 && var.ms_queue_limits.sugerencias_espera_s <= 20
    )
    error_message = "Límites de la cola M/S fuera de rango (ver src/app/ms_queue.py)."
  }
}

locals {
  ms_jobs = var.scientific_api_enabled
  # Un mensaje debe sobrevivir a la espera en cola y a los reintentos tras un reinicio.
  ms_jobs_message_retention = (var.ms_queue_limits.espera_max_s +
  var.ms_queue_limits.lease_s * var.ms_queue_limits.max_intentos + 60)
  ms_queue_environment = var.ms_queue_enabled ? {
    MS_JOBS_TABLE            = aws_dynamodb_table.ms_jobs[0].name
    MS_JOBS_QUEUE_URL        = aws_sqs_queue.ms_jobs[0].url
    MS_COLA_MAX_ACTIVOS      = tostring(var.ms_queue_limits.max_activos)
    MS_COLA_ESPERA_MAX_S     = tostring(var.ms_queue_limits.espera_max_s)
    MS_TRABAJO_LEASE_S       = tostring(var.ms_queue_limits.lease_s)
    MS_TRABAJO_MAX_INTENTOS  = tostring(var.ms_queue_limits.max_intentos)
    MS_RESULTADO_RETENCION_S = tostring(var.ms_queue_limits.retencion_s)
    MS_SUGERENCIAS_ESPERA_S  = tostring(var.ms_queue_limits.sugerencias_espera_s)
  } : {}
}

resource "aws_dynamodb_table" "ms_jobs" {
  count        = local.ms_jobs ? 1 : 0
  name         = "${var.project_name}-ms-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  attribute {
    name = "pk"
    type = "S"
  }
  # Borrado diferido de trabajos vencidos; la aplicación también comprueba el vencimiento al leer.
  ttl {
    attribute_name = "expira_ttl"
    enabled        = true
  }
}

resource "aws_sqs_queue" "ms_jobs_dlq" {
  count                     = local.ms_jobs ? 1 : 0
  name                      = "${var.project_name}-ms-jobs-dlq"
  message_retention_seconds = 345600 # 4 días, solo diagnóstico; sin reprocesado automático.
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "ms_jobs" {
  count                      = local.ms_jobs ? 1 : 0
  name                       = "${var.project_name}-ms-jobs"
  visibility_timeout_seconds = var.ms_queue_limits.lease_s + 60
  message_retention_seconds  = local.ms_jobs_message_retention
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ms_jobs_dlq[0].arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "ms_jobs_dlq" {
  count     = local.ms_jobs ? 1 : 0
  queue_url = aws_sqs_queue.ms_jobs_dlq[0].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.ms_jobs[0].arn]
  })
}

# El rol de tarea es compartido por API y ciencia (igual que la lectura de modelos);
# los permisos se limitan a esta tabla y esta cola.
resource "aws_iam_role_policy" "ms_jobs" {
  count = local.ms_jobs ? 1 : 0
  name  = "ms-jobs-queue"
  role  = local.create_ecs_roles ? aws_iam_role.task[0].name : data.aws_iam_role.ecs[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.ms_jobs[0].arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan"]
        Resource = aws_dynamodb_table.ms_jobs[0].arn
      },
    ]
  })
}

output "ms_jobs_table_name" {
  value = try(aws_dynamodb_table.ms_jobs[0].name, null)
}
output "ms_jobs_queue_url" {
  value = try(aws_sqs_queue.ms_jobs[0].url, null)
}
output "ms_jobs_dlq_url" {
  value = try(aws_sqs_queue.ms_jobs_dlq[0].url, null)
}
