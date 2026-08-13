resource "snowflake_warehouse" "this" {
  name                = var.warehouse_name
  warehouse_size      = var.warehouse_size
  auto_suspend        = var.auto_suspend_seconds
  auto_resume         = true
  initially_suspended = true
  comment             = "Warehouse for the Retail Inventory Analytics Warehouse project"
}

resource "snowflake_database" "this" {
  name    = var.database_name
  comment = "Raw and analytics data for retail inventory/pricing observations"
}

resource "snowflake_schema" "this" {
  for_each = toset(var.schemas)

  database = snowflake_database.this.name
  name     = each.value
  comment  = "Managed by Terraform (modules/snowflake)"
}

resource "snowflake_account_role" "dbt" {
  name    = var.dbt_role_name
  comment = "Role used by the ingestion pipeline, dbt, and the dashboard for this project"
}

# --- Warehouse + database-level grants ------------------------------------

resource "snowflake_grant_privileges_to_account_role" "warehouse_usage" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["USAGE", "OPERATE"]

  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.this.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database_usage" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["USAGE", "CREATE SCHEMA"]

  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.this.name
  }
}

# --- Schema-level grants ----------------------------------------------------
# ALL on the pre-created RAW/ANALYTICS schemas, plus ALL on every schema dbt
# creates going forward (ANALYTICS_STAGING etc.) via its custom schema
# naming -- mirrors snowflake/roles.sql exactly.

resource "snowflake_grant_privileges_to_account_role" "schema_all" {
  for_each = snowflake_schema.this

  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["ALL"]

  on_schema {
    schema_name = "\"${snowflake_database.this.name}\".\"${each.value.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "future_schemas" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["ALL"]

  on_schema {
    future_schemas_in_database = snowflake_database.this.name
  }
}

# --- Table/view grants -------------------------------------------------
# Existing objects (relevant if this is layered onto a database that
# already has tables, e.g. adopting Terraform after manual setup) plus
# future objects in every schema, present and dbt-created.

resource "snowflake_grant_privileges_to_account_role" "tables_all" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["ALL"]

  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_database        = snowflake_database.this.name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "future_tables" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["ALL"]

  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_database        = snowflake_database.this.name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "views_all" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["ALL"]

  on_schema_object {
    all {
      object_type_plural = "VIEWS"
      in_database        = snowflake_database.this.name
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "future_views" {
  account_role_name = snowflake_account_role.dbt.name
  privileges        = ["ALL"]

  on_schema_object {
    future {
      object_type_plural = "VIEWS"
      in_database        = snowflake_database.this.name
    }
  }
}

# --- CI service user (key-pair auth) --------------------------------------

resource "snowflake_user" "ci" {
  count = var.ci_user_rsa_public_key != "" ? 1 : 0

  name              = var.ci_user_name
  default_role      = snowflake_account_role.dbt.name
  default_warehouse = snowflake_warehouse.this.name
  rsa_public_key    = var.ci_user_rsa_public_key
  comment           = "Service user for GitHub Actions CI"
}

resource "snowflake_grant_account_role" "ci_user" {
  count = var.ci_user_rsa_public_key != "" ? 1 : 0

  role_name = snowflake_account_role.dbt.name
  user_name = snowflake_user.ci[0].name
}

resource "snowflake_grant_account_role" "developer_users" {
  for_each = toset(var.grant_role_to_users)

  role_name = snowflake_account_role.dbt.name
  user_name = each.value
}

# --- S3 storage integration --------------------------------------------
# storage_aws_role_arn points at the IAM role from modules/iam. Its trust
# policy starts locked (no real Snowflake principal yet) -- the
# storage_aws_iam_user_arn / storage_aws_external_id this resource computes
# are exactly what phase 2 feeds back into that role's trust policy. See the
# storage integration bootstrap note in the root README.

resource "snowflake_storage_integration" "s3" {
  name                      = var.storage_integration_name
  type                      = "EXTERNAL_STAGE"
  storage_provider          = "S3"
  storage_aws_role_arn      = var.storage_integration_iam_role_arn
  storage_allowed_locations = ["s3://${var.s3_bucket_name}/${var.s3_raw_prefix}"]
  enabled                   = true
  comment                   = "Connects Snowflake external stages to the raw payload bucket"
}
