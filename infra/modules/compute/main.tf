# Compute - the three deployable units on one ECS cluster, plus the managed
# counter store (ADR-0002, ADR-0017):
#   * api    - modular monolith, Fargate behind the ALB, autoscaled
#   * relay   - outbox relay / FR5 transition, Fargate singleton (ADR-0006/0010)
#   * worker  - notification delivery, container-image Lambda triggered by SQS
# The RSVP counter runs on ElastiCache Redis (ADR-0005), defined in
# elasticache.tf.
#
# All task/execution/Lambda roles reference the pre-provisioned LabRole; no IAM
# resources are created here (ADR-0017).

locals {
  name = "${var.project}-${var.environment}"
  # Reach ElastiCache at its node endpoint (ADR-0005). Defined in elasticache.tf.
  redis_url = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"

  # Plaintext environment for the API container. UVICORN_WORKERS and the pool
  # sizes are bounded together so an autoscaled fleet stays within the RDS
  # connection budget (see compute/variables.tf capacity note). CORS origins are
  # only injected when set, so the API keeps its localhost dev default otherwise.
  api_environment = concat(
    [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "REDIS_URL", value = local.redis_url },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "AWS_SNS_TOPIC_ARN", value = var.sns_topic_arn },
      { name = "EMAIL_PROVIDER", value = var.email_provider },
      { name = "EMAIL_FROM_ADDRESS", value = var.email_from_address },
      { name = "UVICORN_WORKERS", value = tostring(var.uvicorn_workers) },
      { name = "DB_POOL_SIZE", value = tostring(var.db_pool_size) },
      { name = "DB_MAX_OVERFLOW", value = tostring(var.db_max_overflow) },
    ],
    var.cors_allowed_origins != "" ? [
      { name = "CORS_ALLOWED_ORIGINS", value = var.cors_allowed_origins },
    ] : [],
  )

  # Inject every secret present in secret_arns whose key the API understands.
  # RESEND_API_KEY may be absent (email disabled) - only inject what exists.
  api_secret_keys = [
    for k in ["DATABASE_URL", "DATABASE_REPLICA_URL", "SECRET_KEY", "RESEND_API_KEY", "VAPID_PUBLIC_KEY"] :
    k if contains(keys(var.secret_arns), k)
  ]
  api_secrets = [
    for k in local.api_secret_keys : { name = k, valueFrom = var.secret_arns[k] }
  ]

  relay_environment = [
    { name = "AWS_REGION", value = var.aws_region },
    { name = "AWS_SNS_TOPIC_ARN", value = var.sns_topic_arn },
    { name = "RELAY_POLL_INTERVAL_SECONDS", value = tostring(var.relay_poll_interval_seconds) },
  ]

  relay_secrets = [
    { name = "DATABASE_URL", valueFrom = var.secret_arns["DATABASE_URL"] },
  ]
}

resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = { Name = local.name }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_cloudwatch_log_group" "this" {
  for_each          = toset(["api", "relay", "worker"])
  name              = "/ecs/${local.name}/${each.key}"
  retention_in_days = var.log_retention_days
  tags              = { Name = "${local.name}-${each.key}" }
}
