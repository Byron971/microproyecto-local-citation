mock_provider "aws" {
  mock_resource "aws_cloudfront_function" {
    defaults = { arn = "arn:aws:cloudfront::123456789012:function/test-routes" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b"] }
  }
  mock_data "aws_ecr_repository" {
    defaults = { repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/citas-api" }
  }
  mock_data "aws_ssm_parameter" {
    defaults = { value = "test-image" }
  }
  mock_data "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/LabRole" }
  }
}

run "personal_account" {
  command = plan
  variables { ecs_role_name = "" }
  assert {
    condition     = length(aws_iam_role.execution) == 1 && length(aws_iam_role.task) == 1 && length(data.aws_iam_role.ecs) == 0
    error_message = "La cuenta personal debe crear ambos roles sin consultar LabRole."
  }
  assert {
    condition     = toset(keys(aws_apigatewayv2_route.api)) == toset(["GET /", "GET /{proxy+}", "POST /{proxy+}"])
    error_message = "Las rutas no deben capturar OPTIONS; API Gateway debe responder el preflight."
  }
  assert {
    condition     = endswith(aws_iam_role_policy_attachment.execution[0].policy_arn, ":iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy") && length(aws_iam_role_policy.secrets) == 0
    error_message = "Solo se conceden permisos de ejecución y no secretos sin configurar."
  }
  assert {
    condition     = jsondecode(aws_iam_role.task[0].assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012"
    error_message = "La confianza debe limitarse a la cuenta actual."
  }
}

run "learner_lab" {
  command = plan
  variables { ecs_role_name = "LabRole" }
  assert {
    condition     = length(aws_iam_role.execution) == 0 && length(aws_iam_role.task) == 0 && length(aws_iam_role_policy_attachment.execution) == 0 && length(aws_iam_role_policy.secrets) == 0
    error_message = "El laboratorio no debe crear ni modificar roles IAM."
  }
  assert {
    condition     = aws_ecs_task_definition.api.execution_role_arn == "arn:aws:iam::123456789012:role/LabRole" && aws_ecs_task_definition.api.task_role_arn == "arn:aws:iam::123456789012:role/LabRole"
    error_message = "La tarea debe reutilizar LabRole en ambos roles."
  }
}

run "configured_secrets" {
  command = plan
  variables {
    ecs_role_name        = ""
    app_secrets          = { API_KEY = "arn:aws:ssm:us-east-1:123456789012:parameter/citas-api/key" }
    secrets_kms_key_arns = ["arn:aws:kms:us-east-1:123456789012:key/example"]
  }
  assert {
    condition     = toset(jsondecode(aws_iam_role_policy.secrets[0].policy).Statement[0].Resource) == toset(values(var.app_secrets)) && toset(jsondecode(aws_iam_role_policy.secrets[0].policy).Statement[1].Resource) == toset(var.secrets_kms_key_arns)
    error_message = "Los permisos SSM/KMS deben limitarse a los ARN configurados."
  }
}

run "unified_frontend" {
  command = apply
  # Solo el grafo de API/CloudFront; todo usa el proveedor simulado.
  plan_options { target = [aws_apigatewayv2_api.main] }
  variables {
    ecs_role_name        = ""
    cors_allowed_origins = ["http://localhost:5173"]
  }
  override_resource {
    target = aws_cloudfront_distribution.web
    values = { domain_name = "test-ui.cloudfront.net" }
  }
  override_resource {
    target = aws_apigatewayv2_api.main
    values = { api_endpoint = "https://test-api.execute-api.us-east-1.amazonaws.com" }
  }
  assert {
    condition     = toset(aws_apigatewayv2_api.main.cors_configuration[0].allow_origins) == toset(["https://test-ui.cloudfront.net", "http://localhost:5173"])
    error_message = "CORS debe permitir CloudFront automáticamente y conservar los orígenes extra."
  }
  assert {
    condition     = output.frontend_url == "https://test-ui.cloudfront.net" && output.api_base_url == "https://test-api.execute-api.us-east-1.amazonaws.com"
    error_message = "El mismo estado debe devolver las URLs del frontend y del API para publicar la UI."
  }
  assert {
    condition     = aws_s3_bucket.web.bucket == "citas-api-web-123456789012-us-east-1"
    error_message = "El bucket web debe pertenecer al proyecto, cuenta y región actuales."
  }
}
