variable "project" {
  type        = string
  description = "Project slug."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "visibility_timeout_seconds" {
  type        = number
  description = "SQS visibility timeout; should exceed the Lambda timeout."
  default     = 60
}

variable "max_receive_count" {
  type        = number
  description = "Deliveries attempted before a message moves to the DLQ."
  default     = 5
}
