"""Backend configuration.

Defaults match the stage design: funding_history top-N = 20, snapshot cache
TTL = 60s, bind 127.0.0.1:8787. Offline mode reads the frozen raw-sample
directory captured in the contract stage (read-only reference to frozen
evidence).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
FROZEN_RAW_DIR = (
    REPO_ROOT
    / "reports/api-samples/public-market-contract-v2/20260703T051738Z/raw"
)
# Stage 2026-07-real-borrow-execution-v1 (A+B): local SQLite path for the
# durable borrow-task store. Default lives under ``data/`` (gitignored). Tests
# point this at a ``TemporaryDirectory``.
BORROW_DB_PATH = REPO_ROOT / "data" / "borrow-tasks.sqlite3"
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
    # Stage 2026-07: dedicated per-symbol successful-result cache for settled
    # /fapi/v1/fundingRate deep history (immutable records -> longer TTL than
    # the 60s whole-snapshot cache). Defaults to 30 minutes; failure results are
    # NOT cached (the service retries them on the next snapshot rebuild).
    funding_history_cache_ttl_seconds: int = 1800
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
    # §1.5: borrow_validation probing cap (neg-funding + MARGIN_SPOT_CANDIDATE +
    # CRYPTO baseAssets, deduped, truncated by abs daily rate DESC). Supersedes the
    # Phase 2 top-N (was 10); the v1 probe set is wider (default 50, §2.A.2 scen 3).
    borrow_check_max_calls: int = 50
    # §1.6: two independent private-channel TTL groups.
    # 1800s: slow scheduled private transport (classic-reference / account-info /
    # crossMarginData VIP table). Effective value must stay <=1800 so a stale
    # transport entry cannot masquerade as a 30-minute successful refresh (stage
    # 2026-07-cache-refresh-scheduler-v2, ADR-2 / FR-2).
    private_channel_ttl_seconds: int = 1800
    # 60s: account balances (E3/E4/E6) — aligns with the public refresh cadence.
    private_channel_fast_ttl_seconds: int = 60
    private_recv_window: int = 10000
    # Explicit operator switch. API keys may exist in the environment, but the
    # private read-only channel stays disabled unless this flag is true.
    private_channel_enabled: bool = False
    # Stage 2026-07-history-background-refresh-v1: serial background worker that
    # owns all domain-cache writes and the single immutable PublishedState.
    # Default-on kill switch: setting False (live) makes get_snapshot a pure
    # last-good/503 read with zero upstream fetch and never starts the worker.
    # Offline mode never starts the worker regardless (it keeps the synchronous
    # fixture build path).
    background_refresh_enabled: bool = True
    # Worker tick cadence (seconds): how often the loop wakes to sweep the next
    # default-view history batch and refresh base rows when age >= cache_ttl.
    background_tick_seconds: int = 30
    # Max default-view history entries refreshed per scheduled tick (10-design
    # D2). Bounds per-tick /fapi/v1/fundingRate call volume.
    history_sweep_batch_size: int = 10
    # Bounded wait for a one-shot RefreshSymbolCommand (10-design D7/D3). The
    # shared deadline is also the publication gate (breakdown §10): a command
    # whose upstream I/O completes after this monotonic deadline must NOT commit
    # cache changes or publish a new PublishedState.
    symbol_refresh_timeout_seconds: float = 30.0
    # Boundary C: the borrow executor is one of ``disabled`` (default, no-network)
    # or ``live`` (the exact-path PM borrow client, still off-by-default until an
    # explicit operator Start). Any other selection is rejected in from_env.
    borrow_executor: str = "disabled"
    borrow_db_path: Path = BORROW_DB_PATH
    # Dedicated PM borrow credentials (Boundary C). Empty by default. ``live``
    # mode with empty credentials is a dispatch gate (block_reason
    # ``borrow_credentials_missing``), not a crash. Both are ``repr=False`` so a
    # Config repr/log can never leak the secret.
    binance_borrow_api_key: str = field(default="", repr=False)
    binance_borrow_api_secret: str = field(default="", repr=False)


# Stage 2026-07-cache-refresh-scheduler-v2: fixed Group B shared/unified source
# business cadence (CC-2). Not environment-configurable; the slow scheduled
# private transport TTL (private_channel_ttl_seconds) may be set lower but must
# remain <=1800 and must not amplify this fixed business cadence.
GROUP_B_REFRESH_SECONDS = 1800

DEFAULT = Config()


def _env(
    environ: Mapping[str, str],
    name: str,
    default: str | None = None,
    *aliases: str,
) -> str | None:
    for key in (name, *aliases):
        value = environ.get(key)
        if value is not None and value != "":
            return value
    return default


def _env_bool(environ: Mapping[str, str], name: str, default: bool, *aliases: str) -> bool:
    value = _env(environ, name, None, *aliases)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean environment value for {name}: {value!r}")


def _env_int(environ: Mapping[str, str], name: str, default: int, *aliases: str) -> int:
    value = _env(environ, name, None, *aliases)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"invalid integer environment value for {name}: {value!r}") from exc


def _env_float(environ: Mapping[str, str], name: str, default: float, *aliases: str) -> float:
    value = _env(environ, name, None, *aliases)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"invalid float environment value for {name}: {value!r}") from exc


def _env_path(environ: Mapping[str, str], name: str, default: Path, *aliases: str) -> Path:
    value = _env(environ, name, None, *aliases)
    return default if value is None else Path(value).expanduser()


def from_env(environ: Mapping[str, str] | None = None) -> Config:
    """Build runtime config from process environment.

    The shell startup script loads `.env` into the environment first. This helper
    only reads values; it does not parse `.env` directly, so tests and review
    commands do not accidentally consume local secrets.
    """
    env = os.environ if environ is None else environ
    private_channel_ttl_seconds = _env_int(
        env,
        "BINANCE_PRIVATE_CHANNEL_TTL_SECONDS",
        DEFAULT.private_channel_ttl_seconds,
        "FUNDING_HEDGING_PRIVATE_CHANNEL_TTL_SECONDS",
    )
    # FR-2 / §5.5: the slow scheduled private transport TTL must stay <=1800 so a
    # stale transport entry cannot masquerade as a 30-minute successful refresh.
    if private_channel_ttl_seconds > 1800:
        raise ValueError(
            "invalid integer environment value for "
            "BINANCE_PRIVATE_CHANNEL_TTL_SECONDS: "
            f"{private_channel_ttl_seconds!r} (effective slow scheduled private "
            "transport TTL must be <=1800)"
        )
    borrow_executor = _env(
        env,
        "APP_BORROW_EXECUTOR",
        DEFAULT.borrow_executor,
        "FUNDING_HEDGING_BORROW_EXECUTOR",
    )
    # Boundary C: ``disabled`` (default, no-network) and ``live`` (the exact-path
    # PM borrow client, off-by-default until an explicit operator Start) are the
    # only two selections. Anything else is rejected, not built.
    if borrow_executor not in {"disabled", "live"}:
        raise ValueError(
            f"invalid borrow executor {borrow_executor!r}: only 'disabled' or "
            "'live' is implemented"
        )
    return Config(
        bind_host=_env(env, "APP_BIND_HOST", DEFAULT.bind_host, "FUNDING_HEDGING_BIND_HOST"),
        bind_port=_env_int(env, "APP_BIND_PORT", DEFAULT.bind_port, "FUNDING_HEDGING_BIND_PORT"),
        top_n=_env_int(env, "APP_TOP_N", DEFAULT.top_n, "FUNDING_HEDGING_TOP_N"),
        cache_ttl_seconds=_env_int(
            env,
            "APP_CACHE_TTL_SECONDS",
            DEFAULT.cache_ttl_seconds,
            "FUNDING_HEDGING_CACHE_TTL_SECONDS",
        ),
        funding_history_cache_ttl_seconds=_env_int(
            env,
            "APP_FUNDING_HISTORY_CACHE_TTL_SECONDS",
            DEFAULT.funding_history_cache_ttl_seconds,
            "FUNDING_HEDGING_FUNDING_HISTORY_CACHE_TTL_SECONDS",
        ),
        offline=_env_bool(env, "APP_OFFLINE", DEFAULT.offline, "FUNDING_HEDGING_OFFLINE"),
        offline_raw_dir=_env_path(
            env,
            "APP_OFFLINE_RAW_DIR",
            DEFAULT.offline_raw_dir,
            "FUNDING_HEDGING_OFFLINE_RAW_DIR",
        ),
        request_timeout=_env_float(
            env,
            "APP_REQUEST_TIMEOUT",
            DEFAULT.request_timeout,
            "FUNDING_HEDGING_REQUEST_TIMEOUT",
        ),
        borrow_check_max_calls=_env_int(
            env,
            "BINANCE_BORROW_CHECK_MAX_CALLS",
            DEFAULT.borrow_check_max_calls,
            "FUNDING_HEDGING_BORROW_CHECK_MAX_CALLS",
        ),
        private_channel_ttl_seconds=private_channel_ttl_seconds,
        private_channel_fast_ttl_seconds=_env_int(
            env,
            "BINANCE_PRIVATE_CHANNEL_FAST_TTL_SECONDS",
            DEFAULT.private_channel_fast_ttl_seconds,
            "FUNDING_HEDGING_PRIVATE_CHANNEL_FAST_TTL_SECONDS",
        ),
        private_recv_window=_env_int(
            env,
            "BINANCE_RECV_WINDOW",
            DEFAULT.private_recv_window,
            "FUNDING_HEDGING_BINANCE_RECV_WINDOW",
        ),
        private_channel_enabled=_env_bool(
            env,
            "BINANCE_PRIVATE_CHANNEL_ENABLED",
            DEFAULT.private_channel_enabled,
            "FUNDING_HEDGING_PRIVATE_CHANNEL_ENABLED",
        ),
        background_refresh_enabled=_env_bool(
            env,
            "APP_BACKGROUND_REFRESH_ENABLED",
            DEFAULT.background_refresh_enabled,
            "FUNDING_HEDGING_BACKGROUND_REFRESH_ENABLED",
        ),
        background_tick_seconds=_env_int(
            env,
            "APP_BACKGROUND_TICK_SECONDS",
            DEFAULT.background_tick_seconds,
            "FUNDING_HEDGING_BACKGROUND_TICK_SECONDS",
        ),
        history_sweep_batch_size=_env_int(
            env,
            "APP_HISTORY_SWEEP_BATCH_SIZE",
            DEFAULT.history_sweep_batch_size,
            "FUNDING_HEDGING_HISTORY_SWEEP_BATCH_SIZE",
        ),
        symbol_refresh_timeout_seconds=_env_float(
            env,
            "APP_SYMBOL_REFRESH_TIMEOUT_SECONDS",
            DEFAULT.symbol_refresh_timeout_seconds,
            "FUNDING_HEDGING_SYMBOL_REFRESH_TIMEOUT_SECONDS",
        ),
        borrow_executor=borrow_executor,
        borrow_db_path=_env_path(
            env,
            "APP_BORROW_DB_PATH",
            DEFAULT.borrow_db_path,
            "FUNDING_HEDGING_BORROW_DB_PATH",
        ),
        # Dedicated PM borrow credentials (Boundary C). Read verbatim from the
        # environment only; .env itself is never parsed here. Empty unless set.
        binance_borrow_api_key=_env(env, "BINANCE_BORROW_API_KEY", "") or "",
        binance_borrow_api_secret=_env(env, "BINANCE_BORROW_API_SECRET", "") or "",
    )
