# Frontend - public S3 static website over HTTP (ADR-0020), the Learner Lab SPA
# host (voclabs denies cloudfront:*, so the CloudFront module is full-account
# only). HTTP both ends (the API is HTTP over the ALB) avoids mixed content.
# This module only creates the bucket + website config; scripts/deploy-web.sh
# builds and syncs the bundle post-apply (the build bakes the ALB API URL).

locals {
  name = "${var.project}-${var.environment}-web-site"
}

resource "aws_s3_bucket" "web" {
  bucket        = "${local.name}-${var.bucket_suffix}"
  force_destroy = true
  tags          = { Name = local.name }
}

# Public website hosting requires public access. The lab permits it (probed);
# only cloudfront:* is denied, not public S3.
resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  index_document {
    suffix = "index.html"
  }

  # Static-export + SPA routing: any unmatched path falls back to the app shell.
  error_document {
    key = "index.html"
  }
}

# Public read of objects only (no listing, no writes). Must apply after the
# public access block is relaxed, or S3 rejects a public policy.
resource "aws_s3_bucket_policy" "web" {
  bucket     = aws_s3_bucket.web.id
  depends_on = [aws_s3_bucket_public_access_block.web]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.web.arn}/*"
    }]
  })
}
