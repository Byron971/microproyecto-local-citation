variable "scientific_models_enabled" {
  description = "Crea almacenamiento privado y lectura ECS para artefactos científicos versionados."
  type        = bool
  default     = true
}

resource "aws_s3_bucket" "models" {
  count  = var.scientific_models_enabled ? 1 : 0
  bucket = "${var.project_name}-models-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "models" {
  count                   = var.scientific_models_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.models[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "models" {
  count  = var.scientific_models_enabled ? 1 : 0
  bucket = aws_s3_bucket.models[0].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  count  = var.scientific_models_enabled ? 1 : 0
  bucket = aws_s3_bucket.models[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "models" {
  count  = var.scientific_models_enabled ? 1 : 0
  bucket = aws_s3_bucket.models[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_policy" "models" {
  count  = var.scientific_models_enabled ? 1 : 0
  bucket = aws_s3_bucket.models[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireTLS", Effect = "Deny", Principal = "*", Action = "s3:*"
      Resource  = [aws_s3_bucket.models[0].arn, "${aws_s3_bucket.models[0].arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.models]
}

resource "aws_iam_role_policy" "models" {
  count = var.scientific_models_enabled ? 1 : 0
  name  = "read-scientific-model-releases"
  role  = local.create_ecs_roles ? aws_iam_role.task[0].name : data.aws_iam_role.ecs[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["s3:GetObject"]
      Resource = "${aws_s3_bucket.models[0].arn}/releases/*"
    }]
  })
}

output "scientific_models_bucket" {
  value = try(aws_s3_bucket.models[0].id, null)
}
