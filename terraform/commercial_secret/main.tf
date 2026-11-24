# La clave se escribe sin persistir su valor en estado ni plan.
terraform {
  required_version = ">= 1.11, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 5.100.0" }
  }
}
provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = ["646941583111"]
}
variable "openai_api_key" {
  type      = string
  sensitive = true
  ephemeral = true
}
variable "key_version" {
  type    = number
  default = 1
}
resource "aws_ssm_parameter" "openai" {
  name             = "/citas-api/commercial/openai_api_key"
  type             = "SecureString"
  value_wo         = var.openai_api_key
  value_wo_version = var.key_version
  tags             = { Project = "citas-api", ManagedBy = "Terraform" }
}
output "parameter_arn" { value = aws_ssm_parameter.openai.arn }

output "key_version" { value = aws_ssm_parameter.openai.value_wo_version }
