output "bucket_name" {
  value       = aws_s3_bucket.raw.id
  description = "Name of the raw payload bucket."
}

output "bucket_arn" {
  value       = aws_s3_bucket.raw.arn
  description = "ARN of the raw payload bucket, consumed by modules/iam and modules/snowflake."
}
