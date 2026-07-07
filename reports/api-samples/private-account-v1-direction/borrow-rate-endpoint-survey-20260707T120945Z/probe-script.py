#!/usr/bin/env python3
"""Read-only borrow-rate endpoint survey probe.

This script is a one-off discovery artifact. It calls only GET endpoints that are
already in backend/services/private_client.py:WHITELIST. No orders, borrows,
repays, or transfers are performed.

Outputs:
- raw/*.json: full response bodies with headers (in-memory analysis only; not
  committed to git by this tool run).
- sanitized/*.json: redacted response bodies safe for archiving.
- stdout: a concise evidence matrix for the report.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
RECV_WINDOW = "10000"
USER_AGENT = "funding-hedging-borrow-rate-survey/1.0"

BASE_URLS = {
    "sapi": "https://api.binance.com",
    "papi": "https://papi.binance.com",
}

# 9 candidate assets: OPG positive control, UI-gap assets, DOGE, liquid, bStock.
ASSETS = ["OPG", "0G", "AIGENSYN", "ALGO", "DOGE", "BTC", "ETH", "SOL", "TSLAB"]


def sign(params: Dict[str, str]) -> str:
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(
        API_SECRET.encode("utf-8"), qs.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def call(base_family: str, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    base = BASE_URLS[base_family]
    p = dict(params or {})
    p["recvWindow"] = RECV_WINDOW
    p["timestamp"] = str(int(time.time() * 1000))
    qs = "&".join(f"{k}={v}" for k, v in sorted(p.items()))
    signature = sign(p)
    url = f"{base}{path}?{qs}&signature={signature}"
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
    return {
        "url": url,
        "status": status,
        "headers": headers,
        "payload": payload,
        "latency_ms": latency,
    }


def weight_headers(headers: Dict[str, str]) -> Dict[str, str]:
    keys = [
        "x-mbx-used-weight-1m",
        "x-mbx-used-weight",
        "x-mbx-used-uid-weight-1m",
        "x-mbx-used-uid-weight",
        "x-sapi-used-ip-weight-1m",
        "x-sapi-used-uid-weight-1m",
        "x-sapi-used-weight-1m",
        "x-response-time",
    ]
    lower = {k.lower(): v for k, v in headers.items()}
    return {k: lower.get(k, "") for k in keys if lower.get(k)}


def all_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Return all headers with original casing for forensic inspection."""
    return dict(headers)


def sanitize_account_info(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    redacted = dict(payload)
    for k in list(redacted.keys()):
        if k.lower() in {"uid", "accountid", "email", "mobilenumber", "inserttime"}:
            redacted[k] = "<REDACTED>"
    # balances / permissions: keep permission names only, drop amounts
    if isinstance(redacted.get("permissions"), list):
        redacted["permissions"] = [str(x) for x in redacted["permissions"]]
    return redacted


def sanitize_max_borrowable(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    out: Dict[str, Any] = {}
    for k in ("amount", "borrowLimit"):
        v = payload.get(k)
        if v is None:
            out[k] = {"present": False, "type": None, "non_empty": False, "gt_zero": None}
        else:
            try:
                gt_zero = Decimal(str(v)) > 0
            except Exception:
                gt_zero = None
            out[k] = {
                "present": True,
                "type": type(v).__name__,
                "non_empty": bool(str(v).strip()),
                "gt_zero": gt_zero,
            }
    # keep any other non-sensitive scalar keys if they exist
    for k, v in payload.items():
        if k not in out:
            out[k] = v if not isinstance(v, (dict, list)) else type(v).__name__
    return out


def sanitize_interest_history(payload: Any) -> Any:
    """Redact absolute interest/principal amounts while preserving rate/time/asset."""
    if not isinstance(payload, list):
        return payload
    out = []
    for row in payload[:5]:  # cap sample rows
        if not isinstance(row, dict):
            continue
        redacted = {}
        for k, v in row.items():
            lk = k.lower()
            if any(x in lk for x in ("interest", "principal", "amount", "income")):
                redacted[k] = {"type": type(v).__name__, "redacted": True}
            else:
                redacted[k] = v
        out.append(redacted)
    return out


def sanitize(endpoint: str, payload: Any) -> Any:
    if endpoint == "/sapi/v1/account/info":
        return sanitize_account_info(payload)
    if endpoint == "/papi/v1/margin/maxBorrowable":
        return sanitize_max_borrowable(payload)
    if endpoint in ("/papi/v1/margin/marginInterestHistory", "/papi/v1/portfolio/interest-history"):
        return sanitize_interest_history(payload)
    return payload


def save_evidence(
    name: str,
    endpoint: str,
    params: Dict[str, str],
    result: Dict[str, Any],
    raw_dir: str,
    sanitized_dir: str,
) -> None:
    raw_path = os.path.join(raw_dir, f"{name}.json")
    sanitized_path = os.path.join(sanitized_dir, f"{name}.json")
    evidence = {
        "endpoint": endpoint,
        "params": params,
        "status": result["status"],
        "weight_headers": weight_headers(result["headers"]),
        "all_headers": all_headers(result["headers"]),
        "latency_ms": result["latency_ms"],
        "payload": result["payload"],
    }
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=2)
    evidence["payload"] = sanitize(endpoint, result["payload"])
    with open(sanitized_path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, ensure_ascii=False, indent=2)


def summarize_fields(payload: Any, path: str = "$") -> List[Dict[str, str]]:
    rows = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            rows.append({"path": f"{path}.{k}", "type": type(v).__name__})
            rows.extend(summarize_fields(v, f"{path}.{k}"))
    elif isinstance(payload, list) and payload:
        rows.append({"path": f"{path}[]", "type": f"list[{type(payload[0]).__name__}]"})
        if isinstance(payload[0], dict):
            for k, v in payload[0].items():
                rows.append({"path": f"{path}[].{k}", "type": type(v).__name__})
    return rows


def main() -> None:
    if not API_KEY or not API_SECRET:
        raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET missing")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sample_dir = f"reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-{ts}"
    raw_dir = os.path.join(sample_dir, "raw")
    sanitized_dir = os.path.join(sample_dir, "sanitized")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(sanitized_dir, exist_ok=True)

    calls: List[Tuple[str, str, Dict[str, str], str]] = []

    # 1. next-hourly (batch)
    calls.append((
        "next_hourly_batch",
        "/sapi/v1/margin/next-hourly-interest-rate",
        {"assets": ",".join(ASSETS), "isIsolated": "false"},
        "sapi",
    ))

    # 2. interestRateHistory per asset
    for asset in ASSETS:
        calls.append((
            f"interest_rate_history_{asset}",
            "/sapi/v1/margin/interestRateHistory",
            {"asset": asset},
            "sapi",
        ))

    # 3. crossMarginData
    calls.append((
        "cross_margin_data",
        "/sapi/v1/margin/crossMarginData",
        {},
        "sapi",
    ))

    # 4. account.info
    calls.append((
        "account_info",
        "/sapi/v1/account/info",
        {},
        "sapi",
    ))

    # 5. maxBorrowable per asset
    for asset in ASSETS:
        calls.append((
            f"max_borrowable_{asset}",
            "/papi/v1/margin/maxBorrowable",
            {"asset": asset},
            "papi",
        ))

    # 6a. marginInterestHistory (try OPG then no-asset)
    calls.append((
        "margin_interest_history_opg",
        "/papi/v1/margin/marginInterestHistory",
        {"asset": "OPG", "size": "5"},
        "papi",
    ))
    calls.append((
        "margin_interest_history_no_asset",
        "/papi/v1/margin/marginInterestHistory",
        {"size": "5"},
        "papi",
    ))

    # 6b. portfolio interest-history
    calls.append((
        "portfolio_interest_history_opg",
        "/papi/v1/portfolio/interest-history",
        {"asset": "OPG", "size": "5"},
        "papi",
    ))
    calls.append((
        "portfolio_interest_history_no_asset",
        "/papi/v1/portfolio/interest-history",
        {"size": "5"},
        "papi",
    ))

    results: Dict[str, Dict[str, Any]] = {}
    for name, endpoint, params, family in calls:
        result = call(family, endpoint, params)
        save_evidence(name, endpoint, params, result, raw_dir, sanitized_dir)
        results[name] = result
        time.sleep(0.25)  # conservative spacing

    # Print concise matrix for the report.
    print("\n=== Endpoint Survey Matrix ===")
    for name, endpoint, params, family in calls:
        r = results[name]
        payload = r["payload"]
        is_list = isinstance(payload, list)
        is_dict = isinstance(payload, dict)
        item_count = len(payload) if is_list else None
        code = payload.get("code") if is_dict else None
        msg = payload.get("msg") if is_dict else None
        print(
            f"{name:40s} | {endpoint:45s} | status={r['status']:3d} | "
            f"weight={json.dumps(weight_headers(r['headers']), ensure_ascii=False)} | "
            f"items={item_count} code={code} msg={msg}"
        )

    print(f"\nSample directory: {sample_dir}")


if __name__ == "__main__":
    main()
