provider "aws" {
  region = var.aws_region
}

# Account, user, and auth (private key or password) come from SNOWFLAKE_*
# environment variables -- never put Snowflake credentials in .tfvars.
# See the README for the exact variable names.
provider "snowflake" {
  role = var.snowflake_dbt_role_name
}

module "s3" {
  source = "./modules/s3"

  bucket_name             = var.raw_bucket_name
  raw_prefix              = var.raw_prefix
  glacier_transition_days = var.glacier_transition_days
  tags                    = var.tags
}

module "iam" {
  source = "./modules/iam"

  project_name     = var.project_name
  bucket_arn       = module.s3.bucket_arn
  raw_prefix       = var.raw_prefix
  state_bucket_arn = var.state_bucket_arn
  state_object_key = var.state_object_key
  lock_table_arn   = var.lock_table_arn

  storage_integration_iam_user_arn = var.storage_integration_iam_user_arn
  storage_integration_external_id  = var.storage_integration_external_id

  tags = var.tags
}

module "snowflake" {
  source = "./modules/snowflake"

  database_name          = var.snowflake_database_name
  schemas                = var.snowflake_schemas
  warehouse_name         = var.snowflake_warehouse_name
  warehouse_size         = var.snowflake_warehouse_size
  auto_suspend_seconds   = var.snowflake_auto_suspend_seconds
  dbt_role_name          = var.snowflake_dbt_role_name
  grant_role_to_users    = var.snowflake_grant_role_to_users
  ci_user_name           = var.snowflake_ci_user_name
  ci_user_rsa_public_key = var.snowflake_ci_user_rsa_public_key

  storage_integration_name         = var.snowflake_storage_integration_name
  storage_integration_iam_role_arn = module.iam.storage_integration_role_arn
  s3_bucket_name                   = module.s3.bucket_name
  s3_raw_prefix                    = var.raw_prefix
}
