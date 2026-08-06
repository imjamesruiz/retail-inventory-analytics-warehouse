from datetime import UTC, datetime

import pytest

from inventory_pipeline.extractors.base import ProductRef
from inventory_pipeline.models import InventoryStatus, SourceName
from inventory_pipeline.normalizers import gamestop, pokemon_center, target, walmart

PRODUCT = ProductRef(
    id="p1",
    retailer=SourceName.TARGET,
    retailer_product_id="12345",
    name="Fallback Name",
    url="https://example.com/p1",
    category="trading-cards",
)
NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "status,expected",
    [
        ("AVAILABLE", InventoryStatus.IN_STOCK),
        ("IN_STOCK", InventoryStatus.IN_STOCK),
        ("UNAVAILABLE", InventoryStatus.OUT_OF_STOCK),
        ("NOT_AVAILABLE", InventoryStatus.OUT_OF_STOCK),
        ("PREORDER", InventoryStatus.PREORDER),
        ("BACKORDER", InventoryStatus.BACKORDER),
        (None, InventoryStatus.UNKNOWN),
        ("SOME_NEW_STATUS", InventoryStatus.UNKNOWN),
    ],
)
def test_target_availability_mapping(status, expected):
    raw = {
        "data": {
            "product": {
                "item": {"product_description": {"title": "Target Product"}},
                "price": {"current_retail": 19.99},
                "available_to_promise": {
                    "availability": status,
                    "available_to_promise_quantity": 5,
                },
            }
        }
    }
    event = target.normalize(
        raw, PRODUCT, ingestion_run_id="run-1", observed_at=NOW, extracted_at=NOW
    )
    assert event.inventory_status == expected
    assert event.price == 19.99
    assert event.product_name == "Target Product"


def test_target_missing_product_raises():
    with pytest.raises(ValueError, match="no product data"):
        target.normalize(
            {"data": {}}, PRODUCT, ingestion_run_id="r", observed_at=NOW, extracted_at=NOW
        )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ({"availableOnline": True}, InventoryStatus.IN_STOCK),
        ({"availableOnline": False}, InventoryStatus.OUT_OF_STOCK),
        ({"stock": "Available"}, InventoryStatus.IN_STOCK),
        ({"stock": "Not available"}, InventoryStatus.OUT_OF_STOCK),
        ({}, InventoryStatus.UNKNOWN),
    ],
)
def test_walmart_stock_mapping(raw, expected):
    raw = {**raw, "name": "Walmart Product", "salePrice": 29.99}
    event = walmart.normalize(
        raw, PRODUCT, ingestion_run_id="run-1", observed_at=NOW, extracted_at=NOW
    )
    assert event.inventory_status == expected


def test_walmart_empty_response_raises():
    with pytest.raises(ValueError, match="empty response"):
        walmart.normalize({}, PRODUCT, ingestion_run_id="r", observed_at=NOW, extracted_at=NOW)


@pytest.mark.parametrize(
    "available,expected",
    [
        (True, InventoryStatus.IN_STOCK),
        (False, InventoryStatus.OUT_OF_STOCK),
        (None, InventoryStatus.UNKNOWN),
    ],
)
def test_pokemon_center_availability_mapping(available, expected):
    raw = {
        "product": {
            "title": "PC Product",
            "variants": [{"price": "39.99", "available": available, "sku": "SKU1"}],
        }
    }
    event = pokemon_center.normalize(
        raw, PRODUCT, ingestion_run_id="run-1", observed_at=NOW, extracted_at=NOW
    )
    assert event.inventory_status == expected


def test_pokemon_center_missing_product_raises():
    with pytest.raises(ValueError, match="no product data"):
        pokemon_center.normalize(
            {}, PRODUCT, ingestion_run_id="r", observed_at=NOW, extracted_at=NOW
        )


def test_gamestop_in_stock_mapping():
    raw = {
        "productName": "GS Product",
        "pricing": {"salePrice": 59.99},
        "availability": {"isInStock": True},
        "sku": "SKU2",
    }
    event = gamestop.normalize(
        raw, PRODUCT, ingestion_run_id="run-1", observed_at=NOW, extracted_at=NOW
    )
    assert event.inventory_status == InventoryStatus.IN_STOCK
    assert event.price == 59.99


def test_gamestop_empty_response_raises():
    with pytest.raises(ValueError, match="empty response"):
        gamestop.normalize({}, PRODUCT, ingestion_run_id="r", observed_at=NOW, extracted_at=NOW)
