terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Deliberately no `backend` block. This config provisions the state bucket
  # and lock table that the *main* config's S3 backend depends on, so it
  # can't depend on that backend itself -- see the "Bootstrap problem" section
  # of the root README's Terraform notes. State for this directory stays
  # local (terraform/bootstrap/terraform.tfstate, gitignored).
}
