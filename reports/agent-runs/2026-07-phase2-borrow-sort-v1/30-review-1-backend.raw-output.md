• I need act as reviewer_1. Must be fresh read-only. Need inspect repo, recompute diff fingerprint, compare status.json. Need review git diff backend/schemas/docs/api parts. Need check design, constraints, endpoint whitelist, tests, discovery evidence. Need produce narrative + strict json verdict. No writing files. We must use tools read-only. Let's start by listing reports/agent-runs/2026-07-phase2-borrow-sort-v1 contents. Also read status.json and design docs. Need verify git state.

• I'll perform the review-1 task: recompute the fingerprint, inspect the diff, and produce a schema-compliant verdict.?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/30-review-1-backend.raw-output.md
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/30-review-1-frontend.raw-output.md
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-task-a-by-kimi.prompt.md
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-task-b-by-glm.prompt.md
92b949f Sync Harness bookkeeper parallel gates
ccb76ba controller RECEIPT 2026-07-phase2-borrow-sort-v1: mark Phase 1-3 done, next_dispatch -> review-1
f168204 H_docs 2026-07-phase2-borrow-sort-v1: stage-delivery required files (aggregated/index)
59e0eab H_bind 2026-07-phase2-borrow-sort-v1: bind diff_fingerprint + status -> review_1
cc25148 H_B 2026-07-phase2-borrow-sort-v1: frontend column split + daily-rate visibility, zero sort
total 544
drwxr-xr-x@ 29 ark  staff    928  7月  4 23:33 .
drwxr-x---@ 14 ark  staff    448  7月  4 21:03 ..
-rw-r--r--@  1 ark  staff   4240  7月  4 21:03 00-intake.md
-rw-r--r--@  1 ark  staff   1865  7月  4 21:05 00-task.md
-rw-r--r--@  1 ark  staff  14970  7月  4 21:38 10-design.md
-rw-r--r--@  1 ark  staff   2606  7月  4 23:24 11-adr.md
-rw-r--r--@  1 ark  staff   8341  7月  4 22:23 20-implementation-backend.md
-rw-r--r--@  1 ark  staff   5428  7月  4 22:17 20-implementation-frontend.md
-rw-r--r--@  1 ark  staff   2869  7月  4 23:24 20-implementation.md
-rw-r--r--@  1 ark  staff   1393  7月  4 23:33 30-review-1-backend.raw-output.md
-rw-r--r--@  1 ark  staff    349  7月  4 23:33 30-review-1-frontend.raw-output.md
-rw-r--r--@  1 ark  staff   9419  7月  4 22:20 60-test-output.txt
-rw-r--r--@  1 ark  staff   1640  7月  4 23:24 70-handoff.md
-rw-r--r--@  1 ark  staff   5856  7月  4 23:27 controller-start-prompt.md
-rw-r--r--@  1 ark  staff  53780  7月  4 22:24 embedded-review-a-round1.diff.patch
-rw-r--r--@  1 ark  staff   4261  7月  4 22:24 embedded-review-a-round1.prompt-for-kimi.md
-rw-r--r--@  1 ark  staff  25566  7月  4 22:53 embedded-review-a-round1.raw-output.md
-rw-r--r--@  1 ark  staff  26965  7月  4 22:19 embedded-review-b-round1.diff.patch
-rw-r--r--@  1 ark  staff   1123  7月  4 22:54 embedded-review-b-round1.fix-note.md
-rw-r--r--@  1 ark  staff   2090  7月  4 22:20 embedded-review-b-round1.prompt-for-glm.md
-rw-r--r--@  1 ark  staff   6982  7月  4 23:06 embedded-review-b-round1.raw-output.md
-rw-r--r--@  1 ark  staff   3269  7月  4 23:15 pre-review-task-a-by-kimi.prompt.md
-rw-r--r--@  1 ark  staff   3272  7月  4 22:54 pre-review-task-b-by-glm.prompt.md
-rw-r--r--@  1 ark  staff   2308  7月  4 23:31 review-1-task-a-by-kimi.prompt.md
-rw-r--r--@  1 ark  staff   2068  7月  4 23:31 review-1-task-b-by-glm.prompt.md
-rw-r--r--@  1 ark  staff   4177  7月  4 21:09 review-prompts-templates.md
-rw-r--r--@  1 ark  staff  10028  7月  4 23:20 status.json
-rw-r--r--@  1 ark  staff   3583  7月  4 23:15 task-a-glm-backend.prompt.md
-rw-r--r--@  1 ark  staff   4134  7月  4 23:15 task-b-kimi-frontend.prompt.md
• Need compute fingerprint. The formula excludes reports/agent-runs/<stage>/status.json. Command: git diff --binary 4d47ad2..cc25148 -- . ":(exclude)reports/agent-runs/2026-07-phase2-borrow-sort-v1/status.json" | sha256sum. Then compare to status value 9dc905d... Need ensure no status changes. Also compute diff stats. Read design doc.recomputed=9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a
recorded=9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a
MATCH
Now need inspect diff for Task A scope. Compute diff restricted to backend/schemas/docs/api. Also maybe include all diff to know files. Need read implementation report, adr, test output, review prompt templates. Also verify tests can replay? We can run pytest to confirm. Since I am read-only reviewer, I can run tests (read-only). Running tests is allowed (does not modify files). Need also sha256 discovery evidence index/sample. Let's do parallel reads. backend/adapters/binance_public.py             |  11 +
 backend/config.py                              |   5 +
 backend/domain/snapshot.py                     | 149 ++++++++++++-
 backend/services/private_client.py             | 222 +++++++++++++++++++
 backend/services/snapshot_service.py           |  67 +++++-
 backend/tests/test_phase2_borrow_sort.py       | 286 +++++++++++++++++++++++++
 backend/tests/test_private_client.py           | 230 ++++++++++++++++++++
 docs/api/public-market-contract.md             |  72 ++++++-
 schemas/api/public-market/snapshot.schema.json |  63 ++++++
 9 files changed, 1101 insertions(+), 4 deletions(-)
Need review diff in detail for backend, schema, contract. Also test replay by running pytest. Check discovery evidence index and sha256. Check embedded pre-review output maybe. Need inspect code changes. Let's get diff content for changed files. Use git diff for relevant paths. Also maybe view full files. Let's diff backend.diff --git a/backend/adapters/binance_public.py b/backend/adapters/binance_public.py
index df5ee51..b640c4d 100644
--- a/backend/adapters/binance_public.py
+++ b/backend/adapters/binance_public.py
@@ -71,6 +71,9 @@ class BinancePublicClient:
             "premium_index": premium,
             "spot_exchange_info": spot_ei,
             "funding_history_by_sym": self._offline_funding_index(d),
+            # No frozen fundingInfo sample in the contract-v2 raw dir; offline
+            # mode falls back to the Binance 8h default for every symbol.
+            "funding_interval_by_sym": {},
         }
 
     def _offline_funding_index(self, d: Path) -> Dict[str, List[dict]]:
@@ -91,11 +94,19 @@ class BinancePublicClient:
         premium = self._http_get(f"{self.futures_base_url}/fapi/v1/premiumIndex")
         self._bump("GET /api/v3/exchangeInfo")
         spot_ei = self._http_get(f"{self.spot_base_url}/api/v3/exchangeInfo")
+        self._bump("GET /fapi/v1/fundingInfo")
+        funding_info = self._http_get(f"{self.futures_base_url}/fapi/v1/fundingInfo")
+        funding_interval_by_sym = {
+            x["symbol"]: int(x["fundingIntervalHours"])
+            for x in funding_info
+            if isinstance(x, dict) and "symbol" in x and "fundingIntervalHours" in x
+        }
         return {
             "futures_exchange_info": futures_ei,
             "premium_index": premium,
             "spot_exchange_info": spot_ei,
             "funding_history_by_sym": {},
+            "funding_interval_by_sym": funding_interval_by_sym,
         }
 
     def fetch_funding_rate(self, symbol: str) -> List[dict]:
diff --git a/backend/config.py b/backend/config.py
index b615185..22ebc31 100644
--- a/backend/config.py
+++ b/backend/config.py
@@ -33,8 +33,13 @@ class Config:
     frontend_dir: Path = FRONTEND_DIR
     futures_base_url: str = "https://fapi.binance.com"
     spot_base_url: str = "https://api.binance.com"
+    sapi_base_url: str = "https://api.binance.com"
+    papi_base_url: str = "https://papi.binance.com"
     user_agent: str = "funding-hedging-public-market/1.0"
     request_timeout: float = 15.0
+    borrow_check_top_n: int = 10
+    private_channel_ttl_seconds: int = 3600
+    private_recv_window: int = 10000
 
 
 DEFAULT = Config()
diff --git a/backend/domain/snapshot.py b/backend/domain/snapshot.py
index b7dadd9..1a9d780 100644
--- a/backend/domain/snapshot.py
+++ b/backend/domain/snapshot.py
@@ -7,7 +7,7 @@ every decimal field is serialized as a string straight from the raw JSON.
 from __future__ import annotations
 
 from decimal import Decimal, InvalidOperation
-from typing import Dict, List
+from typing import Dict, List, Optional
 
 from .classify import classify_route, negative_funding_status
 from .normalize import asset_tag_for, filter_of, resolve_spot_leg
@@ -53,6 +53,8 @@ def build_rows(
     premium_by_sym: Dict[str, dict],
     spot_by_sym: Dict[str, dict],
     funding_history_by_sym: Dict[str, List[dict]],
+    *,
+    funding_interval_by_sym: Optional[Dict[str, int]] = None,
 ) -> List[dict]:
     """Build snapshot rows from already-filtered futures symbols.
 
@@ -60,7 +62,14 @@ def build_rows(
     ``funding_history`` is filled for every symbol that has history available in
     ``funding_history_by_sym``. The service restricts LIVE funding-rate fetching
     to the top-N by abs(rate); offline uses all frozen fixtures (no HTTP cost).
+
+    ``funding_interval_by_sym`` (symbol -> fundingIntervalHours from public
+    ``/fapi/v1/fundingInfo``) populates ``funding_interval_hours`` and drives the
+    ``daily_funding_rate = Decimal(lastFundingRate) * (24/interval)`` computation.
+    Symbols absent from fundingInfo default to 8 (Binance default); ``None``/empty
+    means all symbols use the 8h default.
     """
+    interval_map = funding_interval_by_sym or {}
     rows: List[dict] = []
     for obj in futures_symbols:
         sym = obj["symbol"]
@@ -75,6 +84,10 @@ def build_rows(
         )
         neg = negative_funding_status(route, asset_tag)
         prem = premium_by_sym.get(sym, {})
+        interval_hours = int(interval_map.get(sym, 8))
+        daily_rate = compute_daily_funding_rate(
+            prem.get("lastFundingRate", "0"), interval_hours
+        )
 
         ui_flags = ["MARGIN_PUBLIC_UNVERIFIED"]
         if route == "PERP_ONLY_EXCLUDED":
@@ -130,6 +143,8 @@ def build_rows(
                     "source": "unverified",
                 },
                 "funding_history": funding_history,
+                "funding_interval_hours": interval_hours,
+                "daily_funding_rate": daily_rate,
                 "ui_flags": ui_flags,
             }
         )
@@ -150,13 +165,21 @@ def assemble_snapshot(
     generated_at: str,
     data_time: str,
     source_sample_id: str,
+    private_channel_status: str = "disabled",
 ) -> dict:
-    """Assemble the full snapshot. ``summary`` is aggregated from ``rows``."""
+    """Assemble the full snapshot. ``summary`` is aggregated from ``rows``.
+
+    ``private_channel_status`` is ``"enabled"`` when the private borrow-validation
+    channel returned a classic reference; otherwise ``"disabled"`` (env missing or
+    endpoint failure), in which case every row's ``borrow_validation.verified``
+    is false with null data fields.
+    """
     return {
         "schema_version": SCHEMA_VERSION,
         "generated_at": generated_at,
         "data_time": data_time,
         "source_sample_id": source_sample_id,
+        "private_channel": private_channel_status,
         "summary": {
             "total_rows": len(rows),
             "route_counts": _counts(rows, "route_class"),
@@ -166,3 +189,125 @@ def assemble_snapshot(
         "rows": rows,
         "warnings": list(CONTRACT_WARNINGS),
     }
+
+
+def compute_daily_funding_rate(
+    last_funding_rate, interval_hours: int
+) -> Optional[str]:
+    """``Decimal(lastFundingRate) * (24 / interval)`` as a fixed-point string.
+
+    8-place quantization (``Decimal('1E-8')``), no scientific notation; negative
+    zero is normalized to ``"0.00000000"``. Missing/empty/non-numeric input or a
+    non-positive interval -> ``None`` (rows with ``None`` sort last). Decimal-only;
+    float never touches a value path.
+
+    Vectors (10-design §3.3):
+      ``"0.00010000"`` x24/8 -> ``"0.00030000"``;
+      ``"0.00010000"`` x24/4 -> ``"0.00060000"``;
+      ``"-0.00005000"`` x24/4 -> ``"-0.00030000"``;
+      ``"0.00002000"`` x24/1 -> ``"0.00048000"``;
+      ``"-0.00000000"`` x24/8 -> ``"0.00000000"`` (negative-zero normalization);
+      missing/``""`` -> ``None``.
+    """
+    if last_funding_rate is None or last_funding_rate == "":
+        return None
+    try:
+        rate = Decimal(str(last_funding_rate))
+    except (InvalidOperation, ValueError, TypeError):
+        return None
+    try:
+        interval = int(interval_hours)
+    except (TypeError, ValueError):
+        return None
+    if interval <= 0:
+        return None
+    daily = rate * (Decimal(24) / Decimal(interval))
+    if daily == 0:  # normalize negative zero before quantize
+        daily = Decimal(0)
+    daily = daily.quantize(Decimal("1E-8"))
+    return format(daily, "f")
+
+
+def sort_rows(rows: List[dict]) -> List[dict]:
+    """Order rows by ``abs(daily_funding_rate)`` DESC, nulls last, symbol ASC tie-break.
+
+    Deterministic total order — this IS the payload order the frontend renders
+    (the frontend must not reorder; filters only hide). Uses Decimal, never float.
+    """
+
+    def key(r: dict):
+        sym = r.get("symbol", "")
+        d = r.get("daily_funding_rate")
+        if d is None:
+            return (1, Decimal(0), sym)  # nulls sort last
+        try:
+            neg = -abs(Decimal(str(d)))
+        except (InvalidOperation, ValueError, TypeError):
+            return (1, Decimal(0), sym)
+        return (0, neg, sym)  # neg ascending == abs descending; symbol asc
+
+    return sorted(rows, key=key)
+
+
+def assemble_borrow_validation(
+    row: dict,
+    classic_ref: Optional[dict],
+    portfolio_by_asset: Dict[str, dict],
+    checked_at: Optional[str],
+    error: Optional[str],
+) -> dict:
+    """Three-state borrow-validation block (parallel output; never alters classify).
+
+    - ``classic_ref is None`` (private channel disabled/failed): ``verified=false``,
+      every data field null, ``error`` carries the reason.
+    - verified, pair not listed in the classic list: ``verified=true``,
+      ``pair_listed=false``, asset/interest fields null.
+    - verified, pair listed: ``verified=true``, ``pair_listed=true`` + asset/interest.
+
+    ``portfolio_account`` carries values only for bounded candidates present in
+    ``portfolio_by_asset``; other rows keep null amount fields (the block is still
+    present with its ``source``). ``checked_at`` is the request-success moment.
+    """
+    base = row.get("base_asset", "")
+    sym = row.get("symbol", "")
+    if classic_ref is None:
+        return {
+            "verified": False,
+            "classic_margin": {
+                "pair_listed": None,
+                "asset_borrowable": None,
+                "daily_interest_vip0": None,
+                "source": "sapi_reference",
+            },
+            "portfolio_account": {
+                "max_borrowable": None,
+                "borrow_limit": None,
+                "source": "papi_max_borrowable",
+            },
+            "checked_at": None,
+            "error": error,
+        }
+    pair_listed = classic_ref.get("pair_listed_by_symbol", {}).get(sym)
+    if pair_listed:
+        asset_borrowable = classic_ref.get("asset_borrowable_by_name", {}).get(base)
+        daily_vip0 = classic_ref.get("daily_interest_vip0_by_coin", {}).get(base)
+    else:
+        asset_borrowable = None
+        daily_vip0 = None
+    portfolio = portfolio_by_asset.get(base, {})
+    return {
+        "verified": True,
+        "classic_margin": {
+            "pair_listed": bool(pair_listed),
+            "asset_borrowable": asset_borrowable,
+            "daily_interest_vip0": daily_vip0,
+            "source": "sapi_reference",
+        },
+        "portfolio_account": {
+            "max_borrowable": portfolio.get("max_borrowable"),
+            "borrow_limit": portfolio.get("borrow_limit"),
+            "source": "papi_max_borrowable",
+        },
+        "checked_at": checked_at,
+        "error": None,
+    }
diff --git a/backend/services/private_client.py b/backend/services/private_client.py
new file mode 100644
index 0000000..8d1603a
--- /dev/null
+++ b/backend/services/private_client.py
@@ -0,0 +1,222 @@
+"""Private read-only Binance client — the repo's SINGLE HMAC exit point.
+
+Security gates (all reviewer-checked + negative-tested in
+``backend/tests/test_private_client.py``):
+
+1. **Single HMAC exit.** This module is the only place in the repo that
+   constructs an HMAC-SHA256 signature. A grep-level test asserts the
+   ``hmac``/``hashlib``/``signature`` surface appears only here.
+2. **deny-by-default whitelist.** ``WHITELIST`` maps ``(method, exact-path)``
+   pairs to their base URL and is the single source of truth. Any path not in
+   the whitelist, or any non-GET method, raises in ``_require_whitelisted``
+   BEFORE a signature is constructed. Base URLs are NOT injectable.
+3. **GET-only.** No POST/PUT/DELETE code path exists.
+4. **Outbound audit log.** Each signed call records
+   ``(logical_endpoint, method, http_status, error, latency_ms)`` — sanitized
+   path only, never key/secret/signature/full query/headers.
+5. **Degradation.** Missing env -> ``enabled=False``; fetch methods return
+   ``None`` and set ``last_error`` so the public snapshot still renders with
+   ``borrow_validation.verified=false``.
+6. **Rate-limit robustness.** Per-``(method,path,params)`` 1h TTL cache; on
+   429 / -1003 a single bounded backoff retry runs; persistent failure raises
+   ``PrivateEndpointError`` so the caller degrades without blocking the public
+   snapshot.
+
+Decimal discipline: amount/rate values are passed through as raw strings
+(Binance returns them as strings); no float touches any value path.
+"""
+from __future__ import annotations
+
+import hashlib
+import hmac
+import json
+import time
+import urllib.error
+import urllib.request
+from typing import Any, Dict, Optional, Tuple
+
+# ---- deny-by-default whitelist: (method, exact-path) -> base URL (hardcoded) ----
+# This is the single source of truth for which private endpoints may be called.
+# Base URLs are bound here and are NOT overridable from config (anti-injection).
+WHITELIST: Dict[Tuple[str, str], str] = {
+    ("GET", "/sapi/v1/margin/allPairs"): "https://api.binance.com",
+    ("GET", "/sapi/v1/margin/allAssets"): "https://api.binance.com",
+    ("GET", "/sapi/v1/margin/crossMarginData"): "https://api.binance.com",
+    ("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
+}
+
+
+class PrivateEndpointError(Exception):
+    """Raised when a whitelisted private endpoint returns a non-2xx result.
+
+    Carries the sanitized logical path and HTTP status so the caller can record
+    a reason in ``borrow_validation.error`` without surfacing credentials.
+    """
+
+    def __init__(self, logical_path: str, status: Optional[int], reason: str):
+        self.logical_path = logical_path
+        self.status = status
+        self.reason = reason
+        super().__init__(f"{logical_path} failed: status={status} reason={reason}")
+
+
+class PrivateClient:
+    """The repo's only HMAC-SHA256 signing channel."""
+
+    def __init__(
+        self,
+        api_key: Optional[str],
+        api_secret: Optional[str],
+        *,
+        user_agent: str,
+        timeout: float,
+        recv_window: int,
+        ttl_seconds: int,
+    ):
+        self.api_key = api_key or ""
+        self.api_secret = api_secret or ""
+        self.enabled = bool(self.api_key and self.api_secret)
+        self._user_agent = user_agent
+        self._timeout = timeout
+        self._recv_window = recv_window
+        self._ttl = ttl_seconds
+        self.audit_log: list = []
+        self.last_error: Optional[str] = None
+        self._cache: Dict[Tuple[str, str, Tuple[Tuple[str, str], ...]], Tuple[float, Any]] = {}
+
+    # -- security gate (raises BEFORE any signature construction) --
+    @staticmethod
+    def _require_whitelisted(method: str, path: str) -> str:
+        if (method, path) not in WHITELIST:
+            raise PermissionError(f"private endpoint not whitelisted: {method} {path}")
+        if method != "GET":
+            raise PermissionError(f"private client is GET-only: {method} {path}")
+        return WHITELIST[(method, path)]
+
+    # -- single HMAC exit --
+    def _signed_get(
+        self,
+        method: str,
+        path: str,
+        params: Optional[Dict[str, str]] = None,
+        _retry: bool = True,
+    ) -> Any:
+        base = self._require_whitelisted(method, path)  # raises before signing
+        if not self.enabled:
+            raise RuntimeError("private client disabled (env missing)")
+        p = dict(params or {})
+        p["recvWindow"] = str(self._recv_window)
+        p["timestamp"] = str(int(time.time() * 1000))
+        qs = "&".join(f"{k}={v}" for k, v in sorted(p.items()))
+        signature = hmac.new(
+            self.api_secret.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256
+        ).hexdigest()
+        url = f"{base}{path}?{qs}&signature={signature}"
+        req = urllib.request.Request(
+            url,
+            headers={"X-MBX-APIKEY": self.api_key, "User-Agent": self._user_agent},
+            method="GET",
+        )
+        t0 = time.monotonic()
+        try:
+            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
+                body, status, err = resp.read().decode("utf-8"), resp.status, None
+        except urllib.error.HTTPError as exc:
+            body = exc.read().decode("utf-8", "replace")
+            status, err = exc.code, f"HTTP {exc.code}"
+        except Exception as exc:  # network / timeout / DNS
+            body, status, err = "", None, type(exc).__name__
+        latency = round((time.monotonic() - t0) * 1000, 1)
+        # audit log: sanitized path only; NO key/secret/signature/query/headers
+        self.audit_log.append(
+            {
+                "logical_endpoint": path,
+                "method": "GET",
+                "http_status": status,
+                "error": err,
+                "latency_ms": latency,
+            }
+        )
+        # bounded rate-limit backoff (one retry); failure raises -> caller degrades
+        if _retry and self._is_rate_limited(status, body):
+            time.sleep(0.5)
+            return self._signed_get(method, path, params, _retry=False)
+        if status is None or status >= 400:
+            raise PrivateEndpointError(path, status, err or "unknown")
+        return json.loads(body)
+
+    @staticmethod
+    def _is_rate_limited(status: Optional[int], body: str) -> bool:
+        if status == 429:
+            return True
+        if status == 400 and body:
+            try:
+                if json.loads(body).get("code") == -1003:
+                    return True
+            except (ValueError, TypeError):
+                pass
+        return False
+
+    def _cached_get(
+        self, method: str, path: str, params: Optional[Dict[str, str]] = None
+    ) -> Any:
+        key = (method, path, tuple(sorted((params or {}).items())))
+        now = time.monotonic()
+        cached = self._cache.get(key)
+        if cached and cached[0] > now:
+            return cached[1]
+        data = self._signed_get(method, path, params)
+        self._cache[key] = (now + self._ttl, data)
+        return data
+
+    # -- high-level fetchers (return None + set last_error on disable/failure) --
+    def fetch_classic_reference(self) -> Optional[Dict[str, Any]]:
+        """Market-level classic-margin reference (E2+E3+E4), 1h TTL.
+
+        Returns ``{"pair_listed_by_symbol", "asset_borrowable_by_name",
+        "daily_interest_vip0_by_coin"}`` or ``None`` (disabled/failed). On
+        failure sets ``last_error``; caller records verified=false.
+        """
+        if not self.enabled:
+            self.last_error = "private_channel_disabled"
+            return None
+        try:
+            all_pairs = self._cached_get("GET", "/sapi/v1/margin/allPairs")
+            all_assets = self._cached_get("GET", "/sapi/v1/margin/allAssets")
+            cross = self._cached_get("GET", "/sapi/v1/margin/crossMarginData")
+        except PrivateEndpointError as exc:
+            self.last_error = f"classic_reference_failed:{exc.logical_path}:{exc.reason}"
+            return None
+        return {
+            "pair_listed_by_symbol": {
+                x.get("symbol"): bool(x.get("isMarginTrade")) for x in all_pairs
+            },
+            "asset_borrowable_by_name": {
+                x.get("assetName"): bool(x.get("isBorrowable")) for x in all_assets
+            },
+            "daily_interest_vip0_by_coin": {
+                x.get("coin"): x.get("dailyInterest")
+                for x in cross
+                if str(x.get("vipLevel")) == "0"
+            },
+        }
+
+    def fetch_max_borrowable(self, asset: str) -> Optional[Dict[str, Optional[str]]]:
+        """Account-level maxBorrowable for one asset (E5), 1h TTL.
+
+        Returns ``{"max_borrowable", "borrow_limit"}`` (raw strings) or ``None``
+        (disabled/failed). On failure sets ``last_error``.
+        """
+        if not self.enabled:
+            return None
+        try:
+            data = self._cached_get(
+                "GET", "/papi/v1/margin/maxBorrowable", {"asset": asset}
+            )
+        except PrivateEndpointError as exc:
+            self.last_error = f"max_borrowable_failed:{asset}:{exc.reason}"
+            return None
+        return {
+            "max_borrowable": data.get("amount"),
+            "borrow_limit": data.get("borrowLimit"),
+        }
diff --git a/backend/services/snapshot_service.py b/backend/services/snapshot_service.py
index 92b0857..83618cc 100644
--- a/backend/services/snapshot_service.py
+++ b/backend/services/snapshot_service.py
@@ -8,6 +8,7 @@ failure it raises and the caller maps that to HTTP 503.
 from __future__ import annotations
 
 import json
+import os
 import time
 from datetime import datetime, timezone
 from typing import Optional
@@ -18,10 +19,13 @@ from ..adapters.binance_public import BinancePublicClient
 from ..config import Config, FROZEN_GENERATED_AT, FROZEN_SOURCE_SAMPLE_ID
 from ..domain.normalize import iso_from_ms
 from ..domain.snapshot import (
+    assemble_borrow_validation,
     assemble_snapshot,
     build_rows,
+    sort_rows,
     top_symbols_by_abs_rate,
 )
+from ..services.private_client import PrivateClient
 
 ELIGIBLE_CONTRACT_TYPES = ("PERPETUAL", "TRADIFI_PERPETUAL")
 
@@ -39,6 +43,23 @@ class SnapshotService:
         )
         self._cache = None  # (monotonic, snapshot)
         self._schema = None
+        # Private borrow-validation client (the repo's single HMAC exit). Offline
+        # mode never touches the private channel (no key, no network) -> every row
+        # degrades to verified=false. Live mode reads key/secret from env; missing
+        # -> enabled=False -> same verified=false degradation.
+        if config.offline:
+            _api_key = _api_secret = None
+        else:
+            _api_key = os.environ.get("BINANCE_API_KEY")
+            _api_secret = os.environ.get("BINANCE_API_SECRET")
+        self._private = PrivateClient(
+            api_key=_api_key,
+            api_secret=_api_secret,
+            user_agent=config.user_agent,
+            timeout=config.request_timeout,
+            recv_window=config.private_recv_window,
+            ttl_seconds=config.private_channel_ttl_seconds,
+        )
 
     def _load_schema(self):
         if self._schema is None:
@@ -70,6 +91,7 @@ class SnapshotService:
             s["symbol"]: s for s in raw["spot_exchange_info"].get("symbols", [])
         }
         funding_by_sym = dict(raw.get("funding_history_by_sym", {}))
+        funding_interval_by_sym = raw.get("funding_interval_by_sym", {})
 
         if not self.client.offline:
             # Top-N bounds LIVE /fapi/v1/fundingRate call volume. Offline uses
@@ -82,8 +104,50 @@ class SnapshotService:
                     funding_by_sym[sym] = self.client.fetch_funding_rate(sym)
 
         rows = build_rows(
-            futures_symbols, premium_by_sym, spot_by_sym, funding_by_sym
+            futures_symbols,
+            premium_by_sym,
+            spot_by_sym,
+            funding_by_sym,
+            funding_interval_by_sym=funding_interval_by_sym,
         )
+        rows = sort_rows(rows)
+
+        # Private borrow-validation channel (single HMAC exit, deny-by-default).
+        # Disabled (env missing) or endpoint failure -> classic_ref None -> every
+        # row verified=false with null data fields; the public snapshot still renders.
+        classic_ref = self._private.fetch_classic_reference()
+        private_channel_status = "enabled" if classic_ref is not None else "disabled"
+        private_error = self._private.last_error if classic_ref is None else None
+        checked_at = (
+            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
+            if classic_ref is not None
+            else None
+        )
+
+        # E5 account-level maxBorrowable is bounded to the top-N
+        # MARGIN_SPOT_CANDIDATE + CRYPTO baseAssets by abs daily rate (rows are
+        # already sorted DESC). bStock rows are excluded (asset_tag != CRYPTO);
+        # their portfolio_account amount fields stay null.
+        bounded_assets = [
+            r["base_asset"]
+            for r in rows
+            if r["route_class"] == "MARGIN_SPOT_CANDIDATE"
+            and r["asset_tag"] == "CRYPTO"
+        ][: self.config.borrow_check_top_n]
+        portfolio_by_asset: dict = {}
+        for asset in bounded_assets:
+            if asset in portfolio_by_asset:
+                continue
+            res = self._private.fetch_max_borrowable(asset)
+            portfolio_by_asset[asset] = res or {
+                "max_borrowable": None,
+                "borrow_limit": None,
+            }
+
+        for row in rows:
+            row["borrow_validation"] = assemble_borrow_validation(
+                row, classic_ref, portfolio_by_asset, checked_at, private_error
+            )
 
         data_time_ms = max((p.get("time", 0) for p in raw["premium_index"]), default=0)
         if self.client.offline:
@@ -99,6 +163,7 @@ class SnapshotService:
             generated_at=generated_at,
             data_time=iso_from_ms(data_time_ms),
             source_sample_id=source_sample_id,
+            private_channel_status=private_channel_status,
         )
 
     def request_log(self) -> dict:
diff --git a/backend/tests/test_phase2_borrow_sort.py b/backend/tests/test_phase2_borrow_sort.py
new file mode 100644
index 0000000..c5b0649
--- /dev/null
+++ b/backend/tests/test_phase2_borrow_sort.py
@@ -0,0 +1,286 @@
+"""Phase 2 tests: fundingInfo daily-rate + row sort + borrow_validation.
+
+Covers 10-design §3.3 (daily-rate vectors), §1.2 (deterministic total order),
+§1.3 (three-state borrow_validation), §3.4 (bounded portfolio set), and §3.5
+(schema v0.2 validation, disabled-channel degradation, offline 8h default, and
+v0.1-fixture backward compatibility). The §3.2 security-gate negative tests live
+in ``test_private_client.py``.
+"""
+from __future__ import annotations
+
+from decimal import Decimal
+
+import jsonschema
+import pytest
+
+from backend.config import Config
+from backend.domain.snapshot import (
+    assemble_borrow_validation,
+    build_rows,
+    compute_daily_funding_rate,
+    sort_rows,
+)
+from backend.services.snapshot_service import SnapshotService
+
+ELIGIBLE = ("PERPETUAL", "TRADIFI_PERPETUAL")
+
+
+def _eligible(futures):
+    return [
+        s for s in futures["symbols"] if s["status"] == "TRADING" and s["contractType"] in ELIGIBLE
+    ]
+
+
+def _row(sym, daily, base=None):
+    return {"symbol": sym, "base_asset": base or sym.replace("USDT", ""), "daily_funding_rate": daily}
+
+
+# --- §3.3 daily-rate vectors (10-design table) ---
+@pytest.mark.parametrize(
+    "rate,interval,expected",
+    [
+        ("0.00010000", 8, "0.00030000"),
+        ("0.00010000", 4, "0.00060000"),
+        ("-0.00005000", 4, "-0.00030000"),
+        ("0.00002000", 1, "0.00048000"),
+        ("-0.00000000", 8, "0.00000000"),  # negative-zero normalization
+        ("", 8, None),
+        (None, 8, None),
+    ],
+)
+def test_daily_funding_rate_vectors(rate, interval, expected):
+    assert compute_daily_funding_rate(rate, interval) == expected
+
+
+def test_daily_funding_rate_no_float_no_scientific():
+    out = compute_daily_funding_rate("0.00002000", 1)
+    assert out == "0.00048000"
+    assert "e" not in out.lower()
+    # A tiny rate that would render in scientific notation if a float ever touched it.
+    assert compute_daily_funding_rate("0.00000001", 8) == "0.00000003"
+    assert compute_daily_funding_rate("0.00000001", 4) == "0.00000006"
+
+
+def test_daily_funding_rate_bad_input_is_none():
+    assert compute_daily_funding_rate("not-a-number", 8) is None
+    assert compute_daily_funding_rate("0.0001", 0) is None  # non-positive interval
+    assert compute_daily_funding_rate("0.0001", -4) is None
+
+
+# --- §1.2 deterministic total order ---
+def test_sort_abs_daily_desc_nulls_last_symbol_tiebreak():
+    rows = [
+        _row("DUSDT", None),           # null -> last
+        _row("CUSDT", "-0.00030000"),  # abs 0.0003
+        _row("AUSDT", "0.00060000"),   # abs 0.0006 (highest)
+        _row("BUSDT", "0.00060000"),   # abs 0.0006, tie -> symbol ASC (B after A)
+        _row("EUSDT", "0.00030000"),   # abs 0.0003, tie with C -> symbol ASC (E after C)
+    ]
+    assert [r["symbol"] for r in sort_rows(rows)] == ["AUSDT", "BUSDT", "CUSDT", "EUSDT", "DUSDT"]
+
+
+def test_sort_single_period_lower_but_daily_higher_ranks_first():
+    # 10-design §4.3 fixture invariant: A's single-period rate is lower than B's,
+    # but A's daily rate is higher (shorter interval) -> A ranks first.
+    rows = [
+        _row("BUSDT", "0.00045000"),  # 0.00015 x3
+        _row("AUSDT", "0.00060000"),  # 0.00010 x6 -> higher daily
+    ]
+    assert sort_rows(rows)[0]["symbol"] == "AUSDT"
+
+
+def test_sort_all_null_keeps_symbol_asc():
+    rows = [_row("ZUSDT", None), _row("AUSDT", None), _row("MUSDT", None)]
+    assert [r["symbol"] for r in sort_rows(rows)] == ["AUSDT", "MUSDT", "ZUSDT"]
+
+
+def test_sort_does_not_mutate_input():
+    rows = [_row("BUSDT", "0.0001"), _row("AUSDT", "0.0009")]
+    original = [r["symbol"] for r in rows]
+    sort_rows(rows)
+    assert [r["symbol"] for r in rows] == original  # returns a new list
+
+
+# --- §1.3 three-state borrow_validation semantics ---
+_CLASSIC_LISTED = {
+    "pair_listed_by_symbol": {"BTCUSDT": True, "ETHUSDT": False},
+    "asset_borrowable_by_name": {"BTC": True},
+    "daily_interest_vip0_by_coin": {"BTC": "0.0005"},
+}
+
+
+def test_borrow_validation_disabled_state():
+    bv = assemble_borrow_validation(
+        {"symbol": "BTCUSDT", "base_asset": "BTC"}, None, {}, None, "private_channel_disabled"
+    )
+    assert bv["verified"] is False
+    assert bv["classic_margin"]["pair_listed"] is None
+    assert bv["classic_margin"]["asset_borrowable"] is None
+    assert bv["classic_margin"]["daily_interest_vip0"] is None
+    assert bv["portfolio_account"]["max_borrowable"] is None
+    assert bv["portfolio_account"]["borrow_limit"] is None
+    assert bv["checked_at"] is None
+    assert bv["error"] == "private_channel_disabled"
+    assert bv["classic_margin"]["source"] == "sapi_reference"
+    assert bv["portfolio_account"]["source"] == "papi_max_borrowable"
+
+
+def test_borrow_validation_verified_not_listed_data_null():
+    bv = assemble_borrow_validation(
+        {"symbol": "ETHUSDT", "base_asset": "ETH"}, _CLASSIC_LISTED, {}, "2026-07-04T13:00:00Z", None
+    )
+    assert bv["verified"] is True
+    assert bv["classic_margin"]["pair_listed"] is False
+    # pair not listed -> asset/interest null even though other coins have data
+    assert bv["classic_margin"]["asset_borrowable"] is None
+    assert bv["classic_margin"]["daily_interest_vip0"] is None
+    assert bv["checked_at"] == "2026-07-04T13:00:00Z"
+    assert bv["error"] is None
+
+
+def test_borrow_validation_verified_listed_carries_data():
+    bv = assemble_borrow_validation(
+        {"symbol": "BTCUSDT", "base_asset": "BTC"}, _CLASSIC_LISTED, {}, "2026-07-04T13:00:00Z", None
+    )
+    assert bv["verified"] is True
+    assert bv["classic_margin"]["pair_listed"] is True
+    assert bv["classic_margin"]["asset_borrowable"] is True
+    assert bv["classic_margin"]["daily_interest_vip0"] == "0.0005"
+
+
+def test_borrow_validation_portfolio_bounded_only():
+    portfolio = {"BTC": {"max_borrowable": "1.5", "borrow_limit": "60"}}
+    btc = assemble_borrow_validation(
+        {"symbol": "BTCUSDT", "base_asset": "BTC"}, _CLASSIC_LISTED, portfolio, "t", None
+    )
+    eth = assemble_borrow_validation(
+        {"symbol": "ETHUSDT", "base_asset": "ETH"}, _CLASSIC_LISTED, portfolio, "t", None
+    )
+    assert btc["portfolio_account"]["max_borrowable"] == "1.5"
+    assert btc["portfolio_account"]["borrow_limit"] == "60"
+    # ETH is outside the bounded set -> null amounts, block still present
+    assert eth["portfolio_account"]["max_borrowable"] is None
+    assert eth["portfolio_account"]["borrow_limit"] is None
+    assert eth["portfolio_account"]["source"] == "papi_max_borrowable"
+
+
+def test_borrow_validation_portfolio_failed_endpoint_null_amounts():
+    # bounded candidate whose maxBorrowable call failed -> None amounts recorded
+    portfolio = {"BTC": {"max_borrowable": None, "borrow_limit": None}}
+    bv = assemble_borrow_validation(
+        {"symbol": "BTCUSDT", "base_asset": "BTC"}, _CLASSIC_LISTED, portfolio, "t", None
+    )
+    assert bv["verified"] is True
+    assert bv["portfolio_account"]["max_borrowable"] is None
+    assert bv["portfolio_account"]["borrow_limit"] is None
+
+
+def test_borrow_validation_each_state_validates_in_full_snapshot(schema):
+    # borrow_validation always lives inside a row, so validate each state through
+    # a full snapshot (not the isolated $def, whose $ref to $defs/decimal_string
+    # only resolves under the root schema).
+    snap = SnapshotService(Config(offline=True)).build_snapshot()
+    rows = snap["rows"]
+    # state 1 (disabled) is the offline default -> snapshot already valid.
+    jsonschema.validate(snap, schema)
+
+    # state 3: verified, listed + bounded portfolio on a known symbol.
+    btc = next((r for r in rows if r["symbol"] == "BTCUSDT"), rows[0])
+    listed = {
+        "pair_listed_by_symbol": {btc["symbol"]: True},
+        "asset_borrowable_by_name": {btc["base_asset"]: True},
+        "daily_interest_vip0_by_coin": {btc["base_asset"]: "0.0005"},
+    }
+    btc["borrow_validation"] = assemble_borrow_validation(
+        btc, listed, {btc["base_asset"]: {"max_borrowable": "1.5", "borrow_limit": "60"}}, "t", None
+    )
+
+    # state 2: verified, not listed on a different row.
+    other = next((r for r in rows if r is not btc), None)
+    if other is not None:
+        not_listed = {
+            "pair_listed_by_symbol": {other["symbol"]: False},
+            "asset_borrowable_by_name": {},
+            "daily_interest_vip0_by_coin": {},
+        }
+        other["borrow_validation"] = assemble_borrow_validation(other, not_listed, {}, "t", None)
+
+    jsonschema.validate(snap, schema)
+
+
+# --- schema v0.2 validates a full Phase-2 snapshot (offline) ---
+def test_offline_full_snapshot_validates_v02_schema(schema):
+    snap = SnapshotService(Config(offline=True)).build_snapshot()
+    jsonschema.validate(snap, schema)
+    assert snap["private_channel"] == "disabled"
+    assert snap["rows"]
+    for r in snap["rows"]:
+        assert r["funding_interval_hours"] in (1, 4, 8)
+        assert isinstance(r["daily_funding_rate"], (str, type(None)))
+        bv = r["borrow_validation"]
+        assert set(bv) == {"verified", "classic_margin", "portfolio_account", "checked_at", "error"}
+        assert set(bv["classic_margin"]) == {
+            "pair_listed",
+            "asset_borrowable",
+            "daily_interest_vip0",
+            "source",
+        }
+        assert set(bv["portfolio_account"]) == {"max_borrowable", "borrow_limit", "source"}
+
+
+def test_offline_private_channel_disabled_all_rows_verified_false():
+    snap = SnapshotService(Config(offline=True)).build_snapshot()
+    assert snap["private_channel"] == "disabled"
+    for r in snap["rows"]:
+        bv = r["borrow_validation"]
+        assert bv["verified"] is False
+        assert bv["classic_margin"]["pair_listed"] is None
+        assert bv["portfolio_account"]["max_borrowable"] is None
+        assert bv["checked_at"] is None
+        assert bv["error"] == "private_channel_disabled"
+
+
+def test_offline_build_rows_defaults_8h_without_funding_info(raw_inputs):
+    # The offline raw dir has no fundingInfo sample -> every row defaults to 8h.
+    elig = _eligible(raw_inputs["futures"])
+    premium = {p["symbol"]: p for p in raw_inputs["premium"]}
+    spot = {s["symbol"]: s for s in raw_inputs["spot"]["symbols"]}
+    rows = build_rows(elig, premium, spot, raw_inputs["funding"])  # no interval map
+    assert rows
+    assert all(r["funding_interval_hours"] == 8 for r in rows)
+    assert all(isinstance(r["daily_funding_rate"], (str, type(None))) for r in rows)
+
+
+def test_offline_snapshot_rows_sorted_abs_daily_desc_nulls_last():
+    snap = SnapshotService(Config(offline=True)).build_snapshot()
+    daily = [r["daily_funding_rate"] for r in snap["rows"]]
+
+    def absv(d):
+        return None if d is None else abs(Decimal(d))
+
+    absvals = [absv(d) for d in daily]
+    non_null = [a for a in absvals if a is not None]
+    # non-null prefix is non-increasing (abs daily DESC)
+    assert all(non_null[i] >= non_null[i + 1] for i in range(len(non_null) - 1))
+    # nulls (if any) are all after the non-null prefix
+    if None in absvals:
+        first_null = absvals.index(None)
+        assert all(a is None for a in absvals[first_null:])
+
+
+def test_offline_get_snapshot_no_private_http_and_cached(schema):
+    # Offline private channel is disabled in __init__, so no signed HTTP fires;
+    # the public client also performs no HTTP offline. Snapshot is cached.
+    service = SnapshotService(Config(offline=True, cache_ttl_seconds=60))
+    first = service.get_snapshot()
+    second = service.get_snapshot()
+    assert first is second
+    assert service.request_log() == {}
+    jsonschema.validate(first, schema)
+
+
+# --- v0.1 frozen fixture stays valid under v0.2 schema (additive amendment) ---
+def test_frozen_v01_normalized_validates_under_v02_schema(schema, frozen_normalized):
+    # The v0.1 fixture has none of the v0.2 fields; they are all optional, so it
+    # must still validate. Locks the additive-only / backward-compatible guarantee.
+    jsonschema.validate(frozen_normalized, schema)
diff --git a/backend/tests/test_private_client.py b/backend/tests/test_private_client.py
new file mode 100644
index 0000000..d55cee4
--- /dev/null
+++ b/backend/tests/test_private_client.py
@@ -0,0 +1,230 @@
+"""Negative tests for private_client security gates (10-design §3.2).
+
+No network: ``urlopen`` is monkeypatched. Asserts the single-HMAC exit,
+deny-by-default whitelist, GET-only, gate-fires-before-signing, env-missing
+degradation, audit-log credential hygiene, bounded rate-limit backoff, and
+that no private-domain path appears outside private_client.py.
+"""
+from __future__ import annotations
+
+import io
+import json
+import re
+from pathlib import Path
+
+import pytest
+import urllib.error
+import urllib.request
+
+from backend.services import private_client
+from backend.services.private_client import PrivateClient, PrivateEndpointError
+
+REPO_ROOT = Path(__file__).resolve().parents[2]
+BACKEND_DIR = REPO_ROOT / "backend"
+
+_HMAC_RE = re.compile(r"\bhmac\b")
+_HASHLIB_RE = re.compile(r"hashlib")
+_SIGNATURE_ASSIGN_RE = re.compile(r"signature\s*=")
+
+
+class _FakeResp:
+    def __init__(self, body: str, status: int):
+        self._body = body.encode("utf-8")
+        self.status = status
+
+    def read(self):
+        return self._body
+
+    def __enter__(self):
+        return self
+
+    def __exit__(self, *exc):
+        return False
+
+
+def _make_client(monkeypatch, responses, *, enabled=True):
+    """PrivateClient whose urlopen yields `responses` in order.
+
+    Each item is either a (body_str, status_int) tuple or an HTTPError to raise.
+    """
+    key = "k" * 64 if enabled else None
+    secret = "s" * 64 if enabled else None
+    client = PrivateClient(
+        key, secret, user_agent="test/1.0", timeout=5,
+        recv_window=10000, ttl_seconds=3600,
+    )
+    it = iter(responses)
+
+    def fake_urlopen(req, timeout=None):
+        item = next(it)
+        if isinstance(item, urllib.error.HTTPError):
+            raise item
+        body, status = item
+        return _FakeResp(body, status)
+
+    monkeypatch.setattr(private_client.urllib.request, "urlopen", fake_urlopen)
+    monkeypatch.setattr(private_client.time, "sleep", lambda *_: None)  # no real sleeps
+    return client
+
+
+def _http_error(code: int, body: str) -> urllib.error.HTTPError:
+    return urllib.error.HTTPError(
+        "https://example.invalid", code, "err", {}, io.BytesIO(body.encode("utf-8"))
+    )
+
+
+# ---- 1. single HMAC exit (grep-level over product code) ----
+def test_single_hmac_exit_in_product_code():
+    """No product module other than private_client.py touches hmac/hashlib/signature."""
+    bad = []
+    for py in BACKEND_DIR.rglob("*.py"):
+        rel = py.relative_to(REPO_ROOT)
+        if "tests" in rel.parts or rel.name == "private_client.py":
+            continue
+        text = py.read_text(encoding="utf-8")
+        if _HMAC_RE.search(text) or _HASHLIB_RE.search(text) or _SIGNATURE_ASSIGN_RE.search(text):
+            bad.append(str(rel))
+    assert bad == [], f"hmac/hashlib/signature found outside private_client.py: {bad}"
+
+
+def test_urlopen_only_in_designated_http_clients():
+    """Direct-HTTP guard: only private_client.py and binance_public.py may call
+    urlopen, so no other product module can bypass them to hit Binance directly
+    (with or without a signature)."""
+    allowed = {"private_client.py", "binance_public.py"}
+    bad = []
+    for py in BACKEND_DIR.rglob("*.py"):
+        rel = py.relative_to(REPO_ROOT)
+        if "tests" in rel.parts or rel.name in allowed:
+            continue
+        if "urlopen" in py.read_text(encoding="utf-8"):
+            bad.append(str(rel))
+    assert bad == [], f"urlopen found outside the two HTTP clients: {bad}"
+
+
+# ---- 2. deny-by-default whitelist + GET-only ----
+def test_whitelist_rejects_unknown_path():
+    with pytest.raises(PermissionError):
+        PrivateClient._require_whitelisted("GET", "/sapi/v1/margin/forbidden")
+
+
+def test_whitelist_rejects_non_get_on_whitelisted_path():
+    with pytest.raises(PermissionError):
+        PrivateClient._require_whitelisted("POST", "/sapi/v1/margin/allPairs")
+
+
+def test_whitelist_rejects_delete_on_whitelisted_path():
+    with pytest.raises(PermissionError):
+        PrivateClient._require_whitelisted("DELETE", "/papi/v1/margin/maxBorrowable")
+
+
+def test_whitelist_accepts_exactly_four_get_endpoints():
+    assert len(private_client.WHITELIST) == 4
+    for method, path in private_client.WHITELIST:
+        assert method == "GET"
+        assert PrivateClient._require_whitelisted(method, path)
+
+
+def test_whitelist_matches_status_json_endpoint_whitelist():
+    """The four whitelisted pairs must equal status.json endpoint_whitelist."""
+    import json as _json
+    status = _json.loads(
+        (REPO_ROOT / "reports/agent-runs/2026-07-phase2-borrow-sort-v1/status.json").read_text()
+    )
+    expected = {tuple(pair) for pair in status["endpoint_whitelist"]}
+    assert set(private_client.WHITELIST.keys()) == expected
+
+
+# ---- 3. gate fires BEFORE signature construction ----
+def test_gate_fires_before_signature_construction(monkeypatch):
+    """An unknown path must raise without ever calling urlopen (no signature sent)."""
+    client = _make_client(monkeypatch, [])  # empty: reaching urlopen would StopIteration
+    with pytest.raises(PermissionError):
+        client._signed_get("GET", "/sapi/v1/margin/forbidden")
+
+
+# ---- 4. env-missing degradation ----
+def test_disabled_when_env_missing():
+    client = PrivateClient(
+        None, None, user_agent="t", timeout=5, recv_window=10000, ttl_seconds=3600,
+    )
+    assert client.enabled is False
+    assert client.fetch_classic_reference() is None
+    assert client.fetch_max_borrowable("BTC") is None
+    assert client.last_error == "private_channel_disabled"
+
+
+# ---- 5. audit-log credential hygiene ----
+def test_audit_log_has_no_credentials(monkeypatch):
+    client = _make_client(monkeypatch, [
+        (json.dumps([{"symbol": "BTCUSDT", "isMarginTrade": True}]), 200),  # allPairs
+        ("[]", 200),  # allAssets
+        ("[]", 200),  # crossMarginData
+    ])
+    client.fetch_classic_reference()
+    blob = json.dumps(client.audit_log)
+    assert "k" * 64 not in blob  # real key never appears
+    assert "s" * 64 not in blob  # real secret never appears
+    for entry in client.audit_log:
+        # only sanitized fields; no query string, no signature, no headers
+        assert set(entry.keys()) == {
+            "logical_endpoint", "method", "http_status", "error", "latency_ms",
+        }
+        assert "=" not in entry["logical_endpoint"]
+        assert "signature" not in entry["logical_endpoint"].lower()
+
+
+# ---- 6. bounded rate-limit backoff (retry once, then succeed) ----
+def test_rate_limit_backoff_retries_once_then_succeeds(monkeypatch):
+    client = _make_client(monkeypatch, [
+        (json.dumps({"code": -1003, "msg": "busy"}), 400),  # first: rate-limited
+        (json.dumps({"amount": "1.0", "borrowLimit": "60"}), 200),  # retry succeeds
+    ])
+    result = client.fetch_max_borrowable("BTC")
+    assert result == {"max_borrowable": "1.0", "borrow_limit": "60"}
+    assert len(client.audit_log) == 2  # both attempts logged
+
+
+def test_rate_limit_429_also_retries(monkeypatch):
+    client = _make_client(monkeypatch, [
+        ('{"code":-1003,"msg":"x"}', 429),
+        (json.dumps({"amount": "2", "borrowLimit": "5"}), 200),
+    ])
+    assert client.fetch_max_borrowable("ETH") == {"max_borrowable": "2", "borrow_limit": "5"}
+
+
+# ---- 7. endpoint failure -> caller degrades (None + last_error) ----
+def test_classic_reference_degrades_on_endpoint_failure(monkeypatch):
+    client = _make_client(monkeypatch, [_http_error(403, '{"code":-2014}')])  # allPairs 403
+    assert client.fetch_classic_reference() is None
+    assert client.last_error.startswith("classic_reference_failed")
+
+
+def test_max_borrowable_degrades_on_endpoint_failure(monkeypatch):
+    client = _make_client(monkeypatch, [_http_error(401, '{"code":-2015}')])
+    assert client.fetch_max_borrowable("BTC") is None
+    assert client.last_error.startswith("max_borrowable_failed:BTC")
+
+
+# ---- 8. happy-path classic reference mapping (raw camelCase -> snake_case dict) ----
+def test_classic_reference_maps_raw_fields(monkeypatch):
+    client = _make_client(monkeypatch, [
+        (json.dumps([{"symbol": "BTCUSDT", "isMarginTrade": True},
+                     {"symbol": "FOOUSDT", "isMarginTrade": False}]), 200),
+        (json.dumps([{"assetName": "BTC", "isBorrowable": True}]), 200),
+        (json.dumps([{"coin": "BTC", "vipLevel": 0, "dailyInterest": "0.0005"},
+                     {"coin": "BTC", "vipLevel": 1, "dailyInterest": "0.0004"}]), 200),
+    ])
+    ref = client.fetch_classic_reference()
+    assert ref == {
+        "pair_listed_by_symbol": {"BTCUSDT": True, "FOOUSDT": False},
+        "asset_borrowable_by_name": {"BTC": True},
+        "daily_interest_vip0_by_coin": {"BTC": "0.0005"},  # only vipLevel 0
+    }
+
+
+def test_max_borrowable_maps_raw_fields(monkeypatch):
+    client = _make_client(monkeypatch, [
+        (json.dumps({"amount": "1.5", "borrowLimit": "60"}), 200),
+    ])
+    assert client.fetch_max_borrowable("BTC") == {"max_borrowable": "1.5", "borrow_limit": "60"}
diff --git a/docs/api/public-market-contract.md b/docs/api/public-market-contract.md
index 1301781..bc66803 100644
--- a/docs/api/public-market-contract.md
+++ b/docs/api/public-market-contract.md
@@ -1,6 +1,8 @@
 # Public Market API Contract
 
-Status: contract v0.1, response shape unchanged. Binance public fields verified
+Status: contract v0.2 (Phase 2 amendment, additive). The v0.1 response shape is
+preserved; the Phase 2 additions are documented in "Phase 2 Amendment (v0.2)" at
+the end of this file. Binance public fields verified
 2026-07-03 by Claude-GLM against live no-key public calls and `llms-full.txt`.
 Verified findings are recorded below in "Verified Findings" and in
 `reports/agent-runs/2026-07-public-market-contract-v2/api-field-matrix.md`.
@@ -298,3 +300,71 @@ Remaining (non-blocking, later phase):
 
 - Settle-time sample to remove the `lastFundingRate` ambiguity.
 - Private borrowability validation for `MARGIN_SPOT_CANDIDATE`.
+
+## Phase 2 Amendment (v0.2, stage `2026-07-phase2-borrow-sort-v1`)
+
+Frozen 2026-07-04. Response shape extended additively (backward-compatible: the
+v0.1 field set and enums are unchanged). Evidence: H_intake discovery under
+`reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/`
+(`evidence-index.md` + sha256 table + redacted samples); raw-field freeze in
+`reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md §2.A`.
+
+### New public row fields
+
+- `funding_interval_hours`: int ∈ {1, 4, 8}. Source `GET /fapi/v1/fundingInfo`
+  (public, no key). Symbols listed in the response use their
+  `fundingIntervalHours`; unlisted symbols default to 8 (Binance default). Offline
+  mode (no frozen fundingInfo sample) -> all symbols 8h.
+- `daily_funding_rate`: string (8-place, same format as `last_funding_rate`) or
+  null. Computed `Decimal(lastFundingRate) × (24 / interval)` — Decimal-only, no
+  float; `quantize(Decimal('1E-8'))`, no scientific notation; negative zero is
+  normalized to `0.00000000`. Missing/empty `lastFundingRate` -> null.
+
+### Row order (frozen)
+
+`rows` are returned sorted by `abs(Decimal(daily_funding_rate))` DESC; rows with
+null `daily_funding_rate` sort last; ties break by `symbol` ASC. This is a
+deterministic total order and IS the payload order. The frontend must not reorder
+(filters only hide).
+
+### New private block `borrow_validation` (frontend does not consume this stage)
+
+Three states:
+
+1. private channel disabled or request failed: `verified=false`, all data fields
+   null, `error` carries the reason;
+2. verified, pair not in the classic list: `verified=true`, `pair_listed=false`,
+   asset/interest fields null;
+3. verified, pair listed: `verified=true`, `pair_listed=true` + asset/interest.
+
+`checked_at` is the request-success moment (not the data-effective moment). All
+numeric fields are strings.
+
+`portfolio_account` is populated only for the bounded candidate set — the top-N
+`MARGIN_SPOT_CANDIDATE` + `CRYPTO` baseAssets by abs daily rate (default N=10,
+`Config.borrow_check_top_n`). Other rows keep null amount fields (the block is
+still present with its `source`). bStock rows are excluded from account-level
+probing (`asset_tag != CRYPTO`).
+
+Raw-to-contract field mapping (raw camelCase -> contract snake_case; raw key
+names frozen in 10-design §2.A — note E3 keys on `assetName`, E4 on `coin`, not
+`asset`):
+
+- `classic_margin.pair_listed` <- `allPairs[].isMarginTrade` (matched by symbol);
+- `classic_margin.asset_borrowable` <- `allAssets[].isBorrowable` (key `assetName`);
+- `classic_margin.daily_interest_vip0` <- `crossMarginData[].dailyInterest` where
+  `vipLevel == 0` (key `coin`); only the VIP0 tier is present in the captured
+  account shape;
+- `portfolio_account.max_borrowable` <- `maxBorrowable.amount`;
+- `portfolio_account.borrow_limit` <- `maxBorrowable.borrowLimit`.
+
+### Snapshot metadata
+
+- `private_channel` (top-level): `"enabled"` | `"disabled"`. `"enabled"` iff the
+  private borrow-validation channel returned a classic reference.
+
+### Regression red lines (unchanged)
+
+`negative_funding_status` / `route_class` / `asset_tag` enums and their priority
+order, `classify.py`, and `normalize.py` are unchanged. `borrow_validation` is a
+parallel output block and never alters classification or route derivation.
diff --git a/schemas/api/public-market/snapshot.schema.json b/schemas/api/public-market/snapshot.schema.json
index 888d8b9..488b798 100644
--- a/schemas/api/public-market/snapshot.schema.json
+++ b/schemas/api/public-market/snapshot.schema.json
@@ -65,6 +65,10 @@
       "items": {
         "type": "string"
       }
+    },
+    "private_channel": {
+      "type": "string",
+      "enum": ["enabled", "disabled"]
     }
   },
   "$defs": {
@@ -287,8 +291,67 @@
           "items": {
             "type": "string"
           }
+        },
+        "funding_interval_hours": {
+          "type": "integer",
+          "enum": [1, 4, 8]
+        },
+        "daily_funding_rate": {
+          "anyOf": [
+            { "$ref": "#/$defs/decimal_string" },
+            { "type": "null" }
+          ]
+        },
+        "borrow_validation": {
+          "$ref": "#/$defs/borrow_validation"
         }
       }
+    },
+    "borrow_validation": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["verified", "classic_margin", "portfolio_account", "checked_at", "error"],
+      "properties": {
+        "verified": { "type": "boolean" },
+        "classic_margin": {
+          "type": "object",
+          "additionalProperties": false,
+          "required": ["pair_listed", "asset_borrowable", "daily_interest_vip0", "source"],
+          "properties": {
+            "pair_listed": { "type": ["boolean", "null"] },
+            "asset_borrowable": { "type": ["boolean", "null"] },
+            "daily_interest_vip0": {
+              "anyOf": [
+                { "$ref": "#/$defs/decimal_string" },
+                { "type": "null" }
+              ]
+            },
+            "source": { "type": "string" }
+          }
+        },
+        "portfolio_account": {
+          "type": "object",
+          "additionalProperties": false,
+          "required": ["max_borrowable", "borrow_limit", "source"],
+          "properties": {
+            "max_borrowable": {
+              "anyOf": [
+                { "$ref": "#/$defs/decimal_string" },
+                { "type": "null" }
+              ]
+            },
+            "borrow_limit": {
+              "anyOf": [
+                { "$ref": "#/$defs/decimal_string" },
+                { "type": "null" }
+              ]
+            },
+            "source": { "type": "string" }
+          }
+        },
+        "checked_at": { "type": ["string", "null"] },
+        "error": { "type": ["string", "null"] }
+      }
     }
   }
 }
Diff output truncated; can read full via output_path if needed, but we saw key backend diff. Need inspect schema and contract diffs. Also check frontend? Task A review only backend/schemas/docs/api. Need verify contract tail. Also maybe check 11-adr etc. Need inspect snapshot.schema.json.total 744
drwxr-xr-x@ 9 ark  staff     288  7月  4 21:34 .
drwxr-xr-x@ 3 ark  staff      96  7月  4 21:34 ..
-rw-r--r--@ 1 ark  staff    2585  7月  4 21:34 evidence-index.md
-rw-r--r--@ 1 ark  staff  121424  7月  4 21:34 fapi-v1-fundingInfo.json
-rw-r--r--@ 1 ark  staff      55  7月  4 21:34 papi-v1-margin-maxBorrowable-BTC.json
-rw-r--r--@ 1 ark  staff      55  7月  4 21:34 papi-v1-margin-maxBorrowable-ETH.json
-rw-r--r--@ 1 ark  staff   53014  7月  4 21:34 sapi-v1-margin-allAssets.json
-rw-r--r--@ 1 ark  staff  104217  7月  4 21:34 sapi-v1-margin-allPairs.json
-rw-r--r--@ 1 ark  staff   84011  7月  4 21:34 sapi-v1-margin-crossMarginData.json
Need read evidence-index.md and sha256 check maybe.Need verify sha256 of sample files. Let's compute for fundingInfo and one maxBorrowable. Also verify distribution maybe.33f61539987942245c8df0c41f9b9ebf8da2dc9eb7946673f830acceefd53287  fapi-v1-fundingInfo.json
119eff4de9b75cd3410b10a0e3cbc9b1b72a6cb438eb6f51def1a41a645a0bdb  papi-v1-margin-maxBorrowable-BTC.json
119eff4de9b75cd3410b10a0e3cbc9b1b72a6cb438eb6f51def1a41a645a0bdb  papi-v1-margin-maxBorrowable-ETH.json
80e67eb96fa82afb7165021faf5111e82339c33d28bcc9bf064f343a40e46a52  sapi-v1-margin-allAssets.json
00b7238d816a8df7321c9d7a526d1d29e04b7a1bcc8b61665e979ae3acb00c40  sapi-v1-margin-allPairs.json
2cd9ca7192b0456fe6dcc48da08f0e4e589b03c7558b2f02445bb0eaedfe7109  sapi-v1-margin-crossMarginData.json
count 711
distribution {1: 2, 4: 440, 8: 269}
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
. [ 75%]
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
.
                                                  [100%]

95 passed in 3.01s
Tests pass. Need also run validate-stage script? The prompt says before dispatching review, validate-stage should run. We can run for pre-review or review-1 phase? The controller presumably ran. But as reviewer I can run to confirm.STAGE VALIDATION FAILED
- review/acceptance gates require a clean committed worktree; commit or revert these changes first:
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/30-review-1-backend.raw-output.md
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/30-review-1-frontend.raw-output.md
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-task-a-by-kimi.prompt.md
?? reports/agent-runs/2026-07-phase2-borrow-sort-v1/review-1-task-b-by-glm.prompt.md
usage: validate-stage.py [-h] [--phase {pre-review,pre-accept,checkpoint}]
                         stage
validate-stage.py: error: argument --phase: invalid choice: 'review-1' (choose from 'pre-review', 'pre-accept', 'checkpoint')
Validator complains about untracked files in stage dir (review outputs/prompts). That's expected: those are generated by bookkeeper for this review and are not part of committed state; but script requires clean worktree. We can note that. Maybe run after excluding those? But script checks git status. This is a harness issue, not a code issue. Need perhaps run validate-stage with --phase pre-review? It failed due untracked. The untracked files are review-1 artifacts. Need consider if that blocks? The committed diff fingerprint matches; untracked files are not part of diff. But validator's pre-review gate expects clean. In harness, bookkeeper should have committed or maybe review outputs not in repo? They are inside reports/agent-runs/stage. The script flags them. Maybe status.json should already account? This is a meta issue. Need determine if it blocks acceptance. The prompt says before dispatching review-1, run validate-stage.py <stage-id> --phase <phase> and preserve output. But if it fails because of untracked review prompts, that's a harness procedural issue. We should not reject product code because of review-prompt files. But the Harness gate says review gates require committed state. Yet the review prompts are part of dispatch. The controller put them in stage dir untracked. Maybe expected? Could be that pre-review was run before adding those. In status, it says H_A/H_B committed, diff_fingerprint bound, status=review_1. So pre-review likely passed earlier before prompts. For review-1, validator doesn't have review-1 phase. It might only need pre-review. The untracked files are the review prompts/outputs being created now; should not be committed before review? Hmm.

  Need be thorough: check no other red flags. Need inspect that classify/normalize unchanged. We can git diff for those: no diff. Need check that frontend not changed under Task A scope? Not relevant. Need check that reports/api-samples read-only: no new samples in stage? The discovery dir existed; not modified by Task A. Need check no key leaks in code/tests/reports. Search for API secret? frontend/index.html    |  28 +++-
 frontend/self-check.js | 412 ++++++++++++++++++++++++++++++++++++-------------
 2 files changed, 329 insertions(+), 111 deletions(-)
Task A review doesn't cover frontend. But we can note frontend changes in diff are present but not in scope. Need check backend grep: hmac/hashlib only in private_client and test_private_client. The test file is allowed to mention hmac/hashlib/signature for assertions. The grep test excludes tests and private_client. Fine. Need check that no credentials in source. The string "k"*64 and "s"*64 in test are placeholder fake, not real. No env values. Good.

  Need check that endpoint_whitelist exactly matches status. Test asserts. Good.

  Need maybe inspect snapshot_service import: no issue.

  Need consider if there are any subtle deviations from design:
  - Schema schema_version const remains "public-market-snapshot/v1" even though contract v0.2. Is that acceptable? The schema_version didn't change. Design didn't specify schema_version update. Contract says v0.2 but schema_version stays v1. That could be a discrepancy. In schema, schema_version const v1. Design §1.4 says snapshot schema extended. 10-design §1.4 says "快照 schema（snapshot.schema.json）按 §1.1-1.3 扩展，其余不动。" So schema_version unchanged is intentional. Contract status v0.2 but schema_version v1 is existing convention. Not a bug.
  - `private_channel` top-level added as optional not required; fine.
  - `borrow_validation` required fields include source strings; design shows source strings. Good.
  - `daily_interest_vip0` schema anyOf decimal_string|null, but design says string数值字段一律 string; for not listed state data fields null. Good.
  - `portfolio_account` max_borrowable/borrow_limit anyOf decimal_string|null. Good.
  - `daily_funding_rate` pattern allows integer strings without decimal? pattern `^-?[0-9]+(\\.[0-9]+)?$` allows "0" and "0.00000000". Fine.
  - `funding_interval_hours` enum 1,4,8. Good.

  Potential issue: In `compute_daily_funding_rate`, if last_funding_rate is numeric non-string (e.g., 0.0001 float from raw? But Binance returns string). The code uses Decimal(str(last_funding_rate)). If float passed, str may produce '0.0001'. Fine. If int, fine. It does convert to str before Decimal. Good. No float math.

  Potential issue: daily rate uses `Decimal(24) / Decimal(interval)` which yields exact decimal for interval 1,4,8 (24/8=3, etc). Good.

  Potential issue: sort_rows key uses Decimal(str(d)) but daily_rate is string produced by compute. For null, uses Decimal(0). Good.

  Potential issue: In `sort_rows`, invalid daily strings are treated as null (sort last). Acceptable.

  Potential issue: build_rows now passes `funding_interval_by_sym=funding_interval_by_sym`. In offline test uses build_rows with 4 positional args (no kwarg) -> defaults to {}. Good.

  Potential issue: `snapshot_service` offline mode forces private disabled. Good.

  Potential issue: direct-HTTP guard test allows `binance_public.py` and `private_client.py` only. Good.

  Potential issue: private_client uses `time.sleep(0.5)` for backoff. Fine.

  Potential issue: E5 account-level redaction at capture time. The implementation does not capture samples; discovery script does. Need check script maybe? Not in diff? Maybe not changed. We can inspect script. But not part of Task A? The capture script is in scripts/. However design says redaction script committed and testable. We haven't seen tests for redaction. Need check if discovery script redacts. But this might be H_intake, not Task A. The prompt says account-level responses redacted at capture time; redaction script committed and testable. This is a hard constraint. We should verify.Need continue. We checked discovery script. Need perhaps inspect tests for redaction? Not present. But script is committed and its redaction logic straightforward. Hard constraints say "Account-level responses redacted at capture time; redaction script committed and testable." It doesn't require test for redaction in this stage, but "testable" maybe means script can be run. However we can note no dedicated unit test for redaction. Is that a blocker? It might be acceptable; the constraint is redaction at capture time, which script does. The implementation doesn't do capture. So okay.

  Need verify that frontend/self-check passes? Not in scope but could note. The prompt says review Task A only. Maybe not run frontend. But can quickly check if self-check exists. However Task A review scope: backend/schemas/docs/api. We don't need frontend. But the stage review includes both A and B separately; B review will cover frontend. We can ignore.

  Need maybe inspect `backend/services/snapshot_service.py` changes fully for any issue. We saw diff. Need ensure `private_channel_status` string values exactly "enabled"/"disabled" matching schema enum. In code: `"enabled" if classic_ref is not None else "disabled"`. Good.

  Need ensure that when private disabled due to env missing, `fetch_classic_reference` returns None and sets last_error. In __init__, offline sets key/secret None => enabled False. `fetch_classic_reference` checks enabled false, sets last_error, returns None. Good.

  Need ensure that `last_error` is only set on classic_ref failure; for maxBorrowable fetch when disabled, returns None without setting last_error? In disabled state, `fetch_max_borrowable` returns None but does not set last_error. In `assemble_borrow_validation`, error is `private_error` which is `self._private.last_error if classic_ref is None else None`. If disabled, classic_ref None and last_error set to "private_channel_disabled". So max borrowable error not needed. Good.

  Potential issue: `SnapshotService.__init__` reads env even when offline=False? Actually if config.offline: api_key/secret None. Good.

  Potential issue: The `private_recv_window` default 10000. Good.

  Potential issue: `PrivateClient._signed_get` raises RuntimeError if not enabled after whitelist check. Since gate fires before signature, but disabled path would raise RuntimeError after whitelist if called. However high-level fetchers check enabled before calling _cached_get/_signed_get, so not reached. But test `_make_client(enabled=False)` may not call. Fine.

  Potential issue: The cache key includes params tuple sorted. For fetch_classic_reference, no params. Good.

  Potential issue: TTL expiry uses monotonic. Good.

  Potential issue: In `test_urlopen_only_in_designated_http_clients`, allowed includes binance_public.py and private_client.py. That checks no other product code uses `urlopen`. Good.

  Potential issue: In `test_single_hmac_exit_in_product_code`, signature assignment regex `signature\s*=` could match variable named signature in other files. It currently finds none. Good.

  Potential issue: Grep found `backend/services/snapshot_service.py` contains hmac/hashlib? It likely imports nothing. Wait grep output includes snapshot_service.py for hmac|hashlib|signature= etc. Let's check context.It matches api_secret variable, not actual secret. Fine. No hmac/hashlib/signature.

  Need also verify `backend/adapters/binance_public.py` diff. We saw it. It adds fundingInfo public GET. Good.

  Potential issue: `BinancePublicClient._offline_inputs` returns funding_interval_by_sym {}. That means offline defaults all 8h. Good.

  Potential issue: In live `fetch_raw`, it calls `_http_get` fundingInfo. If failure, returns no fundingInfo? It doesn't handle exception; it would propagate. Design says fundingInfo failure default all 8h + warning. Does implementation catch? In binance_public.py `_http_get` likely raises on HTTP error. The design says failure mode default 8h + warning. Is there a warning? Need inspect `_http_get`.`_http_get` doesn't catch exceptions. If fundingInfo fails, build_snapshot would raise, not degrade. Design table says E1 failure default all 8h + warning. The implementation doesn't catch. Is that a blocker? We need check if this is required for this stage. 10-design §2 failure mode for E1: "缺省全 8h + warning". The implementation doesn't implement fallback. In live, if fundingInfo fails, snapshot would fail. However tests don't cover live failure. Should we require REWORK? Need decide.

  Also `_fetch_live` only includes symbols that have fundingIntervalHours and are dict; missing symbols default to 8 in build_rows. If whole fundingInfo fails, exception propagates. There is no warning field for E1 fallback. The contract amendment says "Symbols listed in response use ...; unlisted default to 8. Offline mode -> all 8h." Doesn't explicitly say E1 failure fallback. But design failure mode table says default 8h + warning. Implementation deviation. Is it significant? If fundingInfo is public and reliable, maybe okay. But reviewer should flag.

  Another potential issue: private_client high-level fetchers don't include `last_error` reset on success. If first call fails and then later call succeeds, last_error remains. In `snapshot_service`, only uses last_error when classic_ref None. If first fetch_classic_reference fails (sets last_error), subsequent maybe cached? Actually `fetch_classic_reference` builds from three calls; if first raises, returns None and last_error. Then `snapshot_service` checks `classic_ref is None`, uses `private_error = self._private.last_error`. Fine. If private channel disabled, last_error set. Good.

  Potential issue: `fetch_classic_reference` maps `pair_listed_by_symbol` to `bool(x.get("isMarginTrade"))`. It doesn't handle null -> False. For not listed, pair_listed false. Good.

  Potential issue: E4 crossMarginData: if response is not a list? It would fail iteration. But it expects list. Fine.

  Potential issue: TTL cache uses `tuple(sorted((params or {}).items()))` but dict values must be strings; fine.

  Potential issue: signature query string sorted includes recvWindow and timestamp. Then URL includes qs & signature. Fine.

  Potential issue: timestamp uses time.time() * 1000 truncated int, not timezone dependent. Fine.

  Potential issue: `PrivateClient` reads api_key/secret in __init__ and `enabled = bool(...)`. Good.

  Potential issue: `snapshot_service` reads env in __init__ even if offline=False? Wait `if config.offline: _api_key = _api_secret = None else: os.environ.get`. Good.

  Potential issue: `snapshot_service` imports `os`. Good.

  Potential issue: `SnapshotService.get_snapshot()` caches snapshot and schema. Need check not changed? No diff shown? Let's inspect full service to see caching and request_log.Note: `request_log` only returns public client request log; private audit_log not exposed. Not a requirement. Fine.

  Need check `top_symbols_by_abs_rate` still uses `lastFundingRate` not daily. It sorts by abs single-period rate for selecting top symbols to fetch funding history. Not changed. Good.

  Potential issue: Live E1 failure not caught. Let's decide severity. The design failure mode table says E1: default 8h + warning. This is a design requirement. Implementation deviates. But is it part of "必查项" in prompt? The prompt lists: 单一 HMAC 出口/白名单三态/key 卫生/Decimal 向量/排序全序/三态语义/零改动红线/契约证据链. It doesn't explicitly list E1 failure fallback. But it says 对照 10-design.md §1/§2/§3 + status.json hard_constraints + endpoint_whitelist. §2 failure mode includes E1 default. However, E1 is public, no signature; if it fails, maybe service should still produce snapshot. The code would raise HTTPError and fail. In production, this would cause outage. That's not acceptable. Should require REWORK? Need formulate fix_start_prompt.

  But before concluding, need check if there is any error handling at app level that catches and returns 503. The snapshot_service docstring says on validation failure raises -> caller maps to 503. No fallback. `build_snapshot` called by `get_snapshot` which catches? No, only validates. So E1 failure = exception. Design says default 8h + warning. This is a clear deviation. Also what about E2/E3/E4 failures? They are handled in private_client (returns None). Good. E5 failure handled. E1 not.

  However, we must consider if this is within scope of Task A. Task A includes `fundingInfo + 排序` (10-design §3.3) and `binance_public.py` fetch_raw. It should implement E1 failure mode. So REWORK is justified.

  But need be careful: The implementation report and tests don't mention E1 failure fallback. The embed pre-review round1 likely didn't catch? It said PASS. But we are fresh and independent. We should flag.

  Also another potential issue: `binance_public.py` `_http_get` doesn't set User-Agent? It does. Fine.

  Another issue: The `compute_daily_funding_rate` returns `None` when last_funding_rate is `""` or None. But what if `lastFundingRate` is `"0"` or integer? It would compute. Good.

  Another issue: `daily_funding_rate` for `lastFundingRate` missing in live `premiumIndex`? `premiumIndex` always has lastFundingRate? Possibly empty string? It handles.

  Another issue: `sort_rows` uses string daily_rate. If value is something like `"0.00000000"` Decimal okay.

  Another issue: `test_offline_snapshot_rows_sorted_abs_daily_desc_nulls_last` uses `Decimal(d)`; all values are strings.

  Another issue: `schema` fixture used in tests. Need check conftest? Not necessary.

  Another issue: The new `private_channel` top-level field is optional; `assemble_snapshot` always includes it. Good. Schema doesn't require it but allows.

  Now consider whether to ACCEPT with observations or REWORK. The E1 fallback is a design-specified failure mode. If reviewer ignores, product could break. As a responsible reviewer, REWORK. But need check if fix is trivial: wrap fundingInfo call in try/except, log warning, return empty dict, maybe add warning to snapshot. Warnings are existing `CONTRACT_WARNINGS` constant. Could add dynamic warning. Implementation would need adjust `binance_public.py` and perhaps `snapshot_service.py` to capture warning. But design says "+ warning". We need require fix. However, is this within "hard constraints"? Not hard constraint, but design. The prompt says review对照 10-design §1/§2/§3. So yes.

  But wait, maybe there is an existing warning in `CONTRACT_WARNINGS` for missing fundingInfo? Let's check.No E1 fallback warning.

  Also check `_fetch_live` ordering: it fetches fundingInfo after exchangeInfo/premiumIndex/spot. If earlier fails, no fallback. But those are existing public endpoints; no fallback required historically.

  Another thing: The `BinancePublicClient` `_http_get` will raise on HTTP error. The `SnapshotService.build_snapshot` catches? No. `get_snapshot` validates but doesn't catch build errors. So any public endpoint failure results in exception -> 503. The design failure mode only mentions E1 default 8h. E2/E4 are private. So only E1. But should E1 fallback be implemented? I think yes.

  Now, another potential issue: The discovery script and status.json mention H_intake discovery evidence dir `reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/`. It exists. Good.

  Now, need also verify that the contract amendment includes bounded portfolio bStock exclusion. It does.

  Need consider whether `portfolio_account` source strings are correct: "papi_max_borrowable". Good.

  Need consider if the `private_channel_status` is set to enabled only when classic_ref not None, even if maxBorrowable fails. That means if classic ref succeeds but max borrowable fails, private_channel=enabled and borrow_validation for bounded rows may have portfolio_account None but verified true. That's correct per design: classic verified; portfolio failure is per-asset null.

  Need consider that `fetch_max_borrowable` on failure sets `last_error` but `snapshot_service` doesn't use it for those rows. It uses `portfolio_by_asset` with None. No error recorded per row. Design says error field for private channel disabled/failed; for portfolio failure, maybe not required. It says "private channel未启用/请求失败：error注明". For maxBorrowable per-asset failure, not a global failure. Fine.

  Need check if `borrow_validation` block is added after sorting; that means borrow_validation not considered in sort. Good.

  Now, determine verdict. I think REWORK due to E1 fallback. But we need also note maybe the validate-stage failure due to untracked files is a harness procedural issue, not code. We can mention it as observation not a code blocker. However, if the validator fails because of untracked files, the pre-review gate may not pass. But status.json says already passed pre-review. The untracked files are review prompts added by controller after. We can note that running validate-stage now fails due to these untracked artifacts; bookkeeper should clean/ignore them or commit them separately before pre-accept. But as reviewer, our verdict is on code.

  Need craft `fix_start_prompt` if REWORK. It should be ready-to-send to fix implementer (claude_glm? Since Task A implementer is claude_glm). Need preserve raw artifact paths, findings, required fixes, file boundaries, exact test commands, acceptance criteria.

  Required fix: Implement E1 failure fallback in `backend/adapters/binance_public.py`: wrap the `/fapi/v1/fundingInfo` call in try/except; on failure return empty `funding_interval_by_sym` and surface a warning to snapshot. Need decide how to surface warning. Options:
  - Add dynamic warning to `assemble_snapshot` or `build_snapshot`. Since `fetch_raw` returns a warning string? Could add `warnings` list to raw return; `snapshot_service` merges into snapshot warnings. Or simply add to `CONTRACT_WARNINGS`? But dynamic per call. Simpler: `fetch_raw` returns `{"funding_interval_by_sym": {}, "funding_info_warning": "..."}`; `build_snapshot` adds to snapshot warnings. Or modify `_fetch_live` to catch and return empty and a warning field; `snapshot_service` adds it. Since only `binance_public.py` and `snapshot_service.py` are allowed files. We can require minimal fix.

  Need also update tests: add a test that live fundingInfo failure returns 8h defaults and warning. The existing `backend/tests/test_phase2_borrow_sort.py` can be extended. Also maybe `test_offline_build_rows_defaults_8h_without_funding_info` already covers offline. Need live failure simulation using monkeypatch on `urllib.request.urlopen` perhaps.

  Need ensure the fix doesn't change contract or schema. It adds a warning string to snapshot warnings (already array of strings). Good.

  Need also consider if this is the only finding. We should include other observations that are not blockers.

  Let's also check if `BinancePublicClient._fetch_live` returns `funding_interval_by_sym` with only dict items. If fundingInfo returns list with entries missing fundingIntervalHours, they are skipped -> default 8. Good.

  Potential issue: `build_rows` uses `int(interval_map.get(sym, 8))`. If map value not int (e.g., string) would fail; but map values are int. Good.

  Potential issue: `compute_daily_funding_rate` uses `Decimal(str(last_funding_rate))`. If `last_funding_rate` is already Decimal? Not from raw. Fine.

  Now, also need check the `test_urlopen_only_in_designated_http_clients` includes binance_public.py and private_client.py. But `discovery-capture-phase2.py` in scripts also uses urlopen and hmac. The test only scans backend dir, not scripts. Hard constraints mention redaction script committed and testable, but not subject to product-code guard. Fine.

  Now, maybe there's an issue with `private_client.py` `WHITELIST` base URLs hardcoded but `snapshot_service` config has sapi_base_url/papi_base_url not used. The design says base URLs are hardcoded in private_client, not injectable. Good.

  Now, need maybe run `frontend/self-check.js`? Not scope. But we might mention we didn't review frontend (Task B) per scope.

  Need produce final output with narrative and JSON verdict. Since REWORK, fix_start_prompt required. Also need include footer per project instructions: local Beijing time, next model, next task. Need call `date` to get local time. The system date is stale. Use `date` command.2026-07-04 23:37:15 CST
Need produce verdict JSON. Let's first construct reasoning narrative.

  Review summary:
  - Recomputed diff fingerprint: matches.
  - Scope note: e831137 parallel-mode doc not reviewed.
  - Tests: 95 passed on rerun; replayable.
  - Discovery evidence: sha256 matches index; distribution matches.
  - Code review: private_client single HMAC exit, whitelist, GET-only, audit log hygiene, degradation, rate-limit backoff all correct and tested.
  - Decimal daily rate vectors correct; sorting deterministic; three-state borrow_validation semantics correct; schema v0.2 additive and backward-compatible; classify/normalize untouched; contract amendment documents mapping.
  - Finding: `backend/adapters/binance_public.py` `_fetch_live` does not implement the E1 failure mode from 10-design §2: "GET /fapi/v1/fundingInfo ... 失败模式：缺省全 8h + warning". If fundingInfo call fails, exception propagates and snapshot build fails instead of degrading to 8h defaults with a warning. This is a design-scope deviation that could cause outage. Required fix.
  - Minor observation: `scripts/validate-stage.py` run now fails because of untracked review-1 prompt/output files added in the stage directory (not part of committed diff). Bookkeeper should address before pre-accept gate; it does not affect code verdict.

  Verdict: REWORK. Need fix_start_prompt.

  Need ensure JSON matches schema. Need check `schemas/review-verdict.schema.json`.Schema role enum doesn't include "second_reviewer"! The prompt says role=`second_reviewer`, but schema only allows "designer_review", "first_reviewer", "final_reviewer", "reality_checker". review-1 is first_reviewer. The prompt says role=second_reviewer but that conflicts with schema. As reviewer, I must follow schema for JSON verdict; the prompt's instruction inside task body says role=second_reviewer. Conflict: project instruction says schema is authority. The schema is `schemas/review-verdict.schema.json` which is authority order 4. Also prompt says output JSON符合 schema. So we must use a valid role enum value. review-1 corresponds to first_reviewer? In Harness, review-1 is cross-review (first formal review), review-2 is final. So role should be "first_reviewer". Use that. Mention in narrative maybe the prompt said second_reviewer but schema only supports first_reviewer; using first_reviewer for review-1.

  Model: "kimi" or "kimi-for-coding"? Use "kimi".

  reviewer_prior_involvement: "none".

  Need include fix_start_prompt. It must be a string. We'll embed a detailed prompt.

  Need include findings array. Severity P0? E1 fallback is a functional failure mode deviation but not a security breach. Could be P1. Since it could cause outage if public endpoint fails, but public endpoint reliable. P1 is appropriate. Maybe P0? P0 usually blocker. We'll set P1.

  Need include residual_risks maybe.

  Need ensure next_action "fix".

  Need craft fix_start_prompt precisely. It should reference raw artifacts. We can include:

  ```
  You are the Task A fix implementer (claude_glm) for stage 2026-07-phase2-borrow-sort-v1.

  Required fix:
  - Implement the E1 failure mode specified in 10-design.md §2: if GET /fapi/v1/fundingInfo fails in backend/adapters/binance_public.py, the snapshot must degrade to funding_interval_hours=8 for all rows and include a warning in snapshot.warnings, instead of propagating an exception.
  - Add/update deterministic tests in backend/tests/test_phase2_borrow_sort.py covering live-mode fundingInfo failure fallback (e.g., monkeypatch urllib.request.urlopen to raise HTTPError for fundingInfo only, assert all rows have funding_interval_hours==8 and snapshot.warnings contains a warning mentioning fundingInfo/default 8h). Keep existing 95 tests passing.

  File boundaries:
  - Allowed: backend/adapters/binance_public.py, backend/services/snapshot_service.py, backend/domain/snapshot.py, backend/tests/test_phase2_borrow_sort.py, reports/agent-runs/2026-07-phase2-borrow-sort-v1/20-implementation-backend.md (update after fix).
  - Forbidden: backend/domain/classify.py, backend/domain/normalize.py, frontend/**, schemas/**, docs/api/**, reports/api-samples/**.

  Authority:
  - 10-design.md §2 (E1 failure mode: default 8h + warning) and §3.3.
  - 60-test-output.txt must remain 95+ passed after fix.

  Exact test command:
  python3 -m pytest backend/tests/ -v

  Success criteria:
  1. backend/adapters/binance_public.py catches fundingInfo failure and returns empty funding_interval_by_sym plus a warning string.
  2. SnapshotService propagates that warning into snapshot.warnings.
  3. New deterministic test asserts the fallback.
  4. All 95 existing tests still pass; no new failures.
  5. Do not change contract/schema/frontend; do not touch forbidden files.
  6. Do not commit; leave changes in working tree; update 20-implementation-backend.md with the fix note.

  Base/head context:
  - base_sha: 4d47ad2d3f2068e86b634b5e39d5063dc4ed526f
  - head_sha: cc25148aa7924e7bb89364f4bba7c8fe978e91f9
  - diff_fingerprint: cc25148:9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a
  ```

  Need ensure footer after JSON? Project instructions: footer before final JSON block or inside schema-approved fields. Since final JSON must be parseable and schema doesn't have footer field, place footer before JSON. The prompt says output 评审叙述 + 末尾单个 ```json verdict. So place footer before the JSON block, not after. Good.

  Need be careful with JSON string escaping for fix_start_prompt. We'll embed newlines as \n to keep JSON single-line string. Use proper JSON.

  Let's also include reviewed_artifacts list.

  Need maybe mention validate-stage issue as a finding? It's procedural. Could include as P2 observation. But next_action fix. Let's include as finding P2 maybe not required fix, but residual risk. Since it's a harness issue, mention in narrative, not necessarily JSON findings. But we can include a P2 finding about untracked files causing validate-stage failure. However, required_fixes should include only code fix. Findings can include both. Let's include P2 finding for validator untracked files; recommendation bookkeeper clean/ignore.

  Need ensure the JSON doesn't have trailing commas.

  Now, need also maybe check if the fix_start_prompt asks to update 20-implementation-backend.md. Is that allowed file? It's in stage reports, yes. But implementer shouldn't touch status.json. Good.

  Need also mention that the review did not inspect e831137 parallel-mode doc, per scope.

  Now produce final answer in Chinese, since user used Chinese. Keep code terms English. Use Markdown.

  Let's draft final.

## Task A（后端）review-1 评审结论

  **身份隔离声明**：本会话为全新只读 Kimi 会话，未参与本阶段设计、实现、修复或嵌入预审；`reviewer_prior_involvement = none`。

  **指纹核对**：按 `status.json` 公式重算 `diff_fingerprint`（排除 `status.json`）：

  ```bash
  git diff --binary 4d47ad2..cc25148 -- . ":(exclude)reports/agent-runs/2026-07-phase2-borrow-sort-v1/status.json" | sha256sum
  ```

  结果与 `status.json` 记载一致：`9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a` → **MATCH**。

  **范围注记**：`base..head` 中 `e831137` 对 `docs/parallel-development-mode.md` 的 harness 层试运行修订不在本 Task A 评审范围，仅知悉。

  **已审 artifacts**：
  - `backend/adapters/binance_public.py`
  - `backend/config.py`
  - `backend/domain/snapshot.py`
  - `backend/services/private_client.py`
  - `backend/services/snapshot_service.py`
  - `backend/tests/test_private_client.py`
  - `backend/tests/test_phase2_borrow_sort.py`
  - `schemas/api/public-market/snapshot.schema.json`
  - `docs/api/public-market-contract.md`
  - `reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md`
  - `reports/agent-runs/2026-07-phase2-borrow-sort-v1/11-adr.md`
  - `reports/agent-runs/2026-07-phase2-borrow-sort-v1/60-test-output.txt`
  - `reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/evidence-index.md` 及样本 sha256

  **测试重放**：`python3 -m pytest backend/tests/ -v` → **95 passed**（本地复现）。

  **discovery 证据抽验**：5 个样本 sha256 与 `evidence-index.md` 完全一致；`fundingInfo` 样本 711 条，`{1h:2, 4h:440, 8h:269}`，与 status.json 记载一致；`maxBorrowable` 两样本均已脱敏为 `<AMOUNT>`。

  ### 通过项

  - **单一 HMAC 出口**：`backend/services/private_client.py` 是仓库唯一 HMAC-SHA256 签名点；`test_single_hmac_exit_in_product_code` 确认其余产品代码无 `hmac`/`hashlib`/`signature=`。
  - **白名单三态 + GET-only**：`WHITELIST` 与 `status.json` `endpoint_whitelist` 完全一致（四项），`test_whitelist_matches_status_json_endpoint_whitelist` 通过；非 GET/非白名单路径在签名构造前 `raise PermissionError`。
  - **key 卫生**：审计日志仅含 `logical_endpoint/method/http_status/error/latency_ms`，无 key/secret/signature/query/headers。
  - **Decimal 向量**：6 组 daily-rate 测试向量（含负零归一化与缺失→null）全部通过；计算路径无 float。
  - **排序全序**：`abs(daily)` 降序、null 末尾、`symbol` 升序 tie-break，测试覆盖。
  - **三态语义**：disabled / verified-not-listed / verified-listed 三种 `borrow_validation` 状态均实现并 schema 校验。
  - **零改动红线**：`backend/domain/classify.py`、`backend/domain/normalize.py`、`frontend/**` 在 `base..head` 中无改动（Task A 范围内）。
  - **契约证据链**：`docs/api/public-market-contract.md` v0.2 amendment 记载了新增字段、排序、三态、raw→snake_case 映射，并引用 discovery 目录。

  ### 阻塞性发现（REWORK）

  **P1 — `GET /fapi/v1/fundingInfo` 失败未按设计降级**

  - **位置**：`backend/adapters/binance_public.py:90-103`（`_fetch_live`）
  - **证据**：`10-design.md §2` 中 E1 失败模式明确为“缺省全 8h + warning”；当前实现直接调用 `self._http_get(.../fundingInfo)`，任何 `HTTPError`/网络异常都会向上抛，导致 `SnapshotService.build_snapshot()` 整体失败，而不是回退到 8h 并带 warning。
  - **影响**：公开端点偶发失败即可使整站快照 503，违反设计约定的韧性行为。
  - **建议**：在 `_fetch_live` 中捕获 fundingInfo 异常，返回空 `funding_interval_by_sym`，并让 `SnapshotService` 把一条警告加入 `snapshot.warnings`；新增确定性测试覆盖该失败回退。

  ### 程序性观察（非代码阻塞）

  - `scripts/validate-stage.py 2026-07-phase2-borrow-sort-v1 --phase pre-review` 当前因 stage 目录下未跟踪的 review-1 提示/输出文件（`review-1-task-*.prompt.md`、`30-review-1-*.raw-output.md`）而报 worktree 不 clean。这些文件是本次 review 调度产物，不属于产品代码 diff；bookkeeper 应在进入 `pre-accept` 门前处理（提交、忽略或移出 stage 目录），避免 validator 在最终门处失败。

  ---

  本地北京时间: 2026-07-04 23:37:15 CST
  下一步模型: claude_glm（Task A fix implementer）
  下一步任务: 修复 `fundingInfo` 失败回退并补充测试后重新进入 review-1

  ```json
  {
    "schema_version": 1,
    "stage_id": "2026-07-phase2-borrow-sort-v1",
    "role": "first_reviewer",
    "model": "kimi",
    "verdict": "REWORK",
    "diff_fingerprint": "cc25148aa7924e7bb89364f4bba7c8fe978e91f9:9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a",
    "reviewer_prior_involvement": "none",
    "reviewer_prior_involvement_notes": "Fresh read-only Kimi session; no prior design, implementation, fix, or embedded pre-review involvement for Task A.",
    "reviewed_artifacts": [
      "backend/adapters/binance_public.py",
      "backend/config.py",
      "backend/domain/snapshot.py",
      "backend/services/private_client.py",
      "backend/services/snapshot_service.py",
      "backend/tests/test_private_client.py",
      "backend/tests/test_phase2_borrow_sort.py",
      "schemas/api/public-market/snapshot.schema.json",
      "docs/api/public-market-contract.md",
      "reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md",
      "reports/agent-runs/2026-07-phase2-borrow-sort-v1/11-adr.md",
      "reports/agent-runs/2026-07-phase2-borrow-sort-v1/60-test-output.txt",
      "reports/api-samples/2026-07-phase2-borrow-sort-v1/20260704T133406Z/evidence-index.md"
    ],
    "findings": [
      {
        "severity": "P1",
        "title": "fundingInfo live failure does not fall back to 8h + warning",
        "file": "backend/adapters/binance_public.py",
        "line": 90,
        "evidence": "10-design.md §2 E1 failure mode requires default 8h + warning; _fetch_live calls _http_get for /fapi/v1/fundingInfo without try/except, so any HTTP/network error propagates and breaks snapshot build instead of degrading.",
        "impact": "Public fundingInfo outage causes entire snapshot service to fail with 503, violating the design's degradation contract.",
        "recommendation": "Wrap the fundingInfo call in try/except in _fetch_live, return empty funding_interval_by_sym on failure, and surface a warning in snapshot.warnings via SnapshotService."
      },
      {
        "severity": "P2",
        "title": "validate-stage.py fails due to untracked review-1 artifacts in stage dir",
        "file": "reports/agent-runs/2026-07-phase2-borrow-sort-v1/",
        "line": null,
        "evidence": "scripts/validate-stage.py --phase pre-review reports ?? review-1-task-a-by-kimi.prompt.md, review-1-task-b-by-glm.prompt.md, 30-review-1-backend.raw-output.md, 30-review-1-frontend.raw-output.md as uncommitted changes.",
        "impact": "The pre-accept validator gate will fail even though the product code diff is committed and the fingerprint matches.",
        "recommendation": "Bookkeeper should commit these review artifacts separately, add them to .gitignore, or move them outside the stage evidence dir before running validate-stage.py pre-accept."
      }
    ],
    "required_fixes": [
      "Implement E1 failure fallback in backend/adapters/binance_public.py: if GET /fapi/v1/fundingInfo fails, return empty funding_interval_by_sym so all rows default to 8h.",
      "Propagate a fundingInfo warning into snapshot.warnings (via SnapshotService or assemble_snapshot) when the fallback is triggered.",
      "Add a deterministic test in backend/tests/test_phase2_borrow_sort.py that monkey-patches urllib.request.urlopen to raise HTTPError for fundingInfo only, asserts all rows have funding_interval_hours==8, and asserts snapshot.warnings contains a fundingInfo/default-8h warning.",
      "Ensure all existing 95 tests continue to pass; update 20-implementation-backend.md with the fix note."
    ],
    "residual_risks": [
      "bounded portfolio strategy leaves portfolio_account null for all rows in current market conditions; this is a design-layer observation (ADR-5 DEFERRED), not an implementation defect.",
      "validate-stage.py worktree-clean check may reject the stage if untracked review artifacts remain in reports/agent-runs/2026-07-phase2-borrow-sort-v1/."
    ],
    "fix_start_prompt": "You are the Task A fix implementer (claude_glm) for stage 2026-07-phase2-borrow-sort-v1.\n\nRequired fix:\n- Implement the E1 failure mode specified in reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md §2: if GET /fapi/v1/fundingInfo fails in backend/adapters/binance_public.py, the snapshot must degrade to funding_interval_hours=8 for all rows and include a warning in snapshot.warnings, instead of propagating an exception.\n- Add/update deterministic tests in backend/tests/test_phase2_borrow_sort.py covering live-mode fundingInfo failure fallback (e.g., monkeypatch urllib.request.urlopen to raise HTTPError for fundingInfo only, assert all rows have funding_interval_hours==8 and snapshot.warnings contains a warning mentioning fundingInfo/default 8h). Keep existing tests passing.\n\nFile boundaries:\n- Allowed: backend/adapters/binance_public.py, backend/services/snapshot_service.py, backend/domain/snapshot.py, backend/tests/test_phase2_borrow_sort.py, reports/agent-runs/2026-07-phase2-borrow-sort-v1/20-implementation-backend.md (update after fix).\n- Forbidden: backend/domain/classify.py, backend/domain/normalize.py, frontend/**, schemas/**, docs/api/**, reports/api-samples/**, status.json.\n\nAuthority:\n- reports/agent-runs/2026-07-phase2-borrow-sort-v1/10-design.md §2 (E1 failure mode: default 8h + warning) and §3.3.\n- schemas/api/public-market/snapshot.schema.json must still validate; contract and schema must remain unchanged except for the dynamic warning string.\n\nExact test command:\npython3 -m pytest backend/tests/ -v\n\nSuccess criteria:\n1. backend/adapters/binance_public.py catches fundingInfo failure and returns empty funding_interval_by_sym plus a warning string.\n2. SnapshotService propagates that warning into snapshot.warnings.\n3. New deterministic test asserts the fallback behavior.\n4. All 95 existing tests still pass; no new failures.\n5. Do not change contract/schema/frontend; do not touch forbidden files.\n6. Do not commit; leave changes in working tree; update 20-implementation-backend.md with the fix note.\n\nBase/head context:\n- base_sha: 4d47ad2d3f2068e86b634b5e39d5063dc4ed526f\n- head_sha: cc25148aa7924e7bb89364f4bba7c8fe978e91f9\n- diff_fingerprint: cc25148aa7924e7bb89364f4bba7c8fe978e91f9:9dc905d56fd003b1b5ebfa31cdebedd363b49f57ddd488b5bef85ac73f3fcb3a",
    "next_action": "fix"
  }
  ```

To resume this session: kimi -r session_bfdbafa6-aa77-4fbe-a7d6-16d94980d99e
