"""Private read-only Binance client — the repo's SINGLE HMAC exit point.

Security gates (all reviewer-checked + negative-tested in
``backend/tests/test_private_client.py``):

1. **Single HMAC exit.** This module is the only place in the repo that
   constructs an HMAC-SHA256 signature. A grep-level test asserts the
   ``hmac``/``hashlib``/``signature`` surface appears only here.
2. **deny-by-default whitelist.** ``WHITELIST`` maps ``(method, exact-path)``
   pairs to their base URL and is the single source of truth. Any path not in
   the whitelist, or any non-GET method, raises in ``_require_whitelisted``
   BEFORE a signature is constructed. Base URLs are NOT injectable.
3. **GET-only.** No POST/PUT/DELETE code path exists.
4. **Outbound audit log.** Each signed call records
   ``(logical_endpoint, method, http_status, error, latency_ms)`` — sanitized
   path only, never key/secret/signature/full query/headers.
5. **Degradation.** Missing env -> ``enabled=False``; fetch methods return
   ``None`` and set ``last_error`` so the public snapshot still renders with
   ``borrow_validation.verified=false``.
6. **Rate-limit robustness.** Per-``(method,path,params)`` TTL cache; on
   429 / -1003 a single bounded backoff retry runs; persistent failure raises
   ``PrivateEndpointError`` so the caller degrades without blocking the public
   snapshot.

Two TTL groups (10-design §1.6): the 1h rate-chain/maxBorrowable group and the
60s account-balance group (E3/E4/E6), independent of each other. E1/E1b
(marginInterestHistory / portfolio interest-history) are registered in the
whitelist for discovery-only reuse but are NOT called by any fetcher here —
this stage's snapshot assembly does not consume them (10-design §2).

Decimal discipline: amount/rate values are passed through as raw strings
(Binance returns them as strings); no float touches any value path.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# ---- deny-by-default whitelist: (method, exact-path) -> base URL (hardcoded) ----
# This is the single source of truth for which private endpoints may be called.
# Base URLs are bound here and are NOT overridable from config (anti-injection).
# Frozen by H_intake (10-design §2.A.1) — api/papi are distinct X-MBX weight pools.
WHITELIST: Dict[Tuple[str, str], str] = {
    # W1/W2/W3 — existing market-level classic-margin references (sapi).
    ("GET", "/sapi/v1/margin/allPairs"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/allAssets"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/crossMarginData"): "https://api.binance.com",
    # E2/E2b/E5 — cost-leg chain (sapi). E2 next-hourly is the heaviest (weight 100).
    ("GET", "/sapi/v1/margin/next-hourly-interest-rate"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/interestRateHistory"): "https://api.binance.com",
    ("GET", "/sapi/v1/account/info"): "https://api.binance.com",
    # E6 — spot balances (api).
    ("GET", "/api/v3/account"): "https://api.binance.com",
    # papi endpoints — account IP weight pool (distinct from sapi/api).
    ("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
    ("GET", "/papi/v1/balance"): "https://papi.binance.com",
    ("GET", "/papi/v1/um/positionRisk"): "https://papi.binance.com",
    # E1/E1b — discovery-only; registered but NOT called by snapshot assembly.
    ("GET", "/papi/v1/margin/marginInterestHistory"): "https://papi.binance.com",
    ("GET", "/papi/v1/portfolio/interest-history"): "https://papi.binance.com",
}


class PrivateEndpointError(Exception):
    """Raised when a whitelisted private endpoint returns a non-2xx result.

    Carries the sanitized logical path and HTTP status so the caller can record
    a reason in ``borrow_validation.error`` without surfacing credentials.
    """

    def __init__(self, logical_path: str, status: Optional[int], reason: str):
        self.logical_path = logical_path
        self.status = status
        self.reason = reason
        super().__init__(f"{logical_path} failed: status={status} reason={reason}")


class PrivateClient:
    """The repo's only HMAC-SHA256 signing channel."""

    def __init__(
        self,
        api_key: Optional[str],
        api_secret: Optional[str],
        *,
        user_agent: str,
        timeout: float,
        recv_window: int,
        ttl_seconds: int,
        fast_ttl_seconds: int,
    ):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.enabled = bool(self.api_key and self.api_secret)
        self._user_agent = user_agent
        self._timeout = timeout
        self._recv_window = recv_window
        self._ttl = ttl_seconds          # 1h group: rate chain + maxBorrowable
        self._fast_ttl = fast_ttl_seconds  # 60s group: E3/E4/E6 account balances
        self.audit_log: list = []
        self.last_error: Optional[str] = None
        self._cache: Dict[Tuple[str, str, Tuple[Tuple[str, str], ...]], Tuple[float, Any]] = {}

    # -- security gate (raises BEFORE any signature construction) --
    @staticmethod
    def _require_whitelisted(method: str, path: str) -> str:
        if (method, path) not in WHITELIST:
            raise PermissionError(f"private endpoint not whitelisted: {method} {path}")
        if method != "GET":
            raise PermissionError(f"private client is GET-only: {method} {path}")
        return WHITELIST[(method, path)]

    # -- single HMAC exit --
    def _signed_get(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, str]] = None,
        _retry: bool = True,
    ) -> Any:
        base = self._require_whitelisted(method, path)  # raises before signing
        if not self.enabled:
            raise RuntimeError("private client disabled (env missing)")
        p = dict(params or {})
        p["recvWindow"] = str(self._recv_window)
        p["timestamp"] = str(int(time.time() * 1000))
        qs = "&".join(f"{k}={v}" for k, v in sorted(p.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        url = f"{base}{path}?{qs}&signature={signature}"
        req = urllib.request.Request(
            url,
            headers={"X-MBX-APIKEY": self.api_key, "User-Agent": self._user_agent},
            method="GET",
        )
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body, status, err = resp.read().decode("utf-8"), resp.status, None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            status, err = exc.code, f"HTTP {exc.code}"
        except Exception as exc:  # network / timeout / DNS
            body, status, err = "", None, type(exc).__name__
        latency = round((time.monotonic() - t0) * 1000, 1)
        # audit log: sanitized path only; NO key/secret/signature/query/headers
        self.audit_log.append(
            {
                "logical_endpoint": path,
                "method": "GET",
                "http_status": status,
                "error": err,
                "latency_ms": latency,
            }
        )
        # bounded rate-limit backoff (one retry); failure raises -> caller degrades
        if _retry and self._is_rate_limited(status, body):
            time.sleep(0.5)
            return self._signed_get(method, path, params, _retry=False)
        if status is None or status >= 400:
            raise PrivateEndpointError(path, status, err or "unknown")
        return json.loads(body)

    @staticmethod
    def _is_rate_limited(status: Optional[int], body: str) -> bool:
        if status == 429:
            return True
        if status == 400 and body:
            try:
                if json.loads(body).get("code") == -1003:
                    return True
            except (ValueError, TypeError):
                pass
        return False

    def _cached_get(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, str]] = None,
        *,
        ttl: Optional[int] = None,
    ) -> Any:
        """TTL-cached signed GET. ``ttl`` selects the §1.6 group (default 1h)."""
        key = (method, path, tuple(sorted((params or {}).items())))
        lifetime = self._ttl if ttl is None else ttl
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        data = self._signed_get(method, path, params)
        self._cache[key] = (now + lifetime, data)
        return data

    # -- high-level fetchers (return None + set last_error on disable/failure) --
    def fetch_classic_reference(self) -> Optional[Dict[str, Any]]:
        """Market-level classic-margin reference (W1+W2+W3), 1h TTL.

        Returns ``{"pair_listed_by_symbol", "asset_borrowable_by_name",
        "daily_interest_vip0_by_coin"}`` or ``None`` (disabled/failed). On
        failure sets ``last_error``; caller records verified=false.
        """
        if not self.enabled:
            self.last_error = "private_channel_disabled"
            return None
        try:
            all_pairs = self._cached_get("GET", "/sapi/v1/margin/allPairs")
            all_assets = self._cached_get("GET", "/sapi/v1/margin/allAssets")
            cross = self._cached_get("GET", "/sapi/v1/margin/crossMarginData")
        except PrivateEndpointError as exc:
            self.last_error = f"classic_reference_failed:{exc.logical_path}:{exc.reason}"
            return None
        return {
            "pair_listed_by_symbol": {
                x.get("symbol"): bool(x.get("isMarginTrade")) for x in all_pairs
            },
            "asset_borrowable_by_name": {
                x.get("assetName"): bool(x.get("isBorrowable")) for x in all_assets
            },
            "daily_interest_vip0_by_coin": {
                x.get("coin"): x.get("dailyInterest")
                for x in cross
                if str(x.get("vipLevel")) == "0"
            },
        }

    def fetch_max_borrowable(self, asset: str) -> Optional[Dict[str, Optional[str]]]:
        """Account-level maxBorrowable for one asset (W4), 1h TTL.

        Returns ``{"max_borrowable", "borrow_limit"}`` (raw strings) or ``None``
        (disabled/failed). On failure sets ``last_error``.
        """
        if not self.enabled:
            return None
        try:
            data = self._cached_get(
                "GET", "/papi/v1/margin/maxBorrowable", {"asset": asset}
            )
        except PrivateEndpointError as exc:
            self.last_error = f"max_borrowable_failed:{asset}:{exc.reason}"
            return None
        return {
            "max_borrowable": data.get("amount"),
            "borrow_limit": data.get("borrowLimit"),
        }

    # -- cost-leg chain (10-design §1.3) --
    def fetch_account_info(self) -> Optional[dict]:
        """E5 ``/sapi/v1/account/info`` (1h TTL) — VIP level + account switches.

        Returns the raw dict (``vipLevel``, ``isPortfolioMarginRetailEnabled``,
        ...) or ``None`` (disabled/failed). Per-endpoint failure is NON-blocking:
        the chain degrades to a lower tier (§1.3). Never raises.
        """
        if not self.enabled:
            return None
        try:
            return self._cached_get("GET", "/sapi/v1/account/info")
        except PrivateEndpointError:
            return None

    def fetch_cost_leg_chain(
        self, borrow_assets: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Snapshot-level cost-leg chain (§1.3). One HTTP call per tier probe,
        all in the 1h TTL group (shared cache: crossMarginData reuses the
        classic_reference fetch).

        ``borrow_assets`` = unique probed base assets (§1.5 set, already capped).
        Returns a chain result describing the SINGLE hit tier and its per-asset
        daily-rate table, or ``None`` (channel disabled). Per-endpoint failure
        degrades tier-by-tier (NON-blocking); only a fully-broken chain yields
        tier=None.

        Returned keys:
        - ``chain_hit_tier``: 1|2|3|4|None
        - ``chain_hit_source``: ``next_hourly``|``rate_history``|
          ``cross_margin_tier``|``vip0_reference``|None
        - ``daily_by_asset``: {asset: daily_rate_str} for the hit tier's table
        - ``vip_level``: str|None (E5 vipLevel, used for tier 3 + diagnostics)
        - ``classic_margin_daily_interest_account_available``: bool (tier != None)

        Assumption A1 (documented in 20-implementation-backend.md): E2b
        ``/sapi/v1/margin/interestRateHistory`` is single-asset (frozen
        discovery ``asset=BTC``; the param name is singular vs E2's plural
        ``assets``). It is probed ONCE for the top candidate only; tier②
        coverage is therefore limited to that asset. Tier① (E2, comma-joined)
        covers all candidates in one call and is the realistic primary tier.
        """
        if not self.enabled:
            self.last_error = "private_channel_disabled"
            return None

        info = self.fetch_account_info() or {}
        vip_level_raw = info.get("vipLevel")
        vip_level = str(vip_level_raw) if vip_level_raw is not None else None

        # tier① E2 next-hourly — comma-joined assets, isIsolated=false REQUIRED
        # (H_intake fix: missing isIsolated -> 400 -3026).
        next_hourly: Dict[str, Optional[str]] = {}
        if borrow_assets:
            try:
                e2 = self._cached_get(
                    "GET",
                    "/sapi/v1/margin/next-hourly-interest-rate",
                    {"assets": ",".join(borrow_assets), "isIsolated": "false"},
                )
                next_hourly = {
                    x.get("asset"): x.get("nextHourlyInterestRate")
                    for x in (e2 or [])
                    if isinstance(x, dict)
                }
            except PrivateEndpointError:
                next_hourly = {}

        # tier② E2b interestRateHistory — single-asset probe (A1).
        rate_history: Dict[str, Optional[str]] = {}
        if borrow_assets:
            try:
                e2b = self._cached_get(
                    "GET",
                    "/sapi/v1/margin/interestRateHistory",
                    {"asset": borrow_assets[0]},
                )
                points = [p for p in (e2b or []) if isinstance(p, dict)]
                if points:
                    latest = max(points, key=lambda p: int(p.get("timestamp", 0)))
                    rate_history = {
                        latest.get("asset"): latest.get("dailyInterestRate")
                    }
            except PrivateEndpointError:
                rate_history = {}

        # crossMarginData (W3) — shared cache with classic_reference; one call.
        cross_table: Dict[str, Dict[str, str]] = {}
        try:
            cross = self._cached_get("GET", "/sapi/v1/margin/crossMarginData")
            for row in (cross or []):
                if not isinstance(row, dict):
                    continue
                lvl = str(row.get("vipLevel"))
                cross_table.setdefault(lvl, {})[row.get("coin")] = row.get(
                    "dailyInterest"
                )
        except PrivateEndpointError:
            cross_table = {}

        return _select_chain_tier(
            next_hourly, rate_history, cross_table, vip_level
        )

    # -- private_account block (10-design §1.4); 60s TTL group --
    def fetch_unified_balances(self) -> Optional[List[dict]]:
        """E3 ``/papi/v1/balance`` (60s TTL) — unified-account balances.

        Returns the raw list or ``None`` (disabled/failed). Per §1.4 the
        ``totalWalletBalance`` already includes um/cm/crossMargin sub-accounts
        (anti-double-count); sub-fields are exposure only.
        """
        if not self.enabled:
            return None
        try:
            return self._cached_get("GET", "/papi/v1/balance", ttl=self._fast_ttl)
        except PrivateEndpointError as exc:
            self.last_error = f"papi_balance_failed:{exc.reason}"
            return None

    def fetch_um_positions(self) -> Optional[List[dict]]:
        """E4 ``/papi/v1/um/positionRisk`` (60s TTL) — UM exposure view.

        Returns the raw list (empty when flat) or ``None`` (disabled/failed).
        Nominal value is NEVER counted in ``total_value_usdt`` (§1.4 hard rule).
        """
        if not self.enabled:
            return None
        try:
            return self._cached_get("GET", "/papi/v1/um/positionRisk", ttl=self._fast_ttl)
        except PrivateEndpointError as exc:
            self.last_error = f"um_positionrisk_failed:{exc.reason}"
            return None

    def fetch_spot_balances(self) -> Optional[List[dict]]:
        """E6 ``/api/v3/account`` (60s TTL, omitZeroBalances=true) — spot balances.

        Returns the ``balances`` list ``[{asset, free, locked}]`` or ``None``
        (disabled/failed).
        """
        if not self.enabled:
            return None
        try:
            data = self._cached_get(
                "GET",
                "/api/v3/account",
                {"omitZeroBalances": "true"},
                ttl=self._fast_ttl,
            )
        except PrivateEndpointError as exc:
            self.last_error = f"api_account_failed:{exc.reason}"
            return None
        return data.get("balances") if isinstance(data, dict) else None


def _select_chain_tier(
    next_hourly: Dict[str, Optional[str]],
    rate_history: Dict[str, Optional[str]],
    cross_table: Dict[str, Dict[str, str]],
    vip_level: Optional[str],
) -> Dict[str, Any]:
    """Pick the snapshot-level hit tier (§1.3 / §2.A.5) and its rate table.

    Pure function (no HTTP) so the tier logic is unit-testable in isolation.
    Order: ① next_hourly -> ② rate_history -> ③ cross_margin_tier (vipLevel) ->
    ④ vip0_reference. A tier "hits" when its table is non-empty (and, for ③,
    the VIP level is known and present). All-chain-broken -> tier None.
    """
    # ① next_hourly: hourly × 24 normalization happens in snapshot.compute_daily_from_hourly;
    # here we keep the raw hourly strings and let the caller normalize per asset.
    if any(v for v in next_hourly.values()):
        return {
            "chain_hit_tier": 1,
            "chain_hit_source": "next_hourly",
            "daily_by_asset": dict(next_hourly),
            "vip_level": vip_level,
            "classic_margin_daily_interest_account_available": True,
        }
    if any(v for v in rate_history.values()):
        return {
            "chain_hit_tier": 2,
            "chain_hit_source": "rate_history",
            "daily_by_asset": dict(rate_history),
            "vip_level": vip_level,
            "classic_margin_daily_interest_account_available": True,
        }
    if vip_level is not None and cross_table.get(vip_level):
        return {
            "chain_hit_tier": 3,
            "chain_hit_source": "cross_margin_tier",
            "daily_by_asset": dict(cross_table[vip_level]),
            "vip_level": vip_level,
            "classic_margin_daily_interest_account_available": True,
        }
    if cross_table.get("0"):
        return {
            "chain_hit_tier": 4,
            "chain_hit_source": "vip0_reference",
            "daily_by_asset": dict(cross_table["0"]),
            "vip_level": vip_level,
            "classic_margin_daily_interest_account_available": True,
        }
    return {
        "chain_hit_tier": None,
        "chain_hit_source": None,
        "daily_by_asset": {},
        "vip_level": vip_level,
        "classic_margin_daily_interest_account_available": False,
    }
