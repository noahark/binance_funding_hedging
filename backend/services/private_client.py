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
6. **Rate-limit robustness.** Per-``(method,path,params)`` 1h TTL cache; on
   429 / -1003 a single bounded backoff retry runs; persistent failure raises
   ``PrivateEndpointError`` so the caller degrades without blocking the public
   snapshot.

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
from typing import Any, Dict, Optional, Tuple

# ---- deny-by-default whitelist: (method, exact-path) -> base URL (hardcoded) ----
# This is the single source of truth for which private endpoints may be called.
# Base URLs are bound here and are NOT overridable from config (anti-injection).
WHITELIST: Dict[Tuple[str, str], str] = {
    ("GET", "/sapi/v1/margin/allPairs"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/allAssets"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/crossMarginData"): "https://api.binance.com",
    ("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
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
    ):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.enabled = bool(self.api_key and self.api_secret)
        self._user_agent = user_agent
        self._timeout = timeout
        self._recv_window = recv_window
        self._ttl = ttl_seconds
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
        self, method: str, path: str, params: Optional[Dict[str, str]] = None
    ) -> Any:
        key = (method, path, tuple(sorted((params or {}).items())))
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        data = self._signed_get(method, path, params)
        self._cache[key] = (now + self._ttl, data)
        return data

    # -- high-level fetchers (return None + set last_error on disable/failure) --
    def fetch_classic_reference(self) -> Optional[Dict[str, Any]]:
        """Market-level classic-margin reference (E2+E3+E4), 1h TTL.

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
        """Account-level maxBorrowable for one asset (E5), 1h TTL.

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
