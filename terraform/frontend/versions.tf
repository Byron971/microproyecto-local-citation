terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.100.0"
    }
  }
  backend "s3" {
    key          = "citas-frontend/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}
provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = var.project_name, ManagedBy = "Terraform" }
  }
}
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
variable "api_base_url" {
  description = "Origen HTTPS público de API Gateway, sin sufijo /api."
  type        = string
  validation {
    condition     = can(regex("^https://[a-zA-Z0-9.-]+/?$", var.api_base_url))
    error_message = "Indica el origen HTTPS del API, sin rutas, parámetros ni credenciales."
  }
}
