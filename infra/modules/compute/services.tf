# API and relay Fargate services.
#
# API: behind the ALB, target-tracking autoscaled on CPU (QA1 - the API tier
# scales with map/RSVP traffic). Runs migrations on start via its entrypoint.
# Relay: a singleton poller (ADR-0006/0010); a second instance would contend on
# the outbox, so it is deliberately not autoscaled (desired_count = 1).

# --- API --------------------------------------------------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = var.lab_role_arn
  task_role_arn            = var.lab_role_arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [
        { containerPort = var.app_container_port, protocol = "tcp" }
      ]
      environment = local.api_environment
      secrets     = local.api_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this["api"].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  # The entrypoint runs migrations (behind an advisory lock) before the server
  # binds, so give a new task time to migrate + boot before health checks can
  # mark it unhealthy and ECS kills it mid-startup.
  health_check_grace_period_seconds = var.api_health_check_grace_period

  # Roll forward safely: keep full capacity during a deploy and auto-roll-back
  # a failing task set instead of looping a bad image indefinitely.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.app_container_port
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${local.name}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.api_cpu_target
    scale_in_cooldown  = 60
    scale_out_cooldown = 30
  }
}

# Request-count scaling. This async/IO-bound API saturates its connection pool
# and latency before CPU reaches the CPU target, so CPU-only tracking can fail
# to scale out during the headline spike. Tracking requests-per-target makes the
# API tier scale with the load the test actually generates. CPU stays as a
# backstop for any genuinely CPU-bound path.
resource "aws_appautoscaling_policy" "api_requests" {
  name               = "${local.name}-api-requests"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      # Format: app/<alb>/<id>/targetgroup/<tg>/<id> - the ALB + target group
      # arn_suffixes joined, which is what this metric's resource_label expects.
      resource_label = "${aws_lb.api.arn_suffix}/${aws_lb_target_group.api.arn_suffix}"
    }
    target_value       = var.api_request_count_target
    scale_in_cooldown  = 60
    scale_out_cooldown = 30
  }
}

# --- Relay ------------------------------------------------------------------

resource "aws_ecs_task_definition" "relay" {
  family                   = "${local.name}-relay"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.relay_cpu
  memory                   = var.relay_memory
  execution_role_arn       = var.lab_role_arn
  task_role_arn            = var.lab_role_arn

  container_definitions = jsonencode([
    {
      name        = "relay"
      image       = var.relay_image
      essential   = true
      environment = local.relay_environment
      secrets     = local.relay_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this["relay"].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "relay"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "relay" {
  name            = "relay"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.relay.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # Singleton poller, but still auto-roll-back a bad image rather than
  # crash-loop it. min 0% / max 100% keeps it a singleton across deploys (the
  # outbox lock makes a transient second instance safe, but we avoid two
  # pollers contending by default).
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.app_sg_id]
    assign_public_ip = false
  }
}
