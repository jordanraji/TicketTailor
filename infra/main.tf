# Root composition for the TicketTailor Learner Lab deployment (ADR-0017).
# Wires the networking, database, messaging, registry, compute, and frontend
# modules. The environment is the Terraform workspace (dev/prod).

data "aws_caller_identity" "current" {}

# Learner Lab forbids IAM creation; every role is the pre-provisioned LabRole.
data "aws_iam_role" "lab" {
  name = "LabRole"
}

locals {
  environment = terraform.workspace

  database_url = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${module.database.primary_address}:${module.database.port}/${module.database.db_name}"
  replica_url  = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${module.database.replica_address}:${module.database.port}/${module.database.db_name}"

  # Connection strings + app secrets injected into ECS tasks via SSM. for_each
  # keys must be NON-sensitive, so we drive it off a set of literal key names and
  # look the (sensitive) values up separately. SSM rejects empty values, so
  # RESEND_API_KEY is only stored when set (empty = email disabled); whether it's
  # present is declassified with nonsensitive() - that reveals only that email is
  # configured, not the key itself.
  secret_keys = toset(concat(
    ["DATABASE_URL", "DATABASE_REPLICA_URL", "SECRET_KEY", "VAPID_PUBLIC_KEY"],
    nonsensitive(var.resend_api_key != "") ? ["RESEND_API_KEY"] : [],
  ))
  secret_value = {
    DATABASE_URL         = local.database_url
    DATABASE_REPLICA_URL = local.replica_url
    SECRET_KEY           = var.secret_key
    VAPID_PUBLIC_KEY     = var.vapid_public_key
    RESEND_API_KEY       = var.resend_api_key
  }
}

# --- Secrets (SSM SecureString) ---------------------------------------------

resource "aws_ssm_parameter" "secret" {
  for_each = local.secret_keys
  name     = "/${var.project}/${local.environment}/${each.key}"
  type     = "SecureString"
  value    = local.secret_value[each.key]
}

# --- Modules ----------------------------------------------------------------

module "networking" {
  source             = "./modules/networking"
  project            = var.project
  environment        = local.environment
  vpc_cidr           = var.vpc_cidr
  az_count           = var.az_count
  app_container_port = 8000
}

module "database" {
  source                 = "./modules/database"
  project                = var.project
  environment            = local.environment
  private_subnet_ids     = module.networking.private_subnet_ids
  db_sg_id               = module.networking.db_sg_id
  db_username            = var.db_username
  db_password            = var.db_password
  db_name                = "tickettailor"
  instance_class         = var.db_instance_class
  replica_instance_class = var.db_instance_class
}

module "messaging" {
  source      = "./modules/messaging"
  project     = var.project
  environment = local.environment
}

module "registry" {
  source      = "./modules/registry"
  project     = var.project
  environment = local.environment
}

module "compute" {
  source       = "./modules/compute"
  project      = var.project
  environment  = local.environment
  aws_region   = var.aws_region
  lab_role_arn = data.aws_iam_role.lab.arn

  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids
  alb_sg_id          = module.networking.alb_sg_id
  app_sg_id          = module.networking.app_sg_id
  redis_sg_id        = module.networking.redis_sg_id
  lambda_sg_id       = module.networking.lambda_sg_id

  api_image    = "${module.registry.repository_urls["api"]}:${var.api_image_tag}"
  relay_image  = "${module.registry.repository_urls["relay"]}:${var.relay_image_tag}"
  worker_image = "${module.registry.repository_urls["worker"]}:${var.worker_image_tag}"

  secret_arns = { for k, p in aws_ssm_parameter.secret : k => p.arn }
  worker_secrets = {
    RESEND_API_KEY     = var.resend_api_key
    VAPID_PUBLIC_KEY   = var.vapid_public_key
    VAPID_PRIVATE_KEY  = var.vapid_private_key
    VAPID_CLAIMS_EMAIL = var.vapid_claims_email
  }

  sns_topic_arn = module.messaging.topic_arn
  queue_arns    = module.messaging.queue_arns

  email_provider     = var.email_provider
  email_from_address = var.email_from_address

  api_desired_count = var.api_desired_count
  api_max_count     = var.api_max_count

  # When the S3-website frontend is on, allow its origin (and localhost for dev)
  # through CORS; otherwise fall back to the manual var (empty = localhost dev
  # default). allow_credentials forbids a wildcard, so the origin must be exact.
  cors_allowed_origins = length(module.frontend_website) > 0 ? "${module.frontend_website[0].website_origin},http://localhost:3000" : var.cors_allowed_origins
}

# Full-account frontend: S3 + CloudFront (HTTPS). Gated off on the lab because
# voclabs denies cloudfront:* (ADR-0017).
module "frontend" {
  count         = var.enable_frontend ? 1 : 0
  source        = "./modules/frontend"
  project       = var.project
  environment   = local.environment
  bucket_suffix = data.aws_caller_identity.current.account_id
}

# Learner Lab frontend: public S3 static website over HTTP (ADR-0020). After
# `terraform apply`, run `make web` (scripts/deploy-web.sh) to build + publish.
module "frontend_website" {
  count         = var.enable_frontend_website ? 1 : 0
  source        = "./modules/frontend_website"
  project       = var.project
  environment   = local.environment
  bucket_suffix = data.aws_caller_identity.current.account_id
}
