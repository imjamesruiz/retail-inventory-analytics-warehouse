from datetime import UTC, datetime

import pytest

from inventory_pipeline.extractors.base import ProductRef, SourcePayload
from inventory_pipeline.models import IngestionManifest, InventoryEvent, InventoryStatus, SourceName
from inventory_pipeline.storage.local import LocalRawStorage

PRODUCT = ProductRef(
    id="p1",
    retailer=SourceName.TARGET,
    retailer_product_id="12345",
    name="Test Product",
    url="https://example.com/p1",
)
OBSERVED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _sample_event() -> InventoryEvent:
    return InventoryEvent.build(
        source=SourceName.TARGET,
        retailer_product_id="12345",
        product_name="Test Product",
        product_url="https://example.com/p1",
        inventory_status=InventoryStatus.IN_STOCK,
        observed_at=OBSERVED_AT,
        ingestion_run_id="run-1",
        source_response_hash="deadbeef",
    )


def _sample_manifest(run_id: str = "run-1") -> IngestionManifest:
    return IngestionManifest(
        run_id=run_id,
        source=SourceName.TARGET,
        observed_at=OBSERVED_AT,
        started_at=OBSERVED_AT,
        completed_at=OBSERVED_AT,
        payloads_received=1,
        events_normalized=1,
        events_rejected=0,
    )


def test_write_run_creates_partitioned_files(tmp_path):
    storage = LocalRawStorage(base_dir=tmp_path)
    payloads = [SourcePayload(product=PRODUCT, raw={"foo": "bar"}, observed_at=OBSERVED_AT)]
    events = [_sample_event()]
    manifest = _sample_manifest()

    location = storage.write_run(
        source="TARGET",
        run_id="run-1",
        observed_at=OBSERVED_AT,
        raw_payloads=payloads,
        events=events,
        rejected=[],
        manifest=manifest,
    )

    assert "source=TARGET" in location.raw_payload_path
    assert "year=2026" in location.raw_payload_path
    assert "month=01" in location.raw_payload_path
    assert "day=01" in location.raw_payload_path
    assert "run_id=run-1" in location.raw_payload_path

    assert storage.exists(location.raw_payload_path)
    assert storage.exists(location.normalized_output_path)
    assert storage.exists(location.manifest_path)

    raw_content = storage.read_text(location.raw_payload_path)
    assert "12345" in raw_content


def test_write_run_refuses_to_overwrite(tmp_path):
    storage = LocalRawStorage(base_dir=tmp_path)
    payloads = [SourcePayload(product=PRODUCT, raw={"foo": "bar"}, observed_at=OBSERVED_AT)]
    manifest = _sample_manifest()

    storage.write_run(
        source="TARGET",
        run_id="run-1",
        observed_at=OBSERVED_AT,
        raw_payloads=payloads,
        events=[_sample_event()],
        rejected=[],
        manifest=manifest,
    )

    with pytest.raises(FileExistsError):
        storage.write_run(
            source="TARGET",
            run_id="run-1",
            observed_at=OBSERVED_AT,
            raw_payloads=payloads,
            events=[_sample_event()],
            rejected=[],
            manifest=_sample_manifest(),
        )


def test_manifest_content_is_valid_json(tmp_path):
    storage = LocalRawStorage(base_dir=tmp_path)
    payloads = [SourcePayload(product=PRODUCT, raw={"foo": "bar"}, observed_at=OBSERVED_AT)]
    manifest = _sample_manifest()

    location = storage.write_run(
        source="TARGET",
        run_id="run-1",
        observed_at=OBSERVED_AT,
        raw_payloads=payloads,
        events=[_sample_event()],
        rejected=[],
        manifest=manifest,
    )

    written = storage.read_text(location.manifest_path)
    parsed = IngestionManifest.model_validate_json(written)
    assert parsed.run_id == "run-1"
    assert parsed.content_hashes  # populated by write_run


def test_list_keys_finds_written_files(tmp_path):
    storage = LocalRawStorage(base_dir=tmp_path)
    payloads = [SourcePayload(product=PRODUCT, raw={"foo": "bar"}, observed_at=OBSERVED_AT)]
    storage.write_run(
        source="TARGET",
        run_id="run-1",
        observed_at=OBSERVED_AT,
        raw_payloads=payloads,
        events=[_sample_event()],
        rejected=[],
        manifest=_sample_manifest(),
    )

    keys = storage.list_keys("raw/")
    assert any(k.endswith("manifest.json") for k in keys)
    assert any(k.endswith("normalized_events.ndjson") for k in keys)
