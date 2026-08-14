# --- General ----------------------------------------------------------

variable "aws_region" {
  type        = string
  description = "AWS region for the S3 bucket and IAM resources."
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Short name used as a prefix for IAM role/policy names."
  default     = "retail-inventory"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every AWS resource this config creates."
  default = {
    Project   = "retail-inventory-analytics-warehouse"
    ManagedBy = "terraform"
  }
}

# --- S3 (modules/s3) ----------------------------------------------------

variable "raw_bucket_name" {
  type        = string
  description = "Globally-unique name for the S3 bucket that stores raw retailer payloads. No default -- S3 bucket names collide across all AWS accounts, so pick one and set it explicitly in terraform.tfvars."
}

variable "raw_prefix" {
  type        = string
  description = "Key prefix the ingestion pipeline writes under (matches RawStorage's partitioned layout). IAM and the Snowflake storage integration are both scoped to this prefix only."
  default     = "raw/"
}

variable "glacier_transition_days" {
  type        = number
  description = "Days after object creation before objects transition to S3 Glacier."
  default     = 90
}

# --- IAM (modules/iam) --------------------------------------------------

variable "state_bucket_arn" {
  type        = string
  description = "ARN of the Terraform state bucket from `terraform -chdir=bootstrap output state_bucket_arn`. Lets the CI plan role read remote state."
}

variable "state_object_key" {
  type        = string
  description = "Key of this config's state object, matching the `key` in backend.hcl."
  default     = "retail-inventory-analytics-warehouse/terraform.tfstate"
}

variable "lock_table_arn" {
  type        = string
  description = "ARN of the DynamoDB lock table from `terraform -chdir=bootstrap output lock_table_arn`. Lets the CI plan role acquire/release the state lock."
}

variable "storage_integration_iam_user_arn" {
  type        = string
  description = "Phase-2 input: STORAGE_AWS_IAM_USER_ARN from `DESCRIBE STORAGE INTEGRATION`. Leave empty on the first apply -- see the storage integration bootstrap note in the README."
  default     = ""
}

variable "storage_integration_external_id" {
  type        = string
  description = "Phase-2 input: STORAGE_AWS_EXTERNAL_ID from `DESCRIBE STORAGE INTEGRATION`. Leave empty on the first apply."
  default     = ""
}

# --- Snowflake (modules/snowflake) --------------------------------------
# Snowflake authentication (account, user, private key, role) is supplied via
# SNOWFLAKE_* environment variables read directly by the provider, not
# variables here -- see the provider block in main.tf and the README.

variable "snowflake_database_name" {
  type        = string
  description = "Name of the Snowflake database."
  default     = "RETAIL_INVENTORY"
}

variable "snowflake_schemas" {
  type        = list(string)
  description = "Schemas created directly under the database (dbt creates its own ANALYTICS_* sub-schemas at run time -- see modules/snowflake/variables.tf for why this isn't a literal raw/staging/marts list)."
  default     = ["RAW", "ANALYTICS"]
}

variable "snowflake_warehouse_name" {
  type        = string
  description = "Name of the Snowflake warehouse."
  default     = "RETAIL_INVENTORY_WH"
}

variable "snowflake_warehouse_size" {
  type        = string
  description = "Snowflake warehouse size."
  default     = "XSMALL"
}

variable "snowflake_auto_suspend_seconds" {
  type        = number
  description = "Seconds of inactivity before the warehouse auto-suspends."
  default     = 60
}

variable "snowflake_dbt_role_name" {
  type        = string
  description = "Account role used by the ingestion pipeline, dbt, and the dashboard."
  default     = "RETAIL_INVENTORY_ROLE"
}

variable "snowflake_grant_role_to_users" {
  type        = list(string)
  description = "Snowflake usernames to attach the dbt role to directly (e.g. your own user for local development)."
  default     = []
}

variable "snowflake_ci_user_name" {
  type        = string
  description = "Name of the key-pair-authenticated service user for Jenkins CI."
  default     = "RETAIL_INVENTORY_CI_USER"
}

variable "snowflake_ci_user_rsa_public_key" {
  type        = string
  description = "RSA public key (contents of the .pub file, PEM header/footer stripped) for the CI service user. Leave empty to skip creating the CI user until you've generated a key pair -- see docs/architecture.md."
  default     = ""
}

variable "snowflake_storage_integration_name" {
  type        = string
  description = "Name of the Snowflake storage integration connecting to the raw payload S3 bucket."
  default     = "RETAIL_INVENTORY_S3_INTEGRATION"
}
