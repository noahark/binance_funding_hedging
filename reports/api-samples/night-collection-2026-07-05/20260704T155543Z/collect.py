"""夜间 API 样本采集脚本（公开 + 私有只读白名单）。

- 公开端点：直接 urllib GET，保存原始 JSON + headers。
- 私有端点：经 backend/services/private_client.py 单一 HMAC 出口，
  仅调用 status.json  whitelist 中的四个 GET 端点。
- 所有落档 URL 均剥离 query string；不保存 key/secret/signature。
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
import sys

sys.path.insert(0, str(REPO_ROOT / "backend"))

from services.private_client import PrivateClient  # noqa: E402

USER_AGENT = "funding-hedging-public-market/1.0"
TIMEOUT = 15.0

# 公开端点配置：(name, url, save_filename)
PUBLIC_ENDPOINTS: List[Tuple[str, str, str]] = [
    ("futures_exchangeInfo", "https://fapi.binance.com/fapi/v1/exchangeInfo", "fapi-v1-exchangeInfo"),
    ("premium_index", "https://fapi.binance.com/fapi/v1/premiumIndex", "fapi-v1-premiumIndex"),
    ("funding_info", "https://fapi.binance.com/fapi/v1/fundingInfo", "fapi-v1-fundingInfo"),
    ("spot_exchangeInfo", "https://api.binance.com/api/v3/exchangeInfo", "api-v3-exchangeInfo"),
]

# fundingRate 关注 symbols
FUNDING_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_get(url: str) -> Tuple[Any, Dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
        headers = {k: v for k, v in resp.headers.items()}
        return json.loads(body), headers


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _save_headers(path: Path, headers: Dict[str, str]) -> None:
    # 只保留无敏感信息的头部；Date 由响应给出。
    safe = {
        "status": str(headers.get("status", "")),
        "content-type": headers.get("Content-Type", ""),
        "x-mbx-used-weight-1m": headers.get("x-mbx-used-weight-1m", ""),
        "x-mbx-used-weight": headers.get("x-mbx-used-weight", ""),
        "cf-ray": headers.get("cf-ray", ""),
        "date": headers.get("Date", ""),
    }
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_public(outdir: Path) -> List[Dict[str, Any]]:
    raw_dir = outdir / "raw"
    raw_dir.mkdir(exist_ok=True)
    records: List[Dict[str, Any]] = []

    for name, url, filename in PUBLIC_ENDPOINTS:
        print(f"[public] fetching {name} ...")
        data, headers = _http_get(url)
        _save_json(raw_dir / f"{filename}.json", data)
        _save_headers(raw_dir / f"{filename}.headers", headers)
        records.append(
            {
                "type": "public",
                "name": name,
                "method": "GET",
                "url_stripped": url.split("?")[0],
                "saved_json": f"raw/{filename}.json",
                "saved_headers": f"raw/{filename}.headers",
                "fetched_at": _now_utc(),
            }
        )
        time.sleep(0.5)

    # fundingRate for selected symbols
    for sym in FUNDING_SYMBOLS:
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=20"
        filename = f"fapi-v1-fundingRate-{sym}-limit20"
        print(f"[public] fetching fundingRate {sym} ...")
        data, headers = _http_get(url)
        _save_json(raw_dir / f"{filename}.json", data)
        _save_headers(raw_dir / f"{filename}.headers", headers)
        records.append(
            {
                "type": "public",
                "name": f"funding_rate_{sym}",
                "method": "GET",
                "url_stripped": "https://fapi.binance.com/fapi/v1/fundingRate",
                "saved_json": f"raw/{filename}.json",
                "saved_headers": f"raw/{filename}.headers",
                "fetched_at": _now_utc(),
            }
        )
        time.sleep(0.5)

    return records


def collect_private(outdir: Path) -> List[Dict[str, Any]]:
    raw_dir = outdir / "raw"
    raw_dir.mkdir(exist_ok=True)
    records: List[Dict[str, Any]] = []

    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        print("[private] skipped: BINANCE_API_KEY/BINANCE_API_SECRET not set")
        return records

    client = PrivateClient(
        api_key=api_key,
        api_secret=api_secret,
        user_agent=USER_AGENT,
        timeout=TIMEOUT,
        recv_window=10000,
        ttl_seconds=0,  # 不缓存，保证实抓
    )

    # 调用白名单端点
    private_calls = [
        ("classic_allPairs", lambda: client._cached_get("GET", "/sapi/v1/margin/allPairs")),
        ("classic_allAssets", lambda: client._cached_get("GET", "/sapi/v1/margin/allAssets")),
        ("classic_crossMarginData", lambda: client._cached_get("GET", "/sapi/v1/margin/crossMarginData")),
        ("portfolio_maxBorrowable_BTC", lambda: client._cached_get("GET", "/papi/v1/margin/maxBorrowable", {"asset": "BTC"})),
        ("portfolio_maxBorrowable_ETH", lambda: client._cached_get("GET", "/papi/v1/margin/maxBorrowable", {"asset": "ETH"})),
    ]

    for name, fn in private_calls:
        print(f"[private] fetching {name} ...")
        try:
            data = fn()
        except Exception as exc:
            print(f"[private] {name} failed: {exc}")
            data = {"error": str(type(exc).__name__), "detail": str(exc)}
        filename = name
        _save_json(raw_dir / f"{filename}.json", data)
        # 私有端点不保存 headers（可能含敏感 trace/edge 信息），只记录审计日志中的元数据
        records.append(
            {
                "type": "private",
                "name": name,
                "method": "GET",
                "url_stripped": "https://papi.binance.com/papi/v1/margin/maxBorrowable"
                if name.startswith("portfolio_")
                else f"https://api.binance.com/sapi/v1/margin/{name.split('_', 1)[1]}",
                "saved_json": f"raw/{filename}.json",
                "saved_headers": None,
                "fetched_at": _now_utc(),
                "audit": client.audit_log[-1] if client.audit_log else None,
            }
        )
        time.sleep(1.0)

    return records


def main() -> None:
    outdir = Path(__file__).resolve().parent
    manifest = {
        "generated_at": _now_utc(),
        "source": "night-collection-2026-07-05",
        "records": collect_public(outdir) + collect_private(outdir),
    }
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[done] manifest saved to {outdir / 'manifest.json'}")


if __name__ == "__main__":
    main()
