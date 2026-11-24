variable "commercial_enabled" {
  type    = bool
  default = false
}
variable "commercial_visible" {
  type    = bool
  default = false
  validation {
    condition     = !var.commercial_visible || var.commercial_enabled
    error_message = "El comercial debe estar habilitado antes de mostrarse."
  }
}
variable "commercial_api_key_parameter_arn" {
  type    = string
  default = null
  validation {
    condition     = !var.commercial_enabled || can(regex("^arn:aws:ssm:us-east-1:646941583111:parameter/citas-api/commercial/openai_api_key$", var.commercial_api_key_parameter_arn))
    error_message = "Habilitar el comercial requiere el ARN del SecureString autorizado."
  }
}
variable "commercial_daily_limit" {
  type    = number
  default = 10
  validation {
    condition     = var.commercial_daily_limit >= 1 && var.commercial_daily_limit <= 100 && floor(var.commercial_daily_limit) == var.commercial_daily_limit
    error_message = "El límite diario debe ser entero entre 1 y 100."
  }
}
locals {
  runtime_secrets = merge(var.app_secrets, var.commercial_enabled ? { OPENAI_API_KEY = var.commercial_api_key_parameter_arn } : {})
  commercial_environment = {
    CITAS_COMMERCIAL_VISIBLE     = var.commercial_visible ? "1" : "0"
    CITAS_COMMERCIAL_ENABLED     = var.commercial_enabled ? "1" : "0"
    CITAS_COMMERCIAL_DAILY_LIMIT = tostring(var.commercial_daily_limit)
    CITAS_COMMERCIAL_LIMIT_TABLE = var.commercial_enabled ? aws_dynamodb_table.commercial_limits[0].name : ""
  }
}
resource "aws_dynamodb_table" "commercial_limits" {
  count        = var.commercial_enabled ? 1 : 0
  name         = "${var.project_name}-commercial-limits"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
}
resource "aws_iam_role_policy" "commercial_limits" {
  count = var.commercial_enabled ? 1 : 0
  name  = "reserve-commercial-call"
  role  = local.create_ecs_roles ? aws_iam_role.task[0].id : data.aws_iam_role.ecs[0].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = aws_dynamodb_table.commercial_limits[0].arn
  }] })
}
