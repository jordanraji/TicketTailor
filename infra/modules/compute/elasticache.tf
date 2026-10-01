# Redis counter store on ElastiCache (ADR-0005). ADR-0017 substitution (1)
# (Redis-on-Fargate behind an internal NLB) is reverted: the Learner Lab was
# confirmed to permit ElastiCache, so the counter uses the managed service that
# docs/architecture-overview.md names. A single-node, cluster-mode-disabled
# cluster in the private subnets; the API tasks reach it at the node endpoint.
#
# The counter is reconstructable from persisted RSVP rows (QA3-reconcile), so a
# node replacement is recoverable. A replication group with automatic failover
# is the HA upgrade path called out in ADR-0005; single-node keeps the lab cost
# down and matches the prior single-task footprint.

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name}-redis"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${local.name}-redis" }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id         = "${local.name}-redis"
  engine             = "redis"
  node_type          = var.redis_node_type
  num_cache_nodes    = 1
  port               = 6379
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [var.redis_sg_id]
  apply_immediately  = true
  tags               = { Name = "${local.name}-redis" }
}
