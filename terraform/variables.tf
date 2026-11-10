variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "project_name" {
  type    = string
  default = "citas-api"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,30}$", var.project_name))
    error_message = "Usa hasta 31 caracteres: letras minúsculas, números y guiones."
  }
}
variable "ecr_repository" {
  type    = string
  default = "citas-api"
}
variable "ecs_role_name" {
  description = "Rol existente para ejecución y tarea (LabRole en el lab). Vacío crea dos roles administrados por Terraform."
  type        = string
  default     = ""
  nullable    = false
  validation {
    condition     = var.ecs_role_name == "" || can(regex("^[A-Za-z0-9_+=,.@-]{1,64}$", var.ecs_role_name))
    error_message = "Usa el nombre de un rol IAM existente o una cadena vacía para crear roles."
  }
}
variable "secrets_kms_key_arns" {
  description = "ARN de claves KMS propias usadas por app_secrets; vacío si se usa la clave predeterminada de SSM."
  type        = list(string)
  default     = []
}
variable "task_cpu" {
  type    = number
  default = 512
}
variable "task_memory" {
  type    = number
  default = 1024
}
variable "desired_count" {
  type    = number
  default = 1
  validation {
    condition     = contains([0, 1], var.desired_count)
    error_message = "Este despliegue admite cero o una tarea."
  }
}
variable "use_fargate_spot" {
  type    = bool
  default = false
}
variable "health_check_path" {
  type    = string
  default = "/api/estado"
  validation {
    condition     = can(regex("^/[a-zA-Z0-9/_-]*$", var.health_check_path))
    error_message = "La ruta de salud debe comenzar con / y contener solo letras, números, /, _ o guiones."
  }
}
variable "health_check_start_period" {
  type    = number
  default = 120
  validation {
    condition     = var.health_check_start_period >= 120 && var.health_check_start_period <= 300
    error_message = "El startPeriod debe estar entre 120 y 300 segundos."
  }
}
variable "health_check_grace_period_seconds" {
  type    = number
  default = 180
  validation {
    condition     = var.health_check_grace_period_seconds >= 180 && floor(var.health_check_grace_period_seconds) == var.health_check_grace_period_seconds
    error_message = "La gracia debe ser un número entero de al menos 180 segundos."
  }
}
variable "app_environment" {
  type    = map(string)
  default = {}
}
variable "app_secrets" {
  description = "Nombre de variable de entorno => ARN de parámetro SSM SecureString existente."
  type        = map(string)
  default     = {}
}
variable "custom_domain_name" {
  type    = string
  default = ""
}
variable "certificate_arn" {
  type    = string
  default = ""
}

variable "cors_allowed_origins" {
  description = "Orígenes adicionales permitidos, sin barra final. CloudFront se incluye automáticamente."
  type        = list(string)
  default     = []
  validation {
    condition     = alltrue([for origin in var.cors_allowed_origins : can(regex("^https://[a-zA-Z0-9.-]+(:[0-9]+)?$|^http://(localhost|127\\.0\\.0\\.1):[0-9]+$", origin))])
    error_message = "Usa orígenes HTTPS exactos, o localhost HTTP con puerto, sin rutas ni barra final."
  }
}
