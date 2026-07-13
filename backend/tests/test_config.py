from pathlib import Path

import pytest

from backend.config import DEFAULT, from_env
from backend.services.snapshot_service import SnapshotService


def test_from_env_defaults_keep_private_channel_disabled():
    cfg = from_env({})
    assert cfg.private_channel_enabled is False
    assert cfg.bind_host == DEFAULT.bind_host
    assert cfg.bind_port == DEFAULT.bind_port
    assert cfg.offline is DEFAULT.offline


def test_from_env_parses_runtime_values():
    cfg = from_env(
        {
            "APP_BIND_HOST": "0.0.0.0",
            "APP_BIND_PORT": "9999",
            "APP_OFFLINE": "true",
            "APP_TOP_N": "7",
            "APP_CACHE_TTL_SECONDS": "12",
            "APP_REQUEST_TIMEOUT": "2.5",
            "APP_OFFLINE_RAW_DIR": "~/fixtures",
            "BINANCE_PRIVATE_CHANNEL_ENABLED": "true",
            "BINANCE_RECV_WINDOW": "5000",
            "BINANCE_PRIVATE_CHANNEL_TTL_SECONDS": "180",
            "BINANCE_PRIVATE_CHANNEL_FAST_TTL_SECONDS": "30",
            "BINANCE_BORROW_CHECK_MAX_CALLS": "9",
        }
    )
    assert cfg.bind_host == "0.0.0.0"
    assert cfg.bind_port == 9999
    assert cfg.offline is True
    assert cfg.top_n == 7
    assert cfg.cache_ttl_seconds == 12
    assert cfg.request_timeout == 2.5
    assert cfg.offline_raw_dir == Path("~/fixtures").expanduser()
    assert cfg.private_channel_enabled is True
    assert cfg.private_recv_window == 5000
    assert cfg.private_channel_ttl_seconds == 180
    assert cfg.private_channel_fast_ttl_seconds == 30
    assert cfg.borrow_check_max_calls == 9


def test_from_env_rejects_invalid_boolean():
    with pytest.raises(ValueError, match="BINANCE_PRIVATE_CHANNEL_ENABLED"):
        from_env({"BINANCE_PRIVATE_CHANNEL_ENABLED": "maybe"})


def test_from_env_rejects_invalid_integer_with_variable_name():
    with pytest.raises(ValueError, match="APP_BIND_PORT"):
        from_env({"APP_BIND_PORT": "abc"})


def test_from_env_rejects_invalid_float_with_variable_name():
    with pytest.raises(ValueError, match="APP_REQUEST_TIMEOUT"):
        from_env({"APP_REQUEST_TIMEOUT": "slow"})


def test_private_channel_requires_explicit_switch(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "dummy-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "dummy-secret")

    disabled_cfg = from_env({"APP_OFFLINE": "false"})
    disabled_service = SnapshotService(disabled_cfg)
    assert disabled_service._private.enabled is False

    enabled_cfg = from_env(
        {
            "APP_OFFLINE": "false",
            "BINANCE_PRIVATE_CHANNEL_ENABLED": "true",
        }
    )
    enabled_service = SnapshotService(enabled_cfg)
    assert enabled_service._private.enabled is True


def test_offline_mode_ignores_private_channel_switch(monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "dummy-key")
    monkeypatch.setenv("BINANCE_API_SECRET", "dummy-secret")

    cfg = from_env(
        {
            "APP_OFFLINE": "true",
            "BINANCE_PRIVATE_CHANNEL_ENABLED": "true",
        }
    )
    service = SnapshotService(cfg)
    assert service._private.enabled is False


# --- Stage 2026-07: dedicated per-symbol funding-history cache TTL ---


def test_funding_history_cache_ttl_default_is_1800():
    # Settled records are immutable -> the deep-history cache outlives the 60s
    # whole-snapshot cache (default 30 minutes, ADR-2).
    assert DEFAULT.funding_history_cache_ttl_seconds == 1800
    assert from_env({}).funding_history_cache_ttl_seconds == 1800


def test_funding_history_cache_ttl_env_override():
    cfg = from_env({"APP_FUNDING_HISTORY_CACHE_TTL_SECONDS": "900"})
    assert cfg.funding_history_cache_ttl_seconds == 900
    # Legacy alias is honored too.
    cfg2 = from_env({"FUNDING_HEDGING_FUNDING_HISTORY_CACHE_TTL_SECONDS": "120"})
    assert cfg2.funding_history_cache_ttl_seconds == 120


def test_funding_history_cache_ttl_rejects_invalid_integer():
    with pytest.raises(ValueError, match="APP_FUNDING_HISTORY_CACHE_TTL_SECONDS"):
        from_env({"APP_FUNDING_HISTORY_CACHE_TTL_SECONDS": "soon"})


# --- Stage 2026-07-history-background-refresh-v1: background worker config ---

def test_background_refresh_defaults():
    # kill switch default-on; 30s tick; 10 symbols/tick; 30s symbol timeout.
    assert DEFAULT.background_refresh_enabled is True
    assert DEFAULT.background_tick_seconds == 30
    assert DEFAULT.history_sweep_batch_size == 10
    assert DEFAULT.symbol_refresh_timeout_seconds == 30.0


def test_background_refresh_env_overrides():
    cfg = from_env(
        {
            "APP_BACKGROUND_REFRESH_ENABLED": "false",
            "APP_BACKGROUND_TICK_SECONDS": "5",
            "APP_HISTORY_SWEEP_BATCH_SIZE": "3",
            "APP_SYMBOL_REFRESH_TIMEOUT_SECONDS": "12.5",
        }
    )
    assert cfg.background_refresh_enabled is False
    assert cfg.background_tick_seconds == 5
    assert cfg.history_sweep_batch_size == 3
    assert cfg.symbol_refresh_timeout_seconds == 12.5


def test_background_refresh_alias_env_honored():
    cfg = from_env(
        {
            "FUNDING_HEDGING_BACKGROUND_TICK_SECONDS": "7",
            "FUNDING_HEDGING_HISTORY_SWEEP_BATCH_SIZE": "4",
        }
    )
    assert cfg.background_tick_seconds == 7
    assert cfg.history_sweep_batch_size == 4


def test_background_refresh_enabled_rejects_invalid_boolean():
    with pytest.raises(ValueError, match="APP_BACKGROUND_REFRESH_ENABLED"):
        from_env({"APP_BACKGROUND_REFRESH_ENABLED": "maybe"})


def test_background_tick_rejects_invalid_integer():
    with pytest.raises(ValueError, match="APP_BACKGROUND_TICK_SECONDS"):
        from_env({"APP_BACKGROUND_TICK_SECONDS": "soon"})


def test_symbol_refresh_timeout_rejects_invalid_float():
    with pytest.raises(ValueError, match="APP_SYMBOL_REFRESH_TIMEOUT_SECONDS"):
        from_env({"APP_SYMBOL_REFRESH_TIMEOUT_SECONDS": "slow"})
