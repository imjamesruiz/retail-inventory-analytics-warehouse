# --- S3 --------------------------------------------------------------

output "raw_bucket_name" {
  value       = module.s3.bucket_name
  description = "Name of the raw payload S3 bucket. Set as S3_BUCKET in .env when RAW_STORAGE_BACKEND=s3."
}

output "raw_bucket_arn" {
  value       = module.s3.bucket_arn
  description = "ARN of the raw payload S3 bucket."
}

# --- IAM -------------------------------------------------------------

output "ingestion_role_arn" {
  value       = module.iam.ingestion_role_arn
  description = "ARN the pipeline assumes (via GitHub OIDC) for S3 access. Configure scheduled-pipeline.yml's `aws-actions/configure-aws-credentials` step with this as role-to-assume."
}

output "github_actions_ci_role_arn" {
  value       = module.iam.github_actions_ci_role_arn
  description = "ARN the terraform-plan.yml workflow assumes for `terraform plan`. Read-only."
}

output "storage_integration_role_arn" {
  value       = module.iam.storage_integration_role_arn
  description = "ARN of the IAM role Snowflake's storage integration assumes. Its trust policy is a locked placeholder until the phase-2 apply -- see the README."
}

# --- Snowflake ---------------------------------------------------------

output "snowflake_database_name" {
  value       = module.snowflake.database_name
  description = "Snowflake database name. Set as SNOWFLAKE_DATABASE in .env / GitHub secrets."
}

output "snowflake_warehouse_name" {
  value       = module.snowflake.warehouse_name
  description = "Snowflake warehouse name. Set as SNOWFLAKE_WAREHOUSE in .env / GitHub secrets."
}

output "snowflake_role_name" {
  value       = module.snowflake.dbt_role_name
  description = "Snowflake account role name. Set as SNOWFLAKE_ROLE in .env / GitHub secrets."
}

output "snowflake_storage_integration_iam_user_arn" {
  value       = module.snowflake.storage_integration_iam_user_arn
  description = "Feed into -var storage_integration_iam_user_arn on the phase-2 apply."
}

output "snowflake_storage_integration_external_id" {
  value       = module.snowflake.storage_integration_external_id
  description = "Feed into -var storage_integration_external_id on the phase-2 apply."
}
