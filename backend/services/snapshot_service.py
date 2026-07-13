"""Snapshot service.

Two execution modes (2026-07-history-background-refresh-v1, 10-design §4.6):

* **Offline** (``config.offline=True``): the ONLY synchronous build path. The
  request thread builds from frozen fixtures (zero network) and keeps the 60s
  whole-snapshot cache. This exists so the offline test suite stays
  single-threaded and deterministic.
* **Live** (``config.offline=False``): a single serial background worker owns
  ALL domain-cache writes (``_base_raw``, ``_funding_history_cache``,
  ``_last_private_inputs``) and is the sole publisher of the immutable
  ``PublishedState``. Request threads only read the published state (full
  snapshot / legacy history endpoints) or submit/wait a one-shot
  ``RefreshSymbolCommand`` (symbol-snapshot). They NEVER mutate domain caches or
  publish. The kill switch (``background_refresh_enabled=False``) keeps the
  pure-read behavior with zero upstream fetch: last-good or 503.

Immutable publication: assembly + validation happen in worker-local variables;
only a validated, schema-complete state replaces ``self._published_state`` by
one reference assignment. Readers always see a complete old or new state.
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jsonschema
import referencing

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
    default_view_history_symbols,
    resolve_cost_leg_rate,
    select_borrow_candidates,
    sort_rows,
)
from ..services.private_client import PrivateClient

ELIGIBLE_CONTRACT_TYPES = ("PERPETUAL", "TRADIFI_PERPETUAL")

FUNDING_HISTORY_SCHEMA_VERSION = "public-market-funding-history/v1"
SYMBOL_SNAPSHOT_SCHEMA_VERSION = "public-market-symbol-snapshot/v1"

# Eligible query symbol for the selected-history endpoint: Binance USDⓈ-M
# perpetual symbols are uppercase alphanumerics (e.g. BTCUSDT, 1000SATSUSDT).
# Rejects missing/empty/lower-case/space-injected values as HTTP 400 before the
# snapshot is consulted.
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,40}$")


class SnapshotNotReady(Exception):
    """Raised when a live read arrives before the first base publication.

    The server maps this to HTTP 503 (brief cold-start window, 10-design D7).
    """


@dataclass(frozen=True)
class PublishedState:
    """Immutable, atomically-published snapshot state (10-design §4.1).

    A complete state: ``snapshot`` is the schema-valid full payload,
    ``rows_by_symbol`` is derived from the SAME ``snapshot["rows"]`` list so a
    single-row projection is guaranteed to share the row object and
    ``published_version`` of this publication. Replacing ``self._published_state``
    with a new instance is the only publication step.
    """

    snapshot: dict
    data_time_ms: int
    generated_at: str
    published_version: int
    rows_by_symbol: Dict[str, dict]


class RefreshSymbolCommand:
    """One-shot selected-symbol refresh command (10-design D3 / breakdown §4.3).

    Coalescing key is ``symbol`` (the public/history dimension). Concurrent
    clicks for the same symbol share the SAME command instance and the SAME
    ``deadline_monotonic`` publication gate. The command is discarded once
    completed; a later deliberate click creates a new command.
    """

    __slots__ = (
        "symbol", "deadline_monotonic", "done", "result",
        "error", "refresh_status", "warnings", "published_version",
    )

    def __init__(self, symbol: str, deadline_monotonic: float):
        self.symbol = symbol
        self.deadline_monotonic = deadline_monotonic
        self.done = threading.Event()
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.refresh_status: Optional[str] = None  # "ok" | "partial" | "timeout"
        self.warnings: List[str] = []
        self.published_version: Optional[int] = None


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
        # Offline-only 60s whole-snapshot cache (the sync-build path).
        self._cache: Optional[tuple] = None  # (monotonic, snapshot)
        self._schema = None
        # Dedicated per-symbol successful-result cache for settled deep history
        # (records are immutable -> longer TTL than the 60s snapshot cache, ADR-2).
        # Failed requests are NOT cached so they retry on the next worker tick
        # instead of locking the symbol out for a TTL. Worker-only write.
        self._funding_history_cache: dict = {}  # symbol -> (monotonic, raw entries)
        self._data_time_ms = 0
        self._funding_history_schema = None  # lazily loaded on first endpoint use
        self._symbol_snapshot_schema = None  # lazily loaded on first endpoint use
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

        # ---- live background-worker state (all worker-only writes) ----
        self._published_state: Optional[PublishedState] = None
        self._published_version: int = 0
        self._base_raw: Optional[dict] = None
        self._base_raw_ts: float = 0.0  # monotonic
        self._last_private_inputs: dict = {}  # reuse bundle for click republish
        self._history_cursor: int = 0
        self._command_queue: "queue.Queue[Optional[RefreshSymbolCommand]]" = queue.Queue()
        self._inflight: Dict[str, RefreshSymbolCommand] = {}
        self._inflight_lock = threading.Lock()  # guards ONLY the _inflight dict
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # schema loading
    # ------------------------------------------------------------------
    def _load_schema(self):
        if self._schema is None:
            with open(self.config.schema_path, encoding="utf-8") as fh:
                self._schema = json.load(fh)
        return self._schema

    def _load_funding_history_schema(self):
        if self._funding_history_schema is None:
            path = self.config.schema_path.parent / "funding-history.schema.json"
            with open(path, encoding="utf-8") as fh:
                self._funding_history_schema = json.load(fh)
        return self._funding_history_schema

    def _load_symbol_snapshot_schema(self):
        if self._symbol_snapshot_schema is None:
            path = self.config.schema_path.parent / "symbol-snapshot.schema.json"
            with open(path, encoding="utf-8") as fh:
                schema = json.load(fh)
            # The row property is a cross-file $ref to
            # snapshot.schema.json#/$defs/row. Register the canonical snapshot
            # schema under its $id so the validator can resolve that reference
            # (jsonschema 2020-12 resolves relative $ref against the schema $id).
            with open(self.config.schema_path, encoding="utf-8") as fh:
                snap = json.load(fh)
            registry = referencing.Registry().with_resource(
                snap["$id"], referencing.Resource.from_contents(snap)
            )
            self._symbol_snapshot_schema = jsonschema.Draft202012Validator(
                schema, registry=registry
            )
        return self._symbol_snapshot_schema

    # ------------------------------------------------------------------
    # public reads
    # ------------------------------------------------------------------
    def get_snapshot(self) -> dict:
        """Return the canonical snapshot.

        Offline: synchronous fixture build + 60s cache (the ONLY sync-build
        branch). Live: pure read of the published state — zero upstream fetch.
        Before the first base publication a live read raises
        :class:`SnapshotNotReady` (server maps to 503).
        """
        if self.client.offline:
            now = time.monotonic()
            if self._cache is not None and (now - self._cache[0]) < self.config.cache_ttl_seconds:
                return self._cache[1]
            snapshot = self.build_snapshot()
            jsonschema.validate(instance=snapshot, schema=self._load_schema())
            self._cache = (now, snapshot)
            return snapshot
        # live: zero-upstream pure read of the published state
        state = self._published_state
        if state is not None:
            return state.snapshot
        raise SnapshotNotReady("no published state yet")

    def get_funding_history(self, symbol) -> tuple:
        """Selected-symbol settled-history view — PURE projection (breakdown §8).

        Zero upstream fetch, zero cache write. The legacy endpoint stays for
        contract compatibility; the frontend click flow now uses
        :meth:`get_symbol_snapshot`.

          - 400 ``invalid_symbol``: ``symbol`` missing/malformed.
          - 404 ``symbol_not_found``: well-formed symbol not in the current
            published snapshot's eligible rows.
          - 503 ``snapshot_not_ready``: worker not ready (before first base
            publication, live mode).
          - 200: schema-valid ``public-market-funding-history/v1`` projected
            from the published row; ``history_status`` is ``"available"`` (non-
            empty history) or ``"empty"`` (present but empty).
        """
        if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
            return 400, {"error": "invalid_symbol"}
        if self.client.offline:
            try:
                snapshot = self.get_snapshot()
            except Exception:
                return 503, {"error": "snapshot_not_ready"}
            rows_by_symbol = {r["symbol"]: r for r in snapshot["rows"]}
            data_time = snapshot["data_time"]
            row = rows_by_symbol.get(symbol)
            if row is None:
                return 404, {"error": "symbol_not_found"}
            history = row.get("funding_history", [])
            payload = self._project_funding_history(symbol, data_time, row, history)
            jsonschema.validate(payload, self._load_funding_history_schema())
            return 200, payload
        state = self._published_state
        if state is None:
            return 503, {"error": "snapshot_not_ready"}
        if symbol not in state.rows_by_symbol:
            return 404, {"error": "symbol_not_found"}
        row = state.rows_by_symbol[symbol]
        history = row.get("funding_history", [])
        payload = self._project_funding_history(
            symbol, state.snapshot["data_time"], row, history
        )
        jsonschema.validate(payload, self._load_funding_history_schema())
        return 200, payload

    @staticmethod
    def _project_funding_history(symbol, data_time, row, history) -> dict:
        history_status = "available" if history else "empty"
        return {
            "schema_version": FUNDING_HISTORY_SCHEMA_VERSION,
            "symbol": symbol,
            "data_time": data_time,
            "history_status": history_status,
            "funding_history": history,
            "annualized_funding_7d": row.get("annualized_funding_7d"),
            "annualized_funding_30d": row.get("annualized_funding_30d"),
        }

    def get_symbol_snapshot(self, symbol) -> tuple:
        """Selected-symbol row snapshot (breakdown §9 / 10-design D8).

        Submits one ``RefreshSymbolCommand`` and waits within the bounded
        timeout, then projects the selected row from the LATEST published state
        (same ``published_version`` as the full snapshot, by construction).

          - 400 ``invalid_symbol`` (malformed; validated before command submit).
          - 404 ``symbol_not_found`` (well-formed but not an eligible published row).
          - 503 ``snapshot_not_ready`` (before first base publication, live mode).
          - 200 ``refresh_status`` ``ok``/``partial``/``timeout``.
        """
        if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
            return 400, {"error": "invalid_symbol"}
        if self.client.offline:
            return self._offline_symbol_snapshot(symbol)
        state = self._published_state
        if state is None:
            return 503, {"error": "snapshot_not_ready"}
        if symbol not in state.rows_by_symbol:
            return 404, {"error": "symbol_not_found"}
        cmd: Optional[RefreshSymbolCommand] = None
        if self._worker_running():
            cmd = self.submit_refresh(symbol)
            remaining = cmd.deadline_monotonic - time.monotonic()
            if remaining > 0:
                cmd.done.wait(timeout=remaining)
        latest = self._published_state
        if latest is None or symbol not in latest.rows_by_symbol:
            return 404, {"error": "symbol_not_found"}
        # Refresh-status contract (pre-review repair findings 1 & 4): a command
        # that did not settle within the shared deadline, OR an absent command
        # because no live worker is running, MUST surface as "timeout" — never
        # a fake "ok". The projected row is still the last-good publication.
        if cmd is not None and cmd.refresh_status:
            refresh_status = cmd.refresh_status
            warnings = list(cmd.warnings)
        elif cmd is not None:
            refresh_status = "timeout"
            warnings = list(cmd.warnings) + ["refresh_deadline_exceeded"]
        else:
            refresh_status = "timeout"
            warnings = ["worker_not_running"]
        payload = {
            "schema_version": SYMBOL_SNAPSHOT_SCHEMA_VERSION,
            "symbol": symbol,
            "published_version": latest.published_version,
            "data_time": latest.snapshot["data_time"],
            "generated_at": latest.generated_at,
            "refresh_status": refresh_status,
            "warnings": warnings,
            "row": latest.rows_by_symbol[symbol],
        }
        self._load_symbol_snapshot_schema().validate(payload)
        return 200, payload

    def _offline_symbol_snapshot(self, symbol) -> tuple:
        """Offline: no worker, no click refresh; project the built row directly."""
        try:
            snapshot = self.get_snapshot()
        except Exception:
            return 503, {"error": "snapshot_not_ready"}
        rows_by_symbol = {r["symbol"]: r for r in snapshot["rows"]}
        if symbol not in rows_by_symbol:
            return 404, {"error": "symbol_not_found"}
        payload = {
            "schema_version": SYMBOL_SNAPSHOT_SCHEMA_VERSION,
            "symbol": symbol,
            "published_version": 0,
            "data_time": snapshot["data_time"],
            "generated_at": snapshot["generated_at"],
            "refresh_status": "ok",
            "warnings": [],
            "row": rows_by_symbol[symbol],
        }
        self._load_symbol_snapshot_schema().validate(payload)
        return 200, payload

    # ------------------------------------------------------------------
    # offline synchronous build (the ONLY sync-build path, §4.6)
    # ------------------------------------------------------------------
    def build_snapshot(self) -> dict:
        """Offline synchronous build from frozen fixtures (zero network).

        Live request threads NEVER call this; the worker owns live assembly.
        Existing offline tests call this directly. It delegates the shared
        assembly pipeline to :meth:`_assemble`.
        """
        raw = self.client.fetch_raw()  # offline: frozen fixtures
        snapshot, data_time_ms, _ = self._assemble(raw)
        self._data_time_ms = data_time_ms
        return snapshot

    # ------------------------------------------------------------------
    # shared assembly pipeline (offline build + worker tick/command)
    # ------------------------------------------------------------------
    def _eligible_rows(
        self,
        base_raw: dict,
        *,
        funding_history_overlay: Optional[dict] = None,
        premium_overlay: Optional[dict] = None,
    ) -> tuple:
        """Filter base_raw to eligible rows + build_rows (pure; no HTTP).

        Returns ``(rows, data_time_ms)``. ``premium_overlay`` (selected-symbol
        click) replaces only the overlaid symbol's premium entry; the rest of
        the universe is unchanged. ``funding_history_overlay`` merges cached
        successful history on top of whatever base_raw carries.
        """
        futures_symbols = [
            s
            for s in base_raw["futures_exchange_info"].get("symbols", [])
            if s.get("status") == "TRADING"
            and s.get("contractType") in ELIGIBLE_CONTRACT_TYPES
            and s.get("quoteAsset") == "USDT"
        ]
        premium_by_sym = {p["symbol"]: p for p in base_raw["premium_index"]}
        if premium_overlay:
            for sym, prem in premium_overlay.items():
                if prem:
                    premium_by_sym[sym] = prem
        spot_by_sym = {
            s["symbol"]: s for s in base_raw["spot_exchange_info"].get("symbols", [])
        }
        funding_by_sym = dict(base_raw.get("funding_history_by_sym", {}))
        if funding_history_overlay:
            funding_by_sym.update(funding_history_overlay)
        funding_interval_by_sym = base_raw.get("funding_interval_by_sym", {})
        data_time_ms = max((p.get("time", 0) for p in base_raw["premium_index"]), default=0)
        rows = build_rows(
            futures_symbols,
            premium_by_sym,
            spot_by_sym,
            funding_by_sym,
            funding_interval_by_sym=funding_interval_by_sym,
            t_end_ms=data_time_ms,
        )
        return rows, data_time_ms

    def _assemble(
        self,
        base_raw: dict,
        *,
        funding_history_overlay: Optional[dict] = None,
        premium_overlay: Optional[dict] = None,
        history_warnings: Optional[List[str]] = None,
        forced_overrides: Optional[dict] = None,
        private_reuse: Optional[dict] = None,
    ) -> tuple:
        """Assemble a complete schema-valid snapshot from base_raw + caches.

        Pure pipeline after the (already-fetched) base_raw: build_rows, gather
        private inputs, row assembly, deterministic sort, assemble_snapshot.
        Returns ``(snapshot, data_time_ms, private_inputs)``. The caller (worker)
        validates+publishes; the offline :meth:`build_snapshot` returns the dict
        directly.

        ``forced_overrides`` (selected-symbol click only, breakdown §7): overlays
        the freshly force-TTL'd rate + max-borrowable onto the selected asset so
        its row reflects the click while every other row reuses
        ``private_reuse`` (the last published private bundle).
        """
        rows, data_time_ms = self._eligible_rows(
            base_raw,
            funding_history_overlay=funding_history_overlay,
            premium_overlay=premium_overlay,
        )
        pi = self._gather_private_inputs(
            rows, forced_overrides=forced_overrides, reuse=private_reuse
        )
        classic_ref = pi["classic_ref"]
        cost_leg = pi["cost_leg"]
        portfolio_by_asset = pi["portfolio_by_asset"]
        price_map = pi["price_map"]
        checked_at = pi["checked_at"]
        private_error = pi["private_error"]
        private_channel_status = pi["private_channel_status"]
        rate_probe_assets = pi["rate_probe_assets"]
        borrowability_unprobed_assets = pi["borrowability_unprobed_assets"]

        forced_asset = forced_overrides.get("asset") if forced_overrides else None
        for row in rows:
            base = row.get("base_asset", "")
            daily_borrow_rate = None
            borrow_rate_source = None
            if forced_asset and base == forced_asset:
                # Selected-symbol click: use the freshly forced rate directly.
                daily_borrow_rate = forced_overrides.get("rate")
                borrow_rate_source = forced_overrides.get("source")
            elif base in rate_probe_assets and cost_leg:
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

        cost_leg_available = bool(
            classic_ref is not None and cost_leg and cost_leg.get("chain_hit_tier") is not None
        )
        sort_basis = SORT_BASIS_NET if cost_leg_available else SORT_BASIS_ABS
        rows = sort_rows(rows, sort_basis)

        borrow_validation_summary = {
            "coverage": pi["coverage"],
            "classic_margin_daily_interest_account_available": cost_leg_available,
            "chain_hit_tier": cost_leg.get("chain_hit_tier") if cost_leg else None,
            "chain_hit_source": cost_leg.get("chain_hit_source") if cost_leg else None,
        }

        generated_at, source_sample_id = self._generated_at_source_sample_id()
        fetch_warnings = list(base_raw.get("warnings", []))
        warnings = (
            fetch_warnings
            + pi["account_warnings"]
            + list(history_warnings or [])
        )
        snapshot = assemble_snapshot(
            rows,
            generated_at=generated_at,
            data_time=iso_from_ms(data_time_ms),
            source_sample_id=source_sample_id,
            private_channel_status=private_channel_status,
            sort_basis=sort_basis,
            private_account=pi["private_account"],
            borrow_validation_summary=borrow_validation_summary,
            extra_warnings=warnings,
        )
        return snapshot, data_time_ms, pi

    def _generated_at_source_sample_id(self) -> tuple:
        if self.client.offline:
            return FROZEN_GENERATED_AT, FROZEN_SOURCE_SAMPLE_ID
        now_utc = datetime.now(timezone.utc)
        return (
            now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            now_utc.strftime("%Y%m%dT%H%M%SZ"),
        )

    def _gather_private_inputs(
        self,
        rows: List[dict],
        *,
        forced_overrides: Optional[dict] = None,
        reuse: Optional[dict] = None,
    ) -> dict:
        """Build or reuse the private channel input bundle for assembly.

        Scheduled tick (``forced_overrides`` None): normal TTL-governed fetch of
        classic_ref, cost-leg chain, account panels, maxBorrowable, price map.

        Click republish (``forced_overrides`` set, §7/D6): REUSE
        ``reuse`` (the last published bundle) for classic_ref, price_map,
        private_account, account_warnings, checked_at, and the non-selected
        assets' portfolio + cost-leg rates; overlay ONLY the selected asset's
        forced max-borrowable onto ``portfolio_by_asset``. The selected asset's
        forced RATE is applied in :meth:`_assemble` row assembly, not here. This
        NEVER re-enters fetch_unified_balances / fetch_um_positions /
        fetch_spot_balances (no balances/positions/valuation on the click path).
        """
        click = forced_overrides is not None
        forced_asset = forced_overrides.get("asset") if forced_overrides else None

        # classic_ref (1h TTL): reuse on click, fresh on scheduled.
        if click and reuse and reuse.get("classic_ref") is not None:
            classic_ref = reuse["classic_ref"]
        else:
            classic_ref = self._private.fetch_classic_reference()
        private_channel_status = "enabled" if classic_ref is not None else "disabled"
        private_error = self._private.last_error if classic_ref is None else None

        probe = select_borrow_candidates(rows, self.config.borrow_check_max_calls)
        rate_probe_assets = probe["rate_probe_assets"]
        borrowability_probe_assets = probe["borrowability_probe_assets"]
        borrowability_unprobed_assets = probe["borrowability_unprobed_assets"]
        coverage = probe["coverage"]

        # cost-leg chain (1h TTL): reuse on click (selected asset's rate is
        # overlaid in row assembly via forced_overrides), fresh on scheduled.
        if click and reuse and reuse.get("cost_leg") is not None:
            cost_leg = reuse["cost_leg"]
        else:
            cost_leg = self._private.fetch_cost_leg_chain(rate_probe_assets)

        # price_map (public, full): reuse on click, fresh on scheduled. Disabled
        # channel -> empty (never consumed).
        if click and reuse and reuse.get("price_map") is not None:
            price_map = reuse["price_map"]
        elif classic_ref is None:
            price_map = {}
        else:
            price_map = self.client.fetch_ticker_price_map()

        # private_account block: reuse on click (NEVER re-fetch balances/
        # positions/valuation on the click path), fresh on scheduled.
        if click and reuse and reuse.get("private_account") is not None:
            private_account = reuse["private_account"]
            account_warnings = list(reuse.get("account_warnings", []))
            checked_at = reuse.get("checked_at")
        elif classic_ref is None:
            unified = um_positions = spot_balances = None
            checked_at = None
            private_account, account_warnings = assemble_private_account(
                None, None, None, {}, checked_at=None, error=private_error,
            )
        else:
            unified = self._private.fetch_unified_balances()
            um_positions = self._private.fetch_um_positions()
            spot_balances = self._private.fetch_spot_balances()
            checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            private_account, account_warnings = assemble_private_account(
                unified, spot_balances, um_positions, price_map,
                checked_at=checked_at, error=private_error,
            )

        # portfolio_by_asset (maxBorrowable, 1h TTL): reuse on click and overlay
        # ONLY the selected asset's forced value; fresh full probe on scheduled.
        if click and reuse and reuse.get("portfolio_by_asset") is not None:
            portfolio_by_asset = dict(reuse["portfolio_by_asset"])
            if forced_asset is not None:
                forced_max = (forced_overrides or {}).get("max") or {
                    "max_borrowable": None,
                    "borrow_limit": None,
                    "error_code": None,
                }
                portfolio_by_asset[forced_asset] = forced_max
        else:
            portfolio_by_asset = {}
            for asset in borrowability_probe_assets:
                if asset in portfolio_by_asset:
                    continue
                res = self._private.fetch_max_borrowable(asset)
                portfolio_by_asset[asset] = res or {
                    "max_borrowable": None,
                    "borrow_limit": None,
                    "error_code": None,
                }

        return {
            "classic_ref": classic_ref,
            "cost_leg": cost_leg,
            "portfolio_by_asset": portfolio_by_asset,
            "price_map": price_map,
            "private_account": private_account,
            "account_warnings": account_warnings,
            "checked_at": checked_at,
            "private_channel_status": private_channel_status,
            "private_error": private_error,
            "rate_probe_assets": rate_probe_assets,
            "borrowability_probe_assets": borrowability_probe_assets,
            "borrowability_unprobed_assets": borrowability_unprobed_assets,
            "coverage": coverage,
        }

    def _all_valid_history(self) -> dict:
        """Shallow copy of every unexpired successful funding-history entry
        (10-design D4). Expired/failed entries are skipped. Eligibility (still a
        current USDT perpetual) is rechecked at build_rows time.
        """
        now = time.monotonic()
        ttl = self.config.funding_history_cache_ttl_seconds
        out: Dict[str, list] = {}
        for sym, entry in self._funding_history_cache.items():
            if entry is None:
                continue
            ts, entries = entry
            if (now - ts) < ttl:
                out[sym] = entries
        return out

    def _fetch_history_for(self, symbol: str, t_end_ms: int) -> Optional[List[dict]]:
        """Settled deep history with a per-symbol successful-result cache.

        Worker-only write. Returns the raw ``/fapi/v1/fundingRate`` entries for
        the inclusive ``[t_end - 30d, t_end]`` window, or ``None`` on failure.
        The failure is NOT cached so the next worker tick retries.
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

    def _history_is_fresh(self, symbol: str) -> bool:
        now = time.monotonic()
        cached = self._funding_history_cache.get(symbol)
        return cached is not None and (
            now - cached[0] < self.config.funding_history_cache_ttl_seconds
        )

    # ------------------------------------------------------------------
    # worker lifecycle (10-design D7 / breakdown §4.4-4.6, §5)
    # ------------------------------------------------------------------
    def start_worker(self) -> None:
        """Idempotent. No-op offline or when the kill switch is off."""
        if self.client.offline or not self.config.background_refresh_enabled:
            return
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="snapshot-worker", daemon=True
        )
        self._worker_thread.start()

    def stop_worker(self) -> None:
        if self._worker_thread is None:
            return
        self._stop_event.set()
        # wake the loop if blocked on queue.get; None is the sentinel.
        self._command_queue.put(None)
        self._worker_thread.join(timeout=self.config.symbol_refresh_timeout_seconds + 5)
        self._worker_thread = None

    def _worker_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _worker_loop(self) -> None:
        # bootstrap: immediate base refresh + publication (no sleep).
        try:
            self._scheduled_tick()
        except Exception:
            pass  # worker must not die; the next tick retries
        while not self._stop_event.is_set():
            try:
                cmd = self._command_queue.get(timeout=self.config.background_tick_seconds)
            except queue.Empty:
                cmd = None
            if self._stop_event.is_set():
                break
            if cmd is not None:
                try:
                    self._handle_refresh_command(cmd)
                except Exception as exc:  # never let one command kill the worker
                    if not cmd.done.is_set():
                        cmd.refresh_status = "timeout"
                        cmd.error = f"refresh_internal_error:{exc}"
                        cmd.done.set()
                        self._release_inflight(cmd)
            else:
                try:
                    self._scheduled_tick()
                except Exception:
                    pass

    def _scheduled_tick(self) -> None:
        """Base refresh (age >= 60s) + <=10 default-view history sweep + publish."""
        now = time.monotonic()
        if (
            self._base_raw is None
            or (now - self._base_raw_ts) >= self.config.cache_ttl_seconds
        ):
            self._base_raw = self.client.fetch_raw()
            self._base_raw_ts = time.monotonic()
        base_raw = self._base_raw
        if base_raw is None:
            return
        rows_preview, data_time_ms = self._eligible_rows(base_raw)
        self._data_time_ms = data_time_ms
        candidates = default_view_history_symbols(rows_preview)
        history_warnings = self._sweep_history(candidates, data_time_ms)
        funding_overlay = self._all_valid_history()
        snapshot, _, pi = self._assemble(
            base_raw,
            funding_history_overlay=funding_overlay,
            history_warnings=history_warnings,
        )
        # Validate BEFORE publish (BK-6): a validation failure must leave the
        # published state and _last_private_inputs untouched.
        self._validate(snapshot)
        self._publish_validated(snapshot, data_time_ms, pi)

    def _sweep_history(self, candidates: List[str], data_time_ms: int) -> List[str]:
        """Refresh up to ``history_sweep_batch_size`` missing/expired default-set
        histories, advancing a stable cursor on the candidate snapshot list
        (10-design D2). Failures append a warning and are NOT cached.
        """
        history_warnings: List[str] = []
        if not candidates:
            self._history_cursor = 0
            return history_warnings
        batch_size = self.config.history_sweep_batch_size
        n = len(candidates)
        cursor = self._history_cursor % n
        served = 0
        while served < min(batch_size, n):
            sym = candidates[cursor]
            if not self._history_is_fresh(sym):
                entries = self._fetch_history_for(sym, data_time_ms)
                if entries is None:
                    history_warnings.append(f"funding_history_unavailable:{sym}")
            cursor = (cursor + 1) % n
            served += 1
        self._history_cursor = cursor
        return history_warnings

    def _handle_refresh_command(self, cmd: RefreshSymbolCommand) -> None:
        """Selected-symbol one-shot refresh (breakdown §6/§7/§10).

        Stages all upstream I/O results locally, then re-checks the shared
        deadline gate BEFORE any domain-cache commit or publication. On expiry
        the worker may have completed I/O (incl. updating the private transport
        cache), but commits no history/domain-cache change and publishes nothing.
        """
        symbol = cmd.symbol
        warnings: List[str] = []
        try:
            # Entry deadline gate (pre-review repair finding 2): a command that
            # already expired while queued starts NO new upstream I/O. Frozen
            # rule — expired-before-start -> timeout, zero fetches, no publish.
            if time.monotonic() >= cmd.deadline_monotonic:
                cmd.refresh_status = "timeout"
                cmd.warnings = [f"refresh_command_expired:{symbol}"]
                cmd.done.set()
                return

            base_raw = self._base_raw
            if base_raw is None:
                # Cold path (pre-review repair finding 6): the click path has NO
                # full-universe fetch_raw() exception, even defensively. Complete
                # as timeout with a diagnostic warning, zero upstream I/O.
                cmd.refresh_status = "timeout"
                cmd.error = "base_not_ready"
                cmd.warnings = [f"base_raw_unavailable:{symbol}"]
                cmd.done.set()
                return
            rows_preview, data_time_ms = self._eligible_rows(base_raw)
            eligible_symbols = {r["symbol"] for r in rows_preview}
            if symbol not in eligible_symbols:
                cmd.refresh_status = "timeout"
                cmd.error = "symbol_not_found"
                cmd.done.set()
                self._release_inflight(cmd)
                return
            base_asset = next(
                r["base_asset"] for r in rows_preview if r["symbol"] == symbol
            )

            # ---- I/O phase: results staged locally, NO domain commit yet ----
            premium_overlay: dict = {}
            try:
                prem = self.client.fetch_premium_index_for(symbol)
                if prem:
                    premium_overlay[symbol] = prem
            except Exception:
                warnings.append(f"premium_refresh_failed:{symbol}")

            history_entries: Optional[list] = None
            try:
                start_ms = int(data_time_ms) - 30 * 86_400_000
                history_entries = self.client.fetch_funding_rate(
                    symbol,
                    start_time_ms=start_ms,
                    end_time_ms=int(data_time_ms),
                    limit=1000,
                )
            except Exception:
                history_entries = None
                warnings.append(f"funding_history_unavailable:{symbol}")

            # Selected-asset force-TTL signed reads (breakdown §7). These fire
            # fresh signed GETs through the single HMAC exit; the private
            # transport cache (_cache) is updated by _cached_get, which is
            # transport-layer caching and NOT domain publication (§10).
            forced_rate: Optional[str] = None
            forced_source: Optional[str] = None
            forced_max: Optional[dict] = None
            if base_asset:
                try:
                    forced_chain = self._private.fetch_cost_leg_chain(
                        [base_asset], force=True
                    )
                    if forced_chain:
                        forced_source = forced_chain.get("chain_hit_source")
                        forced_rate = resolve_cost_leg_rate(base_asset, forced_chain)
                except Exception:
                    warnings.append(f"borrow_rate_refresh_failed:{base_asset}")
                try:
                    forced_max = self._private.fetch_max_borrowable(
                        base_asset, force=True
                    )
                except Exception:
                    warnings.append(f"max_borrowable_refresh_failed:{base_asset}")
                    forced_max = None

            # ---- DEADLINE GATE: after I/O, before domain commit / publish ----
            if time.monotonic() >= cmd.deadline_monotonic:
                cmd.refresh_status = "timeout"
                cmd.warnings = warnings
                cmd.done.set()
                self._release_inflight(cmd)
                return

            forced_overrides = {
                "asset": base_asset,
                "rate": forced_rate,
                "source": forced_source,
                "max": forced_max,
            }
            # Build the history overlay WITHOUT writing the domain cache first:
            # inject the freshly fetched history into the in-memory overlay so
            # _assemble sees it, but defer the _funding_history_cache commit until
            # AFTER the post-assemble deadline gate (pre-review repair finding 3).
            funding_overlay = self._all_valid_history()
            if history_entries is not None:
                funding_overlay[symbol] = history_entries
            try:
                snapshot, _, pi = self._assemble(
                    base_raw,
                    funding_history_overlay=funding_overlay,
                    premium_overlay=premium_overlay or None,
                    history_warnings=warnings,
                    forced_overrides=forced_overrides,
                    private_reuse=self._last_private_inputs or None,
                )
                # Post-assemble deadline gate (finding 3): if assembly crossed the
                # deadline, commit NOTHING — not the history cache, not
                # _last_private_inputs, not PublishedState. Keep the old state.
                if time.monotonic() >= cmd.deadline_monotonic:
                    cmd.refresh_status = "timeout"
                    cmd.error = "assemble_crossed_deadline"
                    cmd.warnings = warnings
                    cmd.done.set()
                    return
                # Validate BEFORE any domain commit (BK-6): a schema validation
                # failure must leave _funding_history_cache / _last_private_inputs
                # / PublishedState all unchanged. Raises -> except below ->
                # refresh_status="timeout" with no commit / publish.
                self._validate(snapshot)
                # Final deadline gate (BK-7): _validate itself may consume time,
                # so a snapshot that entered validation in-window can return
                # out-of-window. Re-confirm the deadline AFTER validation returns
                # but BEFORE any domain-cache commit / publish. If it expired,
                # commit NOTHING — history cache / _last_private_inputs /
                # PublishedState all stay at the last-good values.
                if time.monotonic() >= cmd.deadline_monotonic:
                    cmd.refresh_status = "timeout"
                    cmd.error = "validation_crossed_deadline"
                    cmd.warnings = warnings
                    cmd.done.set()
                    return
                # ---- commit domain cache: history success only (worker-only) ----
                if history_entries is not None:
                    self._funding_history_cache[symbol] = (
                        time.monotonic(),
                        history_entries,
                    )
                self._publish_validated(snapshot, data_time_ms, pi)
                cmd.refresh_status = "partial" if warnings else "ok"
                cmd.published_version = self._published_version
            except Exception as exc:
                # validation/assembly failure -> do NOT publish; last state stays.
                cmd.refresh_status = "timeout"
                cmd.error = f"assemble_failed:{exc}"
            cmd.warnings = warnings
            cmd.done.set()
        except Exception as exc:
            cmd.refresh_status = "timeout"
            cmd.error = f"refresh_error:{exc}"
            cmd.warnings = warnings
            if not cmd.done.is_set():
                cmd.done.set()
        finally:
            self._release_inflight(cmd)

    def _validate(self, snapshot: dict) -> None:
        """Validate ``snapshot`` against the canonical schema; raise on failure.

        Callers MUST invoke this BEFORE any domain-cache commit (history cache,
        ``_last_private_inputs``) so that a validation failure leaves all of
        those untouched (pre-review atomicity repair BK-6).
        """
        jsonschema.validate(instance=snapshot, schema=self._load_schema())

    def _publish_validated(
        self, snapshot: dict, data_time_ms: int, private_inputs: dict
    ) -> None:
        """Atomically replace the published state (one ref swap).

        The caller MUST have validated ``snapshot`` via :meth:`_validate` BEFORE
        any domain-cache commit; this helper performs no validation (BK-6: avoid
        double expensive validation, keep validation ahead of all commits).
        """
        self._published_version += 1
        rows_by_symbol = {r["symbol"]: r for r in snapshot["rows"]}
        self._published_state = PublishedState(
            snapshot=snapshot,
            data_time_ms=data_time_ms,
            generated_at=snapshot["generated_at"],
            published_version=self._published_version,
            rows_by_symbol=rows_by_symbol,
        )
        self._last_private_inputs = private_inputs
        self._data_time_ms = data_time_ms

    # ------------------------------------------------------------------
    # command queue / coalescing (breakdown §4.3)
    # ------------------------------------------------------------------
    def submit_refresh(self, symbol: str) -> RefreshSymbolCommand:
        """Submit (or coalesce) a one-shot refresh command for ``symbol``.

        Concurrent clicks for the same symbol share the SAME command and the
        SAME shared ``deadline_monotonic`` publication gate (bounded dedup, not
        retained interest). The merge key is ``symbol`` (public/history
        dimension), distinct from the private cache's base-asset dimension.
        """
        with self._inflight_lock:
            existing = self._inflight.get(symbol)
            if existing is not None:
                return existing
            deadline = time.monotonic() + self.config.symbol_refresh_timeout_seconds
            cmd = RefreshSymbolCommand(symbol, deadline)
            self._inflight[symbol] = cmd
        self._command_queue.put(cmd)
        return cmd

    def _release_inflight(self, cmd: RefreshSymbolCommand) -> None:
        with self._inflight_lock:
            if self._inflight.get(cmd.symbol) is cmd:
                del self._inflight[cmd.symbol]

    # ------------------------------------------------------------------
    # diagnostics
    # ------------------------------------------------------------------
    def request_log(self) -> dict:
        return dict(self.client.request_log)
