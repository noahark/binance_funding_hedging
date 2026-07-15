"""Public Binance REST client. Live (no key) or offline (frozen raw dir).

Records request counts so the implementation report can document rate-limit
headroom. Decimal-safe: never converts price/rate/quantity to float (raw JSON
values are passed through unchanged).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
            # No frozen fundingInfo sample in the contract-v2 raw dir; offline
            # mode falls back to the Binance 8h default for every symbol.
            "funding_interval_by_sym": {},
            "warnings": [],
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

    def fetch_premium_index(self) -> Any:
        """Group A live public seam: ``GET /fapi/v1/premiumIndex`` (all symbols).

        Stage 2026-07-cache-refresh-scheduler-v2 S2: the worker caches this at the
        Group A cadence (cache_ttl_seconds, 60s) independently from the slower
        Group B public sources. Returns the full premium-index payload. Live-only;
        the offline path stays on the synchronous :meth:`fetch_raw` /
        :meth:`_fetch_offline` entry.
        """
        self._bump("GET /fapi/v1/premiumIndex")
        return self._http_get(f"{self.futures_base_url}/fapi/v1/premiumIndex")

    def fetch_exchange_info_group_b(self) -> dict:
        """Group B live public seam: futures + spot exchangeInfo and fundingInfo.

        Stage 2026-07-cache-refresh-scheduler-v2 S2: the worker caches this at the
        fixed Group B cadence (GROUP_B_REFRESH_SECONDS, 1800s) independently from
        the Group A premium source. Returns
        ``{futures_exchange_info, spot_exchange_info, funding_interval_by_sym,
        warnings}``; fundingInfo keeps its best-effort 8h-default degradation.
        Live-only; the offline path stays on :meth:`fetch_raw`.
        """
        self._bump("GET /fapi/v1/exchangeInfo")
        futures_ei = self._http_get(f"{self.futures_base_url}/fapi/v1/exchangeInfo")
        self._bump("GET /api/v3/exchangeInfo")
        spot_ei = self._http_get(f"{self.spot_base_url}/api/v3/exchangeInfo")
        funding_interval_by_sym, warnings = self._fetch_funding_info_best_effort()
        return {
            "futures_exchange_info": futures_ei,
            "spot_exchange_info": spot_ei,
            "funding_interval_by_sym": funding_interval_by_sym,
            "warnings": warnings,
        }

    def _fetch_funding_info_best_effort(self) -> Tuple[Dict[str, int], List[str]]:
        """E1 failure mode (10-design §2): ``/fapi/v1/fundingInfo`` is a public,
        best-effort input. Any HTTP/transport/parse failure degrades to the
        all-8h default + a warning surfaced into snapshot.warnings, instead of
        propagating and failing the whole snapshot (503). The other public
        inputs are NOT degradable — they still raise on failure.
        """
        self._bump("GET /fapi/v1/fundingInfo")
        funding_interval_by_sym: Dict[str, int] = {}
        warnings: List[str] = []
        try:
            funding_info = self._http_get(f"{self.futures_base_url}/fapi/v1/fundingInfo")
            funding_interval_by_sym = {
                x["symbol"]: int(x["fundingIntervalHours"])
                for x in funding_info
                if isinstance(x, dict) and "symbol" in x and "fundingIntervalHours" in x
            }
        except (urllib.error.URLError, OSError, ValueError) as exc:
            warnings.append(
                f"GET /fapi/v1/fundingInfo failed ({type(exc).__name__}); "
                "degraded every row to the 8h funding-interval default."
            )
        return funding_interval_by_sym, warnings

    def _fetch_live(self) -> dict:
        premium = self.fetch_premium_index()
        gb = self.fetch_exchange_info_group_b()
        return {
            "futures_exchange_info": gb["futures_exchange_info"],
            "premium_index": premium,
            "spot_exchange_info": gb["spot_exchange_info"],
            "funding_history_by_sym": {},
            "funding_interval_by_sym": gb["funding_interval_by_sym"],
            "warnings": gb["warnings"],
        }

    def fetch_funding_rate(
        self,
        symbol: str,
        *,
        start_time_ms=None,
        end_time_ms=None,
        limit: int = 1000,
    ) -> List[dict]:
        """Live-only: settled funding history for one symbol.

        Stage 2026-07 deep-history requests pass ``start_time_ms``/
        ``end_time_ms`` (inclusive calendar window, ms) with ``limit=1000``.
        Query parameters are built via :func:`urllib.parse.urlencode` so values
        are encoded safely; the symbol is never string-interpolated raw.

        Raises on transport/HTTP/parse failure. The snapshot service owns the
        per-symbol degradation (empty history + null annualization + warning);
        this method never turns one symbol's failure into a snapshot-wide 503.

        Offline relies on the frozen fixture index built in :meth:`fetch_raw`.
        """
        if self.offline:
            return []
        self._bump("GET /fapi/v1/fundingRate")
        params: Dict[str, str] = {"symbol": symbol, "limit": str(int(limit))}
        if start_time_ms is not None:
            params["startTime"] = str(int(start_time_ms))
        if end_time_ms is not None:
            params["endTime"] = str(int(end_time_ms))
        query = urllib.parse.urlencode(params)
        url = f"{self.futures_base_url}/fapi/v1/fundingRate?{query}"
        return self._http_get(url)

    def fetch_premium_index_for(self, symbol: str) -> dict:
        """Live-only: ``GET /fapi/v1/premiumIndex?symbol=SYMBOL`` for one row
        (2026-07-history-background-refresh-v1 §6 / 10-design D3).

        Returns the single-symbol premium-index object (``markPrice``,
        ``indexPrice``, ``lastFundingRate``, ``nextFundingTime``, ``time``, …)
        the worker overlays onto its worker-owned ``_base_raw["premium_index"]``
        for the selected symbol, so a click refreshes only that row's public
        fields WITHOUT invoking full-universe :meth:`fetch_raw`. The symbol is
        encoded via :func:`urllib.parse.urlencode` (never raw-interpolated).

        Offline returns ``{}`` (the click flow is never triggered offline).
        Raises on transport/HTTP/parse failure; the worker degrades that one
        source to last-good instead of failing the snapshot.
        """
        if self.offline:
            return {}
        self._bump("GET /fapi/v1/premiumIndex?symbol")
        query = urllib.parse.urlencode({"symbol": symbol})
        url = f"{self.futures_base_url}/fapi/v1/premiumIndex?{query}"
        return self._http_get(url)

    def fetch_ticker_price_map(self) -> Dict[str, str]:
        """P5 ``GET /api/v3/ticker/price`` (public, full, no key) -> {symbol: price}.

        Used once per snapshot to value the private_account block (§1.4). Full
        payload (weight 2 per docs / 4 measured, H_intake §2.A.1) is fetched ONCE
        to build the price map; per-symbol calls are never made in the row loop
        (§3.2: no HTTP in the row loop). Decimal-safe: prices are raw strings.

        Offline returns ``{}`` — the private channel is disabled offline (no
        key), so the price map is never consumed there.
        """
        if self.offline:
            return {}
        self._bump("GET /api/v3/ticker/price")
        url = f"{self.spot_base_url}/api/v3/ticker/price"
        rows = self._http_get(url)
        return {row["symbol"]: row["price"] for row in rows if "symbol" in row}
