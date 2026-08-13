output "ingestion_role_arn" {
  value       = aws_iam_role.ingestion.arn
  description = "ARN the pipeline assumes (via GitHub OIDC) to read/write raw payloads in S3."
}

output "ingestion_role_name" {
  value       = aws_iam_role.ingestion.name
  description = "Name of the ingestion role."
}

output "github_actions_ci_role_arn" {
  value       = aws_iam_role.github_actions_ci.arn
  description = "ARN the terraform-plan.yml workflow assumes (via GitHub OIDC) to run `terraform plan`. Read-only -- cannot apply."
}

output "github_oidc_provider_arn" {
  value       = local.github_oidc_provider_arn
  description = "ARN of the GitHub Actions OIDC provider in use (created here or passed in)."
}

output "storage_integration_role_arn" {
  value       = aws_iam_role.storage_integration.arn
  description = "ARN passed to Snowflake as storage_aws_role_arn when creating the storage integration."
}
