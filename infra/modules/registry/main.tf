# Registry - one ECR repository per deployable image (api, relay, worker).
# Images are built and pushed by CI (or the manual build step in the runbook);
# the compute module references them by tag.

locals {
  name = "${var.project}-${var.environment}"
}

resource "aws_ecr_repository" "this" {
  for_each             = toset(var.repositories)
  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${local.name}/${each.key}" }
}

# Keep only the most recent images to bound storage cost.
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images beyond the latest 10"
      selection = {
        tagStatus   = "untagged"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
