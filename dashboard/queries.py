"""SQL query functions backing the dashboard, one per view. All read from
mart/fact tables (see db.marts_table) -- analytics-ready, tested output,
never raw.* directly."""

from __future__ import annotations

import pandas as pd
from db import marts_table, run_query


def _in_clause(column: str, values: list, param_prefix: str) -> tuple[str, dict]:
    """Builds "column in (%(prefix_0)s, %(prefix_1)s, ...)" plus its params.

    The Snowflake connector does not expand a single tuple-valued parameter
    into a SQL IN-list the way some DB-API drivers do -- binding
    `%(name)s` to a tuple produces one malformed value, not a parenthesized
    list, and fails with a syntax error. Each value needs its own
    placeholder.
    """
    keys = [f"{param_prefix}_{i}" for i in range(len(values))]
    clause = f"{column} in ({', '.join(f'%({k})s' for k in keys)})"
    params = dict(zip(keys, values, strict=True))
    return clause, params


def overview_totals() -> pd.DataFrame:
    sql = f"""
        select
            sum(total_events_normalized) as total_observations,
            sum(total_events_rejected) as total_rejected,
            sum(total_runs) as total_runs,
            sum(failed_runs) as total_failed_runs,
            round(100.0 * sum(successful_runs + partial_failure_runs) / nullif(sum(total_runs), 0), 1)
                as overall_success_rate_pct,
            max(last_observed_at) as latest_observed_at,
            avg(avg_availability_pct) as avg_availability_pct
        from {marts_table("MART_RETAILER_SUMMARY")}
    """
    return run_query(sql)


def retailer_summary() -> pd.DataFrame:
    sql = f"""
        select
            source, retailer_name, integration_mode, total_runs, successful_runs,
            partial_failure_runs, failed_runs, run_success_rate_pct,
            total_events_normalized, total_events_rejected, avg_run_duration_seconds,
            last_observed_at, hours_since_last_observation, avg_availability_pct
        from {marts_table("MART_RETAILER_SUMMARY")}
        order by source
    """
    return run_query(sql)


def retailers() -> pd.DataFrame:
    sql = f"select source, retailer_name from {marts_table('DIM_RETAILER')} order by retailer_name"
    return run_query(sql)


def products(selected_retailers: list[str] | None = None) -> pd.DataFrame:
    where_clause = ""
    params: dict = {}
    if selected_retailers:
        clause, params = _in_clause("source", selected_retailers, "retailer")
        where_clause = f"where {clause}"

    sql = f"""
        select product_key, source, product_name, category
        from {marts_table("DIM_PRODUCT")}
        {where_clause}
        order by product_name
    """
    return run_query(sql, params)


def availability_by_product(
    start_date, end_date, selected_retailers, selected_products
) -> pd.DataFrame:
    extra_clauses = []
    params: dict = {"start_date": start_date, "end_date": end_date}

    if selected_retailers:
        clause, retailer_params = _in_clause("source", selected_retailers, "retailer")
        extra_clauses.append(f"and {clause}")
        params.update(retailer_params)
    if selected_products:
        clause, product_params = _in_clause("product_key", selected_products, "product")
        extra_clauses.append(f"and {clause}")
        params.update(product_params)

    sql = f"""
        select
            product_key, source, product_name, category,
            avg(availability_pct) as avg_availability_pct,
            max(observation_date) as last_observation_date,
            sum(observation_count) as total_observations
        from {marts_table("MART_DAILY_PRODUCT_AVAILABILITY")}
        where observation_date between %(start_date)s and %(end_date)s
        {" ".join(extra_clauses)}
        group by 1, 2, 3, 4
        order by avg_availability_pct asc
    """
    return run_query(sql, params)


def availability_timeline(product_key: str, start_date, end_date) -> pd.DataFrame:
    sql = f"""
        select observation_date, availability_pct, last_status, avg_price
        from {marts_table("MART_DAILY_PRODUCT_AVAILABILITY")}
        where product_key = %(product_key)s
          and observation_date between %(start_date)s and %(end_date)s
        order by observation_date
    """
    return run_query(
        sql, {"product_key": product_key, "start_date": start_date, "end_date": end_date}
    )


def price_history(product_key: str, start_date, end_date) -> pd.DataFrame:
    sql = f"""
        select observed_at, current_price, previous_price, price_changed, pct_change
        from {marts_table("FACT_PRICE_OBSERVATION")}
        where product_key = %(product_key)s
          and observed_at between %(start_date)s and %(end_date)s
        order by observed_at
    """
    return run_query(
        sql, {"product_key": product_key, "start_date": start_date, "end_date": end_date}
    )


def state_changes(start_date, end_date, selected_retailers) -> pd.DataFrame:
    extra_clause = ""
    params: dict = {"start_date": start_date, "end_date": end_date}
    if selected_retailers:
        clause, retailer_params = _in_clause("fsc.source", selected_retailers, "retailer")
        extra_clause = f"and {clause}"
        params.update(retailer_params)

    sql = f"""
        select
            fsc.observed_at, fsc.source, dp.product_name, fsc.previous_status,
            fsc.current_status, fsc.restocked, fsc.went_out_of_stock
        from {marts_table("FACT_INVENTORY_STATE_CHANGE")} fsc
        left join {marts_table("DIM_PRODUCT")} dp on dp.product_key = fsc.product_key
        where fsc.observed_at between %(start_date)s and %(end_date)s
        {extra_clause}
        order by fsc.observed_at desc
        limit 500
    """
    return run_query(sql, params)


def daily_observation_volume(start_date, end_date) -> pd.DataFrame:
    sql = f"""
        select cast(observed_at as date) as observation_date, source, count(*) as observations
        from {marts_table("FACT_INVENTORY_OBSERVATION")}
        where observed_at between %(start_date)s and %(end_date)s
        group by 1, 2
        order by 1
    """
    return run_query(sql, {"start_date": start_date, "end_date": end_date})
