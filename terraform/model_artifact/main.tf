terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 5.100.0" }
  }
  backend "s3" {
    bucket       = "citas-api-models-646941583111-us-east-1"
    key          = "terraform/t04-ms-artifact/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = ["646941583111"]
}
resource "aws_s3_object" "bundle" {
  bucket                 = "citas-api-models-646941583111-us-east-1"
  key                    = "experiments/t04-ms-serverless/b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f/model.tar.gz"
  source                 = "/opt/citas/models/ms-scibert-b8ee47317c29afbc.tar.gz"
  source_hash            = "b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f"
  server_side_encryption = "AES256"
  content_type           = "application/gzip"
  metadata               = { sha256 = "b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f" }
  tags                   = { Purpose = "T04-only", Project = "citas-api", Temporary = "true" }
}
output "model_url" { value = "s3://${aws_s3_object.bundle.bucket}/${aws_s3_object.bundle.key}" }
output "version_id" { value = aws_s3_object.bundle.version_id }
