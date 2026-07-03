"""Public Binance REST client. Live (no key) or offline (frozen raw dir).

Records request counts so the implementation report can document rate-limit
headroom. Decimal-safe: never converts price/rate/quantity to float (raw JSON
values are passed through unchanged).
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

_FUNDING_RATE_RE = re.compile(r"fapi-v1-fundingRate-(.+)-limit\d+\.json$")


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class BinancePublicClient:
    """Fetches only public, no-key endpoints. Offline reads frozen fixtures."""

    def __init__(
        self,
        *,
        offline: bool,
        offline_dir,
        futures_base_url: str,
        spot_base_url: str,
        user_agent: str,
        timeout: float,
    ):
        self.offline = offline
        self.offline_dir = Path(offline_dir)
        self.futures_base_url = futures_base_url
        self.spot_base_url = spot_base_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.request_log: Dict[str, int] = {}

    def _bump(self, key: str) -> None:
        self.request_log[key] = self.request_log.get(key, 0) + 1

    def _http_get(self, url: str) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_raw(self) -> dict:
        """Return the public inputs plus an offline funding-history index.

        Live mode returns an empty ``funding_history_by_sym``; the service fills
        it lazily via :meth:`fetch_funding_rate` for the top-N symbols only.
        Offline mode auto-discovers frozen funding-rate fixtures by filename.
        """
        if self.offline:
            return self._fetch_offline()
        return self._fetch_live()

    def _fetch_offline(self) -> dict:
        d = self.offline_dir
        futures_ei = _read_json(d / "fapi-v1-exchangeInfo.json")
        premium = _read_json(d / "fapi-v1-premiumIndex.json")
        curated = d / "api-v3-exchangeInfo-curated-BTCETHXVG.json"
        spot_ei = _read_json(curated) if curated.exists() else {"symbols": []}
        return {
            "futures_exchange_info": futures_ei,
            "premium_index": premium,
            "spot_exchange_info": spot_ei,
            "funding_history_by_sym": self._offline_funding_index(d),
        }

    def _offline_funding_index(self, d: Path) -> Dict[str, List[dict]]:
        out: Dict[str, List[dict]] = {}
        if not d.exists():
            return out
        for path in sorted(d.glob("fapi-v1-fundingRate-*-limit*.json")):
            match = _FUNDING_RATE_RE.search(path.name)
            if not match:
                continue
            out[match.group(1)] = _read_json(path)
        return out

    def _fetch_live(self) -> dict:
        self._bump("GET /fapi/v1/exchangeInfo")
        futures_ei = self._http_get(f"{self.futures_base_url}/fapi/v1/exchangeInfo")
        self._bump("GET /fapi/v1/premiumIndex")
        premium = self._http_get(f"{self.futures_base_url}/fapi/v1/premiumIndex")
        self._bump("GET /api/v3/exchangeInfo")
        spot_ei = self._http_get(f"{self.spot_base_url}/api/v3/exchangeInfo")
        return {
            "futures_exchange_info": futures_ei,
            "premium_index": premium,
            "spot_exchange_info": spot_ei,
            "funding_history_by_sym": {},
        }

    def fetch_funding_rate(self, symbol: str) -> List[dict]:
        """Live-only: recent funding history for one symbol (limit=20).

        Offline relies on the frozen fixture index built in :meth:`fetch_raw`.
        """
        if self.offline:
            return []
        self._bump("GET /fapi/v1/fundingRate")
        url = f"{self.futures_base_url}/fapi/v1/fundingRate?symbol={symbol}&limit=20"
        return self._http_get(url)
