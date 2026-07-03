"""Thin public Binance adapter — stdlib urllib.request only, GET public endpoints."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.domain.funding import get_funding_field_semantics

PUBLIC_HOSTS = frozenset({"fapi.binance.com", "api.binance.com"})

ALLOWED_PATHS = frozenset(
    {
        "/fapi/v1/exchangeInfo",
        "/fapi/v1/premiumIndex",
        "/fapi/v1/fundingRate",
        "/api/v3/exchangeInfo",
        "/fapi/v1/depth",
        "/api/v3/depth",
    }
)

CREDENTIAL_PATTERNS = (
    re.compile(r"X-MBX-APIKEY", re.IGNORECASE),
    re.compile(r"signature", re.IGNORECASE),
    re.compile(r"\btimestamp\b", re.IGNORECASE),
    re.compile(r"recvWindow", re.IGNORECASE),
)


class PublicAdapterError(Exception):
    """Raised when a public-only constraint is violated."""


def validate_public_request(url: str, headers: dict[str, str] | None = None) -> None:
    """Fail closed if URL or headers contain credentials or non-public paths."""
    parsed = urlparse(url)
    if parsed.hostname not in PUBLIC_HOSTS:
        msg = f"Non-public host rejected: {parsed.hostname}"
        raise PublicAdapterError(msg)

    path = parsed.path
    if path not in ALLOWED_PATHS:
        msg = f"Non-public path rejected: {path}"
        raise PublicAdapterError(msg)

    query = parsed.query or ""
    for pattern in CREDENTIAL_PATTERNS:
        if pattern.search(query):
            msg = f"Credential field in query rejected: {pattern.pattern}"
            raise PublicAdapterError(msg)

    if headers:
        for key, value in headers.items():
            combined = f"{key}={value}"
            for pattern in CREDENTIAL_PATTERNS:
                if pattern.search(key) or pattern.search(value) or pattern.search(combined):
                    msg = f"Credential field in headers rejected: {key}"
                    raise PublicAdapterError(msg)


def fetch_json(url: str) -> tuple[Any, int]:
    """GET a public endpoint and return parsed JSON with HTTP status."""
    validate_public_request(url)
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8")
        raise PublicAdapterError(f"HTTP {status}: {body[:200]}") from exc

    return json.loads(body), status


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_compact_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _save_json(path: Path, data: Any) -> int:
    content = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(content, encoding="utf-8")
    return len(content.encode("utf-8"))


def build_public_url(host: str, path: str, query: str = "") -> str:
    """Build and validate a public request URL."""
    base = f"https://{host}{path}"
    url = f"{base}?{query}" if query else base
    validate_public_request(url)
    return url


def capture_samples(
    output_dir: Path | None = None,
    funding_symbols: list[str] | None = None,
) -> Path:
    """
    Capture public market samples and write sample-index.json.

    Returns the output directory path.
    """
    if output_dir is None:
        repo_root = Path(__file__).resolve().parents[2]
        ts = _utc_compact_timestamp()
        output_dir = repo_root / "reports" / "api-samples" / "public-market" / ts

    output_dir.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc).isoformat()
    data_timestamp = _utc_epoch_ms()
    semantics = get_funding_field_semantics()

    index_entries: list[dict[str, Any]] = []

    endpoints: list[tuple[str, str, str, str | None]] = [
        ("fapi.binance.com", "/fapi/v1/exchangeInfo", "fapi_exchange_info.json", None),
        ("fapi.binance.com", "/fapi/v1/premiumIndex", "fapi_premium_index.json", None),
        ("api.binance.com", "/api/v3/exchangeInfo", "spot_exchange_info.json", None),
    ]

    premium_index: list[dict[str, Any]] = []

    for host, path, filename, symbol in endpoints:
        url = build_public_url(host, path)
        data, status = fetch_json(url)
        if filename == "fapi_premium_index.json":
            premium_index = data if isinstance(data, list) else [data]

        byte_size = _save_json(output_dir / filename, data)
        index_entries.append(
            {
                "endpoint": f"GET {path}",
                "url": url,
                "file": filename,
                "http_status": status,
                "byte_size": byte_size,
                "sha256": _sha256_file(output_dir / filename),
                "symbol": symbol,
            }
        )

    if funding_symbols is None:
        funding_symbols = []
        for entry in premium_index:
            sym = entry.get("symbol", "")
            if sym.endswith("USDT"):
                funding_symbols.append(sym)
        funding_symbols = sorted(funding_symbols)[:5]

    for sym in funding_symbols:
        filename = f"fapi_funding_rate_{sym}.json"
        url = build_public_url(
            "fapi.binance.com",
            "/fapi/v1/fundingRate",
            f"symbol={sym}&limit=10",
        )
        data, status = fetch_json(url)
        byte_size = _save_json(output_dir / filename, data)
        index_entries.append(
            {
                "endpoint": "GET /fapi/v1/fundingRate",
                "url": url,
                "file": filename,
                "http_status": status,
                "byte_size": byte_size,
                "sha256": _sha256_file(output_dir / filename),
                "symbol": sym,
            }
        )

    sample_index = {
        "captured_at": captured_at,
        "data_timestamp": str(data_timestamp),
        "funding_field_semantics": semantics,
        "files": index_entries,
    }
    _save_json(output_dir / "sample-index.json", sample_index)

    return output_dir


def load_json_file(path: Path) -> Any:
    """Load a JSON file from disk."""
    return json.loads(path.read_text(encoding="utf-8"))