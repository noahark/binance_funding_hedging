"""Snapshot service.

Pipeline: fetch raw -> filter TRADING USDT-quoted perpetuals/TRADIFI
-> normalize/classify -> assemble -> jsonschema-validate. In-memory TTL cache so repeated requests
within TTL do not refetch. Never serves an invalid snapshot: on validation
failure it raises and the caller maps that to HTTP 503.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import jsonschema

from ..adapters.binance_public import BinancePublicClient
from ..config import Config, FROZEN_GENERATED_AT, FROZEN_SOURCE_SAMPLE_ID
from ..domain.normalize import iso_from_ms
from ..domain.snapshot import (
    SORT_BASIS_ABS,
    SORT_BASIS_NET,
    assemble_borrow_validation,
    assemble_private_account,
    assemble_snapshot,
    build_rows,
    compute_net_daily_yield,
    resolve_cost_leg_rate,
    select_borrow_candidates,
    sort_rows,
    top_symbols_by_abs_rate,
)
from ..services.private_client import PrivateClient

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
        # Private borrow-validation client (the repo's single HMAC exit). Offline
        # mode never touches the private channel (no key, no network) -> every row
        # degrades to verified=false. Live mode reads key/secret from env; missing
        # -> enabled=False -> same verified=false degradation.
        if config.offline:
            _api_key = _api_secret = None
        else:
            _api_key = os.environ.get("BINANCE_API_KEY")
            _api_secret = os.environ.get("BINANCE_API_SECRET")
        self._private = PrivateClient(
            api_key=_api_key,
            api_secret=_api_secret,
            user_agent=config.user_agent,
            timeout=config.request_timeout,
            recv_window=config.private_recv_window,
            ttl_seconds=config.private_channel_ttl_seconds,
            fast_ttl_seconds=config.private_channel_fast_ttl_seconds,
        )

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
        funding_interval_by_sym = raw.get("funding_interval_by_sym", {})
        fetch_warnings = raw.get("warnings", [])

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
            futures_symbols,
            premium_by_sym,
            spot_by_sym,
            funding_by_sym,
            funding_interval_by_sym=funding_interval_by_sym,
        )

        # ---- private channel (single HMAC exit, deny-by-default) ----
        # All signed HTTP happens here, BEFORE the row loop (§3.2: no HTTP in the
        # row loop). Disabled (env missing) or classic-reference failure ->
        # classic_ref None -> every row verified=false; the public snapshot still
        # renders. Offline mode never touches the private channel.
        classic_ref = self._private.fetch_classic_reference()
        private_channel_status = "enabled" if classic_ref is not None else "disabled"
        private_error = self._private.last_error if classic_ref is None else None

        # §1.5 borrow probe set (neg funding + MARGIN_SPOT_CANDIDATE + CRYPTO,
        # deduped by base_asset, capped at borrow_check_max_calls). Truncated
        # candidates render verified=false / not_probed_this_round.
        probe = select_borrow_candidates(rows, self.config.borrow_check_max_calls)
        probed_assets = probe["probed_assets"]
        truncated_assets = probe["truncated_assets"]
        coverage = probe["coverage"]

        # §1.3 cost-leg chain (snapshot-level single tier; 1h TTL group). None
        # when the channel is disabled.
        cost_leg = self._private.fetch_cost_leg_chain(probed_assets)
        cost_leg_available = bool(
            classic_ref is not None and cost_leg and cost_leg.get("chain_hit_tier") is not None
        )

        # §1.4 private_account block (three-state semantics SAME AS
        # borrow_validation, per the §1.4 heading): when classic_ref is None the
        # channel is disabled/failed, so private_account MUST be verified=false
        # regardless of whether the account endpoints would succeed — skip them.
        # Price map (P5, public, full, once) values the balances; the three
        # account fetches use the 60s TTL group.
        if classic_ref is None:
            price_map = {}
            unified = um_positions = spot_balances = None
        else:
            price_map = self.client.fetch_ticker_price_map()
            unified = self._private.fetch_unified_balances()
            um_positions = self._private.fetch_um_positions()
            spot_balances = self._private.fetch_spot_balances()

        checked_at = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if classic_ref is not None
            else None
        )
        private_account, account_warnings = assemble_private_account(
            unified,
            spot_balances,
            um_positions,
            price_map,
            checked_at=checked_at,
            error=private_error,
        )

        # W4 maxBorrowable for the probed candidate set (1h TTL; bounded probe
        # loop over assets, NOT the row loop). bStock rows are excluded upstream
        # (asset_tag != CRYPTO); their portfolio_account amount fields stay null.
        portfolio_by_asset: dict = {}
        for asset in probed_assets:
            if asset in portfolio_by_asset:
                continue
            res = self._private.fetch_max_borrowable(asset)
            portfolio_by_asset[asset] = res or {
                "max_borrowable": None,
                "borrow_limit": None,
            }

        # ---- row assembly (pure; no HTTP) ----
        for row in rows:
            base = row.get("base_asset", "")
            daily_borrow_rate = None
            borrow_rate_source = None
            # Chain rate only for probed (non-truncated) borrow candidates.
            if base in probed_assets and base not in truncated_assets and cost_leg:
                rate = resolve_cost_leg_rate(base, cost_leg)
                if rate is not None:
                    daily_borrow_rate = rate
                    borrow_rate_source = cost_leg.get("chain_hit_source")
            row["net_daily_yield"] = compute_net_daily_yield(
                row.get("daily_funding_rate"), daily_borrow_rate
            )
            row["borrow_rate_source"] = borrow_rate_source
            row["borrow_validation"] = assemble_borrow_validation(
                row,
                classic_ref,
                portfolio_by_asset,
                checked_at,
                private_error,
                daily_interest_account=daily_borrow_rate,
                truncated=base in truncated_assets,
            )

        # §1.2 sort_basis: net when the cost leg is available (incl. vip0_reference),
        # else the Phase 2 abs-daily behavior (full-order regression when disabled).
        sort_basis = SORT_BASIS_NET if cost_leg_available else SORT_BASIS_ABS
        rows = sort_rows(rows, sort_basis)

        borrow_validation_summary = {
            "coverage": coverage,
            "classic_margin_daily_interest_account_available": cost_leg_available,
            "chain_hit_tier": cost_leg.get("chain_hit_tier") if cost_leg else None,
            "chain_hit_source": cost_leg.get("chain_hit_source") if cost_leg else None,
        }

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
            private_channel_status=private_channel_status,
            sort_basis=sort_basis,
            private_account=private_account,
            borrow_validation_summary=borrow_validation_summary,
            extra_warnings=fetch_warnings + account_warnings,
        )

    def request_log(self) -> dict:
        return dict(self.client.request_log)
