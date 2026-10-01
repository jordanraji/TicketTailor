# Messaging - SNS topic → a single notifications SQS queue → the worker Lambda
# (ADR-0006, ADR-0016). The relay publishes one hydrated, per-recipient
# DomainEvent per notification (raw message delivery: the SQS body IS the
# DomainEvent JSON the worker parses). Each message's RecipientSchema carries an
# optional email and an optional push subscription; the worker delivers to both
# channels itself - there is no per-channel queue split. Failed deliveries land
# in the DLQ after maxReceiveCount attempts.

locals {
  name = "${var.project}-${var.environment}"
}

resource "aws_sns_topic" "notifications" {
  name = "${local.name}-notifications"
  tags = { Name = "${local.name}-notifications" }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name}-notifications-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = { Name = "${local.name}-notifications-dlq" }
}

resource "aws_sqs_queue" "notifications" {
  name                       = "${local.name}-notifications"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = 345600 # 4 days
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
  tags = { Name = "${local.name}-notifications" }
}

# Allow the SNS topic to deliver to the queue.
data "aws_iam_policy_document" "queue_policy" {
  statement {
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.notifications.arn]
    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.notifications.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id
  policy    = data.aws_iam_policy_document.queue_policy.json
}

# Raw delivery so the SQS body is the DomainEvent JSON the worker parses; SNS
# message attributes (event_type, dedup_id) pass through. No filter policy - the
# worker handles every event_type.
resource "aws_sns_topic_subscription" "notifications" {
  topic_arn            = aws_sns_topic.notifications.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.notifications.arn
  raw_message_delivery = true
}
