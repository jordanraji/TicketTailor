output "bucket_name" {
  value       = aws_s3_bucket.web.id
  description = "Bucket the SPA build is synced into."
}

output "website_endpoint" {
  value       = aws_s3_bucket_website_configuration.web.website_endpoint
  description = "S3 website host (no scheme)."
}

output "website_origin" {
  value       = "http://${aws_s3_bucket_website_configuration.web.website_endpoint}"
  description = "Full http:// origin of the SPA - the API CORS origin and the URL users open."
}
