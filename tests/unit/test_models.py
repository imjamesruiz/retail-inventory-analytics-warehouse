from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from inventory_pipeline.models import (
    InventoryEvent,
    InventoryStatus,
    SourceName,
    hash_payload,
    make_event_id,
)


def _base_kwargs(**overrides):
    kwargs = dict(
        source=SourceName.TARGET,
        retailer_product_id="12345",
        product_name="Test Product",
        product_url="https://example.com/p/12345",
        inventory_status=InventoryStatus.IN_STOCK,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        ingestion_run_id="run-1",
        source_response_hash="deadbeef",
    )
    kwargs.update(overrides)
    return kwargs


def test_event_id_is_deterministic():
    observed_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    id_a = make_event_id("TARGET", "12345", observed_at)
    id_b = make_event_id("TARGET", "12345", observed_at)
    assert id_a == id_b


def test_event_id_differs_for_different_products():
    observed_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    id_a = make_event_id("TARGET", "12345", observed_at)
    id_b = make_event_id("TARGET", "67890", observed_at)
    assert id_a != id_b


def test_build_derives_event_id():
    event = InventoryEvent.build(**_base_kwargs())
    expected = make_event_id("TARGET", "12345", _base_kwargs()["observed_at"])
    assert event.event_id == expected


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        InventoryEvent(
            event_id="x",
            **_base_kwargs(price=-1.0),
        )


def test_negative_quantity_rejected():
    with pytest.raises(ValidationError):
        InventoryEvent(
            event_id="x",
            **_base_kwargs(quantity_available=-5),
        )


def test_naive_timestamp_assumed_utc():
    naive = datetime(2026, 1, 1, 12, 0)
    event = InventoryEvent(event_id="x", **_base_kwargs(observed_at=naive, extracted_at=naive))
    assert event.observed_at.tzinfo is not None


def test_hash_payload_is_stable_regardless_of_key_order():
    a = hash_payload({"x": 1, "y": 2})
    b = hash_payload({"y": 2, "x": 1})
    assert a == b


def test_hash_payload_differs_for_different_content():
    assert hash_payload({"x": 1}) != hash_payload({"x": 2})
