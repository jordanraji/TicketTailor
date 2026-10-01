# Database - RDS Postgres + PostGIS primary with a managed read replica
# (ADR-0008). Map and event-detail reads route to the replica; writes go to the
# primary. PostGIS is enabled by the application's migrations (the RDS master
# user can `CREATE EXTENSION postgis`).

locals {
  name = "${var.project}-${var.environment}"
}

resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = var.private_subnet_ids
  tags       = { Name = local.name }
}

resource "aws_db_parameter_group" "this" {
  name   = local.name
  family = "postgres16"

  # Surface slow queries during the QA1 load test.
  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }
}

resource "aws_db_instance" "primary" {
  identifier     = "${local.name}-primary"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = [var.db_sg_id]
  publicly_accessible    = false
  multi_az               = false

  # Automated backups (retention > 0) are required to create a read replica.
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = { Name = "${local.name}-primary" }
}

resource "aws_db_instance" "replica" {
  identifier          = "${local.name}-replica"
  replicate_source_db = aws_db_instance.primary.identifier
  instance_class      = var.replica_instance_class

  vpc_security_group_ids = [var.db_sg_id]
  publicly_accessible    = false
  skip_final_snapshot    = true
  deletion_protection    = false
  apply_immediately      = true

  tags = { Name = "${local.name}-replica" }
}
