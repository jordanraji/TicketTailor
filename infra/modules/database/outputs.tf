output "primary_address" {
  value       = aws_db_instance.primary.address
  description = "Hostname of the primary instance."
}

output "replica_address" {
  value       = aws_db_instance.replica.address
  description = "Hostname of the read replica."
}

output "port" {
  value = aws_db_instance.primary.port
}

output "db_name" {
  value = var.db_name
}

output "primary_identifier" {
  value = aws_db_instance.primary.identifier
}

output "replica_identifier" {
  value = aws_db_instance.replica.identifier
}
