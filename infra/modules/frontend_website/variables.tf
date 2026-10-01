variable "project" {
  type        = string
  description = "Project slug."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "bucket_suffix" {
  type        = string
  description = "Suffix to make the bucket name globally unique (e.g. account id)."
}
