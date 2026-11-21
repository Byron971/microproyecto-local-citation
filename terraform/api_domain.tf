locals {
  # Con dominio del frontend, administrar api.<dominio> y su certificado automáticamente.
  # Conservar la opción anterior de un dominio externo y certificado proporcionado.
  managed_api_domain = local.frontend_custom_domain && var.custom_domain_name == ""
  api_domain_name    = var.custom_domain_name != "" ? var.custom_domain_name : (local.frontend_custom_domain ? "api.${var.frontend_domain_name}" : "")
  api_custom_domain  = local.api_domain_name != ""
  api_public_url     = local.api_custom_domain ? "https://${local.api_domain_name}" : aws_apigatewayv2_api.main.api_endpoint
}

resource "aws_acm_certificate" "api" {
  count             = local.managed_api_domain ? 1 : 0
  domain_name       = local.api_domain_name
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "api_validation" {
  for_each = local.managed_api_domain ? {
    for option in aws_acm_certificate.api[0].domain_validation_options : option.domain_name => option
  } : {}
  zone_id = aws_route53domains_domain.app[0].hosted_zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "api" {
  count                   = local.managed_api_domain ? 1 : 0
  certificate_arn         = aws_acm_certificate.api[0].arn
  validation_record_fqdns = [for record in aws_route53_record.api_validation : record.fqdn]
}

resource "aws_route53_record" "api" {
  count   = local.managed_api_domain ? 1 : 0
  zone_id = aws_route53domains_domain.app[0].hosted_zone_id
  name    = local.api_domain_name
  type    = "A"
  alias {
    name                   = aws_apigatewayv2_domain_name.custom[0].domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.custom[0].domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}
