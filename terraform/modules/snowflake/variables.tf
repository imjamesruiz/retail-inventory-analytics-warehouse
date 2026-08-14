variable "database_name" {
  type        = string
  description = "Name of the Snowflake database (matches RETAIL_INVENTORY in snowflake/setup.sql)."
  default     = "RETAIL_INVENTORY"
}

variable "schemas" {
  type        = list(string)
  description = <<-EOT
    Schemas created directly under the database. Matches the existing
    manually-created layout (RAW + ANALYTICS), not a literal raw/staging/marts
    split -- dbt's custom schema naming (`+schema:` in dbt_project.yml)
    creates ANALYTICS_STAGING, ANALYTICS_INTERMEDIATE, ANALYTICS_MARTS, and
    ANALYTICS_SEEDS under ANALYTICS at run time. That's why the dbt role below
    is granted CREATE SCHEMA plus FUTURE SCHEMA grants instead of this list
    trying to enumerate every dbt-managed schema up front.
  EOT
  default     = ["RAW", "ANALYTICS"]
}

variable "warehouse_name" {
  type        = string
  description = "Name of the Snowflake warehouse."
  default     = "RETAIL_INVENTORY_WH"
}

variable "warehouse_size" {
  type        = string
  description = "Snowflake warehouse size."
  default     = "XSMALL"

  validation {
    condition     = contains(["XSMALL", "SMALL", "MEDIUM", "LARGE", "XLARGE"], var.warehouse_size)
    error_message = "warehouse_size must be one of XSMALL, SMALL, MEDIUM, LARGE, XLARGE."
  }
}

variable "auto_suspend_seconds" {
  type        = number
  description = "Seconds of inactivity before the warehouse auto-suspends."
  default     = 60
}

variable "dbt_role_name" {
  type        = string
  description = "Account role used by the ingestion pipeline, dbt, and the dashboard (matches RETAIL_INVENTORY_ROLE in snowflake/roles.sql)."
  default     = "RETAIL_INVENTORY_ROLE"
}

variable "grant_role_to_users" {
  type        = list(string)
  description = "Snowflake usernames to attach dbt_role_name to directly, e.g. for local development. The CI service user (var.ci_user_name) is granted the role automatically when ci_user_rsa_public_key is set."
  default     = []
}

variable "ci_user_name" {
  type        = string
  description = "Name of the key-pair-authenticated service user for Jenkins CI (matches RETAIL_INVENTORY_CI_USER in snowflake/roles.sql)."
  default     = "RETAIL_INVENTORY_CI_USER"
}

variable "ci_user_rsa_public_key" {
  type        = string
  description = "RSA public key (contents of the .pub file, PEM header/footer stripped) for the CI service user's key-pair auth. Leave empty to skip creating the CI user -- see docs/architecture.md for how to generate the key pair."
  default     = ""
}

variable "storage_integration_name" {
  type        = string
  description = "Name of the Snowflake storage integration connecting to the raw payload S3 bucket."
  default     = "RETAIL_INVENTORY_S3_INTEGRATION"
}

variable "storage_integration_iam_role_arn" {
  type        = string
  description = "ARN of the AWS IAM role Snowflake assumes (modules.iam.storage_integration_role_arn)."
}

variable "s3_bucket_name" {
  type        = string
  description = "Name of the raw payload S3 bucket (modules.s3.bucket_name)."
}

variable "s3_raw_prefix" {
  type        = string
  description = "Key prefix the storage integration is allowed to access, matching modules.s3.raw_prefix."
  default     = "raw/"
}
