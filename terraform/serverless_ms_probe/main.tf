# Isolated T04 experiment; never shares production state or changes ECS.
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 5.100.0" }
  }
}
provider "aws" {
  region              = var.region
  profile             = var.profile
  allowed_account_ids = [var.account_id]
}
variable "profile" { default = "josezambrana" }
variable "region" { default = "us-east-1" }
variable "account_id" { default = "646941583111" }
variable "name" { default = "citas-ms-serverless-t04" }
variable "model_bucket" { default = "citas-api-models-646941583111-us-east-1" }
# Compatibilidad con variables locales anteriores; el paquete se publica en EC2.
variable "bundle_path" {
  type    = string
  default = ""
}
variable "bundle_sha256" {
  default = "b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f"
}
variable "deploy_endpoint" { default = false }
variable "image_digest" {
  default = ""
  validation {
    condition     = var.image_digest == "" || can(regex("^sha256:[a-f0-9]{64}$", var.image_digest))
    error_message = "Use the published ECR registry digest, not a mutable tag."
  }
}
locals {
  tags      = { Purpose = "T04-only", Project = "citas-api", Temporary = "true" }
  model_key = "experiments/t04-ms-serverless/${var.bundle_sha256}/model.tar.gz"
}
resource "aws_ecr_repository" "probe" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true # Only this dedicated temporary repository, during cleanup.
  encryption_configuration { encryption_type = "AES256" }
  tags = local.tags
}
# El objeto pertenece al estado aislado terraform/model_artifact, ejecutado en EC2.
data "aws_s3_object" "probe" {
  count  = var.deploy_endpoint ? 1 : 0
  bucket = var.model_bucket
  key    = local.model_key
}
resource "aws_cloudwatch_log_group" "probe" {
  count             = var.deploy_endpoint ? 1 : 0
  name              = "/aws/sagemaker/Endpoints/${var.name}"
  retention_in_days = 3
  tags              = local.tags
}
resource "aws_iam_role" "probe" {
  count = var.deploy_endpoint ? 1 : 0
  name  = var.name
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Principal = { Service = "sagemaker.amazonaws.com" }, Action = "sts:AssumeRole",
    Condition = { StringEquals = { "aws:SourceAccount" = var.account_id }, ArnLike = { "aws:SourceArn" = "arn:aws:sagemaker:${var.region}:${var.account_id}:*" } }
  }] })
  tags = local.tags
}
resource "aws_iam_role_policy" "probe" {
  count = var.deploy_endpoint ? 1 : 0
  name  = "read-probe-artifacts"
  role  = aws_iam_role.probe[0].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "arn:aws:s3:::${var.model_bucket}/${local.model_key}" },
    { Effect = "Allow", Action = ["s3:GetBucketLocation"], Resource = "arn:aws:s3:::${var.model_bucket}" },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = "arn:aws:s3:::${var.model_bucket}", Condition = { StringLike = { "s3:prefix" = local.model_key } } },
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = aws_ecr_repository.probe.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.probe[0].arn}:*" }
  ] })
}
resource "aws_sagemaker_model" "probe" {
  count              = var.deploy_endpoint ? 1 : 0
  name               = var.name
  execution_role_arn = aws_iam_role.probe[0].arn
  primary_container {
    image          = "${aws_ecr_repository.probe.repository_url}@${var.image_digest}"
    model_data_url = "s3://${data.aws_s3_object.probe[0].bucket}/${data.aws_s3_object.probe[0].key}"
  }
  lifecycle {
    precondition {
      condition     = var.image_digest != ""
      error_message = "Publish the AMD64 image with Makefile before enabling the endpoint."
    }
  }
  depends_on = [aws_iam_role_policy.probe]
  tags       = local.tags
}
resource "aws_sagemaker_endpoint_configuration" "probe" {
  count = var.deploy_endpoint ? 1 : 0
  name  = var.name
  production_variants {
    variant_name           = "AllTraffic"
    model_name             = aws_sagemaker_model.probe[0].name
    initial_variant_weight = 1
    serverless_config {
      memory_size_in_mb = 6144
      max_concurrency   = 1
    }
  }
  tags = local.tags
}
resource "aws_sagemaker_endpoint" "probe" {
  count                = var.deploy_endpoint ? 1 : 0
  name                 = var.name
  endpoint_config_name = aws_sagemaker_endpoint_configuration.probe[0].name
  tags                 = local.tags
}
output "repository_url" { value = aws_ecr_repository.probe.repository_url }
output "endpoint_name" { value = var.deploy_endpoint ? aws_sagemaker_endpoint.probe[0].name : null }
output "model_version_id" { value = var.deploy_endpoint ? data.aws_s3_object.probe[0].version_id : null }
