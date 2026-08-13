terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.97"
    }
  }
}
