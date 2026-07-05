#!/usr/bin/env python3
"""One-shot H_intake discovery capture for stage 2026-07-private-account-v1.

Calls EXACTLY the 12 status.json whitelisted signed endpoints (HMAC-SHA256
GET) + 1 public GET /api/v3/ticker/price (full, once), redacts account-level
responses at capture time, archives under
reports/api-samples/<stage>/<UTC-ts>/ with an sha256 evidence-index, and
records the per-call X-MBX-USED-WEIGHT-* / X-SAPI-USED-*-WEIGHT-* response
headers (G3 budget-table input).

Security posture (reviewer-checkable):
- deny-by-default whitelist of (method, exact-path) pairs, hardcoded in-script;
  the whitelist check raises BEFORE any signature is constructed.
- GET-only code path; no POST/PUT/DELETE is ever constructed.
- key/secret/signature/full query string are NEVER printed, logged, or archived;
  archived metadata records only the sanitized logical path.
- account-level responses (E2/E2b/E5/E3/E4/E6/W4/E1/E1b) have every
  numeric-string value replaced with the placeholder '<AMOUNT>' and the
  account-identifier integer fields {uid, vipLevel} replaced with '<ID>',
  preserving keys, structure and type info. Market-level public responses
  (allPairs/allAssets/crossMarginData/ticker-price) carry no account secrets
  and are archived with URL query stripping only.

G2 gate semantics (status.json hard_constraints):
- E3 /papi/v1/balance, E4 /papi/v1/um/positionRisk, E6 /api/v3/account are the
  core private_account view endpoints; ANY of them failing -> BLOCKED (exit 2),
  raw error code archived, escalate user; NO silent fallback.
- E2 /sapi/v1/margin/next-hourly-interest-rate, E2b interestRateHistory,
  E5 /sapi/v1/account/info are the cost-leg chain endpoints; a failure records
  the four-level chain hit tier and does NOT block (chain degrades to
  vip0_reference per 10-design §1.3).
- E1/E1b are discovery-only (attribution comparison), non-blocking.
- W1/W2/W3 (existing market-level refs) and W4 maxBorrowable and P5 ticker/price
  failures are recorded as warnings; only E3/E4/E6 are blocking per the stage gate.

Run AFTER `source ~/.binance-keys` (BINANCE_API_KEY/BINANCE_API_SECRET in env).
Exit codes: 0 = non-blocking capture complete; 2 = a blocking endpoint
(E3/E4/E6) failed -> bookkeeper sets status=blocked and escalates user.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGE_ID = "2026-07-private-account-v1"
SAMPLES_ROOT = REPO_ROOT / "reports" / "api-samples" / STAGE_ID
FIXTURE_PATH = REPO_ROOT / "frontend" / "fixture" / "public-market-snapshot.json"

RECV_WINDOW = 10000
TIMEOUT = 20.0
USER_AGENT = "funding-hedging-h-intake-discovery/private-v1"

# ---- deny-by-default endpoint whitelist (hardcoded, the only truth) ----
# Mirrors status.json endpoint_whitelist (12 signed) verbatim; base URLs bound
# here, NOT injectable from config.
SIGNED_WHITELIST: Dict[Tuple[str, str], str] = {
    # W1-W3 sapi market-level reference (existing)
    ("GET", "/sapi/v1/margin/allPairs"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/allAssets"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/crossMarginData"): "https://api.binance.com",
    # W4 papi maxBorrowable (existing; account-level)
    ("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
    # E1/E1b papi interest history (discovery-only, attribution comparison)
    ("GET", "/papi/v1/margin/marginInterestHistory"): "https://papi.binance.com",
    ("GET", "/papi/v1/portfolio/interest-history"): "https://papi.binance.com",
    # E2/E2b/E5 sapi cost-leg chain
    ("GET", "/sapi/v1/margin/next-hourly-interest-rate"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/interestRateHistory"): "https://api.binance.com",
    ("GET", "/sapi/v1/account/info"): "https://api.binance.com",
    # E3/E4 papi core private_account view (BLOCKING gate)
    ("GET", "/papi/v1/balance"): "https://papi.binance.com",
    ("GET", "/papi/v1/um/positionRisk"): "https://papi.binance.com",
    # E6 api spot account (BLOCKING gate)
    ("GET", "/api/v3/account"): "https://api.binance.com",
}
PUBLIC_WHITELIST: Dict[Tuple[str, str], str] = {
    # P5 public valuation price map (full, once)
    ("GET", "/api/v3/ticker/price"): "https://api.binance.com",
}

# Account-level paths: redact numeric strings + identifier ints at capture.
ACCOUNT_LEVEL_PATHS = {
    "/papi/v1/margin/maxBorrowable",          # W4 amount/borrowLimit
    "/papi/v1/margin/marginInterestHistory",  # E1 interest/principal (discovery)
    "/papi/v1/portfolio/interest-history",    # E1b interest (discovery)
    "/sapi/v1/margin/next-hourly-interest-rate",  # E2 user rate
    "/sapi/v1/margin/interestRateHistory",    # E2b user rate
    "/sapi/v1/account/info",                  # E5 vipLevel/account state
    "/papi/v1/balance",                       # E3 wallet balances
    "/papi/v1/um/positionRisk",               # E4 position amounts/prices
    "/api/v3/account",                        # E6 spot balances + uid
}
# Account-identifier integer fields (JSON numbers, not amount strings) that
# must also be redacted. Error-code ints on error bodies are NOT in this set
# and survive for diagnosis.
IDENTIFIER_INT_FIELDS = {"uid", "vipLevel"}

# Blocking gate (G2): core private_account view endpoints.
BLOCKING_PATHS = {
    "/papi/v1/balance",        # E3
    "/papi/v1/um/positionRisk",  # E4
    "/api/v3/account",         # E6
}

# maxBorrowable sample assets: BTC fixed + highest-abs-rate non-BTC candidate
# from the Phase 1/2 fixture (offline; fundingInfo is NOT whitelisted this run).
FIXED_ASSET = "BTC"
CANDIDATE_FALLBACK = "ETH"


def require_env() -> Tuple[str, str]:
    key = os.environ.get("BINANCE_API_KEY")
    secret = os.environ.get("BINANCE_API_SECRET")
    if not key or not secret:
        sys.exit(
            "ERROR: BINANCE_API_KEY/BINANCE_API_SECRET not set; refusing to run. "
            "Run `source ~/.binance-keys` first."
        )
    return key, secret


def _is_amount_string(value: Any) -> bool:
    """True for non-empty pure decimal strings (account-level amount fields)."""
    if not isinstance(value, str) or not value:
        return False
    try:
        Decimal(value)
        return True
    except (InvalidOperation, ValueError):
        return False


def redact_account_amounts(obj: Any) -> Any:
    """Replace numeric-string amounts with '<AMOUNT>' and account-identifier
    integer fields with '<ID>', preserving keys, structure and type."""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if k in IDENTIFIER_INT_FIELDS and isinstance(v, int) and not isinstance(v, bool):
                out[k] = "<ID>"
            else:
                out[k] = redact_account_amounts(v)
        return out
    if isinstance(obj, list):
        return [redact_account_amounts(v) for v in obj]
    if _is_amount_string(obj):
        return "<AMOUNT>"
    return obj


def _extract_weight_headers(headers: Any) -> Dict[str, str]:
    """Capture all X-MBX-USED-* / X-SAPI-USED-* response headers (G3 input)."""
    out: Dict[str, str] = {}
    try:
        for k, v in headers.items():
            ku = k.upper()
            if ku.startswith("X-MBX-USED") or ku.startswith("X-SAPI-USED"):
                out[ku] = v
    except AttributeError:
        return out
    return out


def _do_request(
    req: urllib.request.Request,
) -> Tuple[Optional[int], str, float, Optional[str], Dict[str, str]]:
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            weights = _extract_weight_headers(resp.headers)
            return resp.status, body, (time.monotonic() - t0) * 1000.0, None, weights
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        weights = _extract_weight_headers(getattr(exc, "headers", None))
        return exc.code, body, (time.monotonic() - t0) * 1000.0, f"HTTP {exc.code}", weights
    except Exception as exc:  # network / timeout / DNS
        return None, "", (time.monotonic() - t0) * 1000.0, f"{type(exc).__name__}: {exc}", {}


def signed_get(
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    request_log: Counter,
    extra_params: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[int], str, float, Optional[str], Dict[str, str]]:
    """HMAC-SHA256 signed GET. Whitelist + GET-only enforced BEFORE signing."""
    if (method, path) not in SIGNED_WHITELIST:
        raise PermissionError(f"endpoint not in signed whitelist: {method} {path}")
    if method != "GET":
        raise PermissionError(f"only GET implemented; got {method}")
    request_log[f"{method} {path}"] += 1

    params: Dict[str, str] = dict(extra_params or {})
    params["recvWindow"] = str(RECV_WINDOW)
    params["timestamp"] = str(int(time.time() * 1000))
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(api_secret.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256).hexdigest()
    # NOTE: url contains the signature; never print/log/archive it.
    url = f"{SIGNED_WHITELIST[(method, path)]}{path}?{qs}&signature={sig}"
    req = urllib.request.Request(
        url, headers={"X-MBX-APIKEY": api_key, "User-Agent": USER_AGENT}, method="GET"
    )
    return _do_request(req)


def public_get(
    method: str,
    path: str,
    request_log: Counter,
) -> Tuple[Optional[int], str, float, Optional[str], Dict[str, str]]:
    if (method, path) not in PUBLIC_WHITELIST:
        raise PermissionError(f"endpoint not in public whitelist: {method} {path}")
    request_log[f"{method} {path}"] += 1
    req = urllib.request.Request(
        f"{PUBLIC_WHITELIST[(method, path)]}{path}", headers={"User-Agent": USER_AGENT}, method="GET"
    )
    return _do_request(req)


def path_to_filename(path: str, suffix: str = "") -> str:
    name = path.strip("/").replace("/", "-")
    return f"{name}{suffix}.json"


def archive(
    out_dir: Path,
    filename: str,
    raw_body: str,
    status: Optional[int],
    sanitized_path: str,
    latency_ms: float,
    error: Optional[str],
    weight_headers: Dict[str, str],
    meta_endpoints: List[Dict[str, Any]],
) -> Optional[Any]:
    """Redact (if account-level), write file, sha256, append metadata.
    Returns parsed_json (un-redacted, for in-memory chain analysis) or None."""
    is_account_level = sanitized_path in ACCOUNT_LEVEL_PATHS
    redacted_text = raw_body
    parsed: Optional[Any] = None
    redacted_amounts = False
    if raw_body:
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            parsed = None
    if is_account_level and parsed is not None:
        redacted_obj = redact_account_amounts(parsed)
        redacted_text = json.dumps(redacted_obj, ensure_ascii=False, indent=2)
        redacted_amounts = True

    file_path = out_dir / filename
    file_path.write_text(redacted_text, encoding="utf-8")
    sha = hashlib.sha256(redacted_text.encode("utf-8")).hexdigest()

    meta_endpoints.append(
        {
            "logical_path": sanitized_path,  # sanitized: NO query string
            "method": "GET",
            "http_status": status,
            "error": error,
            "latency_ms": round(latency_ms, 1),
            "archived_file": filename,
            "sha256": sha,
            "is_account_level": is_account_level,
            "amounts_redacted": redacted_amounts,
            "weight_headers": weight_headers,
        }
    )
    return parsed if isinstance(parsed, (dict, list)) else None


def _ok_and_populated(status: Optional[int], parsed: Any) -> bool:
    """Endpoint returned 200 with a non-empty usable body (chain-hit test)."""
    if status != 200 or parsed is None:
        return False
    if isinstance(parsed, list):
        return len(parsed) > 0
    if isinstance(parsed, dict):
        # treat {} as empty; an object with at least one key as populated
        return len(parsed) > 0
    return False


def compute_chain_tier(
    e2: Tuple[Optional[int], Optional[Any]],
    e2b: Tuple[Optional[int], Optional[Any]],
    w3: Tuple[Optional[int], Optional[Any]],
    e5: Tuple[Optional[int], Optional[Any]],
) -> Tuple[int, str, str]:
    """Four-level cost-leg chain hit tier (10-design §1.3).
    Returns (tier_int, source_enum, rationale)."""
    if _ok_and_populated(*e2):
        return 1, "next_hourly", "E2 /sapi/v1/margin/next-hourly-interest-rate returned usable rate(s)"
    if _ok_and_populated(*e2b):
        return 2, "rate_history", "E2 failed/empty; E2b interestRateHistory returned usable rate(s)"
    if _ok_and_populated(*w3) and _ok_and_populated(*e5):
        return 3, "cross_margin_tier", "E2/E2b failed; crossMarginData VIP table + E5 VIP level usable"
    return 4, "vip0_reference", "E2/E2b/E5 unavailable; degrade to VIP0 reference (Phase 2 behavior)"


def pick_candidate_asset() -> Tuple[str, str]:
    """2nd maxBorrowable sample = highest-abs-rate non-BTC MARGIN_SPOT_CANDIDATE
    +CRYPTO candidate from the Phase 1/2 fixture (offline; no endpoint call).
    Returns (asset, rationale)."""
    try:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return CANDIDATE_FALLBACK, f"fixture unreadable; fallback {CANDIDATE_FALLBACK}"

    best_base: Optional[str] = None
    best_rate = Decimal("-1")
    for row in fixture.get("rows", []):
        if row.get("route_class") != "MARGIN_SPOT_CANDIDATE":
            continue
        if row.get("asset_tag") != "CRYPTO":
            continue
        base = row.get("base_asset")
        if not base or base == FIXED_ASSET:
            continue
        rate = row.get("futures", {}).get("last_funding_rate")
        if not rate:
            continue
        try:
            ar = abs(Decimal(str(rate)))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if ar > best_rate:
            best_rate = ar
            best_base = base
    if best_base is None:
        return CANDIDATE_FALLBACK, f"no non-BTC MARGIN_SPOT_CANDIDATE+CRYPTO candidate in fixture; fallback {CANDIDATE_FALLBACK}"
    return best_base, (
        f"highest-abs-last_funding_rate non-BTC MARGIN_SPOT_CANDIDATE+CRYPTO candidate in "
        f"frontend/fixture/public-market-snapshot.json (offline; fundingInfo not whitelisted this run). "
        f"{best_base}: |last_funding_rate|={best_rate}"
    )


def write_evidence_index(
    out_dir: Path,
    ts: str,
    endpoints: List[Dict[str, Any]],
    request_log: Counter,
    candidate_asset: str,
    candidate_rationale: str,
    chain_tier: Tuple[int, str, str],
    blocking_failed: List[str],
    nonblocking_failures: List[str],
) -> None:
    tier_int, source_enum, tier_rationale = chain_tier
    lines: List[str] = []
    lines.append(f"# Discovery evidence index — {STAGE_ID}")
    lines.append("")
    lines.append(f"- captured_at_utc: `{ts}`")
    lines.append("- captured_by: bookkeeper (claude_glm fresh session, H_intake)")
    lines.append("- base_urls: api.binance.com (sapi/api) / papi.binance.com (papi); hardcoded in script")
    lines.append(f"- total HTTP calls: {sum(request_log.values())} across {len(request_log)} logical endpoints")
    lines.append("- endpoint call counts (whitelist proof):")
    for ep, n in sorted(request_log.items()):
        lines.append(f"  - `{ep}`: {n}")
    lines.append("")
    lines.append("## Archived files (sha256 of redacted content)")
    lines.append("")
    lines.append("| file | logical path | status | account-level | amounts redacted | sha256 |")
    lines.append("|---|---|---|---|---|---|")
    for e in endpoints:
        lines.append(
            f"| `{e['archived_file']}` | `{e['logical_path']}` | {e['http_status']} "
            f"| {e['is_account_level']} | {e['amounts_redacted']} | `{e['sha256']}` |"
        )
    lines.append("")
    lines.append("## Measured rate-limit weight headers (per call; G3 budget-table input)")
    lines.append("")
    lines.append("| logical path | status | weight headers |")
    lines.append("|---|---|---|")
    for e in endpoints:
        wh = e["weight_headers"] or {}
        wh_str = ", ".join(f"{k}={v}" for k, v in sorted(wh.items())) if wh else "(none captured)"
        lines.append(f"| `{e['logical_path']}` | {e['http_status']} | {wh_str} |")
    lines.append("")
    lines.append("## Redaction policy")
    lines.append("")
    lines.append("- URL query strings stripped from all archived metadata (only logical path kept); "
                 "key/secret/signature/recvWindow/timestamp never archived.")
    lines.append("- Account-level responses (E2/E2b/E5/E3/E4/E6/W4/E1/E1b): numeric-string amount "
                 "fields -> literal `<AMOUNT>`; account-identifier integer fields {uid, vipLevel} -> "
                 "`<ID>` (keys, structure and types preserved). Integer error codes on error bodies "
                 "are not amount strings and survive for diagnosis.")
    lines.append("- Market-level public responses (allPairs/allAssets/crossMarginData/ticker-price): "
                 "public market/config data, no account amounts to redact.")
    lines.append("")
    lines.append("## maxBorrowable sample assets")
    lines.append("")
    lines.append(f"- `{FIXED_ASSET}`: fixed by stage prompt.")
    lines.append(f"- `{candidate_asset}`: {candidate_rationale}")
    lines.append("")
    lines.append("## Cost-leg four-level chain hit tier (10-design §1.3)")
    lines.append("")
    lines.append(f"- **hit tier {tier_int}** -> `borrow_rate_source = {source_enum}`")
    lines.append(f"- rationale: {tier_rationale}")
    lines.append("- E2/E2b/E5 failures are NON-blocking (chain degrades per design); only E3/E4/E6 block.")
    lines.append("")
    lines.append("## Gate status (G2)")
    lines.append("")
    if blocking_failed:
        lines.append("**BLOCKING endpoint FAILED: " + ", ".join(f"`{p}`" for p in blocking_failed)
                     + "** -> status = blocked; raw error codes archived in the file(s) above; "
                     "escalate user; NO silent fallback.")
    else:
        lines.append("All blocking endpoints (E3/E4/E6) captured successfully; G2 blocking gate PASSED.")
    if nonblocking_failures:
        lines.append("")
        lines.append("Non-blocking failures recorded (do not block H_intake): "
                     + ", ".join(f"`{p}`" for p in nonblocking_failures) + ".")
    (out_dir / "evidence-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_fail(status: Optional[int]) -> bool:
    return status is None or (isinstance(status, int) and status >= 400)


def main() -> int:
    key, secret = require_env()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = SAMPLES_ROOT / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    request_log: Counter = Counter()
    endpoints: List[Dict[str, Any]] = []
    nonblocking_failures: List[str] = []

    def rec_signed(path: str, filename: str, extra_params: Optional[Dict[str, str]] = None) -> Tuple[Optional[int], Optional[Any]]:
        status, body, lat, err, wh = signed_get(key, secret, "GET", path, request_log, extra_params)
        parsed = archive(out_dir, filename, body, status, path, lat, err, wh, endpoints)
        return status, parsed

    # P5 public ticker/price (full, once) — valuation price map evidence
    status, body, lat, err, wh = public_get("GET", "/api/v3/ticker/price", request_log)
    archive(out_dir, path_to_filename("/api/v3/ticker/price"), body, status,
            "/api/v3/ticker/price", lat, err, wh, endpoints)
    if _is_fail(status):
        nonblocking_failures.append("/api/v3/ticker/price")

    # W1-W3 market-level signed reference (no redaction)
    w3_status_parsed: Tuple[Optional[int], Optional[Any]] = (None, None)
    for path in ("/sapi/v1/margin/allPairs", "/sapi/v1/margin/allAssets", "/sapi/v1/margin/crossMarginData"):
        st, pr = rec_signed(path, path_to_filename(path))
        if path == "/sapi/v1/margin/crossMarginData":
            w3_status_parsed = (st, pr)
        if _is_fail(st):
            nonblocking_failures.append(path)

    # E5 account/info (chain③ tier source; redacted)
    e5_status_parsed = rec_signed("/sapi/v1/account/info", path_to_filename("/sapi/v1/account/info"))
    if _is_fail(e5_status_parsed[0]):
        nonblocking_failures.append("/sapi/v1/account/info")

    # E2 next-hourly (chain①; assets=BTC,ETH sample)
    e2_status_parsed = rec_signed(
        "/sapi/v1/margin/next-hourly-interest-rate",
        path_to_filename("/sapi/v1/margin/next-hourly-interest-rate"),
        extra_params={"assets": "BTC,ETH"},
    )
    if _is_fail(e2_status_parsed[0]):
        nonblocking_failures.append("/sapi/v1/margin/next-hourly-interest-rate")

    # E2b interestRateHistory (chain②; asset=BTC sample)
    e2b_status_parsed = rec_signed(
        "/sapi/v1/margin/interestRateHistory",
        path_to_filename("/sapi/v1/margin/interestRateHistory"),
        extra_params={"asset": "BTC"},
    )
    if _is_fail(e2b_status_parsed[0]):
        nonblocking_failures.append("/sapi/v1/margin/interestRateHistory")

    # E3 /papi/v1/balance — BLOCKING
    e3_status_parsed = rec_signed("/papi/v1/balance", path_to_filename("/papi/v1/balance"))
    # E4 /papi/v1/um/positionRisk — BLOCKING
    e4_status_parsed = rec_signed("/papi/v1/um/positionRisk", path_to_filename("/papi/v1/um/positionRisk"))
    # E6 /api/v3/account (omitZeroBalances=true) — BLOCKING
    e6_status_parsed = rec_signed(
        "/api/v3/account", path_to_filename("/api/v3/account"),
        extra_params={"omitZeroBalances": "true"},
    )

    # W4 maxBorrowable, 2 asset samples (REDACT)
    candidate_asset, candidate_rationale = pick_candidate_asset()
    for asset in (FIXED_ASSET, candidate_asset):
        st, _ = rec_signed(
            "/papi/v1/margin/maxBorrowable",
            path_to_filename("/papi/v1/margin/maxBorrowable", suffix=f"-{asset}"),
            extra_params={"asset": asset},
        )
        if _is_fail(st):
            nonblocking_failures.append(f"/papi/v1/margin/maxBorrowable[{asset}]")

    # E1/E1b discovery-only attribution comparison (one each; REDACT)
    e1_st, _ = rec_signed(
        "/papi/v1/margin/marginInterestHistory",
        path_to_filename("/papi/v1/margin/marginInterestHistory"),
        extra_params={"asset": "BTC"},
    )
    if _is_fail(e1_st):
        nonblocking_failures.append("/papi/v1/margin/marginInterestHistory")
    e1b_st, _ = rec_signed(
        "/papi/v1/portfolio/interest-history",
        path_to_filename("/papi/v1/portfolio/interest-history"),
    )
    if _is_fail(e1b_st):
        nonblocking_failures.append("/papi/v1/portfolio/interest-history")

    # Blocking gate: E3/E4/E6
    blocking_failed: List[str] = []
    for path, sp in (("/papi/v1/balance", e3_status_parsed),
                     ("/papi/v1/um/positionRisk", e4_status_parsed),
                     ("/api/v3/account", e6_status_parsed)):
        if _is_fail(sp[0]):
            blocking_failed.append(path)

    chain_tier = compute_chain_tier(e2_status_parsed, e2b_status_parsed, w3_status_parsed, e5_status_parsed)

    # de-dup nonblocking list preserving order
    seen = set()
    nonblocking_failures = [x for x in nonblocking_failures if not (x in seen or seen.add(x))]

    write_evidence_index(out_dir, ts, endpoints, request_log, candidate_asset,
                         candidate_rationale, chain_tier, blocking_failed, nonblocking_failures)

    # console summary (NO key/secret/signature/query ever printed)
    print(f"captured_at_utc={ts}")
    print(f"out_dir={out_dir}")
    for e in endpoints:
        flag = "OK" if e["http_status"] == 200 else f"ERR({e['http_status']}/{e['error']})"
        wh = e["weight_headers"] or {}
        wh_short = ",".join(f"{k.split('-USED-',1)[-1]}={v}" for k, v in sorted(wh.items())) if wh else "-"
        print(f"  {e['logical_path']:<48} {e['http_status']} {flag}  redact={e['amounts_redacted']}  weight=[{wh_short}]")
    print(f"candidate_asset={candidate_asset}")
    print(f"chain_tier={chain_tier[0]} source={chain_tier[1]}")
    if blocking_failed:
        print("BLOCKING FAILED: " + ", ".join(blocking_failed) + " -> status=blocked; escalate user.")
        return 2
    if nonblocking_failures:
        print("non-blocking failures recorded: " + ", ".join(nonblocking_failures))
    print("H_intake discovery capture complete; blocking gate PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
