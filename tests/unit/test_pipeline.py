import pytest

from inventory_pipeline.config import DataSourceMode, Settings
from inventory_pipeline.models import RunStatus
from inventory_pipeline.pipeline import run_ingestion
from inventory_pipeline.storage.local import LocalRawStorage


def test_run_ingestion_fixture_mode_all_sources_succeed(tmp_path):
    settings = Settings(_env_file=None, data_source_mode=DataSourceMode.FIXTURE)
    storage = LocalRawStorage(base_dir=tmp_path)

    summary = run_ingestion(settings, backfill_days=2, storage=storage)

    assert summary.total_runs == 4 * 2  # 4 sources x 2 simulated days
    assert summary.total_events > 0
    assert summary.failed_runs == 0
    for outcome in summary.outcomes:
        assert outcome.manifest.status in (RunStatus.SUCCESS, RunStatus.PARTIAL_FAILURE)


def test_run_ingestion_repeatable_with_fresh_run_ids(tmp_path):
    settings = Settings(_env_file=None, data_source_mode=DataSourceMode.FIXTURE)
    storage = LocalRawStorage(base_dir=tmp_path)

    first = run_ingestion(settings, backfill_days=1, storage=storage)
    second = run_ingestion(settings, backfill_days=1, storage=storage)

    # Distinct run_ids each time, so re-running never collides with raw storage's
    # overwrite guard -- duplicate detection happens at the Snowflake MERGE
    # stage via the deterministic event_id.
    assert first.total_runs == second.total_runs == 4
    assert first.total_events == second.total_events


def test_backfill_days_gt_one_rejected_in_live_mode(tmp_path):
    settings = Settings(_env_file=None, data_source_mode=DataSourceMode.LIVE)
    storage = LocalRawStorage(base_dir=tmp_path)

    with pytest.raises(ValueError, match="fixture mode"):
        run_ingestion(settings, backfill_days=3, storage=storage)
