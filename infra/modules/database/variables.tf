variable "project" {
  type        = string
  description = "Project slug."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the DB subnet group."
}

variable "db_sg_id" {
  type        = string
  description = "Security group for the database instances."
}

variable "db_name" {
  type        = string
  description = "Initial database name."
  default     = "tickettailor"
}

variable "db_username" {
  type        = string
  description = "Master username."
  default     = "tickettailor"
}

variable "db_password" {
  type        = string
  description = "Master password."
  sensitive   = true
}

variable "engine_version" {
  type        = string
  description = "Postgres major version. Major-only lets RDS pick the latest available minor (avoids 'cannot find version X.Y' when a specific minor is retired in-region)."
  default     = "16"
}

variable "instance_class" {
  type        = string
  description = "Primary instance class."
  default     = "db.t3.micro"
}

variable "replica_instance_class" {
  type        = string
  description = "Read-replica instance class."
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  type        = number
  description = "Initial storage (GiB)."
  default     = 20
}

variable "max_allocated_storage" {
  type        = number
  description = "Storage autoscaling ceiling (GiB)."
  default     = 100
}
