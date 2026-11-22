# M/S is isolated from the lightweight API. The current image is pinned by digest
# in SSM so subsequent baseline deployments preserve this release.
variable "scientific_api_enabled" {
  type    = bool
  default = true
}
variable "scientific_cors_origins" {
  type    = list(string)
  default = ["https://proyectocitas-grupo19.click"]
}
variable "scientific_task_cpu" {
  type    = number
  default = 2048
  validation {
    condition     = contains([2048, 4096, 8192], var.scientific_task_cpu)
    error_message = "Usa 2, 4 u 8 vCPU para el servicio científico."
  }
}
variable "scientific_task_memory" {
  type    = number
  default = 6144
}
variable "scientific_desired_count" {
  type    = number
  default = 1
  validation {
    condition     = contains([0, 1], var.scientific_desired_count)
    error_message = "Usa cero o una tarea científica."
  }
}
data "aws_ssm_parameter" "scientific_image" {
  count = var.scientific_api_enabled ? 1 : 0
  name  = "/${var.project_name}/science/image_uri"
}
resource "aws_cloudwatch_log_group" "scientific" {
  count             = var.scientific_api_enabled ? 1 : 0
  name              = "/ecs/${var.project_name}-science"
  retention_in_days = 14
}
resource "aws_lb_target_group" "scientific" {
  count                = var.scientific_api_enabled ? 1 : 0
  name_prefix          = "ms-"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30
  health_check {
    enabled             = true
    path                = "/health/ready"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
  lifecycle {
    create_before_destroy = true
  }
}
resource "aws_lb_listener_rule" "scientific" {
  count        = var.scientific_api_enabled ? 1 : 0
  listener_arn = aws_lb_listener.api.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.scientific[0].arn
  }
  condition {
    path_pattern {
      # ALB allows three comparisons per condition; reserve this prefix for M/S.
      values = ["/api/analisis-cita-ms*", "/api/recomendar", "/api/modelos"]
    }
  }
}
resource "aws_ecs_task_definition" "scientific" {
  count                    = var.scientific_api_enabled ? 1 : 0
  family                   = "${var.project_name}-science"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.scientific_task_cpu
  memory                   = var.scientific_task_memory
  execution_role_arn       = local.execution_role_arn
  task_role_arn            = local.task_role_arn
  skip_destroy             = true
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "science"
    image        = nonsensitive(aws_ssm_parameter.release_science[0].value)
    essential    = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [for name, value in {
      AWS_REGION      = var.aws_region
      OMP_NUM_THREADS = tostring(var.scientific_task_cpu / 1024)
      MKL_NUM_THREADS = tostring(var.scientific_task_cpu / 1024)
      MS_CORS_ORIGINS = join(",", var.scientific_cors_origins)
    } : { name = name, value = value }]
    healthCheck = {
      command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 300
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.scientific[0].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "science"
      }
    }
  }])
  lifecycle {
    create_before_destroy = true
    precondition {
      condition = contains(lookup({
        "2048" = range(4096, 16385, 1024), "4096" = range(8192, 30721, 1024),
        "8192" = range(16384, 61441, 4096)
      }, tostring(var.scientific_task_cpu), []), var.scientific_task_memory)
      error_message = "Combinación CPU/memoria científica no válida para Fargate."
    }
    precondition {
      condition     = can(regex("@sha256:[a-f0-9]{64}$", nonsensitive(aws_ssm_parameter.release_science[0].value)))
      error_message = "La imagen científica debe fijarse mediante digest SHA256."
    }
  }
}
resource "aws_ecs_service" "scientific" {
  count                              = var.scientific_api_enabled ? 1 : 0
  name                               = "${var.project_name}-science"
  cluster                            = aws_ecs_cluster.main.id
  task_definition                    = aws_ecs_task_definition.scientific[0].arn
  desired_count                      = var.scientific_desired_count
  health_check_grace_period_seconds  = 600
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  capacity_provider_strategy {
    capacity_provider = "FARGATE"
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
  load_balancer {
    target_group_arn = aws_lb_target_group.scientific[0].arn
    container_name   = "science"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener_rule.scientific, aws_iam_role_policy.models]
}
output "scientific_service_name" {
  value = try(aws_ecs_service.scientific[0].name, null)
}
output "scientific_task_definition_arn" {
  value = try(aws_ecs_task_definition.scientific[0].arn, null)
}
