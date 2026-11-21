locals {
  frontend_custom_domain = var.frontend_domain_name != ""
}
resource "aws_acm_certificate" "frontend" {
  count             = local.frontend_custom_domain ? 1 : 0
  provider          = aws.virginia
  domain_name       = var.frontend_domain_name
  validation_method = "DNS"
  lifecycle {
    create_before_destroy = true
  }
}
resource "aws_route53_record" "frontend_validation" {
  for_each = local.frontend_custom_domain ? {
    for option in aws_acm_certificate.frontend[0].domain_validation_options : option.domain_name => option
  } : {}
  zone_id = aws_route53domains_domain.app[0].hosted_zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  records = [each.value.resource_record_value]
  ttl     = 60
}
resource "aws_acm_certificate_validation" "frontend" {
  count                   = local.frontend_custom_domain ? 1 : 0
  provider                = aws.virginia
  certificate_arn         = aws_acm_certificate.frontend[0].arn
  validation_record_fqdns = [for record in aws_route53_record.frontend_validation : record.fqdn]
}
resource "aws_route53_record" "frontend" {
  for_each = local.frontend_custom_domain ? toset(["A", "AAAA"]) : toset([])
  zone_id  = aws_route53domains_domain.app[0].hosted_zone_id
  name     = var.frontend_domain_name
  type     = each.value
  alias {
    name                   = aws_cloudfront_distribution.web.domain_name
    zone_id                = aws_cloudfront_distribution.web.hosted_zone_id
    evaluate_target_health = false
  }
}
