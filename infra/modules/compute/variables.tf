variable "project" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }

variable "lab_role_arn" {
  type        = string
  description = "ARN of the pre-provisioned LabRole used for all task/Lambda roles."
}

# Networking
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "alb_sg_id" { type = string }
variable "app_sg_id" { type = string }
variable "redis_sg_id" { type = string }
variable "lambda_sg_id" { type = string }

variable "app_container_port" {
  type    = number
  default = 8000
}

# Images (full URI including tag)
variable "api_image" { type = string }
variable "relay_image" { type = string }
variable "worker_image" { type = string }

# Secrets injected into ECS tasks from SSM Parameter Store (ARNs).
variable "secret_arns" {
  type        = map(string)
  description = "Map of env var name to SSM parameter ARN for ECS secret injection."
}

# Secret values passed to the Lambda environment (Learner Lab has no native SSM
# injection for Lambda; see ADR-0017 / runbook).
variable "worker_secrets" {
  type      = map(string)
  sensitive = true
}

# Messaging
variable "sns_topic_arn" { type = string }
variable "queue_arns" {
  type        = map(string)
  description = "Per-channel SQS queue ARNs the worker subscribes to."
}

# Email
variable "email_provider" {
  type    = string
  default = "resend"
}
variable "email_from_address" {
  type    = string
  default = "noreply@tickettailor.local"
}

# Sizing - API
variable "api_cpu" {
  type    = number
  default = 512
}
variable "api_memory" {
  type    = number
  default = 1024
}
variable "api_desired_count" {
  type    = number
  default = 2
}
variable "api_max_count" {
  type    = number
  default = 10
}
variable "api_cpu_target" {
  type    = number
  default = 60
}
variable "api_request_count_target" {
  type        = number
  description = "Target ALB requests per task for the request-count autoscaling policy. Calibrate from a dry run; the value at which one task approaches its latency/pool limit."
  default     = 500
}
variable "api_health_check_grace_period" {
  type        = number
  description = "Seconds ECS waits before health checks can mark a new API task unhealthy, covering migration + boot time."
  default     = 120
}
variable "uvicorn_workers" {
  type        = number
  description = "uvicorn worker processes per API task. Roughly one per vCPU (api_cpu/1024). Pool sizing is per-process, so keep workers * (DB_POOL_SIZE + DB_MAX_OVERFLOW) within the RDS connection budget."
  default     = 2
}

# SQLAlchemy pool sizing per engine, per uvicorn worker. Worst-case RDS
# connection use is roughly:
#   api_max_count * uvicorn_workers * 2 engines * (db_pool_size + db_max_overflow)
# Keep that under ~80% of the RDS instance max_connections. With db.t3.medium
# (~450), api_max_count=10, uvicorn_workers=2 and 3+3 below => ~240. Safe.
variable "db_pool_size" {
  type    = number
  default = 3
}
variable "db_max_overflow" {
  type    = number
  default = 3
}

# Allowed CORS origins for the API (comma-separated), e.g. the CloudFront URL
# of the SPA. Left empty by default; when empty the env var is not injected and
# the API keeps its localhost dev default. Set this to the frontend origin when
# enable_frontend is true, or the browser app's requests are blocked at
# preflight.
variable "cors_allowed_origins" {
  type    = string
  default = ""
}

# Sizing - relay
variable "relay_cpu" {
  type    = number
  default = 256
}
variable "relay_memory" {
  type    = number
  default = 512
}
variable "relay_poll_interval_seconds" {
  type    = number
  default = 1.0
}

# Sizing - redis (ElastiCache node type; ADR-0005)
variable "redis_node_type" {
  type    = string
  default = "cache.t3.micro"
}

# Sizing - worker
variable "worker_timeout" {
  type    = number
  default = 30
}
variable "worker_memory" {
  type    = number
  default = 256
}
variable "worker_batch_size" {
  type    = number
  default = 10
}

variable "log_retention_days" {
  type    = number
  default = 7
}
