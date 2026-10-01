# Notification worker - container-image Lambda triggered by the per-channel SQS
# queues (ADR-0002, ADR-0016). Delivery only: no DB, no inbound. Runs in the
# private subnets with the lambda SG so it can reach the web-push and email
# providers via the NAT Gateway. AWS_REGION is supplied by the Lambda runtime
# (reserved key) so it is not set here.

resource "aws_lambda_function" "worker" {
  function_name = "${local.name}-worker"
  role          = var.lab_role_arn
  package_type  = "Image"
  image_uri     = var.worker_image
  timeout       = var.worker_timeout
  memory_size   = var.worker_memory

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_sg_id]
  }

  environment {
    variables = {
      EMAIL_PROVIDER     = var.email_provider
      EMAIL_FROM_ADDRESS = var.email_from_address
      RESEND_API_KEY     = var.worker_secrets["RESEND_API_KEY"]
      VAPID_PUBLIC_KEY   = var.worker_secrets["VAPID_PUBLIC_KEY"]
      VAPID_PRIVATE_KEY  = var.worker_secrets["VAPID_PRIVATE_KEY"]
      VAPID_CLAIMS_EMAIL = var.worker_secrets["VAPID_CLAIMS_EMAIL"]
    }
  }

  tags = { Name = "${local.name}-worker" }
}

# One event-source mapping per channel queue. Partial-batch failures are
# reported so only failed records are retried (and eventually DLQ'd).
resource "aws_lambda_event_source_mapping" "queues" {
  for_each         = var.queue_arns
  event_source_arn = each.value
  function_name    = aws_lambda_function.worker.arn
  batch_size       = var.worker_batch_size

  function_response_types = ["ReportBatchItemFailures"]
}
