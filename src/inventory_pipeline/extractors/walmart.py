"""Walmart extractor -- the Walmart Affiliate API is a documented, registered-key
integration, so this is the project's primary live-mode example. Ported from
src/retailers/walmartClient.ts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from inventory_pipeline.config import DataSourceMode, Settings
from inventory_pipeline.extractors import fixture_data
from inventory_pipeline.extractors.base import BaseExtractor, ProductRef, SourcePayload
from inventory_pipeline.logging_config import get_logger
from inventory_pipeline.models import InventoryEvent, SourceName, utcnow
from inventory_pipeline.normalizers import walmart as walmart_normalizer
from inventory_pipeline.rate_limiter import RateLimiter
from inventory_pipeline.retry import RetryConfig, with_retry

logger = get_logger()

BASE_URL = "https://api.walmartlabs.com/v1/items"
_HEADERS = {"User-Agent": "retail-inventory-analytics-warehouse/0.1"}


class WalmartExtractor(BaseExtractor):
    source = SourceName.WALMART

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
        self._rate_limiter = RateLimiter(delay_seconds=0.5)

    def fetch_payloads(self, products: list[ProductRef]) -> list[SourcePayload]:
        if self.settings.data_source_mode == DataSourceMode.LIVE:
            return self._fetch_live(products)
        return [
            SourcePayload(
                product=product,
                raw=fixture_data.walmart_payload(product, self.day_offset),
                observed_at=self.observed_at,
            )
            for product in products
        ]

    def _fetch_live(self, products: list[ProductRef]) -> list[SourcePayload]:
        self.settings.require_live_credentials("WALMART")
        payloads: list[SourcePayload] = []
        for product in products:
            try:
                raw = self._rate_limiter.run(lambda p=product: self._get_item(p))
                payloads.append(SourcePayload(product=product, raw=raw, observed_at=utcnow()))
            except Exception as err:  # noqa: BLE001 - logged and skipped, not fatal
                logger.error(
                    "walmart_fetch_failed",
                    retailer_product_id=product.retailer_product_id,
                    error=str(err),
                )
        return payloads

    def _get_item(self, product: ProductRef) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            response = httpx.get(
                f"{BASE_URL}/{product.retailer_product_id}",
                params={"apiKey": self.settings.walmart_api_key, "format": "json"},
                headers=_HEADERS,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

        return with_retry(call, RetryConfig())

    def normalize_payload(self, payload: SourcePayload) -> InventoryEvent:
        return walmart_normalizer.normalize(
            payload.raw,
            payload.product,
            ingestion_run_id=self.ingestion_run_id,
            observed_at=payload.observed_at,
            extracted_at=utcnow(),
        )
