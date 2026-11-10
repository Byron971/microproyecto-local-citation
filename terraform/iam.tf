data "aws_partition" "current" {}

data "aws_iam_role" "ecs" {
  count = var.ecs_role_name != "" ? 1 : 0
  name  = var.ecs_role_name
}

locals {
  create_ecs_roles   = var.ecs_role_name == ""
  execution_role_arn = local.create_ecs_roles ? aws_iam_role.execution[0].arn : data.aws_iam_role.ecs[0].arn
  task_role_arn      = local.create_ecs_roles ? aws_iam_role.task[0].arn : data.aws_iam_role.ecs[0].arn
  ecs_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike = {
          "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
        }
      }
    }]
  })
}

resource "aws_iam_role" "execution" {
  count              = local.create_ecs_roles ? 1 : 0
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = local.ecs_trust_policy
}

resource "aws_iam_role_policy_attachment" "execution" {
  count      = local.create_ecs_roles ? 1 : 0
  role       = aws_iam_role.execution[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# El API no necesita permisos AWS propios; los secretos los inyecta ECS.
resource "aws_iam_role" "task" {
  count              = local.create_ecs_roles ? 1 : 0
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = local.ecs_trust_policy
}

resource "aws_iam_role_policy" "secrets" {
  count = local.create_ecs_roles && length(var.app_secrets) > 0 ? 1 : 0
  name  = "read-configured-secrets"
  role  = aws_iam_role.execution[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([{
      Effect   = "Allow"
      Action   = ["ssm:GetParameters"]
      Resource = distinct(values(var.app_secrets))
      }], length(var.secrets_kms_key_arns) == 0 ? [] : [{
      Effect   = "Allow"
      Action   = ["kms:Decrypt"]
      Resource = var.secrets_kms_key_arns
    }])
  })
}
