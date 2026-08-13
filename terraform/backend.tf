# Partial backend configuration -- backend blocks can't reference variables,
# so the actual bucket/table/region come from a gitignored backend.hcl at
# `terraform init -backend-config=backend.hcl` time. See backend.hcl.example
# and the root README's "Bootstrap problem" section: this bucket and table
# must already exist (via terraform/bootstrap) before `terraform init` here
# can succeed.
terraform {
  backend "s3" {
    encrypt = true
  }
}
