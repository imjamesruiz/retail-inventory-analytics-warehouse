"""Command-line entry points, callable directly (`python -m inventory_pipeline.cli ...`
or the `inventory-pipeline` console script) independent of the Makefile."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from inventory_pipeline.config import DataSourceMode, get_settings
from inventory_pipeline.logging_config import configure_logging, get_logger
from inventory_pipeline.metrics import compute_pipeline_metrics, render_markdown
from inventory_pipeline.pipeline import run_ingestion
from inventory_pipeline.storage.factory import get_storage

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


@click.group()
def cli() -> None:
    """Retail Inventory Analytics Warehouse pipeline CLI."""
    settings = get_settings()
    configure_logging(settings.log_level)


@cli.command()
@click.option(
    "--source-mode",
    type=click.Choice(["fixture", "live"]),
    default=None,
    help="Override DATA_SOURCE_MODE for this run.",
)
@click.option(
    "--backfill-days",
    type=int,
    default=None,
    help="Simulate this many days of history (fixture mode only). Default: 14 for "
    "fixture mode, 1 for live mode.",
)
def ingest(source_mode: str | None, backfill_days: int | None) -> None:
    """Extract, normalize, and store raw + normalized events for every source."""
    logger = get_logger()
    settings = get_settings()
    if source_mode:
        settings.data_source_mode = DataSourceMode(source_mode)

    if backfill_days is None:
        backfill_days = 14 if settings.data_source_mode == DataSourceMode.FIXTURE else 1

    summary = run_ingestion(settings, backfill_days=backfill_days)

    logger.info(
        "ingest_command_completed",
        total_runs=summary.total_runs,
        total_events=summary.total_events,
        total_rejected=summary.total_rejected,
        failed_runs=summary.failed_runs,
        success_rate=summary.success_rate,
    )
    click.echo(
        f"Ingestion complete: {summary.total_runs} runs, {summary.total_events} events, "
        f"{summary.total_rejected} rejected, {summary.failed_runs} failed "
        f"({summary.success_rate}% success rate)."
    )
    if summary.total_events == 0:
        sys.exit(1)


@cli.command(name="load-snowflake")
def load_snowflake() -> None:
    """Load everything currently in raw storage into Snowflake (idempotent)."""
    from inventory_pipeline.loaders.snowflake import SnowflakeLoader

    logger = get_logger()
    settings = get_settings()
    storage = get_storage(settings)

    try:
        loader = SnowflakeLoader(settings)
        result = loader.load_from_storage(storage)
    except ValueError as err:
        click.echo(f"Cannot load to Snowflake: {err}", err=True)
        sys.exit(1)

    logger.info("load_snowflake_command_completed", **result.__dict__)
    click.echo(
        f"Loaded {result.events_loaded} new events and {result.runs_loaded} new run "
        f"records into Snowflake."
    )


@cli.command(name="dbt-build")
def dbt_build() -> None:
    """Run `dbt build` against the dbt_inventory project."""
    dbt_dir = Path(__file__).resolve().parents[2] / "dbt_inventory"
    result = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=dbt_dir)
    sys.exit(result.returncode)


@cli.command()
@click.option(
    "--source-mode",
    type=click.Choice(["fixture", "live"]),
    default="fixture",
    help="Data source mode for the full pipeline run.",
)
def pipeline(source_mode: str) -> None:
    """Full run: ingest -> load Snowflake -> dbt build -> summary.

    Exits nonzero if any stage fails, since this command is meant for CI and
    scheduled runs where a silent partial success is worse than a loud one.
    """
    logger = get_logger()
    settings = get_settings()
    settings.data_source_mode = DataSourceMode(source_mode)
    backfill_days = 14 if settings.data_source_mode == DataSourceMode.FIXTURE else 1

    click.echo("== Stage 1/3: ingestion ==")
    summary = run_ingestion(settings, backfill_days=backfill_days)
    click.echo(
        f"  {summary.total_runs} runs, {summary.total_events} events, "
        f"{summary.total_rejected} rejected, {summary.failed_runs} failed."
    )
    if summary.total_events == 0:
        click.echo("Ingestion produced zero events; aborting pipeline.", err=True)
        sys.exit(1)

    click.echo("== Stage 2/3: load into Snowflake ==")
    try:
        from inventory_pipeline.loaders.snowflake import SnowflakeLoader

        storage = get_storage(settings)
        loader = SnowflakeLoader(settings)
        load_result = loader.load_from_storage(storage)
        click.echo(
            f"  Loaded {load_result.events_loaded} new events, "
            f"{load_result.runs_loaded} new run records."
        )
    except ValueError as err:
        click.echo(f"  Skipped: {err}", err=True)
        sys.exit(1)

    click.echo("== Stage 3/3: dbt build ==")
    dbt_dir = Path(__file__).resolve().parents[2] / "dbt_inventory"
    dbt_result = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=dbt_dir)
    if dbt_result.returncode != 0:
        click.echo("  dbt build failed.", err=True)
        sys.exit(dbt_result.returncode)

    logger.info("pipeline_command_completed", status="success")
    click.echo("Pipeline completed successfully.")


@cli.command()
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Where to write the markdown report. Default: docs/project_metrics.md.",
)
def metrics(output: Path | None) -> None:
    """Compute real project statistics and write docs/project_metrics.md."""
    settings = get_settings()
    result = compute_pipeline_metrics(settings)
    markdown = render_markdown(result)

    output_path = output or (DOCS_DIR / "project_metrics.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown)

    click.echo(markdown)
    click.echo(f"Written to {output_path}")


if __name__ == "__main__":
    cli()
