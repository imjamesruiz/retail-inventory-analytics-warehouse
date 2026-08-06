"""GameStop extractor -- fixture-only.

The original bot called GameStop's internal page-data API (no official public
API exists). Same reasoning as the Target extractor: not a permitted access
method, so this project does not port it as a live integration. See
docs/decisions.md.
"""

from __future__ import annotations

from datetime import datetime

from inventory_pipeline.config import DataSourceMode, Settings
from inventory_pipeline.extractors import fixture_data
from inventory_pipeline.extractors.base import BaseExtractor, ProductRef, SourcePayload
from inventory_pipeline.models import InventoryEvent, SourceName, utcnow
from inventory_pipeline.normalizers import gamestop as gamestop_normalizer


class GamestopExtractor(BaseExtractor):
    source = SourceName.GAMESTOP

    def __init__(
        self,
        ingestion_run_id: str,
        settings: Settings,
        observed_at: datetime,
        day_offset: int = 0,
    ) -> None:
        super().__init__(ingestion_run_id)
        self.settings = settings
        self.observed_at = observed_at
        self.day_offset = day_offset

    def fetch_payloads(self, products: list[ProductRef]) -> list[SourcePayload]:
        if self.settings.data_source_mode == DataSourceMode.LIVE:
            raise NotImplementedError(
                "Live mode is not implemented for GAMESTOP: no official public API exists, "
                "and the original bot's endpoint was an unofficial internal API. Set "
                "DATA_SOURCE_MODE=fixture for this source."
            )
        return [
            SourcePayload(
                product=product,
                raw=fixture_data.gamestop_payload(product, self.day_offset),
                observed_at=self.observed_at,
            )
            for product in products
        ]

    def normalize_payload(self, payload: SourcePayload) -> InventoryEvent:
        return gamestop_normalizer.normalize(
            payload.raw,
            payload.product,
            ingestion_run_id=self.ingestion_run_id,
            observed_at=payload.observed_at,
            extracted_at=utcnow(),
        )
