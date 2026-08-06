"""Orchestrates one full ingestion run: extract -> normalize -> store, for
every registered source, optionally backfilling several simulated days of
history in fixture mode.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from inventory_pipeline.catalog import load_catalog
from inventory_pipeline.config import DataSourceMode, Settings
from inventory_pipeline.extractors.base import ProductRef
from inventory_pipeline.extractors.registry import all_sources, get_extractor
from inventory_pipeline.logging_config import get_logger
from inventory_pipeline.models import IngestionManifest, RunStatus, SourceName, utcnow
from inventory_pipeline.storage.base import RawStorage
from inventory_pipeline.storage.factory import get_storage

logger = get_logger()


@dataclass
class RunOutcome:
    source: SourceName
    manifest: IngestionManifest
    error: str | None = None


@dataclass
class IngestionSummary:
    outcomes: list[RunOutcome] = field(default_factory=list)

    @property
    def total_runs(self) -> int:
        return len(self.outcomes)

    @property
    def total_events(self) -> int:
        return sum(o.manifest.events_normalized for o in self.outcomes)

    @property
    def total_rejected(self) -> int:
        return sum(o.manifest.events_rejected for o in self.outcomes)

    @property
    def failed_runs(self) -> int:
        return sum(1 for o in self.outcomes if o.manifest.status == RunStatus.FAILED)

    @property
    def success_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        succeeded = sum(1 for o in self.outcomes if o.manifest.status != RunStatus.FAILED)
        return round(100 * succeeded / len(self.outcomes), 1)


def _run_status(events_normalized: int, events_rejected: int, payloads_received: int) -> RunStatus:
    if payloads_received == 0 or events_normalized == 0:
        return RunStatus.FAILED
    if events_rejected > 0:
        return RunStatus.PARTIAL_FAILURE
    return RunStatus.SUCCESS


def run_ingestion(
    settings: Settings,
    *,
    backfill_days: int = 1,
    sources: list[SourceName] | None = None,
    catalog: list[ProductRef] | None = None,
    storage: RawStorage | None = None,
) -> IngestionSummary:
    """Run extraction + storage for each source, once per simulated day.

    backfill_days=1 means "just today" (a normal scheduled run). Larger values
    only make sense in fixture mode, where they seed a realistic multi-day
    history so the warehouse has something to analyze on first load.
    """
    if settings.data_source_mode == DataSourceMode.LIVE and backfill_days > 1:
        raise ValueError("backfill_days > 1 is only supported in fixture mode")

    storage = storage or get_storage(settings)
    products = catalog or load_catalog()
    sources = sources or all_sources()
    summary = IngestionSummary()

    # The most recent simulated day (day_offset=0) must never land in the
    # future -- anchoring to "today at noon UTC" did that whenever the real
    # run happened before noon. Anchor to the actual current moment instead;
    # every earlier day is just that moment minus N whole days.
    anchor = utcnow()

    for day_offset in range(backfill_days - 1, -1, -1):
        observed_at = anchor - timedelta(days=day_offset)
        for source in sources:
            summary.outcomes.append(
                _run_one(settings, source, observed_at, day_offset, products, storage)
            )

    logger.info(
        "ingestion_summary",
        total_runs=summary.total_runs,
        total_events=summary.total_events,
        total_rejected=summary.total_rejected,
        failed_runs=summary.failed_runs,
        success_rate=summary.success_rate,
    )
    return summary


def _run_one(
    settings: Settings,
    source: SourceName,
    observed_at: datetime,
    day_offset: int,
    products: list[ProductRef],
    storage: RawStorage,
) -> RunOutcome:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    extractor = get_extractor(
        source,
        ingestion_run_id=run_id,
        settings=settings,
        observed_at=observed_at,
        day_offset=day_offset,
    )

    manifest = IngestionManifest(
        run_id=run_id,
        source=source,
        observed_at=observed_at,
        started_at=started_at,
        pipeline_version=settings.pipeline_version,
    )

    try:
        result = extractor.extract(products)
    except NotImplementedError as err:
        manifest.completed_at = datetime.now(UTC)
        manifest.status = RunStatus.FAILED
        manifest.error_summary = [str(err)]
        logger.warning("extraction_skipped", source=source.value, reason=str(err))
        return RunOutcome(source=source, manifest=manifest, error=str(err))

    manifest.payloads_received = result.payloads_received
    manifest.events_normalized = len(result.events)
    manifest.events_rejected = len(result.rejected)
    manifest.error_summary = [r.reason for r in result.rejected][:10]
    manifest.status = _run_status(
        manifest.events_normalized, manifest.events_rejected, manifest.payloads_received
    )
    manifest.completed_at = datetime.now(UTC)

    storage.write_run(
        source=source.value,
        run_id=run_id,
        observed_at=observed_at,
        raw_payloads=result.raw_payloads,
        events=result.events,
        rejected=result.rejected,
        manifest=manifest,
    )

    return RunOutcome(source=source, manifest=manifest)
