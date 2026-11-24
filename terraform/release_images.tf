# Import existing deployment pointers; all changes during this release use Terraform.
# A null override preserves the current pointer and remains compatible with CI.
variable "release_api_image_tag" {
  type     = string
  default  = null
  nullable = true
}
variable "release_science_image_uri" {
  type     = string
  default  = null
  nullable = true
  validation {
    condition     = var.release_science_image_uri == null || can(regex("@sha256:[a-f0-9]{64}$", var.release_science_image_uri))
    error_message = "La imagen científica debe fijarse por digest."
  }
}
resource "aws_ssm_parameter" "release_api" {
  name  = "/${var.project_name}/api/image_tag"
  type  = "String"
  value = coalesce(var.release_api_image_tag, nonsensitive(data.aws_ssm_parameter.image_tag.value))
}
resource "aws_ssm_parameter" "release_science" {
  count = var.scientific_api_enabled ? 1 : 0
  name  = "/${var.project_name}/science/image_uri"
  type  = "String"
  value = coalesce(var.release_science_image_uri, nonsensitive(data.aws_ssm_parameter.scientific_image[0].value))
}
import {
  to = aws_ssm_parameter.release_api
  id = "/${var.project_name}/api/image_tag"
}
import {
  for_each = var.scientific_api_enabled ? { science = true } : {}
  to       = aws_ssm_parameter.release_science[0]
  id       = "/${var.project_name}/science/image_uri"
}
