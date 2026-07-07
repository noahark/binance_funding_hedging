#!/usr/bin/env python3
"""Gate B next-hourly batch-limit probe.

Read-only survey of GET /sapi/v1/margin/next-hourly-interest-rate to determine
why the in-service call with 50 comma-joined assets silently returns empty.

No orders, borrows, repays, transfers, business-code changes, or git commits.
Credentials are read from the project .env file at runtime and never logged.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_PATH = PROJECT_ROOT / ".env"

RECV_WINDOW = "10000"
USER_AGENT = "funding-hedging-borrow-rate-survey/1.1"
BASE_URL = "https://api.binance.com"

# 66 candidate assets from Gate A live check, in the order emitted by the
# service's probed_assets list (assumed abs-daily-rate DESC).
CANDIDATES = [
    "BLUR", "0G", "ACH", "AGLD", "AIGENSYN", "ALGO", "ARB", "ARKM", "ARPA",
    "ATOM", "AXS", "BANANA", "BARD", "BCH", "BEL", "CETUS", "EPIC", "FET",
    "FLUX", "GALA", "GRAM", "GRT", "GTC", "HBAR", "HEI", "HOME", "ID", "INJ",
    "JOE", "JST", "JUP", "LA", "LAYER", "LQTY", "ME", "MINA", "MIRA", "OGN",
    "ONG", "OPG", "OP", "PENGU", "PLUME", "PROVE", "RESOLV", "RE", "RPL", "SEI",
    "SENT", "SLP", "SOL", "SPELL", "TLM", "TRUMP", "TST", "TWT", "USDC", "VANRY",
    "VTHO", "WIF", "WLD", "XLM", "XRP", "XVS", "YFI", "ZK",
]

SAMPLE_DIR = Path(
    "reports/api-samples/private-account-v1-direction/"
    "borrow-rate-endpoint-survey-20260707T120945Z"
)
RAW_DIR = SAMPLE_DIR / "raw"
SANITIZED_DIR = SAMPLE_DIR / "sanitized"


def load_env(path: Path) -> Dict[str, str]:
    """Parse a minimal KEY=VALUE .env file (no shell expansion)."""
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


ENV = load_env(ENV_PATH)
API_KEY = ENV.get("BINANCE_API_KEY", os.environ.get("BINANCE_API_KEY", ""))
API_SECRET = ENV.get("BINANCE_API_SECRET", os.environ.get("BINANCE_API_SECRET", ""))


def sign(params: Dict[str, str]) -> str:
    qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted(params.items()))
    return hmac.new(API_SECRET.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256).hexdigest()


def call_next_hourly(assets: List[str], is_isolated: str = "false") -> Dict[str, Any]:
    if not API_KEY or not API_SECRET:
        raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET missing")

    params: Dict[str, str] = {
        "assets": ",".join(assets),
        "isIsolated": is_isolated,
        "recvWindow": RECV_WINDOW,
        "timestamp": str(int(time.time() * 1000)),
    }
    qs = "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted(params.items()))
    signature = sign(params)
    url = f"{BASE_URL}/sapi/v1/margin/next-hourly-interest-rate?{qs}&signature={signature}"

    req = urllib.request.Request(
        url,
        headers={"X-MBX-APIKEY": API_KEY, "User-Agent": USER_AGENT},
        method="GET",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            headers = dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = exc.code
        headers = dict(exc.headers)
    latency = round((time.monotonic() - t0) * 1000, 1)

    try:
        payload = json.loads(body)
    except Exception:
        payload = {"__parse_error": body[:500]}

    returned_assets: List[str] = []
    if isinstance(payload, list):
        returned_assets = [str(x.get("asset")) for x in payload if isinstance(x, dict)]

    return {
        "url": url,
        "status": status,
        "headers": headers,
        "payload": payload,
        "latency_ms": latency,
        "request_asset_count": len(assets),
        "request_query_bytes": len(params["assets"].encode("utf-8")),
        "returned_asset_count": len(returned_assets),
        "missing_assets": [a for a in assets if a not in returned_assets],
        "binance_code": payload.get("code") if isinstance(payload, dict) else None,
        "binance_msg": payload.get("msg") if isinstance(payload, dict) else None,
        "weight_1m": headers.get("X-SAPI-USED-IP-WEIGHT-1M", headers.get("x-sapi-used-ip-weight-1m", "")),
        "isIsolated": is_isolated,
    }


def conclusion_tag(r: Dict[str, Any]) -> str:
    status = r["status"]
    code = r["binance_code"]
    msg = (r["binance_msg"] or "").lower()
    if status == 429:
        return "WEIGHT_LIMITED"
    if status == 400 and code == -1003:
        return "WEIGHT_LIMITED"
    if status == 400 and code == -11001:
        return "ILLEGAL_ASSET"
    if status == 400 and code == -3026:
        return "PARAM_ERROR"
    if status >= 400:
        if "size" in msg and "larger than" in msg:
            return "LIMIT_HIT"
        return "LIMIT_HIT" if code in (-1003, None) else "PARAM_ERROR"
    if r["returned_asset_count"] < r["request_asset_count"]:
        return "PARTIAL"
    return "SUCCESS"


def save_evidence(name: str, assets: List[str], r: Dict[str, Any]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SANITIZED_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = RAW_DIR / f"{name}.json"
    sanitized_path = SANITIZED_DIR / f"{name}.json"

    # Strip signature and timestamp from URL before saving even to raw.
    parsed = urllib.parse.urlparse(r["url"])
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    qs.pop("signature", None)
    qs["timestamp"] = ["<REDACTED>"]
    safe_qs = urllib.parse.urlencode(qs, doseq=True)
    safe_url = urllib.parse.urlunparse(parsed._replace(query=safe_qs))

    record = {
        "endpoint": "/sapi/v1/margin/next-hourly-interest-rate",
        "params": {"assets": ",".join(assets), "isIsolated": r["isIsolated"]},
        "status": r["status"],
        "weight_headers": {"x-sapi-used-ip-weight-1m": r["weight_1m"]},
        "latency_ms": r["latency_ms"],
        "request_asset_count": r["request_asset_count"],
        "request_query_bytes": r["request_query_bytes"],
        "returned_asset_count": r["returned_asset_count"],
        "missing_assets": r["missing_assets"],
        "binance_code": r["binance_code"],
        "binance_msg": r["binance_msg"],
        "conclusion": conclusion_tag(r),
        "payload": r["payload"],
    }

    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump({**record, "url": safe_url}, fh, ensure_ascii=False, indent=2)

    with open(sanitized_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)

    return sanitized_path


def print_matrix_row(r: Dict[str, Any]) -> None:
    print(
        f"n={r['request_asset_count']:2d} | "
        f"status={r['status']:3d} | "
        f"code={str(r['binance_code']):>7s} | "
        f"returned={r['returned_asset_count']:2d}/{r['request_asset_count']:2d} | "
        f"weight={r['weight_1m']:>5s} | "
        f"tag={conclusion_tag(r):14s} | "
        f"bytes={r['request_query_bytes']:3d}"
    )


def t1_step_ladder() -> List[Dict[str, Any]]:
    print("\n=== T1 step-ladder (N=9,20,30,40,45,50,55,60,66) ===")
    ns = [9, 20, 21, 30, 40, 45, 50, 55, 60, 66]
    results: List[Dict[str, Any]] = []
    for n in ns:
        assets = CANDIDATES[:n]
        r = call_next_hourly(assets)
        save_evidence(f"next_hourly_batch_limit_t1_n{n:02d}", assets, r)
        results.append(r)
        print_matrix_row(r)
        time.sleep(0.5)
    return results


def t2_service_top50() -> Dict[str, Any]:
    print("\n=== T2 service call replica (top 50) ===")
    assets = CANDIDATES[:50]
    r = call_next_hourly(assets)
    save_evidence("next_hourly_batch_limit_t2_top50", assets, r)
    print_matrix_row(r)
    return r


def t3_length_control(failing_n: int) -> List[Dict[str, Any]]:
    print(f"\n=== T3 length-control at N={failing_n} ===")
    # Pick 20 unique short-ticker assets and 20 unique long-ticker assets.
    # Both groups exceed the limit if the limit is < 20; if both succeed,
    # the failure at N={failing_n} is driven by count, not string length.
    short_unique = ["0G", "ID", "LA", "ME", "OP", "RE", "ARB", "BCH", "BEL", "SOL", "BTC", "ETH", "SEI", "JOE", "JST", "LQTY", "OGN", "ONG", "TLM", "XLM"]
    short_unique = list(dict.fromkeys(short_unique))[:20]
    long_unique = ["AIGENSYN", "BANANA", "RESOLV", "PENGU", "PLUME", "PROVE", "LAYER", "TRUMP", "VANRY", "CETUS", "FLUX", "GALA", "GRAM", "GRT", "GTC", "HBAR", "HEI", "HOME", "INJ", "ACH"]
    long_unique = list(dict.fromkeys(long_unique))[:20]

    results: List[Dict[str, Any]] = []
    for label, pool in [("short", short_unique), ("long", long_unique)]:
        r = call_next_hourly(pool)
        save_evidence(f"next_hourly_batch_limit_t3_{label}_n{len(pool):02d}", pool, r)
        print(f"{label:5s} ", end="")
        print_matrix_row(r)
        results.append({"label": label, "result": r})
        time.sleep(0.5)
    return results


def t4_repeated_top50() -> List[Dict[str, Any]]:
    print("\n=== T4 repeated top-50 (weight/429 check) ===")
    assets = CANDIDATES[:50]
    results: List[Dict[str, Any]] = []
    for i in range(5):
        r = call_next_hourly(assets)
        save_evidence(f"next_hourly_batch_limit_t4_repeat{i+1}", assets, r)
        print(f"rep{i+1} ", end="")
        print_matrix_row(r)
        results.append(r)
        time.sleep(1.0)
    return results


def t5_binary_search(assets: List[str]) -> Optional[Tuple[str, Dict[str, Any]]]:
    print(f"\n=== T5 binary search for illegal asset among {len(assets)} ===")
    if len(assets) <= 1:
        if assets:
            r = call_next_hourly(assets)
            save_evidence(f"next_hourly_batch_limit_t5_single_{assets[0]}", assets, r)
            return (assets[0], r) if r["status"] >= 400 else None
        return None

    mid = len(assets) // 2
    left, right = assets[:mid], assets[mid:]

    r_left = call_next_hourly(left)
    save_evidence(f"next_hourly_batch_limit_t5_left_{len(left)}", left, r_left)
    print("left  ", end="")
    print_matrix_row(r_left)
    time.sleep(0.5)

    if r_left["status"] >= 400:
        return t5_binary_search(left)

    r_right = call_next_hourly(right)
    save_evidence(f"next_hourly_batch_limit_t5_right_{len(right)}", right, r_right)
    print("right ", end="")
    print_matrix_row(r_right)
    time.sleep(0.5)

    if r_right["status"] >= 400:
        return t5_binary_search(right)

    print("T5: both halves succeeded; no single illegal asset found in this branch.")
    return None


def main() -> None:
    if not API_KEY or not API_SECRET:
        raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET missing")

    print(f"Probe start UTC: {datetime.now(timezone.utc).isoformat()}")
    print(f"Sample dir: {SAMPLE_DIR}")

    t1_results = t1_step_ladder()
    t2_result = t2_service_top50()

    failing_ns = [r["request_asset_count"] for r in t1_results if r["status"] >= 400]
    first_failing_n = failing_ns[0] if failing_ns else None

    t3_results: List[Dict[str, Any]] = []
    if first_failing_n is not None:
        t3_results = t3_length_control(first_failing_n)

    t4_results = t4_repeated_top50()

    t5_result: Optional[Tuple[str, Dict[str, Any]]] = None
    if t2_result["status"] >= 400:
        small_ok = any(r["status"] == 200 for r in t1_results)
        if small_ok:
            t5_result = t5_binary_search(CANDIDATES[:50])

    # T6 recommendations
    print("\n=== T6 recommendations ===")
    if not failing_ns:
        max_safe = 66
        recommended = 50
        batches = math.ceil(66 / recommended)
        print(f"No LIMIT_HIT observed up to 66 assets.")
        print(f"  next_hourly_max_assets_per_call   = {max_safe}")
        print(f"  recommended_batch_size            = {recommended} (existing service default)")
        print(f"  batches_to_cover_66               = {batches}")
        print(f"  total_weight_per_snapshot         = {batches * 100}")
    else:
        # Find the largest N that succeeded.
        success_ns = [r["request_asset_count"] for r in t1_results if r["status"] == 200]
        max_safe = max(success_ns) if success_ns else 9
        recommended = max(1, max_safe - 5)
        recommended = min(recommended, 45)
        batches = math.ceil(66 / recommended)
        print(f"First failure at N={first_failing_n}; max observed safe N={max_safe}")
        print(f"  next_hourly_max_assets_per_call   = {max_safe}")
        print(f"  recommended_batch_size            = {recommended} (headroom below observed limit)")
        print(f"  batches_to_cover_66               = {batches}")
        print(f"  total_weight_per_snapshot         = {batches * 100}")

    if t5_result:
        asset, r = t5_result
        print(f"  illegal_asset_candidate           = {asset} (status={r['status']} code={r['binance_code']})")

    # Emit a machine-readable summary.
    summary = {
        "probe_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": "/sapi/v1/margin/next-hourly-interest-rate",
        "candidate_count": len(CANDIDATES),
        "t1_step_ladder": [
            {
                "n": r["request_asset_count"],
                "status": r["status"],
                "binance_code": r["binance_code"],
                "returned": r["returned_asset_count"],
                "missing_count": len(r["missing_assets"]),
                "weight_1m": r["weight_1m"],
                "query_bytes": r["request_query_bytes"],
                "conclusion": conclusion_tag(r),
                "sanitized": f"sanitized/next_hourly_batch_limit_t1_n{r['request_asset_count']:02d}.json",
            }
            for r in t1_results
        ],
        "t2_service_top50": {
            "status": t2_result["status"],
            "binance_code": t2_result["binance_code"],
            "returned": t2_result["returned_asset_count"],
            "weight_1m": t2_result["weight_1m"],
            "conclusion": conclusion_tag(t2_result),
            "sanitized": "sanitized/next_hourly_batch_limit_t2_top50.json",
        },
        "t3_length_control": [
            {"label": x["label"], "status": x["result"]["status"], "binance_code": x["result"]["binance_code"],
             "returned": x["result"]["returned_asset_count"], "conclusion": conclusion_tag(x["result"])}
            for x in t3_results
        ],
        "t4_repeated_top50": [
            {"rep": i + 1, "status": r["status"], "binance_code": r["binance_code"],
             "weight_1m": r["weight_1m"], "conclusion": conclusion_tag(r)}
            for i, r in enumerate(t4_results)
        ],
        "t5_binary_search": {
            "illegal_asset": t5_result[0] if t5_result else None,
            "status": t5_result[1]["status"] if t5_result else None,
            "binance_code": t5_result[1]["binance_code"] if t5_result else None,
        },
        "t6_recommendations": {
            "next_hourly_max_assets_per_call": max_safe if not failing_ns else max_safe,
            "recommended_batch_size": recommended if not failing_ns else recommended,
            "batches_to_cover_66": batches,
            "total_weight_per_snapshot": batches * 100,
        },
    }

    summary_path = SAMPLE_DIR / "next_hourly_batch_limit_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
