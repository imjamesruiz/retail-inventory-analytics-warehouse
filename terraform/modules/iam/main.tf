# --- Jenkins CI user ------------------------------------------------------
# A local Jenkins controller (jenkins/) has no public HTTPS endpoint, so it
# can't do OIDC federation the way GitHub Actions did -- there's no JWKS
# endpoint for AWS to call back into. Long-lived access keys on a
# narrowly-scoped IAM user are the pragmatic tradeoff instead: no Terraform
# resource generates the key pair (that would put a secret in state), see the
# README for creating one by hand and storing it in Jenkins' credential
# store.
#
# Carries both the raw-payload read/write policy (for RAW_STORAGE_BACKEND=s3
# ingestion runs) and the read-only terraform-plan policy below -- one
# principal for both Jenkins job types, since they run on the same
# controller.

resource "aws_iam_user" "jenkins_ci" {
  name = "${var.project_name}-jenkins-ci"
  tags = var.tags
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

resource "aws_iam_user_policy_attachment" "ingestion" {
  user       = aws_iam_user.jenkins_ci.name
  policy_arn = aws_iam_policy.ingestion.arn
}

# Read-only by design: this user can never apply, so a compromised Jenkins
# credential can't be used to change infrastructure -- see the "no
# auto-apply" comment in jenkins/Jenkinsfile.terraform.

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
      "iam:ListUserPolicies",
      "iam:ListAttachedUserPolicies",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "ci_plan" {
  name   = "${var.project_name}-jenkins-ci-plan"
  policy = data.aws_iam_policy_document.ci_plan.json
}

resource "aws_iam_user_policy_attachment" "ci_plan" {
  user       = aws_iam_user.jenkins_ci.name
  policy_arn = aws_iam_policy.ci_plan.arn
}

# --- Snowflake storage integration role -----------------------------------
# Assumed by Snowflake (not Jenkins) via the external-ID pattern.
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
