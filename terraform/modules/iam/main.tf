# GitHub Actions authenticates via OIDC federation rather than long-lived
# IAM user access keys -- no AWS secret ever sits in a GitHub secret, and
# each role's trust policy restricts *which* repo/ref can assume it.

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub's OIDC root CA thumbprint. AWS also trusts the provider's TLS
  # chain automatically for token.actions.githubusercontent.com, but the
  # provider resource still requires a value here.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = var.tags
}

locals {
  github_oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.github_oidc_provider_arn
}

# --- Ingestion role -----------------------------------------------------
# Assumed by the scheduled-pipeline.yml workflow when it writes/reads raw
# payloads directly against S3 (RAW_STORAGE_BACKEND=s3). Restricted to the
# main branch -- PR runs use fixture mode / local storage and never need
# AWS credentials.

data "aws_iam_policy_document" "ingestion_assume" {
  statement {
    sid     = "GithubActionsIngestionOIDC"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "ingestion" {
  name               = "${var.project_name}-ingestion"
  assume_role_policy = data.aws_iam_policy_document.ingestion_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "ingestion" {
  statement {
    sid       = "RawPayloadReadWrite"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${var.bucket_arn}/${var.raw_prefix}*"]
  }
}

resource "aws_iam_policy" "ingestion" {
  name   = "${var.project_name}-ingestion"
  policy = data.aws_iam_policy_document.ingestion.json
}

resource "aws_iam_role_policy_attachment" "ingestion" {
  role       = aws_iam_role.ingestion.name
  policy_arn = aws_iam_policy.ingestion.arn
}

# --- GitHub Actions CI role ----------------------------------------------
# Assumed by the terraform-plan.yml workflow on pull requests. Read-only by
# design: this role can never apply, so a compromised or malicious PR can't
# use it to change infrastructure -- see the "no auto-apply" requirement in
# terraform-plan.yml.

data "aws_iam_policy_document" "ci_assume" {
  statement {
    sid     = "GithubActionsCiOIDC"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:*"]
    }
  }
}

resource "aws_iam_role" "github_actions_ci" {
  name               = "${var.project_name}-github-actions-ci"
  assume_role_policy = data.aws_iam_policy_document.ci_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "ci_plan" {
  # Terraform needs to read the state object and hold the DynamoDB lock for
  # any operation, including a read-only `plan`.
  statement {
    sid       = "TerraformStateRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.state_bucket_arn}/${var.state_object_key}"]
  }

  statement {
    sid       = "TerraformStateBucketList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.state_bucket_arn]
  }

  statement {
    sid    = "TerraformLockTable"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
    ]
    resources = [var.lock_table_arn]
  }

  # Read-only visibility into the resource types this config manages, so
  # `plan` can compute an accurate diff. No mutating actions -- `apply` is
  # intentionally never run from CI.
  statement {
    sid    = "PlanReadOnly"
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetLifecycleConfiguration",
      "s3:GetEncryptionConfiguration",
      "s3:GetBucketPolicy",
      "s3:GetAccelerateConfiguration",
      "iam:GetRole",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListPolicyVersions",
      "iam:ListInstanceProfilesForRole",
      "iam:GetOpenIDConnectProvider",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "ci_plan" {
  name   = "${var.project_name}-github-actions-ci-plan"
  policy = data.aws_iam_policy_document.ci_plan.json
}

resource "aws_iam_role_policy_attachment" "ci_plan" {
  role       = aws_iam_role.github_actions_ci.name
  policy_arn = aws_iam_policy.ci_plan.arn
}

# --- Snowflake storage integration role -----------------------------------
# Assumed by Snowflake (not GitHub Actions) via the external-ID pattern.
# Created here with a locked placeholder trust policy because Snowflake only
# generates the real IAM user ARN / external ID *after* the storage
# integration is created with this role's ARN as an input -- see the
# "storage integration bootstrap" section of the root README.

data "aws_iam_policy_document" "storage_integration_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [var.storage_integration_iam_user_arn != "" ? var.storage_integration_iam_user_arn : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    dynamic "condition" {
      for_each = var.storage_integration_external_id != "" ? [1] : []
      content {
        test     = "StringEquals"
        variable = "sts:ExternalId"
        values   = [var.storage_integration_external_id]
      }
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "storage_integration" {
  name = "${var.project_name}-snowflake-storage-integration"

  # Phase 1 (storage_integration_iam_user_arn/external_id unset): trusts only
  # this account's own root, which by itself grants no cross-account access
  # -- effectively unassumable by Snowflake. Phase 2, after `terraform apply`
  # + reading the storage integration's real values back into these
  # variables, narrows the trust to Snowflake's actual IAM user + external ID.
  assume_role_policy = data.aws_iam_policy_document.storage_integration_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "storage_integration" {
  statement {
    sid       = "RawPayloadReadWrite"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:GetObjectVersion", "s3:DeleteObject"]
    resources = ["${var.bucket_arn}/${var.raw_prefix}*"]
  }

  statement {
    sid       = "RawPrefixList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.raw_prefix}*"]
    }
  }
}

resource "aws_iam_policy" "storage_integration" {
  name   = "${var.project_name}-snowflake-storage-integration"
  policy = data.aws_iam_policy_document.storage_integration.json
}

resource "aws_iam_role_policy_attachment" "storage_integration" {
  role       = aws_iam_role.storage_integration.name
  policy_arn = aws_iam_policy.storage_integration.arn
}
