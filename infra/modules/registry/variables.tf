variable "project" {
  type        = string
  description = "Project slug."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "repositories" {
  type        = list(string)
  description = "Image names to create repositories for."
  default     = ["api", "relay", "worker"]
}
