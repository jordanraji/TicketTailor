output "api_url" {
  value       = "http://${module.compute.alb_dns_name}"
  description = "Base URL of the deployed API (ALB DNS, HTTP - see ADR-0017)."
}

output "api_healthcheck" {
  value       = "http://${module.compute.alb_dns_name}/healthz"
  description = "Smoke-check endpoint."
}

output "frontend_url" {
  value       = var.enable_frontend ? "https://${module.frontend[0].cloudfront_domain}" : "(cloudfront frontend disabled: full-account path only, cloudfront:* denied to voclabs - see ADR-0017)"
  description = "CloudFront URL serving the SPA, when enable_frontend = true (full account)."
}

output "frontend_website_url" {
  value       = var.enable_frontend_website ? module.frontend_website[0].website_origin : "(s3 website frontend disabled: set enable_frontend_website = true, then run 'make web' - ADR-0020)"
  description = "Public HTTP URL of the SPA on S3 website hosting (Learner Lab path)."
}

output "frontend_website_bucket" {
  value       = var.enable_frontend_website ? module.frontend_website[0].bucket_name : ""
  description = "Bucket that 'make web' (scripts/deploy-web.sh) syncs the SPA build into."
}

output "sns_topic_arn" {
  value = module.messaging.topic_arn
}

output "queue_urls" {
  value = module.messaging.queue_urls
}

output "ecr_repositories" {
  value       = module.registry.repository_urls
  description = "Push images here before deploying (see runbook)."
}

output "db_primary_address" {
  value = module.database.primary_address
}

output "db_replica_address" {
  value = module.database.replica_address
}

output "ecs_cluster" {
  value = module.compute.cluster_name
}

output "worker_function" {
  value = module.compute.worker_function_name
}
