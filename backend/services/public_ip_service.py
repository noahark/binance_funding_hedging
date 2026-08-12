"""Read-only public-egress IP lookup with in-process caching (stage
2026-08-12-local-ip-display-v1).

Returns the public IP the *backend process* observes, so Human can cross-check
the Binance API IP allowlist. It never drives the whitelist, trading, borrowing,
repayment, transfer, any live gate, or risk action, and it cannot prove the IP
Binance actually sees (VPN/proxy/routing may differ).

Design constraints (accepted plan + dispatch):
- Stdlib only. Zero I/O at construction; the first ``get()`` fetches lazily.
- Injectable ``urlopen`` and monotonic ``clock`` for offline tests.
- Fixed source order: primary ``api.ipify.org`` (JSON ``ip``) -> only on primary
  exception / non-dict / missing or non-string ``ip`` / invalid or non-public IP,
  try backup ``checkip.amazonaws.com`` (stripped plain text). Each read is capped
  at 64 bytes, 2s timeout, GET, no body. Private/loopback addresses are rejected
  (a captive-portal local value must never pose as the public egress IP).
- One 5-minute in-process cache shared across calls; success and failure are both
  cached, and a lock serializes cache misses so each cycle hits each source at
  most once. Stale returns the last successful value; a never-succeeded failure
  returns ``unavailable``. No retry loop, no background thread, no persistence.
- Exception text, URLs, and headers never reach the caller.
"""
from __future__ import annotations

import ipaddress
import json
import threading
import time
import urllib.request
from datetime import datetime, timezone

_PRIMARY_URL = "https://api.ipify.org?format=json"
_BACKUP_URL = "https://checkip.amazonaws.com/"
_CACHE_TTL_SECONDS = 300        # 5 minutes; success and failure share this window
_FETCH_TIMEOUT_SECONDS = 2
_MAX_READ_BYTES = 64
_PRIMARY_SOURCE = "api.ipify.org"
_BACKUP_SOURCE = "checkip.amazonaws.com"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PublicIpService:
    def __init__(self, urlopen=None, clock=None):
        self._urlopen = urlopen if urlopen is not None else urllib.request.urlopen
        self._clock = clock if clock is not None else time.monotonic
        self._lock = threading.Lock()
        self._cache = None         # (result_dict, monotonic_stamp) or None
        self._last_success = None  # (ip, source, checked_at) or None

    def get(self) -> dict:
        now = self._clock()
        with self._lock:
            if self._cache is not None and now - self._cache[1] < _CACHE_TTL_SECONDS:
                return dict(self._cache[0])
            result = self._fetch_cycle()
            self._cache = (result, self._clock())
            return dict(result)

    def _fetch_cycle(self) -> dict:
        ip, source = self._try_sources()
        if ip is not None:
            checked_at = _utc_now_iso()
            self._last_success = (ip, source, checked_at)
            return {"status": "ok", "public_ip": ip,
                    "source": source, "checked_at": checked_at}
        if self._last_success is not None:
            ip, source, checked_at = self._last_success
            return {"status": "stale", "public_ip": ip,
                    "source": source, "checked_at": checked_at}
        return {"status": "unavailable", "public_ip": None,
                "source": None, "checked_at": None}

    def _try_sources(self):
        ip = self._read_primary()
        if ip is not None:
            return ip, _PRIMARY_SOURCE
        ip = self._read_backup()
        if ip is not None:
            return ip, _BACKUP_SOURCE
        return None, None

    def _read_primary(self):
        raw = self._fetch(_PRIMARY_URL)
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except (ValueError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        ip = data.get("ip")
        if not isinstance(ip, str):
            return None
        return self._validate(ip)

    def _read_backup(self):
        raw = self._fetch(_BACKUP_URL)
        if raw is None:
            return None
        return self._validate(raw.decode("utf-8", "replace").strip())

    def _fetch(self, url):
        try:
            with self._urlopen(url, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
                return resp.read(_MAX_READ_BYTES)
        except Exception:
            return None

    @staticmethod
    def _validate(candidate):
        try:
            addr = ipaddress.ip_address(candidate)
        except (ValueError, TypeError):
            return None
        # ponytail: is_private also covers loopback/link-local/reserved; a local
        # substitute must never pose as the public egress IP this feature is for.
        if addr.is_private:
            return None
        return candidate
