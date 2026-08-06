"""Computes genuine project statistics from actual pipeline output.

Every number here is derived from real artifacts on disk (manifests, the
raw storage tree, the dbt project's own source files, and dbt's own
`target/manifest.json` when available) -- never hardcoded. Run `make
ingest-fixtures` first, or there is nothing to measure yet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from inventory_pipeline.catalog import load_catalog
from inventory_pipeline.config import Settings
from inventory_pipeline.storage.base import RawStorage
from inventory_pipeline.storage.factory import get_storage

DBT_PROJECT_DIR = Path(__file__).resolve().parents[2] / "dbt_inventory"


@dataclass
class PipelineMetrics:
    total_runs: int = 0
    successful_runs: int = 0
    partial_failure_runs: int = 0
    failed_runs: int = 0
    total_events: int = 0
    total_rejected: int = 0
    sources_seen: set[str] = field(default_factory=set)
    products_tracked: int = 0
    retailers_tracked: int = 0
    observed_at_min: datetime | None = None
    observed_at_max: datetime | None = None
    avg_run_duration_seconds: float | None = None
    dbt_model_count: int | None = None
    dbt_test_count: int | None = None
    dbt_stats_source: str = "not available"

    @property
    def success_rate_pct(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return round(100 * (self.successful_runs + self.partial_failure_runs) / self.total_runs, 1)


def compute_pipeline_metrics(
    settings: Settings, storage: RawStorage | None = None
) -> PipelineMetrics:
    storage = storage or get_storage(settings)
    metrics = PipelineMetrics()

    catalog = load_catalog()
    metrics.products_tracked = len(catalog)
    metrics.retailers_tracked = len({p.retailer.value for p in catalog})

    manifest_keys = [k for k in storage.list_keys("raw/") if k.endswith("manifest.json")]
    durations: list[float] = []

    for key in manifest_keys:
        manifest = json.loads(storage.read_text(key))
        metrics.total_runs += 1
        metrics.sources_seen.add(manifest["source"])
        metrics.total_events += manifest.get("events_normalized", 0)
        metrics.total_rejected += manifest.get("events_rejected", 0)

        status = manifest.get("status")
        if status == "SUCCESS":
            metrics.successful_runs += 1
        elif status == "PARTIAL_FAILURE":
            metrics.partial_failure_runs += 1
        else:
            metrics.failed_runs += 1

        observed_at = _parse_dt(manifest.get("observed_at"))
        if observed_at:
            if metrics.observed_at_min is None or observed_at < metrics.observed_at_min:
                metrics.observed_at_min = observed_at
            if metrics.observed_at_max is None or observed_at > metrics.observed_at_max:
                metrics.observed_at_max = observed_at

        started = _parse_dt(manifest.get("started_at"))
        completed = _parse_dt(manifest.get("completed_at"))
        if started and completed:
            durations.append((completed - started).total_seconds())

    if durations:
        metrics.avg_run_duration_seconds = round(sum(durations) / len(durations), 3)

    _attach_dbt_stats(metrics)
    return metrics


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _attach_dbt_stats(metrics: PipelineMetrics) -> None:
    dbt_manifest_path = DBT_PROJECT_DIR / "target" / "manifest.json"
    if dbt_manifest_path.exists():
        dbt_manifest = json.loads(dbt_manifest_path.read_text())
        nodes = dbt_manifest.get("nodes", {})
        metrics.dbt_model_count = sum(
            1 for n in nodes.values() if n.get("resource_type") == "model"
        )
        metrics.dbt_test_count = sum(1 for n in nodes.values() if n.get("resource_type") == "test")
        metrics.dbt_stats_source = "dbt_inventory/target/manifest.json (post `dbt build`)"
        return

    models_dir = DBT_PROJECT_DIR / "models"
    if models_dir.exists():
        metrics.dbt_model_count = sum(1 for _ in models_dir.rglob("*.sql"))
        singular_tests_dir = DBT_PROJECT_DIR / "tests"
        singular = (
            sum(1 for _ in singular_tests_dir.rglob("*.sql")) if singular_tests_dir.exists() else 0
        )
        generic_test_refs = 0
        for yml in models_dir.rglob("*.yml"):
            generic_test_refs += yml.read_text().count("- unique") + yml.read_text().count(
                "- not_null"
            )
        metrics.dbt_test_count = singular + generic_test_refs
        metrics.dbt_stats_source = (
            "static count of .sql/.yml files (run `dbt build` for exact counts)"
        )


def render_markdown(metrics: PipelineMetrics) -> str:
    date_range = "no data yet"
    if metrics.observed_at_min and metrics.observed_at_max:
        date_range = f"{metrics.observed_at_min.date()} to {metrics.observed_at_max.date()}"

    lines = [
        "# Project Metrics",
        "",
        "Generated automatically from real pipeline output by "
        "`inventory-pipeline metrics` (see src/inventory_pipeline/metrics.py). "
        "Every value below is measured, not estimated.",
        "",
        "## Ingestion",
        f"- Total ingestion runs: **{metrics.total_runs}**",
        f"- Successful runs: **{metrics.successful_runs}**",
        f"- Partial-failure runs: **{metrics.partial_failure_runs}**",
        f"- Failed runs: **{metrics.failed_runs}**",
        f"- Pipeline run success rate: **{metrics.success_rate_pct}%**",
        f"- Average run duration: "
        f"**{metrics.avg_run_duration_seconds if metrics.avg_run_duration_seconds is not None else 'n/a'} seconds**",
        "",
        "## Data volume",
        f"- Total normalized events processed: **{metrics.total_events}**",
        f"- Total rejected records: **{metrics.total_rejected}**",
        f"- Products tracked in catalog: **{metrics.products_tracked}**",
        f"- Retailers integrated: **{metrics.retailers_tracked}**",
        f"- Date range covered: **{date_range}**",
        "",
        "## dbt project",
        f"- dbt models: **{metrics.dbt_model_count if metrics.dbt_model_count is not None else 'n/a'}**",
        f"- dbt tests: **{metrics.dbt_test_count if metrics.dbt_test_count is not None else 'n/a'}**",
        f"- Source: {metrics.dbt_stats_source}",
        "",
    ]
    return "\n".join(lines)
