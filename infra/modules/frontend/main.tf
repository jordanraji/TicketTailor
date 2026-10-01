# Frontend - private S3 origin behind CloudFront with Origin Access Control
# (ADR-0004). The bucket is not public; only CloudFront can read it. web/ is
# built (Next.js static export, ADR-0018), but the publish step that syncs
# web/out to this bucket is not yet wired, so a placeholder index is uploaded
# and the distribution serves that until the real build is published over it.

locals {
  name = "${var.project}-${var.environment}-web"
}

resource "aws_s3_bucket" "web" {
  bucket        = "${local.name}-${var.bucket_suffix}"
  force_destroy = true
  tags          = { Name = local.name }
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = local.name
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  default_root_object = "index.html"
  comment             = local.name

  origin {
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id                = "s3-web"
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-web"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  # SPA routing: serve index.html for client-side routes.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  price_class = "PriceClass_100"
  tags        = { Name = local.name }
}

# Allow CloudFront (this distribution only) to read the bucket.
data "aws_iam_policy_document" "web" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.web.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web.json
}

# Placeholder until web/out is published (web/ is built, but the S3 upload of
# web/out is not yet wired - see infra/README).
resource "aws_s3_object" "placeholder" {
  bucket       = aws_s3_bucket.web.id
  key          = "index.html"
  content      = "<!doctype html><title>TicketTailor</title><h1>TicketTailor</h1><p>Frontend not yet published (see infra/README).</p>"
  content_type = "text/html"
  etag         = md5("tickettailor-placeholder-v1")
}
