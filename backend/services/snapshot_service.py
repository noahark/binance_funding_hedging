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
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import jsonschema
import referencing

from ..adapters.binance_public import BinancePublicClient
from ..config import GROUP_B_REFRESH_SECONDS, Config, FROZEN_GENERATED_AT, FROZEN_SOURCE_SAMPLE_ID
from ..domain.normalize import iso_from_ms
from ..domain.snapshot import (
    SORT_BASIS_ABS,
    SORT_BASIS_NET,
    assemble_borrow_validation,
    assemble_private_account,
    assemble_snapshot,
    build_opening_quotes,
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

# History refresh-ahead headroom (2026-07-history-refresh-ahead-v1, 10-design):
# the funding-history component becomes refresh-due this many seconds before its
# hard publication expiry, so a cursor visit can warm a fresh entry while the
# prior entry is still publishable. Publication expiry stays at the full TTL.
HISTORY_REFRESH_AHEAD_SECONDS = 300

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
        # Stage 2026-07-cache-refresh-scheduler-v2: three-cadence business caches.
        # _global_source_cache[source_id] = (updated_monotonic, value); each
        # source_id carries its OWN due timestamp (CC-1: one source's success/
        # failure never suppresses another's retry). _borrow_rate_cache[asset] =
        # (ts, raw_value, source) and _max_borrowable_cache[asset] = (ts, value)
        # are Group C component caches (FR-7: history / borrow-rate / max-
        # borrowable tracked independently). _coverage_attempted tracks the
        # cursor-attempt coverage ledger (CC-3). All worker-only writes; every
        # timestamp advances only after a successful result (FR-2).
        self._global_source_cache: Dict[str, tuple] = {}
        self._borrow_rate_cache: Dict[str, tuple] = {}
        self._max_borrowable_cache: Dict[str, tuple] = {}
        self._coverage_attempted: set = set()
        # Wall-clock timestamp of the most recent successful Group A private
        # account-panel refresh (unified/um/spot). Cache-only assembly reads it
        # for ``assemble_private_account(checked_at=...)`` instead of stamping
        # ``now`` on every tick (the panels are read from _global_source_cache).
        self._account_checked_at: Optional[str] = None
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
        timeout, then projects the selected row from the LATEST published
        state (a new publication only when the command settles in-window;
        otherwise the previously published, last-good, state). The full
        snapshot wire payload carries no ``published_version`` field, so this
        value gives no client-verifiable cross-request equality guarantee.

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

    def _attach_opening_quotes(self, rows: List[dict]) -> None:
        """Project the ``book_ticker_pair`` cache onto each row's
        ``opening_quotes`` (2026-07-bookticker-open-columns-v1, 10-design §D2/D4).

        Public and always-on; independent of the private channel. The cache age
        is recomputed from ``time.monotonic()`` EVERY assembly, so a pair that
        crosses ``2 * cache_ttl_seconds`` flips to ``stale`` on the next assembly
        without waiting for another fetch failure. Joins use the row's resolved
        leg symbols: futures quote by ``row.futures.symbol``, spot quote by the
        already-resolved ``row.spot.symbol`` (bStock reuses its B-suffix alias,
        e.g. futures ``TSLAUSDT`` -> spot ``TSLABUSDT``); a ``None`` spot leg
        yields ``incomplete`` without guessing a substitute asset.
        """
        ttl = self.config.cache_ttl_seconds
        now = time.monotonic()
        entry = self._global_source_cache.get("book_ticker_pair")
        if entry is None:
            usable = False
            updated_at = None
            spot_map: Dict[str, dict] = {}
            futures_map: Dict[str, dict] = {}
        else:
            success_ts, pair = entry
            usable = (now - success_ts) < 2 * ttl
            updated_at = pair.get("updated_at")
            spot_map = pair.get("spot") or {}
            futures_map = pair.get("futures") or {}
        for row in rows:
            fut_sym = (row.get("futures") or {}).get("symbol")
            spot_sym = (row.get("spot") or {}).get("symbol")
            futures_quote = futures_map.get(fut_sym) if fut_sym else None
            spot_quote = spot_map.get(spot_sym) if spot_sym else None
            row["opening_quotes"] = build_opening_quotes(
                spot_quote,
                futures_quote,
                usable=usable,
                updated_at=updated_at,
            )

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
        resolved_rates = pi.get("resolved_rates", {})
        for row in rows:
            base = row.get("base_asset", "")
            daily_borrow_rate = None
            borrow_rate_source = None
            if forced_asset and base == forced_asset:
                # Selected-symbol click: use the freshly forced rate directly.
                daily_borrow_rate = forced_overrides.get("rate")
                borrow_rate_source = forced_overrides.get("source")
            elif base in rate_probe_assets:
                # S5: per-asset resolved rate (cache-only on the scheduled path,
                # reused on the click path); fall back to a whole cost_leg only
                # when no per-asset resolution is available (CC-4: the next_hourly
                # value is normalized exactly once via resolve_cost_leg_rate).
                resolved = resolved_rates.get(base)
                if resolved is not None:
                    daily_borrow_rate, borrow_rate_source = resolved
                elif cost_leg:
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

        # opening_quotes (2026-07-bookticker-open-columns-v1): project the
        # book_ticker_pair cache onto every row. Public + always-on; recomputed
        # every assembly from the monotonic cache age (stale is a projection,
        # not a fetch-failure side effect). Independent of the private channel.
        self._attach_opening_quotes(rows)

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

        Scheduled tick (``forced_overrides`` None, S3/S8): CACHE-ONLY. Reads
        classic_ref / account_info / account panels / price_map from
        _global_source_cache, computes the FR-4 homepage borrow universe +
        cursor-attempt coverage (CC-3) + per-asset resolved borrow rates (S5),
        and synthesizes the aggregate chain diagnostic. It NEVER calls
        fetch_cost_leg_chain(rate_probe_assets) or a top-50 max-borrowable loop
        (FR-3) — those scheduled fetches live in _refresh_due_sources /
        _sweep_group_c.

        Click republish (``forced_overrides`` set, §7/D6/S9): REUSE
        ``reuse`` (the last published bundle) for classic_ref, price_map,
        private_account, account_warnings, checked_at, resolved_rates, and the
        non-selected assets' portfolio + cost-leg; overlay ONLY the selected
        asset's forced max-borrowable onto ``portfolio_by_asset``. The selected
        asset's forced RATE is applied in :meth:`_assemble` row assembly. This
        NEVER re-enters fetch_unified_balances / fetch_um_positions /
        fetch_spot_balances (no balances/positions/valuation on the click path).
        """
        if forced_overrides is not None:
            return self._gather_private_inputs_click(rows, forced_overrides, reuse)
        return self._gather_private_inputs_scheduled(rows)

    def _gather_private_inputs_click(
        self,
        rows: List[dict],
        forced_overrides: dict,
        reuse: Optional[dict],
    ) -> dict:
        """Click republish path (S9): reuse the last published bundle and overlay
        only the selected asset's forced max-borrowable. Unchanged from the
        pre-v2 click path except ``resolved_rates`` is reused too, so per-asset
        rate resolution stays consistent with the last scheduled publication."""
        forced_asset = forced_overrides.get("asset")

        # classic_ref: reuse on click.
        if reuse and reuse.get("classic_ref") is not None:
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

        # cost-leg chain: reuse on click (selected asset's rate is overlaid in
        # row assembly via forced_overrides).
        if reuse and reuse.get("cost_leg") is not None:
            cost_leg = reuse["cost_leg"]
        else:
            cost_leg = self._private.fetch_cost_leg_chain(rate_probe_assets)

        # price_map: reuse on click. Disabled channel -> empty.
        if reuse and reuse.get("price_map") is not None:
            price_map = reuse["price_map"]
        elif classic_ref is None:
            price_map = {}
        else:
            price_map = self.client.fetch_ticker_price_map()

        # private_account block: reuse on click (NEVER re-fetch balances/
        # positions/valuation on the click path).
        if reuse and reuse.get("private_account") is not None:
            private_account = reuse["private_account"]
            account_warnings = list(reuse.get("account_warnings", []))
            checked_at = reuse.get("checked_at")
        elif classic_ref is None:
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

        # portfolio_by_asset: reuse on click and overlay ONLY the selected
        # asset's forced value.
        if reuse and reuse.get("portfolio_by_asset") is not None:
            portfolio_by_asset = dict(reuse["portfolio_by_asset"])
            if forced_asset is not None:
                forced_max = forced_overrides.get("max") or {
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

        resolved_rates = dict(reuse.get("resolved_rates", {})) if reuse else {}
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
            "resolved_rates": resolved_rates,
        }

    def _gather_private_inputs_scheduled(self, rows: List[dict]) -> dict:
        """Scheduled cache-only assembly path (S3/S5/S7/S8). Reads every private
        input from the worker-owned business caches and performs NO upstream
        I/O (FR-3). Computes the FR-4 homepage borrow universe, cursor-attempt
        coverage (CC-3), per-asset resolved borrow rates (S5), and the aggregate
        chain diagnostic (S8)."""
        classic_ref = self._cached_source_value("classic_reference")
        private_channel_status = "enabled" if classic_ref is not None else "disabled"
        if classic_ref is None:
            # Live scheduled ticks already set last_error via _refresh_due_sources'
            # fetch_classic_reference call; the offline sync build (build_snapshot)
            # never runs that, so last_error stays at its init None. Fall back to
            # the canonical disabled sentinel when the channel is offline or
            # switched off (preserves the pre-v2 offline borrow-error contract).
            private_error = self._private.last_error
            if private_error is None and (
                self.client.offline or not self.config.private_channel_enabled
            ):
                private_error = "private_channel_disabled"
        else:
            private_error = None

        # FR-4 homepage borrow universe replaces select_borrow_candidates' top-50
        universe = self._homepage_borrow_universe(rows, classic_ref)

        # Cursor-attempt coverage (CC-3 / INV-4). The coverage ledger is pruned
        # to the CURRENT universe: an asset that exits (e.g. its funding rate
        # crossed the -0.00030000 boundary) is dropped, so a later re-entry
        # starts unattempted (probed only after a real scheduled max-borrowable
        # attempt). Out-of-universe assets are not counted at all.
        universe_set = set(universe)
        self._coverage_attempted &= universe_set
        probed = [a for a in universe if a in self._coverage_attempted]
        skipped = [a for a in universe if a not in self._coverage_attempted]
        coverage = {
            "probed": len(probed),
            "skipped": len(skipped),
            "reason": "rate_limit_budget" if skipped else None,
        }

        # account VIP level (Group B account_info) for tier ③ resolution.
        account_info = self._cached_source_value("account_info") or {}
        vip_raw = account_info.get("vipLevel") if account_info else None
        vip_level = str(vip_raw) if vip_raw is not None else None

        # Per-asset resolved borrow rates (S5); CC-4 normalizes next_hourly x24
        # exactly once inside resolve_cost_leg_rate.
        resolved_rates: Dict[str, tuple] = {}
        for base in universe:
            resolved = self._resolve_borrow_rate_for_asset(base, classic_ref, vip_level)
            if resolved is not None:
                resolved_rates[base] = resolved

        cost_leg = self._synthesize_cost_leg(resolved_rates, vip_level)

        if classic_ref is None:
            price_map = {}
            checked_at = None
            private_account, account_warnings = assemble_private_account(
                None, None, None, {}, checked_at=None, error=private_error,
            )
            portfolio_by_asset = {}
        else:
            price_map = self._cached_source_value("price_map", {})
            unified = self._cached_source_value("unified_balances")
            um_positions = self._cached_source_value("um_positions")
            spot_balances = self._cached_source_value("spot_balances")
            checked_at = self._account_checked_at
            private_account, account_warnings = assemble_private_account(
                unified, spot_balances, um_positions, price_map,
                checked_at=checked_at, error=private_error,
            )
            # portfolio_by_asset from the per-asset max-borrowable cache; only
            # cursor-attempted universe assets are present (the rest render
            # borrowability_truncated -> borrowability_not_probed, §4.3).
            portfolio_by_asset = {
                base: self._max_borrowable_cache[base][1]
                for base in universe
                if base in self._max_borrowable_cache
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
            "rate_probe_assets": list(universe),
            "borrowability_probe_assets": probed,
            "borrowability_unprobed_assets": set(skipped),
            "coverage": coverage,
            "resolved_rates": resolved_rates,
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
        # Refresh-ahead reuse guard: the cache is reused only until the refresh
        # threshold (publication TTL - headroom), not the full publication TTL,
        # so a cursor visit at 1500s performs real upstream I/O (10-design).
        ttl = self._history_refresh_ttl()
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

    def _history_refresh_ttl(self) -> int:
        """Refresh-fresh threshold for the history component: the configured
        publication TTL minus the refresh-ahead headroom, clamped at 0. This is
        strictly smaller than the publication expiry, so a cursor visit can warm
        a fresh entry before the prior entry stops being publishable
        (2026-07-history-refresh-ahead-v1, 10-design / 11-adr)."""
        return max(
            0,
            self.config.funding_history_cache_ttl_seconds - HISTORY_REFRESH_AHEAD_SECONDS,
        )

    def _history_is_fresh(self, symbol: str) -> bool:
        now = time.monotonic()
        cached = self._funding_history_cache.get(symbol)
        return cached is not None and (
            now - cached[0] < self._history_refresh_ttl()
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

    # borrow-rate source priority for the aggregate chain diagnostic (S5/S8).
    _BORROW_SOURCE_TIER = {
        "next_hourly": 1,
        "rate_history": 2,
        "cross_margin_tier": 3,
        "vip0_reference": 4,
    }

    def _scheduled_tick(self) -> None:
        """Three-cadence refresh + cache-only assembly + atomic publish.

        Group A (60s) / Group B (1800s) sources are refreshed independently
        (CC-1: each source_id owns its own due timestamp); then at most 10
        Group C homepage symbols are swept (history for every candidate;
        borrow-rate + max-borrowable only for the FR-4 universe). Assembly is
        cache-only: it reads _global_source_cache + the per-asset caches and
        never calls the all-row fetch_cost_leg_chain / top-50 max-borrowable
        probe (FR-3).
        """
        now = time.monotonic()
        self._refresh_due_sources(now)
        base_raw = self._compose_base_raw()
        if base_raw is None:
            return
        # Preserve _base_raw / _base_raw_ts for the manual click path and the
        # legacy _base_raw contract (selected-symbol refresh reads _base_raw).
        self._base_raw = base_raw
        self._base_raw_ts = now
        rows_preview, data_time_ms = self._eligible_rows(base_raw)
        self._data_time_ms = data_time_ms
        candidates = default_view_history_symbols(rows_preview)
        rows_by_symbol = {r["symbol"]: r for r in rows_preview}
        history_warnings = self._sweep_group_c(
            candidates, rows_by_symbol, data_time_ms, now
        )
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

    def _source_due(self, source_id: str, now: float, ttl: int) -> bool:
        """True when ``source_id`` is missing or its successful timestamp is
        age >= ``ttl`` (CC-1: every source_id owns its own due)."""
        entry = self._global_source_cache.get(source_id)
        return entry is None or (now - entry[0]) >= ttl

    def _cached_source_value(self, source_id: str, default: Any = None) -> Any:
        entry = self._global_source_cache.get(source_id)
        return entry[1] if entry is not None else default

    def _refresh_due_sources(self, now: float) -> None:
        """Refresh due Group A/B sources into _global_source_cache (worker-only).

        Each source_id is independent (CC-1): one source's failure never
        suppresses another's retry, and one source's success never forces a
        still-fresh source to re-fetch. Timestamps advance only on success
        (FR-2). Legacy stub clients without the split public seams fall back to
        a single fetch_raw() that serves both public groups (keeps the legacy
        single-timestamp bootstrap contract for the existing endpoint tests).
        """
        ttl_a = self.config.cache_ttl_seconds
        has_seams = hasattr(self.client, "fetch_premium_index") and hasattr(
            self.client, "fetch_exchange_info_group_b"
        )
        # ---- public sources ----
        if has_seams:
            if self._source_due("premium_index", now, ttl_a):
                try:
                    value = self.client.fetch_premium_index()
                except (urllib.error.URLError, OSError, ValueError):
                    value = None
                if value is not None:
                    self._global_source_cache["premium_index"] = (
                        time.monotonic(), value,
                    )
            if self._source_due("group_b_public", now, GROUP_B_REFRESH_SECONDS):
                try:
                    value = self.client.fetch_exchange_info_group_b()
                except (urllib.error.URLError, OSError, ValueError):
                    value = None
                if value is not None:
                    self._global_source_cache["group_b_public"] = (
                        time.monotonic(), value,
                    )
        elif self._source_due("premium_index", now, ttl_a) or self._source_due(
            "group_b_public", now, GROUP_B_REFRESH_SECONDS
        ):
            # Legacy fallback: one fetch_raw() serves both public groups (the
            # stub has no split seams). Gated by the faster premium cadence so
            # the existing endpoint tests keep their single-timestamp bootstrap.
            try:
                raw = self.client.fetch_raw()
            except (urllib.error.URLError, OSError, ValueError):
                raw = None
            if raw is not None:
                completed = time.monotonic()
                self._global_source_cache["premium_index"] = (
                    completed, raw["premium_index"],
                )
                self._global_source_cache["group_b_public"] = (
                    completed,
                    {
                        "futures_exchange_info": raw["futures_exchange_info"],
                        "spot_exchange_info": raw["spot_exchange_info"],
                        "funding_interval_by_sym": raw.get("funding_interval_by_sym", {}),
                        "warnings": raw.get("warnings", []),
                    },
                )
        # ---- book_ticker_pair: Group A public, always-on cross-market quotes
        # (2026-07-bookticker-open-columns-v1). Independent of the private
        # channel and of the premium/group_b seams; capability-checked so a
        # legacy client without the seam stays never-succeeded (P2-2). Atomic:
        # cached only after BOTH endpoints + non-empty-list shape + non-empty-map
        # normalization succeed (the adapter raises on any partial/empty side),
        # so one side failing advances neither timestamp nor map (FR-2). ----
        if hasattr(self.client, "fetch_book_ticker_pair") and self._source_due(
            "book_ticker_pair", now, ttl_a
        ):
            try:
                pair = self.client.fetch_book_ticker_pair()
            except (urllib.error.URLError, OSError, ValueError):
                pair = None
            if pair is not None:
                self._global_source_cache["book_ticker_pair"] = (
                    time.monotonic(),
                    {
                        "updated_at": datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "spot": pair["spot"],
                        "futures": pair["futures"],
                    },
                )
        # ---- Group B private reference: classic_reference (1800s) ----
        classic_ref = self._cached_source_value("classic_reference")
        if self._source_due("classic_reference", now, GROUP_B_REFRESH_SECONDS):
            fetched = self._private.fetch_classic_reference()
            if fetched is not None:
                # completion-time stamp (INV-5/FR-2): transport_ts <= business_ts.
                self._global_source_cache["classic_reference"] = (
                    time.monotonic(), fetched,
                )
                classic_ref = fetched
            # failure / disabled -> NOT cached (FR-2); retried next tick
        # ---- Group B account_info + Group A account panels — only when the
        # read-only private channel is usable (classic_ref present) ----
        if classic_ref is not None:
            if self._source_due("account_info", now, GROUP_B_REFRESH_SECONDS):
                info = self._private.fetch_account_info()
                if info is not None:
                    self._global_source_cache["account_info"] = (
                        time.monotonic(), info,
                    )
            panels_refreshed = False
            panel_fetchers = (
                ("price_map", self.client.fetch_ticker_price_map),
                ("unified_balances", self._private.fetch_unified_balances),
                ("um_positions", self._private.fetch_um_positions),
                ("spot_balances", self._private.fetch_spot_balances),
            )
            for sid, fetcher in panel_fetchers:
                if self._source_due(sid, now, ttl_a):
                    try:
                        value = fetcher()
                    except (urllib.error.URLError, OSError, ValueError):
                        value = None
                    if value is not None:
                        self._global_source_cache[sid] = (time.monotonic(), value)
                        if sid != "price_map":
                            panels_refreshed = True
            if panels_refreshed:
                self._account_checked_at = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

    def _compose_base_raw(self) -> Optional[dict]:
        """Rebuild the base_raw dict from cached Group A/B public sources.

        Returns None until both the Group A premium source and the Group B
        public source have at least one successful entry (cold start waits for
        A+B before publishing, 10-design §Scheduling 1).
        """
        premium_entry = self._global_source_cache.get("premium_index")
        group_b_entry = self._global_source_cache.get("group_b_public")
        if premium_entry is None or group_b_entry is None:
            return None
        gb = group_b_entry[1]
        return {
            "futures_exchange_info": gb["futures_exchange_info"],
            "premium_index": premium_entry[1],
            "spot_exchange_info": gb["spot_exchange_info"],
            "funding_history_by_sym": {},
            "funding_interval_by_sym": gb.get("funding_interval_by_sym", {}),
            "warnings": list(gb.get("warnings", [])),
        }

    def _is_scheduled_borrow_candidate(self, row: dict, classic_ref: Any) -> bool:
        """FR-4 scheduled-borrow predicate (stricter than
        select_borrow_candidates' ``< 0``): ``daily_funding_rate <
        -0.00030000`` AND ``MARGIN_SPOT_CANDIDATE`` AND ``asset_tag in
        {CRYPTO, METAL}`` AND the read-only private channel is usable."""
        if classic_ref is None:
            return False
        rate = row.get("daily_funding_rate")
        if not rate:
            return False
        try:
            if Decimal(str(rate)) >= Decimal("-0.00030000"):
                return False
        except (InvalidOperation, ValueError, TypeError):
            return False
        return (
            row.get("route_class") == "MARGIN_SPOT_CANDIDATE"
            and row.get("asset_tag") in ("CRYPTO", "METAL")
        )

    def _homepage_borrow_universe(
        self, rows: List[dict], classic_ref: Any
    ) -> List[str]:
        """De-duplicated base_asset list satisfying the FR-4 predicate, in the
        stable row order build_rows already produced."""
        seen: set = set()
        out: List[str] = []
        for r in rows:
            if not self._is_scheduled_borrow_candidate(r, classic_ref):
                continue
            base = r.get("base_asset", "")
            if not base or base in seen:
                continue
            seen.add(base)
            out.append(base)
        return out

    def _sweep_group_c(
        self,
        candidates: List[str],
        rows_by_symbol: Dict[str, dict],
        data_time_ms: int,
        now: float,
    ) -> List[str]:
        """Component-aware Group C sweep (S4/S6/S7).

        For the next at-most-``history_sweep_batch_size`` symbols on the stable
        cursor: refresh the history component for every homepage candidate, and
        refresh the borrow-rate + max-borrowable components ONLY for FR-4
        universe rows. The three components are freshness-independent (FR-7).
        The cursor advances for every examined symbol even when all components
        are fresh and no request is issued (11-adr Edge Cases). Borrow-rate
        uses the S3b narrow seam fetch_next_hourly_rates (NOT
        fetch_cost_leg_chain); max-borrowable has NO top-50 cap (FR-5).
        """
        warnings: List[str] = []
        if not candidates:
            self._history_cursor = 0
            return warnings
        classic_ref = self._cached_source_value("classic_reference")
        component_ttl = self.config.funding_history_cache_ttl_seconds
        batch_size = self.config.history_sweep_batch_size
        n = len(candidates)
        cursor = self._history_cursor % n
        served = 0
        borrow_due: List[str] = []
        max_due: List[str] = []
        while served < min(batch_size, n):
            sym = candidates[cursor]
            # history component — every homepage candidate
            if not self._history_is_fresh(sym):
                entries = self._fetch_history_for(sym, data_time_ms)
                if entries is None:
                    warnings.append(f"funding_history_unavailable:{sym}")
            # borrow components — FR-4 universe only
            row = rows_by_symbol.get(sym)
            if row and self._is_scheduled_borrow_candidate(row, classic_ref):
                base = row.get("base_asset", "")
                if base and self._borrow_rate_due(base, now, component_ttl):
                    if base not in borrow_due:
                        borrow_due.append(base)
                if base and self._max_borrowable_due(base, now, component_ttl):
                    if base not in max_due:
                        max_due.append(base)
            cursor = (cursor + 1) % n
            served += 1
        self._history_cursor = cursor
        if borrow_due:
            self._refresh_borrow_rates(borrow_due)
        for base in max_due:
            self._refresh_max_borrowable(base)
        return warnings

    def _borrow_rate_due(self, base: str, now: float, ttl: int) -> bool:
        entry = self._borrow_rate_cache.get(base)
        return entry is None or (now - entry[0]) >= ttl

    def _max_borrowable_due(self, base: str, now: float, ttl: int) -> bool:
        entry = self._max_borrowable_cache.get(base)
        return entry is None or (now - entry[0]) >= ttl

    def _refresh_borrow_rates(self, due_assets: List[str]) -> None:
        """One batched next-hourly call for the due assets (S3b narrow seam),
        unpacked per base_asset with its own timestamp (FR-7). Assets whose
        next-hourly value is absent/failed fall back to interestRateHistory for
        THAT asset only (FR-6). Failed assets are NOT cached (FR-2)."""
        rates = self._private.fetch_next_hourly_rates(due_assets)
        if rates is None:
            return  # private channel disabled -> no borrow-rate work
        # completion-time stamp (INV-5/FR-2): the batch timestamp is captured
        # AFTER the successful next-hourly fetch so transport_ts <= business_ts.
        batch_completed = time.monotonic()
        for asset in due_assets:
            raw = rates.get(asset)
            if raw:
                self._borrow_rate_cache[asset] = (batch_completed, raw, "next_hourly")
            else:
                daily = self._private.fetch_interest_rate_history_latest(asset)
                if daily:
                    self._borrow_rate_cache[asset] = (
                        time.monotonic(), daily, "rate_history",
                    )
                # no usable value -> not cached; retried when next due

    def _refresh_max_borrowable(self, base: str) -> None:
        """One maxBorrowable call for a due unique base asset. The attempt is
        recorded in _coverage_attempted whether or not it succeeds (CC-3); only
        a success advances the cache timestamp (FR-2). No top-50 cap (FR-5)."""
        res = self._private.fetch_max_borrowable(base)
        self._coverage_attempted.add(base)
        if res is not None:
            # completion-time stamp (INV-5/FR-2): transport_ts <= business_ts.
            self._max_borrowable_cache[base] = (time.monotonic(), res)

    def _resolve_borrow_rate_for_asset(
        self, base: str, classic_ref: Any, vip_level: Optional[str]
    ) -> Optional[tuple]:
        """S5 per-asset daily borrow-rate resolution (no network). Priority
        ① next_hourly (raw hourly, x24 exactly once via resolve_cost_leg_rate)
        -> ② rate_history (daily) -> ③ cross_margin_tier[account VIP level] ->
        ④ vip0_reference. Tiers ③/④ derive from the Group B classic cross
        table; Group C never re-fetches a Group B endpoint for them. Returns
        ``(daily_str, source)`` or None."""
        br_entry = self._borrow_rate_cache.get(base)
        if br_entry:
            _ts, value, source = br_entry
            if value:
                synthetic = {"daily_by_asset": {base: value}, "chain_hit_source": source}
                rate = resolve_cost_leg_rate(base, synthetic)
                if rate is not None:
                    return rate, source
        if classic_ref:
            cross = classic_ref.get("cross_margin_daily_by_vip", {}) or {}
            if vip_level and cross.get(vip_level, {}).get(base):
                synthetic = {
                    "daily_by_asset": {base: cross[vip_level][base]},
                    "chain_hit_source": "cross_margin_tier",
                }
                rate = resolve_cost_leg_rate(base, synthetic)
                if rate is not None:
                    return rate, "cross_margin_tier"
            if cross.get("0", {}).get(base):
                synthetic = {
                    "daily_by_asset": {base: cross["0"][base]},
                    "chain_hit_source": "vip0_reference",
                }
                rate = resolve_cost_leg_rate(base, synthetic)
                if rate is not None:
                    return rate, "vip0_reference"
        return None

    def _synthesize_cost_leg(
        self, resolved_rates: Dict[str, tuple], vip_level: Optional[str]
    ) -> dict:
        """S8 aggregate chain diagnostic (shape-compatible with
        _select_chain_tier). chain_hit_tier/source reflect the HIGHEST-priority
        source used by at least one current borrow row (a compatibility
        diagnostic, NOT a per-row same-source claim)."""
        if not resolved_rates:
            return {
                "chain_hit_tier": None,
                "chain_hit_source": None,
                "daily_by_asset": {},
                "vip_level": vip_level,
                "classic_margin_daily_interest_account_available": False,
            }
        present = {
            src for (_rate, src) in resolved_rates.values()
            if src in self._BORROW_SOURCE_TIER
        }
        best = min(present, key=lambda s: self._BORROW_SOURCE_TIER[s]) if present else None
        return {
            "chain_hit_tier": self._BORROW_SOURCE_TIER.get(best),
            "chain_hit_source": best,
            "daily_by_asset": {
                base: rate for (base, (rate, _s)) in resolved_rates.items()
            },
            "vip_level": vip_level,
            "classic_margin_daily_interest_account_available": True,
        }

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
