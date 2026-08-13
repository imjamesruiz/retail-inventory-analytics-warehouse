variable "aws_region" {
  type        = string
  description = "AWS region for the Terraform state bucket and lock table."
  default     = "us-east-1"
}

variable "state_bucket_name" {
  type        = string
  description = "Globally-unique name for the S3 bucket that stores Terraform remote state. Must be created before the main config's backend.tf can be initialized."
}

variable "lock_table_name" {
  type        = string
  description = "Name of the DynamoDB table used for Terraform state locking."
  default     = "retail-inventory-tflock"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the state bucket and lock table."
  default = {
    Project   = "retail-inventory-analytics-warehouse"
    ManagedBy = "terraform-bootstrap"
  }
}
