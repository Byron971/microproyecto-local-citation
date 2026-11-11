data "aws_caller_identity" "current" {}
data "aws_ecr_repository" "api" {
  name = var.ecr_repository
}
data "aws_iam_role" "ecs" {
  name = var.ecs_role_name
}
data "aws_ssm_parameter" "image_tag" {
  name = "/${var.project_name}/api/image_tag"
}
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}
resource "aws_ecs_cluster" "main" {
  name = var.project_name
}
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project_name}.internal"
  vpc  = aws_vpc.main.id
}
resource "aws_service_discovery_service" "api" {
  name = "api"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "SRV"
    }
  }
  health_check_custom_config {
    failure_threshold = 1
  }
}
resource "aws_ecs_task_definition" "api" {
  family                   = var.project_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = data.aws_iam_role.ecs.arn
  task_role_arn            = data.aws_iam_role.ecs.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "api"
    image        = "${data.aws_ecr_repository.api.repository_url}:${nonsensitive(data.aws_ssm_parameter.image_tag.value)}"
    essential    = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [for name, value in merge(var.app_environment, {
      APP_ENV = "production", APP_HOST = "0.0.0.0"
    }) : { name = name, value = value }]
    secrets = [for name, arn in var.app_secrets : { name = name, valueFrom = arn }]
    healthCheck = {
      command     = ["CMD", "/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000${var.health_check_path}', timeout=4)"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = var.health_check_start_period
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
  lifecycle {
    precondition {
      condition = contains(lookup({
        "256"   = [512, 1024, 2048], "512" = [1024, 2048, 3072, 4096],
        "1024"  = range(2048, 8193, 1024), "2048" = range(4096, 16385, 1024),
        "4096"  = range(8192, 30721, 1024), "8192" = range(16384, 61441, 4096),
        "16384" = range(32768, 122881, 8192)
      }, tostring(var.task_cpu), []), var.task_memory)
      error_message = "La combinación CPU/memoria no es válida para Fargate Linux."
    }
    precondition {
      condition     = length(setintersection(toset(keys(var.app_environment)), toset(keys(var.app_secrets)))) == 0
      error_message = "Una variable no puede estar a la vez en environment y secrets."
    }
  }
}
resource "aws_ecs_service" "api" {
  name                               = var.project_name
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.api.arn
  desired_count                      = var.desired_count
  health_check_grace_period_seconds  = var.health_check_grace_period_seconds
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  capacity_provider_strategy {
    capacity_provider = var.use_fargate_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 1
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }
  service_registries {
    registry_arn   = aws_service_discovery_service.api.arn
    container_name = "api"
    container_port = 8000
  }
  depends_on = [aws_route_table_association.public, aws_vpc_security_group_egress_rule.task]
}
