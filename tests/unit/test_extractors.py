from datetime import UTC, datetime

import pytest

from inventory_pipeline.config import DataSourceMode, Settings
from inventory_pipeline.extractors.base import BaseExtractor, ProductRef, SourcePayload
from inventory_pipeline.extractors.gamestop import GamestopExtractor
from inventory_pipeline.extractors.registry import all_sources, get_extractor
from inventory_pipeline.extractors.target import TargetExtractor
from inventory_pipeline.extractors.walmart import WalmartExtractor
from inventory_pipeline.models import InventoryEvent, SourceName

OBSERVED_AT = datetime(2026, 1, 1, tzinfo=UTC)

PRODUCTS = [
    ProductRef(
        id="target-1",
        retailer=SourceName.TARGET,
        retailer_product_id="111",
        name="Target Product",
        url="https://example.com/t1",
    ),
    ProductRef(
        id="walmart-1",
        retailer=SourceName.WALMART,
        retailer_product_id="222",
        name="Walmart Product",
        url="https://example.com/w1",
    ),
]


def _settings(mode: DataSourceMode = DataSourceMode.FIXTURE) -> Settings:
    return Settings(_env_file=None, data_source_mode=mode)


def test_fixture_extraction_produces_events_only_for_matching_source():
    extractor = TargetExtractor(
        ingestion_run_id="run-1", settings=_settings(), observed_at=OBSERVED_AT, day_offset=0
    )
    result = extractor.extract(PRODUCTS)
    assert result.payloads_received == 1
    assert len(result.events) == 1
    assert result.events[0].source == SourceName.TARGET


def test_target_live_mode_raises_not_implemented():
    extractor = TargetExtractor(
        ingestion_run_id="run-1",
        settings=_settings(DataSourceMode.LIVE),
        observed_at=OBSERVED_AT,
    )
    with pytest.raises(NotImplementedError):
        extractor.fetch_payloads(PRODUCTS)


def test_gamestop_live_mode_raises_not_implemented():
    extractor = GamestopExtractor(
        ingestion_run_id="run-1",
        settings=_settings(DataSourceMode.LIVE),
        observed_at=OBSERVED_AT,
    )
    with pytest.raises(NotImplementedError):
        extractor.fetch_payloads(PRODUCTS)


def test_walmart_live_mode_requires_api_key():
    extractor = WalmartExtractor(
        ingestion_run_id="run-1",
        settings=_settings(DataSourceMode.LIVE),
        observed_at=OBSERVED_AT,
    )
    with pytest.raises(ValueError, match="WALMART_API_KEY"):
        extractor._fetch_live(PRODUCTS)


def test_registry_returns_extractor_per_source():
    for source in all_sources():
        extractor = get_extractor(
            source, ingestion_run_id="run-1", settings=_settings(), observed_at=OBSERVED_AT
        )
        assert extractor.source == source


def test_registry_unknown_source_raises():
    with pytest.raises(ValueError, match="No extractor registered"):
        get_extractor(
            "NOT_A_SOURCE",  # type: ignore[arg-type]
            ingestion_run_id="run-1",
            settings=_settings(),
            observed_at=OBSERVED_AT,
        )


class _BrokenExtractor(BaseExtractor):
    source = SourceName.TARGET

    def fetch_payloads(self, products: list[ProductRef]) -> list[SourcePayload]:
        return [SourcePayload(product=products[0], raw={"bad": True}, observed_at=OBSERVED_AT)]

    def normalize_payload(self, payload: SourcePayload) -> InventoryEvent:
        raise ValueError("malformed payload: missing required field")


def test_normalization_failures_become_rejected_records_not_exceptions():
    extractor = _BrokenExtractor(ingestion_run_id="run-1")
    result = extractor.extract(PRODUCTS)
    assert result.events == []
    assert len(result.rejected) == 1
    assert "malformed payload" in result.rejected[0].reason
    assert result.rejected[0].retailer_product_id == "111"
