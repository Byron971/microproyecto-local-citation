output "api_url" {
  value = local.api_public_url
}
output "ecr_repository_url" {
  value = data.aws_ecr_repository.api.repository_url
}
output "cluster_name" {
  value = aws_ecs_cluster.main.name
}
output "service_name" {
  value = aws_ecs_service.api.name
}
output "task_definition_arn" {
  value = aws_ecs_task_definition.api.arn
}
output "custom_domain_target" {
  value = try(aws_apigatewayv2_domain_name.custom[0].domain_name_configuration[0].target_domain_name, null)
}

output "frontend_url" {
  description = "URL HTTPS de la aplicación React, con dominio propio cuando está habilitado."
  value       = local.frontend_custom_domain ? "https://${var.frontend_domain_name}" : "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "frontend_bucket" {
  value = aws_s3_bucket.web.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.web.id
}

output "api_base_url" {
  value = local.api_public_url
}

output "domain_hosted_zone_id" {
  value = try(aws_route53domains_domain.app[0].hosted_zone_id, null)
}
output "domain_expiration_date" {
  value = try(aws_route53domains_domain.app[0].expiration_date, null)
}
