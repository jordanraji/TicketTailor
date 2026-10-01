terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Shared remote state per the CSSE6400 Terraform collaboration guide.
  # Learner Lab credentials are short-lived, so state lives in a pre-created S3
  # bucket the whole team can reach. Initialise with a partial backend config:
  #
  #   terraform init -backend-config=backend.hcl
  #
  # Leave this commented to use local state (e.g. for `terraform validate`).
  #
  # backend "s3" {
  #   key     = "tickettailor/terraform.tfstate"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = terraform.workspace
      ManagedBy   = "terraform"
    }
  }
}
