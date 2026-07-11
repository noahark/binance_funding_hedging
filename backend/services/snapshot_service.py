"""Snapshot service.

Pipeline: fetch raw -> filter TRADING USDT-quoted perpetuals/TRADIFI
-> normalize/classify -> assemble -> jsonschema-validate. In-memory TTL cache so repeated requests
within TTL do not refetch. Never serves an invalid snapshot: on validation
failure it raises and the caller maps that to HTTP 503.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
from datetime import datetime, timezone
from typing import List, Optional

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
    settle_history_view,
    sort_rows,
    top_symbols_by_abs_rate,
)
from ..services.private_client import PrivateClient

ELIGIBLE_CONTRACT_TYPES = ("PERPETUAL", "TRADIFI_PERPETUAL")

FUNDING_HISTORY_SCHEMA_VERSION = "public-market-funding-history/v1"

# Eligible query symbol for the selected-history endpoint: Binance USDⓈ-M
# perpetual symbols are uppercase alphanumerics (e.g. BTCUSDT, 1000SATSUSDT).
# Rejects missing/empty/lower-case/space-injected values as HTTP 400 before the
# snapshot is consulted.
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,40}$")


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
        # Dedicated per-symbol successful-result cache for settled deep history
        # (records are immutable -> longer TTL than the 60s snapshot cache, ADR-2).
        # Failed requests are NOT cached so they retry on the next snapshot
        # rebuild instead of locking the symbol out for a TTL.
        self._funding_history_cache: dict = {}  # symbol -> (monotonic, raw entries)
        # Selected-symbol history endpoint (Task C): the snapshot premium-index
        # time (ms) is the settled-window end; set on each build_snapshot so the
        # endpoint reuses the SAME boundary as the cached snapshot it validated
        # against (60s snapshot cache hit keeps the last-build boundary in sync).
        self._data_time_ms = 0
        self._funding_history_schema = None  # lazily loaded on first endpoint use
        # Private borrow-validation client (the repo's single HMAC exit). Offline
        # mode never touches the private channel (no key, no network) -> every row
        # degrades to verified=false. Live mode still requires an explicit
        # operator switch before reading key/secret from env; missing switch or
        # missing keys -> enabled=False -> same verified=false degradation.
        if config.offline or not config.private_channel_enabled:
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

        # Snapshot premium-index time scopes the settled-history window: it is
        # the inclusive end of both the live deep-history request and the 7D/30D
        # annualization windows.
        data_time_ms = max((p.get("time", 0) for p in raw["premium_index"]), default=0)
        self._data_time_ms = data_time_ms  # Task C endpoint window end
        history_warnings: List[str] = []

        if not self.client.offline:
            # Top-N bounds LIVE /fapi/v1/fundingRate call volume (ADR-2). Offline
            # uses all frozen fixtures already in funding_by_sym (no HTTP cost).
            top_symbols = top_symbols_by_abs_rate(
                futures_symbols, premium_by_sym, self.config.top_n
            )
            for sym in top_symbols:
                if sym in funding_by_sym:
                    continue
                entries = self._fetch_history_for(sym, data_time_ms)
                if entries is None:
                    # Individual failure degrades only this row (empty history +
                    # null 7D/30D + warning); the snapshot still renders. The
                    # failed request is NOT cached so it retries next rebuild.
                    history_warnings.append(f"funding_history_unavailable:{sym}")
                    continue
                funding_by_sym[sym] = entries

        rows = build_rows(
            futures_symbols,
            premium_by_sym,
            spot_by_sym,
            funding_by_sym,
            funding_interval_by_sym=funding_interval_by_sym,
            t_end_ms=data_time_ms,
        )

        # ---- private channel (single HMAC exit, deny-by-default) ----
        # All signed HTTP happens here, BEFORE the row loop (§3.2: no HTTP in the
        # row loop). Disabled (env missing) or classic-reference failure ->
        # classic_ref None -> every row verified=false; the public snapshot still
        # renders. Offline mode never touches the private channel.
        classic_ref = self._private.fetch_classic_reference()
        private_channel_status = "enabled" if classic_ref is not None else "disabled"
        private_error = self._private.last_error if classic_ref is None else None

        # §1.5 borrow probe sets (neg funding + MARGIN_SPOT_CANDIDATE + {CRYPTO, METAL},
        # deduped by base_asset). The rate budget (rate_probe_assets, full pool)
        # and the borrowability budget (borrowability_probe_assets, capped at
        # borrow_check_max_calls) are decoupled: rate coverage is NOT bounded by
        # the maxBorrowable cost. Unprobed candidates keep their rate and render
        # verified=false / error="borrowability_not_probed".
        probe = select_borrow_candidates(rows, self.config.borrow_check_max_calls)
        rate_probe_assets = probe["rate_probe_assets"]
        borrowability_probe_assets = probe["borrowability_probe_assets"]
        borrowability_unprobed_assets = probe["borrowability_unprobed_assets"]
        coverage = probe["coverage"]

        # §1.3 cost-leg chain (snapshot-level single tier; 1h TTL group). None
        # when the channel is disabled. Driven by the FULL rate set.
        cost_leg = self._private.fetch_cost_leg_chain(rate_probe_assets)
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

        # W4 maxBorrowable for the borrowability-probed candidate set (1h TTL;
        # bounded probe loop over assets, NOT the row loop). bStock rows are
        # excluded upstream (asset_tag not in {CRYPTO, METAL}); their portfolio_account amount
        # fields stay null.
        portfolio_by_asset: dict = {}
        for asset in borrowability_probe_assets:
            if asset in portfolio_by_asset:
                continue
            res = self._private.fetch_max_borrowable(asset)
            portfolio_by_asset[asset] = res or {
                "max_borrowable": None,
                "borrow_limit": None,
                "error_code": None,
            }

        # ---- row assembly (pure; no HTTP) ----
        for row in rows:
            base = row.get("base_asset", "")
            daily_borrow_rate = None
            borrow_rate_source = None
            # Rate coverage depends ONLY on the rate set (decoupled from the
            # borrowability cap); the asset need not be in borrowability_probe.
            if base in rate_probe_assets and cost_leg:
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
                borrowability_truncated=base in borrowability_unprobed_assets,
                price_map=price_map,
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
            extra_warnings=fetch_warnings + account_warnings + history_warnings,
        )

    def _fetch_history_for(self, symbol: str, t_end_ms: int) -> Optional[List[dict]]:
        """Top-N settled deep history with a dedicated per-symbol successful-
        result cache (ADR-2).

        Returns the raw Binance ``/fapi/v1/fundingRate`` entries for the inclusive
        ``[t_end - 30d, t_end]`` window, or ``None`` on a transport/HTTP/parse
        failure. The caller degrades that row (empty history + null 7D/30D +
        warning); the failure is NOT cached, so it retries on the next snapshot
        rebuild instead of locking the symbol out for a TTL. The 60-second
        whole-snapshot cache is independent of this TTL.
        """
        now = time.monotonic()
        ttl = self.config.funding_history_cache_ttl_seconds
        cached = self._funding_history_cache.get(symbol)
        if cached is not None and (now - cached[0]) < ttl:
            return cached[1]
        start_ms = int(t_end_ms) - 30 * 86_400_000
        try:
            entries = self.client.fetch_funding_rate(
                symbol,
                start_time_ms=start_ms,
                end_time_ms=int(t_end_ms),
                limit=1000,
            )
        except (urllib.error.URLError, OSError, ValueError):
            return None
        self._funding_history_cache[symbol] = (now, entries)
        return entries

    def _load_funding_history_schema(self):
        if self._funding_history_schema is None:
            path = self.config.schema_path.parent / "funding-history.schema.json"
            with open(path, encoding="utf-8") as fh:
                self._funding_history_schema = json.load(fh)
        return self._funding_history_schema

    def get_funding_history(self, symbol) -> tuple:
        """Selected-symbol settled-history view (Task C / ADR-4).

        Returns ``(http_status, payload)``:
          - 400 ``invalid_symbol``: ``symbol`` missing or malformed.
          - 404 ``symbol_not_found``: well-formed symbol not in the current
            snapshot's eligible rows.
          - 502 ``funding_history_unavailable``: the snapshot itself is
            unavailable, or the public upstream settled-history call failed
            (the failure is NOT cached, matching the snapshot's degrade path).
          - 200: a schema-valid ``public-market-funding-history/v1`` payload.

        The window end is the current snapshot's premium-index time
        (``self._data_time_ms``); the upstream fetch reuses the existing
        per-symbol successful-result 1,800-second cache. The browser never calls
        Binance, no private channel/credential is touched, and there is no
        full-universe prefetch — a non-top-N eligible symbol is fetched on
        demand through the same bounded cache. A successful empty window is
        HTTP 200 ``history_status: "empty"`` and IS cached; it is never confused
        with an upstream failure.
        """
        if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
            return 400, {"error": "invalid_symbol"}
        try:
            snapshot = self.get_snapshot()
        except Exception:
            # Snapshot unavailable (fetch/validation) -> the endpoint cannot
            # resolve symbol eligibility or a window boundary. Treat it as the
            # upstream-unavailable surface (502).
            return 502, {"error": "funding_history_unavailable"}
        if symbol not in {r["symbol"] for r in snapshot["rows"]}:
            return 404, {"error": "symbol_not_found"}
        entries = self._fetch_history_for(symbol, self._data_time_ms)
        if entries is None:
            return 502, {"error": "funding_history_unavailable"}
        history, annualized_7d, annualized_30d, history_status = settle_history_view(
            entries, self._data_time_ms
        )
        payload = {
            "schema_version": FUNDING_HISTORY_SCHEMA_VERSION,
            "symbol": symbol,
            "data_time": snapshot["data_time"],
            "history_status": history_status,
            "funding_history": history,
            "annualized_funding_7d": annualized_7d,
            "annualized_funding_30d": annualized_30d,
        }
        jsonschema.validate(payload, self._load_funding_history_schema())
        return 200, payload

    def request_log(self) -> dict:
        return dict(self.client.request_log)
