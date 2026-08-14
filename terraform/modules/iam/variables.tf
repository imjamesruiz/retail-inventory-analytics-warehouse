variable "project_name" {
  type        = string
  description = "Short name used as a prefix for IAM role/policy names."
  default     = "retail-inventory"
}

variable "bucket_arn" {
  type        = string
  description = "ARN of the raw payload S3 bucket (from modules/s3), scoping the ingestion policy."
}

variable "raw_prefix" {
  type        = string
  description = "Key prefix the ingestion role is allowed to read/write, matching modules.s3.raw_prefix."
  default     = "raw/"
}

variable "state_bucket_arn" {
  type        = string
  description = "ARN of the Terraform state bucket (from terraform/bootstrap), so the CI plan role can read the state object it needs for `terraform plan`."
}

variable "state_object_key" {
  type        = string
  description = "Key of the state object within the state bucket, matching backend.hcl's `key`."
}

variable "lock_table_arn" {
  type        = string
  description = "ARN of the DynamoDB lock table (from terraform/bootstrap), so the CI plan role can acquire/release the state lock."
}

variable "storage_integration_iam_user_arn" {
  type        = string
  description = "STORAGE_AWS_IAM_USER_ARN from `DESCRIBE STORAGE INTEGRATION`, filled in on the second apply once the Snowflake storage integration exists. Empty on the first apply -- see the storage integration bootstrap note in the root README."
  default     = ""
}

variable "storage_integration_external_id" {
  type        = string
  description = "STORAGE_AWS_EXTERNAL_ID from `DESCRIBE STORAGE INTEGRATION`, filled in on the second apply. Empty on the first apply."
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to IAM roles and policies."
  default     = {}
}
