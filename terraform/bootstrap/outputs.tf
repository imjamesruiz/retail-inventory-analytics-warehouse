output "state_bucket_name" {
  value       = aws_s3_bucket.tfstate.id
  description = "Name to use as `bucket` in the main config's backend.hcl."
}

output "state_bucket_arn" {
  value       = aws_s3_bucket.tfstate.arn
  description = "ARN of the state bucket, needed by the CI IAM role's read policy in modules/iam."
}

output "lock_table_name" {
  value       = aws_dynamodb_table.tflock.name
  description = "Name to use as `dynamodb_table` in the main config's backend.hcl."
}

output "lock_table_arn" {
  value       = aws_dynamodb_table.tflock.arn
  description = "ARN of the lock table, needed by the CI IAM role's read policy in modules/iam."
}
