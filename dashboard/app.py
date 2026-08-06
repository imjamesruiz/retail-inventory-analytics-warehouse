"""Retail Inventory Analytics Warehouse -- Streamlit dashboard.

Queries Snowflake mart/fact tables only (see db.py, queries.py) -- never raw
tables directly, so everything shown here has passed dbt's tests.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

import queries  # noqa: E402
from charts import RETAILER_COLORS, SEQUENTIAL_SCALE, STATUS_COLORS  # noqa: E402
from db import get_settings_cached  # noqa: E402

st.set_page_config(page_title="Retail Inventory Analytics", layout="wide")

st.title("Retail Inventory Analytics Warehouse")
st.caption(
    "Historical inventory and pricing analytics, built on Snowflake + dbt. "
    "Every view below reads dbt mart/fact tables -- not raw data."
)


def _load_overview() -> pd.DataFrame | None:
    try:
        return queries.overview_totals()
    except Exception as err:  # noqa: BLE001 - any connection/config problem lands here
        st.error(
            "Could not query Snowflake. This dashboard reads dbt's mart/fact tables, "
            "so it needs a populated warehouse and valid credentials.\n\n"
            f"**Details:** {err}"
        )
        st.info(
            "To load data:\n"
            "1. `make ingest-fixtures` -- generates and stores fixture inventory events\n"
            "2. `make load-snowflake` -- loads them into Snowflake's RAW schema\n"
            "3. `make dbt-build` -- builds and tests the staging/intermediate/mart models\n\n"
            "Or run all three with `make pipeline`. See docs/architecture.md for Snowflake "
            "account setup if you haven't run snowflake/setup.sql yet."
        )
        return None


overview_df = _load_overview()
if overview_df is None or overview_df.empty or overview_df["TOTAL_OBSERVATIONS"].iloc[0] is None:
    st.warning(
        "Connected to Snowflake, but no data has been loaded yet. Run `make pipeline` "
        "to populate the warehouse with fixture data."
    )
    st.stop()

row = overview_df.iloc[0]

st.caption(
    f"Dashboard query cache refreshes every 5 minutes. Warehouse data as of "
    f"latest observation: **{row['LATEST_OBSERVED_AT']}**."
)

metric_cols = st.columns(5)
metric_cols[0].metric("Total observations", f"{int(row['TOTAL_OBSERVATIONS']):,}")
metric_cols[1].metric("Rejected records", f"{int(row['TOTAL_REJECTED'] or 0):,}")
metric_cols[2].metric("Ingestion runs", f"{int(row['TOTAL_RUNS'] or 0):,}")
metric_cols[3].metric("Pipeline success rate", f"{row['OVERALL_SUCCESS_RATE_PCT'] or 0:.1f}%")
metric_cols[4].metric("Avg. availability", f"{row['AVG_AVAILABILITY_PCT'] or 0:.1f}%")

st.divider()

retailers_df = queries.retailers()
all_retailers = retailers_df["SOURCE"].tolist()

with st.sidebar:
    st.header("Filters")
    selected_retailers = st.multiselect("Retailers", options=all_retailers, default=all_retailers)
    default_start = date.today() - timedelta(days=30)
    start_date, end_date = st.date_input("Date range", value=(default_start, date.today()))
    if isinstance(start_date, date) and not isinstance(end_date, date):
        end_date = start_date

products_df = queries.products(selected_retailers or None)
product_options = dict(zip(products_df["PRODUCT_NAME"], products_df["PRODUCT_KEY"], strict=False))

tab_health, tab_availability, tab_price, tab_changes, tab_volume = st.tabs(
    [
        "Retailer Health",
        "Product Availability",
        "Price History",
        "Inventory State Changes",
        "Daily Ingestion Volume",
    ]
)

with tab_health:
    st.subheader("Pipeline health and freshness by retailer")
    summary_df = queries.retailer_summary()
    if selected_retailers:
        summary_df = summary_df[summary_df["SOURCE"].isin(selected_retailers)]

    fig = px.bar(
        summary_df,
        x="SOURCE",
        y="RUN_SUCCESS_RATE_PCT",
        color="SOURCE",
        color_discrete_map=RETAILER_COLORS,
        labels={"SOURCE": "Retailer", "RUN_SUCCESS_RATE_PCT": "Run success rate (%)"},
        title="Ingestion run success rate",
    )
    fig.update_layout(showlegend=False, yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)

    stale = summary_df[summary_df["HOURS_SINCE_LAST_OBSERVATION"] > 26]
    if not stale.empty:
        st.warning(
            f"{len(stale)} retailer(s) have not reported an observation in over 26 hours: "
            f"{', '.join(stale['SOURCE'].tolist())}."
        )

    st.dataframe(
        summary_df[
            [
                "SOURCE",
                "RETAILER_NAME",
                "INTEGRATION_MODE",
                "TOTAL_RUNS",
                "SUCCESSFUL_RUNS",
                "FAILED_RUNS",
                "TOTAL_EVENTS_NORMALIZED",
                "TOTAL_EVENTS_REJECTED",
                "AVG_RUN_DURATION_SECONDS",
                "LAST_OBSERVED_AT",
                "HOURS_SINCE_LAST_OBSERVATION",
                "AVG_AVAILABILITY_PCT",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

with tab_availability:
    st.subheader("Availability by product")
    avail_df = queries.availability_by_product(
        start_date, end_date, selected_retailers, list(product_options.values()) or None
    )
    if avail_df.empty:
        st.info("No availability data for the selected filters.")
    else:
        fig = px.bar(
            avail_df.sort_values("AVG_AVAILABILITY_PCT").head(20),
            x="AVG_AVAILABILITY_PCT",
            y="PRODUCT_NAME",
            color="AVG_AVAILABILITY_PCT",
            color_continuous_scale=SEQUENTIAL_SCALE,
            orientation="h",
            labels={"AVG_AVAILABILITY_PCT": "Avg. availability (%)", "PRODUCT_NAME": "Product"},
            title="Lowest-availability products in range",
        )
        fig.update_layout(xaxis_range=[0, 100], coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(avail_df, use_container_width=True, hide_index=True)

    st.subheader("Availability timeline for one product")
    if product_options:
        chosen_name = st.selectbox("Product", options=list(product_options.keys()))
        chosen_key = product_options[chosen_name]
        timeline_df = queries.availability_timeline(chosen_key, start_date, end_date)
        if timeline_df.empty:
            st.info("No observations for this product in the selected date range.")
        else:
            fig = px.line(
                timeline_df,
                x="OBSERVATION_DATE",
                y="AVAILABILITY_PCT",
                markers=True,
                labels={"OBSERVATION_DATE": "Date", "AVAILABILITY_PCT": "Availability (%)"},
                title=f"Daily availability: {chosen_name}",
            )
            fig.update_traces(line_color=RETAILER_COLORS.get("TARGET", "#0072B2"))
            fig.update_layout(yaxis_range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No products match the current filters.")

with tab_price:
    st.subheader("Price history for one product")
    if product_options:
        chosen_name = st.selectbox(
            "Product", options=list(product_options.keys()), key="price_product"
        )
        chosen_key = product_options[chosen_name]
        price_df = queries.price_history(chosen_key, start_date, end_date)
        if price_df.empty:
            st.info("No priced observations for this product in the selected date range.")
        else:
            fig = px.line(
                price_df,
                x="OBSERVED_AT",
                y="CURRENT_PRICE",
                markers=True,
                labels={"OBSERVED_AT": "Observed at", "CURRENT_PRICE": "Price (USD)"},
                title=f"Price history: {chosen_name}",
            )
            changes = price_df[price_df["PRICE_CHANGED"]]
            if not changes.empty:
                fig.add_scatter(
                    x=changes["OBSERVED_AT"],
                    y=changes["CURRENT_PRICE"],
                    mode="markers",
                    marker={"size": 10, "color": STATUS_COLORS["went_out_of_stock"]},
                    name="Price change",
                )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(price_df, use_container_width=True, hide_index=True)
    else:
        st.info("No products match the current filters.")

with tab_changes:
    st.subheader("Recent inventory state transitions")
    changes_df = queries.state_changes(start_date, end_date, selected_retailers)
    if changes_df.empty:
        st.info("No status transitions in the selected range.")
    else:
        restocks = int(changes_df["RESTOCKED"].sum())
        stockouts = int(changes_df["WENT_OUT_OF_STOCK"].sum())
        c1, c2 = st.columns(2)
        c1.metric("Restocks", restocks)
        c2.metric("Went out of stock", stockouts)
        st.dataframe(changes_df, use_container_width=True, hide_index=True)

with tab_volume:
    st.subheader("Daily observation volume by retailer")
    volume_df = queries.daily_observation_volume(start_date, end_date)
    if selected_retailers:
        volume_df = volume_df[volume_df["SOURCE"].isin(selected_retailers)]
    if volume_df.empty:
        st.info("No observations in the selected date range.")
    else:
        fig = px.bar(
            volume_df,
            x="OBSERVATION_DATE",
            y="OBSERVATIONS",
            color="SOURCE",
            color_discrete_map=RETAILER_COLORS,
            labels={"OBSERVATION_DATE": "Date", "OBSERVATIONS": "Observations"},
            title="Observations collected per day",
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(
    f"Retail Inventory Analytics Warehouse -- pipeline version "
    f"{get_settings_cached().pipeline_version}. Fixture mode by default; see README for "
    f"switching to live retailer data."
)
