output "alb_dns_name" {
  value       = aws_lb.api.dns_name
  description = "Public DNS name of the API load balancer."
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "worker_function_name" {
  value = aws_lambda_function.worker.function_name
}

output "redis_endpoint" {
  value       = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379"
  description = "ElastiCache Redis node endpoint fronting the RSVP counter."
}
