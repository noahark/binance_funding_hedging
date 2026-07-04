"""Snapshot service.

Pipeline: fetch raw -> filter TRADING USDT-quoted perpetuals/TRADIFI
-> normalize/classify -> assemble -> jsonschema-validate. In-memory TTL cache so repeated requests
within TTL do not refetch. Never serves an invalid snapshot: on validation
failure it raises and the caller maps that to HTTP 503.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional

import jsonschema

from ..adapters.binance_public import BinancePublicClient
from ..config import Config, FROZEN_GENERATED_AT, FROZEN_SOURCE_SAMPLE_ID
from ..domain.normalize import iso_from_ms
from ..domain.snapshot import (
    assemble_snapshot,
    build_rows,
    top_symbols_by_abs_rate,
)

ELIGIBLE_CONTRACT_TYPES = ("PERPETUAL", "TRADIFI_PERPETUAL")


class SnapshotService:
    def __init__(self, config: Config, client: Optional[BinancePublicClient] = None):
        self.config = config
        self.client = client or BinancePublicClient(
            offline=config.offline,
            offline_dir=config.offline_raw_dir,
            futures_base_url=config.futures_base_url,
            spot_base_url=config.spot_base_url,
            user_agent=config.user_agent,
            timeout=config.request_timeout,
        )
        self._cache = None  # (monotonic, snapshot)
        self._schema = None

    def _load_schema(self):
        if self._schema is None:
            with open(self.config.schema_path, encoding="utf-8") as fh:
                self._schema = json.load(fh)
        return self._schema

    def get_snapshot(self) -> dict:
        """Return a cached snapshot within TTL, else build + validate + cache."""
        now = time.monotonic()
        if self._cache is not None and (now - self._cache[0]) < self.config.cache_ttl_seconds:
            return self._cache[1]
        snapshot = self.build_snapshot()
        jsonschema.validate(instance=snapshot, schema=self._load_schema())
        self._cache = (now, snapshot)
        return snapshot

    def build_snapshot(self) -> dict:
        raw = self.client.fetch_raw()
        futures_symbols = [
            s
            for s in raw["futures_exchange_info"].get("symbols", [])
            if s.get("status") == "TRADING"
            and s.get("contractType") in ELIGIBLE_CONTRACT_TYPES
            and s.get("quoteAsset") == "USDT"
        ]
        premium_by_sym = {p["symbol"]: p for p in raw["premium_index"]}
        spot_by_sym = {
            s["symbol"]: s for s in raw["spot_exchange_info"].get("symbols", [])
        }
        funding_by_sym = dict(raw.get("funding_history_by_sym", {}))

        if not self.client.offline:
            # Top-N bounds LIVE /fapi/v1/fundingRate call volume. Offline uses
            # all frozen fixtures already in funding_by_sym (no HTTP cost).
            top_symbols = top_symbols_by_abs_rate(
                futures_symbols, premium_by_sym, self.config.top_n
            )
            for sym in top_symbols:
                if sym not in funding_by_sym:
                    funding_by_sym[sym] = self.client.fetch_funding_rate(sym)

        rows = build_rows(
            futures_symbols, premium_by_sym, spot_by_sym, funding_by_sym
        )

        data_time_ms = max((p.get("time", 0) for p in raw["premium_index"]), default=0)
        if self.client.offline:
            generated_at = FROZEN_GENERATED_AT
            source_sample_id = FROZEN_SOURCE_SAMPLE_ID
        else:
            now_utc = datetime.now(timezone.utc)
            generated_at = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            source_sample_id = now_utc.strftime("%Y%m%dT%H%M%SZ")

        return assemble_snapshot(
            rows,
            generated_at=generated_at,
            data_time=iso_from_ms(data_time_ms),
            source_sample_id=source_sample_id,
        )

    def request_log(self) -> dict:
        return dict(self.client.request_log)
