output "database_name" {
  value       = snowflake_database.this.name
  description = "Name of the Snowflake database."
}

output "warehouse_name" {
  value       = snowflake_warehouse.this.name
  description = "Name of the Snowflake warehouse."
}

output "dbt_role_name" {
  value       = snowflake_account_role.dbt.name
  description = "Account role used by the pipeline/dbt/dashboard."
}

output "schemas" {
  value       = [for s in snowflake_schema.this : s.name]
  description = "Schemas created directly under the database."
}

output "storage_integration_name" {
  value       = snowflake_storage_integration.s3.name
  description = "Name of the Snowflake storage integration."
}

output "storage_integration_iam_user_arn" {
  value       = snowflake_storage_integration.s3.storage_aws_iam_user_arn
  description = "Snowflake's IAM user ARN for this integration. Feed into modules.iam.storage_integration_iam_user_arn on the second apply -- see the root README's storage integration bootstrap note."
}

output "storage_integration_external_id" {
  value       = snowflake_storage_integration.s3.storage_aws_external_id
  description = "Snowflake's external ID for this integration. Feed into modules.iam.storage_integration_external_id on the second apply."
}
