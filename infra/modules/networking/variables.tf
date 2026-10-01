variable "project" {
  type        = string
  description = "Project slug, used in resource names."
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev/prod), from the Terraform workspace."
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."
  default     = "10.20.0.0/16"
}

variable "az_count" {
  type        = number
  description = "Number of availability zones to spread subnets across."
  default     = 2
}

variable "app_container_port" {
  type        = number
  description = "Container port the API listens on (ALB target port)."
  default     = 8000
}
