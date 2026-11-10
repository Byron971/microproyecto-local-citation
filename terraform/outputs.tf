output "api_url" {
  value = aws_apigatewayv2_stage.main.invoke_url
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

output "frontend_url" { value = "https://${aws_cloudfront_distribution.web.domain_name}" }
output "frontend_bucket" { value = aws_s3_bucket.web.id }
output "distribution_id" { value = aws_cloudfront_distribution.web.id }
output "api_base_url" { value = aws_apigatewayv2_api.main.api_endpoint }
