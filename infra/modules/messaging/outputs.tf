output "topic_arn" {
  value       = aws_sns_topic.notifications.arn
  description = "SNS topic the relay publishes per-recipient notifications to."
}

# Map (single entry) so the compute module can create one event-source mapping
# per queue with for_each; keeps room for additional streams later.
output "queue_arns" {
  value       = { notifications = aws_sqs_queue.notifications.arn }
  description = "Notification SQS queue ARN the worker Lambda consumes."
}

output "queue_urls" {
  value = { notifications = aws_sqs_queue.notifications.id }
}

output "dlq_arn" {
  value = aws_sqs_queue.dlq.arn
}
