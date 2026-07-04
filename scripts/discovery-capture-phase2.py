#!/usr/bin/env python3
"""One-shot H_intake discovery capture for stage 2026-07-phase2-borrow-sort-v1.

Calls EXACTLY the 5 whitelisted endpoints (4 HMAC-SHA256 signed GET + 1 public
GET fundingInfo), redacts at capture time, archives under
reports/api-samples/<stage>/<UTC-ts>/ with an sha256 evidence-index.

Security posture (reviewer-checkable):
- deny-by-default whitelist of (method, exact-path) pairs, hardcoded in-script;
  the whitelist check raises BEFORE any signature is constructed.
- GET-only code path; no POST/PUT/DELETE is ever constructed.
- key/secret/signature/full query string are NEVER printed, logged, or archived;
  archived metadata records only the sanitized logical path.
- account-level response (maxBorrowable) has its amount values replaced with a
  placeholder at capture time, preserving keys, structure and type info.
- market-level responses (allPairs/allAssets/crossMarginData) are public market
  data: no amount redaction, only URL query stripping on archive.

Run AFTER `source ~/.binance-keys` (BINANCE_API_KEY/BINANCE_API_SECRET in env).
Exit codes: 0 = all endpoints captured; 2 = at least one signed endpoint failed
(E5 maxBorrowable failure OR E2/E3/E4 failure) -> controller must set status to
human_escalation_required and surface raw error code to user; no silent fallback.
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
STAGE_ID = "2026-07-phase2-borrow-sort-v1"
SAMPLES_ROOT = REPO_ROOT / "reports" / "api-samples" / STAGE_ID

# ---- deny-by-default endpoint whitelist (hardcoded, the only truth) ----
SIGNED_WHITELIST: Dict[Tuple[str, str], str] = {
    ("GET", "/sapi/v1/margin/allPairs"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/allAssets"): "https://api.binance.com",
    ("GET", "/sapi/v1/margin/crossMarginData"): "https://api.binance.com",
    ("GET", "/papi/v1/margin/maxBorrowable"): "https://papi.binance.com",
}
PUBLIC_WHITELIST: Dict[Tuple[str, str], str] = {
    ("GET", "/fapi/v1/fundingInfo"): "https://fapi.binance.com",
}
ACCOUNT_LEVEL_PATHS = {"/papi/v1/margin/maxBorrowable"}

RECV_WINDOW = 10000
TIMEOUT = 15.0
USER_AGENT = "funding-hedging-h-intake-discovery/1.0"

# E5 maxBorrowable sample assets. BTC is fixed (stage prompt). The 2nd sample is
# the "highest daily-rate candidate asset": premiumIndex (lastFundingRate) is
# OUTSIDE the 5-endpoint whitelist, so candidate ranking uses the Phase 1 fixture
# snapshot's last_funding_rate (offline) crossed with the live fundingInfo
# interval captured in this same run.
FIXED_ASSET = "BTC"
FIXTURE_PATH = REPO_ROOT / "frontend" / "fixture" / "public-market-snapshot.json"
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
    """Replace numeric-string amounts with '<AMOUNT>', preserving keys,
    structure and type (string stays string). Integer error codes (JSON numbers)
    are NOT strings, so they survive untouched on error bodies."""
    if isinstance(obj, dict):
        return {k: redact_account_amounts(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_account_amounts(v) for v in obj]
    if _is_amount_string(obj):
        return "<AMOUNT>"
    return obj


def signed_get(
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    base_url: str,
    request_log: Counter,
    extra_params: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[int], str, float, Optional[str]]:
    """HMAC-SHA256 signed GET. Whitelist + GET-only enforced BEFORE signing."""
    if (method, path) not in SIGNED_WHITELIST:
        raise PermissionError(f"endpoint not in signed whitelist: {method} {path}")
    if method != "GET":
        raise PermissionError(f"only GET implemented; got {method}")
    request_log[f"{method} {path}"] += 1

    params: Dict[str, str] = dict(extra_params or {})
    params["recvWindow"] = str(RECV_WINDOW)
    params["timestamp"] = str(int(time.time() * 1000))
    # deterministic key order for signature stability
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(api_secret.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256).hexdigest()
    # NOTE: url contains the signature; never print/log/archive it.
    url = f"{base_url}{path}?{qs}&signature={sig}"
    req = urllib.request.Request(
        url, headers={"X-MBX-APIKEY": api_key, "User-Agent": USER_AGENT}, method="GET"
    )
    return _do_request(req, path)


def public_get(
    method: str,
    path: str,
    base_url: str,
    request_log: Counter,
) -> Tuple[Optional[int], str, float, Optional[str]]:
    if (method, path) not in PUBLIC_WHITELIST:
        raise PermissionError(f"endpoint not in public whitelist: {method} {path}")
    request_log[f"{method} {path}"] += 1
    req = urllib.request.Request(
        f"{base_url}{path}", headers={"User-Agent": USER_AGENT}, method="GET"
    )
    return _do_request(req, path)


def _do_request(
    req: urllib.request.Request, path: str
) -> Tuple[Optional[int], str, float, Optional[str]]:
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8"), (time.monotonic() - t0) * 1000.0, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return exc.code, body, (time.monotonic() - t0) * 1000.0, f"HTTP {exc.code}"
    except Exception as exc:  # network / timeout / DNS
        return None, "", (time.monotonic() - t0) * 1000.0, f"{type(exc).__name__}: {exc}"


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
    is_account_level: bool,
    meta_endpoints: List[Dict[str, Any]],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Redact (if account-level), write file, sha256, append metadata.
    Returns (sha256_hex, parsed_json_or_none)."""
    redacted_text = raw_body
    parsed: Optional[Dict[str, Any]] = None
    redacted_amounts = False
    if is_account_level and raw_body:
        try:
            parsed = json.loads(raw_body)
            parsed = redact_account_amounts(parsed)
            redacted_text = json.dumps(parsed, ensure_ascii=False, indent=2)
            redacted_amounts = True
        except json.JSONDecodeError:
            # non-JSON error body (e.g. plain text) -> keep as-is, no amounts to redact
            parsed = None

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
        }
    )
    return sha, parsed if isinstance(parsed, (dict, list)) else None


def pick_candidate_asset(interval_by_sym: Dict[str, int]) -> Tuple[str, str]:
    """2nd maxBorrowable sample = highest-abs-daily-rate non-BTC candidate from
    the Phase 1 fixture (MARGIN_SPOT_CANDIDATE + CRYPTO), using live interval.
    Returns (asset, rationale)."""
    try:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return CANDIDATE_FALLBACK, f"fixture unreadable; fallback {CANDIDATE_FALLBACK}"

    best_base: Optional[str] = None
    best_daily = Decimal("-1")
    best_detail = ""
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
        sym = f"{base}USDT"
        interval = interval_by_sym.get(sym, 8)
        try:
            daily = abs(Decimal(str(rate))) * (Decimal(24) / Decimal(interval))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if daily > best_daily:
            best_daily = daily
            best_base = base
            best_detail = f"{base}: |{rate}| x 24/{interval}h = {daily}"
    if best_base is None:
        return CANDIDATE_FALLBACK, f"no non-BTC candidate in fixture; fallback {CANDIDATE_FALLBACK}"
    return best_base, (
        f"highest-abs-daily-rate non-BTC MARGIN_SPOT_CANDIDATE+CRYPTO candidate in "
        f"Phase 1 fixture (offline last_funding_rate x live fundingInfo interval). "
        f"{best_detail}"
    )


def write_evidence_index(
    out_dir: Path,
    ts: str,
    endpoints: List[Dict[str, Any]],
    request_log: Counter,
    candidate_asset: str,
    candidate_rationale: str,
    interval_dist: Dict[int, int],
    e5_failed: bool,
    any_signed_failed: bool,
) -> None:
    lines: List[str] = []
    lines.append(f"# Discovery evidence index — {STAGE_ID}")
    lines.append("")
    lines.append(f"- captured_at_utc: `{ts}`")
    lines.append(f"- captured_by: bookkeeper/controller (claude_glm session, H_intake)")
    lines.append(f"- base_urls: fapi/papi/sapi per Binance public docs (hardcoded in script)")
    lines.append(f"- total HTTP calls: {sum(request_log.values())} across {len(request_log)} endpoints")
    lines.append("- endpoint call counts (whitelist proof):")
    for ep, n in sorted(request_log.items()):
        lines.append(f"  - `{ep}`: {n}")
    lines.append("")
    lines.append("## Archived files (sha256 of redacted content)")
    lines.append("")
    lines.append("| file | logical path | status | sha256 | account-level | amounts redacted |")
    lines.append("|---|---|---|---|---|---|")
    for e in endpoints:
        lines.append(
            f"| `{e['archived_file']}` | `{e['logical_path']}` | {e['http_status']} "
            f"| `{e['sha256']}` | {e['is_account_level']} | {e['amounts_redacted']} |"
        )
    lines.append("")
    lines.append("## Redaction policy")
    lines.append("")
    lines.append(
        "- URL query strings stripped from all archived metadata (only logical path kept); "
        "key/secret/signature/recvWindow/timestamp never archived."
    )
    lines.append(
        "- Account-level response (maxBorrowable): numeric-string amount fields replaced with "
        "literal `<AMOUNT>` (keys, structure and string type preserved); integer error codes "
        "(JSON numbers) are not strings and survive on error bodies for diagnosis."
    )
    lines.append("- Market-level responses (allPairs/allAssets/crossMarginData): public market "
                 "data, no amount redaction.")
    lines.append("")
    lines.append(f"## maxBorrowable sample assets")
    lines.append("")
    lines.append(f"- `{FIXED_ASSET}`: fixed by stage prompt.")
    lines.append(f"- `{candidate_asset}: {candidate_rationale}")
    lines.append("")
    lines.append("## fundingInfo interval distribution (live, this run)")
    lines.append("")
    for hours, n in sorted(interval_dist.items()):
        lines.append(f"- {hours}h: {n} symbols")
    lines.append("")
    lines.append("## Gate status")
    lines.append("")
    if e5_failed:
        lines.append("**E5 /papi/v1/margin/maxBorrowable FAILED** -> status = "
                     "human_escalation_required; raw error code archived in the maxBorrowable "
                     "file(s) above; NO silent fallback to /sapi.")
    elif any_signed_failed:
        lines.append("**A market-level signed endpoint (E2/E3/E4) FAILED** -> status = "
                     "human_escalation_required; raw error archived above.")
    else:
        lines.append("All 5 endpoints captured successfully; E5 gate PASSED.")
    (out_dir / "evidence-index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    key, secret = require_env()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = SAMPLES_ROOT / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    request_log: Counter = Counter()
    endpoints: List[Dict[str, Any]] = []
    interval_by_sym: Dict[str, int] = {}

    # 1) public fundingInfo (also feeds candidate selection + interval evidence)
    status, body, lat, err = public_get("GET", "/fapi/v1/fundingInfo", PUBLIC_WHITELIST[("GET", "/fapi/v1/fundingInfo")], request_log)
    try:
        fi = json.loads(body) if status == 200 and body else []
        if isinstance(fi, list):
            interval_by_sym = {x["symbol"]: int(x.get("fundingIntervalHours", 8)) for x in fi if isinstance(x, dict) and "symbol" in x}
    except json.JSONDecodeError:
        fi = []
    archive(out_dir, path_to_filename("/fapi/v1/fundingInfo"), body, status,
            "/fapi/v1/fundingInfo", lat, err, is_account_level=False, meta_endpoints=endpoints)
    interval_dist = dict(Counter(interval_by_sym.values()))

    # 2-4) market-level signed endpoints (no amount redaction)
    for path in ("/sapi/v1/margin/allPairs", "/sapi/v1/margin/allAssets", "/sapi/v1/margin/crossMarginData"):
        status, body, lat, err = signed_get(key, secret, "GET", path, SIGNED_WHITELIST[("GET", path)], request_log)
        archive(out_dir, path_to_filename(path), body, status, path, lat, err,
                is_account_level=False, meta_endpoints=endpoints)

    # 5) account-level maxBorrowable, 2 asset samples (REDACT amounts); E5 gate
    candidate_asset, candidate_rationale = pick_candidate_asset(interval_by_sym)
    e5_failed = False
    for asset in (FIXED_ASSET, candidate_asset):
        status, body, lat, err = signed_get(
            key, secret, "GET", "/papi/v1/margin/maxBorrowable",
            SIGNED_WHITELIST[("GET", "/papi/v1/margin/maxBorrowable")],
            request_log, extra_params={"asset": asset},
        )
        archive(out_dir, path_to_filename("/papi/v1/margin/maxBorrowable", suffix=f"-{asset}"),
                body, status, "/papi/v1/margin/maxBorrowable", lat, err,
                is_account_level=True, meta_endpoints=endpoints)
        if status is None or (isinstance(status, int) and status >= 400):
            e5_failed = True

    any_signed_failed = any(
        e["logical_path"].startswith(("/sapi/", "/papi/"))
        and (e["http_status"] is None or (isinstance(e["http_status"], int) and e["http_status"] >= 400))
        for e in endpoints
    )

    write_evidence_index(out_dir, ts, endpoints, request_log, candidate_asset,
                         candidate_rationale, interval_dist, e5_failed, any_signed_failed)

    # console summary (NO key/secret/signature/query ever printed)
    print(f"captured_at_utc={ts}")
    print(f"out_dir={out_dir}")
    for e in endpoints:
        flag = "OK" if e["http_status"] == 200 else f"ERR({e['http_status']}/{e['error']})"
        print(f"  {e['logical_path']:<40} {e['http_status']} {flag}  sha={e['sha256'][:12]}  redact={e['amounts_redacted']}")
    print(f"candidate_asset={candidate_asset}")
    if e5_failed:
        print("E5 maxBorrowable FAILED -> BLOCKED (human_escalation_required); see archived error bodies.")
        return 2
    if any_signed_failed:
        print("A signed market-level endpoint FAILED -> BLOCKED (human_escalation_required).")
        return 2
    print("ALL 5 ENDPOINTS OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
