variable "bucket_name" {
  type        = string
  description = "Globally-unique name for the S3 bucket that stores raw retailer payloads."
}

variable "raw_prefix" {
  type        = string
  description = "Key prefix under which the ingestion pipeline writes raw payloads (matches RawStorage's partitioned layout, e.g. `raw/`). IAM policies in modules/iam scope access to this prefix only."
  default     = "raw/"
}

variable "glacier_transition_days" {
  type        = number
  description = "Number of days after object creation before objects transition to S3 Glacier."
  default     = 90
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the bucket."
  default     = {}
}
