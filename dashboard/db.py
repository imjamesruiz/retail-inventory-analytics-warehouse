"""Snowflake connection + cached query execution for the dashboard.

Every dashboard view queries mart/fact tables only -- never raw.* directly --
so what's displayed always reflects dbt's tested, documented output.
"""

from __future__ import annotations

import pandas as pd
import snowflake.connector
import streamlit as st

from inventory_pipeline.config import Settings, get_settings


@st.cache_resource(show_spinner=False)
def get_settings_cached() -> Settings:
    return get_settings()


@st.cache_resource(show_spinner=False)
def get_connection() -> snowflake.connector.SnowflakeConnection:
    settings = get_settings_cached()
    settings.require_snowflake()
    kwargs: dict[str, str] = {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "role": settings.snowflake_role,
        "warehouse": settings.snowflake_warehouse,
        "database": settings.snowflake_database,
    }
    if settings.snowflake_private_key_path:
        kwargs["private_key_file"] = settings.snowflake_private_key_path
    else:
        kwargs["password"] = settings.snowflake_password
    return snowflake.connector.connect(**kwargs)


def marts_table(name: str) -> str:
    """Fully-qualified name of a mart/fact table, matching dbt's custom schema
    naming (target schema + "_marts"). Table/schema names come from trusted
    config, not user input, so this f-string is not an injection risk."""
    settings = get_settings_cached()
    schema = f"{settings.snowflake_schema_analytics}_MARTS"
    return f"{settings.snowflake_database}.{schema}.{name}"


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.fetch_pandas_all()
