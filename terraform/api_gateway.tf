resource "aws_apigatewayv2_api" "main" {
  name          = var.project_name
  protocol_type = "HTTP"
}
resource "aws_apigatewayv2_vpc_link" "main" {
  name               = var.project_name
  security_group_ids = [aws_security_group.link.id]
  subnet_ids         = aws_subnet.public[*].id
}
resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = aws_lb_listener.api.arn
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.main.id
  payload_format_version = "1.0"
  timeout_milliseconds   = 30000
  request_parameters     = { "overwrite:path" = "$request.path" }
}
resource "aws_apigatewayv2_route" "api" {
  for_each  = toset(["ANY /", "ANY /{proxy+}"])
  api_id    = aws_apigatewayv2_api.main.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}
resource "aws_cloudwatch_log_group" "gateway" {
  name              = "/apigateway/${var.project_name}"
  retention_in_days = 14
}
resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = 20
    throttling_burst_limit = 40
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId", sourceIp = "$context.identity.sourceIp",
      requestTime    = "$context.requestTime", httpMethod = "$context.httpMethod",
      routeKey       = "$context.routeKey", status = "$context.status",
      responseLength = "$context.responseLength", integrationError = "$context.integrationErrorMessage"
    })
  }
}
resource "aws_apigatewayv2_domain_name" "custom" {
  count       = var.custom_domain_name != "" ? 1 : 0
  domain_name = var.custom_domain_name
  domain_name_configuration {
    certificate_arn = var.certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }
  lifecycle {
    precondition {
      condition     = var.certificate_arn != ""
      error_message = "El dominio personalizado requiere un certificado ACM en la misma región."
    }
  }
}
resource "aws_apigatewayv2_api_mapping" "custom" {
  count       = var.custom_domain_name != "" ? 1 : 0
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.custom[0].id
  stage       = aws_apigatewayv2_stage.main.id
}
