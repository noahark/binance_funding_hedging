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
