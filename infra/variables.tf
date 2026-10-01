variable "project" {
  type        = string
  description = "Project slug used in resource names."
  default     = "tickettailor"
}

variable "aws_region" {
  type        = string
  description = "AWS region. Learner Lab classic restricts compute to us-east-1; confirm what your lab session grants. The application default is ap-southeast-2."
  default     = "us-east-1"
}

# --- Networking -------------------------------------------------------------

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "az_count" {
  type    = number
  default = 2
}

# --- Database ---------------------------------------------------------------

variable "db_username" {
  type    = string
  default = "tickettailor"
}

variable "db_password" {
  type        = string
  description = "RDS master password."
  sensitive   = true
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class for primary and replica. db.t3.medium (~450 max_connections) is sized so a 10-task API scale-out (workers x 2 engines x pool) stays within the connection budget; db.t3.micro (~112) cannot sustain that fleet. Confirm db.t3.medium is permitted in your Learner Lab session before applying."
  default     = "db.t3.medium"
}

# --- Application secrets -----------------------------------------------------

variable "secret_key" {
  type        = string
  description = "JWT signing key for the API (ADR-0014)."
  sensitive   = true
}

variable "resend_api_key" {
  type        = string
  description = "Resend API key for outbound email (ADR-0012). Empty disables real sends."
  sensitive   = true
  default     = ""
}

variable "vapid_public_key" {
  type        = string
  description = "VAPID public key for web push (ADR-0011)."
  sensitive   = true
}

variable "vapid_private_key" {
  type        = string
  description = "VAPID private key for web push (ADR-0011)."
  sensitive   = true
}

variable "vapid_claims_email" {
  type    = string
  default = "mailto:noreply@tickettailor.local"
}

# --- Email ------------------------------------------------------------------

variable "email_provider" {
  type    = string
  default = "resend"
}

variable "email_from_address" {
  type    = string
  default = "noreply@tickettailor.local"
}

# --- Images -----------------------------------------------------------------

variable "api_image_tag" {
  type    = string
  default = "latest"
}

variable "relay_image_tag" {
  type    = string
  default = "latest"
}

variable "worker_image_tag" {
  type    = string
  default = "latest"
}

# --- Frontend ----------------------------------------------------------------

variable "enable_frontend" {
  type        = bool
  description = "Provision S3 + CloudFront for the SPA (HTTPS). Default off: voclabs is denied cloudfront:* (ADR-0017), so this is the full-account path. On the Learner Lab use enable_frontend_website instead."
  default     = false
}

variable "enable_frontend_website" {
  type        = bool
  description = "Provision a public S3 static-website bucket that serves the SPA over HTTP (ADR-0020). This is the Learner Lab frontend path (cloudfront is denied). After `terraform apply`, build + publish the bundle with `make web` (scripts/deploy-web.sh). When true, the API CORS origin is set to the website origin automatically."
  default     = false
}

variable "cors_allowed_origins" {
  type        = string
  description = "Comma-separated CORS origins for the API. Ignored when enable_frontend_website is true (the website origin is wired automatically). Otherwise set this to the SPA origin, or leave empty to keep the localhost dev default."
  default     = ""
}

# --- API sizing / autoscaling -----------------------------------------------

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "api_max_count" {
  type    = number
  default = 10
}
