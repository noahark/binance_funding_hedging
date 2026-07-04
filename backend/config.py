"""Backend configuration.

Defaults match the stage design: funding_history top-N = 20, snapshot cache
TTL = 60s, bind 127.0.0.1:8787. Offline mode reads the frozen raw-sample
directory captured in the contract stage (read-only reference to frozen
evidence).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FROZEN_RAW_DIR = (
    REPO_ROOT
    / "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw"
)
SCHEMA_PATH = REPO_ROOT / "schemas/api/public-market/snapshot.schema.json"
FRONTEND_DIR = REPO_ROOT / "frontend"
FROZEN_SOURCE_SAMPLE_ID = "20260703T051738Z"
FROZEN_GENERATED_AT = "2026-07-03T05:17:38Z"


@dataclass(frozen=True)
class Config:
    bind_host: str = "127.0.0.1"
    bind_port: int = 8787
    top_n: int = 20
    cache_ttl_seconds: int = 60
    offline: bool = False
    offline_raw_dir: Path = FROZEN_RAW_DIR
    schema_path: Path = SCHEMA_PATH
    frontend_dir: Path = FRONTEND_DIR
    futures_base_url: str = "https://fapi.binance.com"
    spot_base_url: str = "https://api.binance.com"
    sapi_base_url: str = "https://api.binance.com"
    papi_base_url: str = "https://papi.binance.com"
    user_agent: str = "funding-hedging-public-market/1.0"
    request_timeout: float = 15.0
    borrow_check_top_n: int = 10
    private_channel_ttl_seconds: int = 3600
    private_recv_window: int = 10000


DEFAULT = Config()
