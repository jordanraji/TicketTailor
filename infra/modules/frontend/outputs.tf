output "bucket_name" {
  value = aws_s3_bucket.web.id
}

output "cloudfront_domain" {
  value       = aws_cloudfront_distribution.web.domain_name
  description = "CloudFront default domain serving the SPA."
}

output "distribution_id" {
  value = aws_cloudfront_distribution.web.id
}
