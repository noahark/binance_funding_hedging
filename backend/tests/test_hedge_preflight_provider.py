"""S4b (ADR-H5) three-state leg-existence probe tests for
backend/services/hedge_preflight_provider.py.

No real network: the public ``urlopen`` is injected. The probe distinguishes
three states per leg — True (present), False (confirmed absent, e.g. a spot
-1121), None (indeterminate read failure) — and the caller never blocks on None.
"""
from __future__ import annotations

import io
import json
import urllib.error

from backend.services.hedge_preflight_provider import (
    HedgePreflightProvider,
    _perp_leg_exists,
    _spot_leg_exists,
)


class _Resp:
    """Minimal http response: .status / .read() / context manager, matching what
    the provider reads via ``with urlopen(req, timeout=...) as resp``."""

    def __init__(self, status, body):
        self.status = status
        self._raw = json.dumps(body).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body):
    """A real urllib HTTPError carrying a JSON body, the way Binance ships a
    -1121 (HTTP 400 + body ``{"code": -1121, ...}``)."""
    return urllib.error.HTTPError(
        "https://api.binance.com/x", code, "Bad Request", {},
        io.BytesIO(json.dumps(body).encode()),
    )


class _FakeUrlopen:
    """Routes by URL substring: ``fapi`` -> the perp response, otherwise spot.
    Any stored value that is an Exception instance is raised (transport or HTTP
    error); a _Resp is returned as a 2xx response."""

    def __init__(self, spot, perp):
        self._spot = spot
        self._perp = perp
        self.urls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        target = self._perp if "fapi" in url else self._spot
        if isinstance(target, BaseException):
            raise target
        return target


def _provider(spot, perp):
    fake = _FakeUrlopen(spot, perp)
    return HedgePreflightProvider(now_ms=lambda: 0, public_urlopen=fake), fake


COIN = "BTCUSDT"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_spot_leg_exists_states():
    assert _spot_leg_exists(200, {"symbols": [{"symbol": COIN}]}, COIN) is True
    assert _spot_leg_exists(400, {"code": -1121, "msg": "Invalid symbol"}, COIN) is False
    assert _spot_leg_exists(None, None, COIN) is None            # transport failure
    assert _spot_leg_exists(500, None, COIN) is None             # 5xx indeterminate
    assert _spot_leg_exists(200, {"symbols": []}, COIN) is None  # 2xx but missing
    assert _spot_leg_exists(400, {"code": -1000}, COIN) is None  # 400 not -1121


def test_perp_leg_exists_states():
    assert _perp_leg_exists(200, {"symbols": [{"symbol": COIN}]}, COIN) is True
    assert _perp_leg_exists(200, {"symbols": []}, COIN) is False  # absent in list
    assert _perp_leg_exists(None, None, COIN) is None
    assert _perp_leg_exists(500, {"symbols": []}, COIN) is None


# ---------------------------------------------------------------------------
# check_symbol_legs end-to-end (three-state x two-leg matrix)
# ---------------------------------------------------------------------------

def test_check_symbol_legs_both_present():
    prov, _ = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN, "status": "TRADING"}]}),
        _Resp(200, {"symbols": [{"symbol": COIN, "status": "TRADING"}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": True, "perp": True}


def test_check_symbol_legs_spot_minus_1121_perp_present():
    # The KORUUSDT case: spot leg absent (HTTP 400 body code -1121), UM present.
    prov, _ = _provider(
        _http_error(400, {"code": -1121, "msg": "Invalid symbol"}),
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": False, "perp": True}


def test_check_symbol_legs_perp_absent_spot_present():
    prov, _ = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
        _Resp(200, {"symbols": [{"symbol": "ETHUSDT"}]}),  # coin not in UM list
    )
    assert prov.check_symbol_legs(COIN) == {"spot": True, "perp": False}


def test_check_symbol_legs_both_absent():
    prov, _ = _provider(
        _http_error(400, {"code": -1121, "msg": "Invalid symbol"}),
        _Resp(200, {"symbols": [{"symbol": "ETHUSDT"}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": False, "perp": False}


def test_check_symbol_legs_spot_transport_failure_is_indeterminate():
    # A plain transport error (connection reset / timeout) on spot -> None,
    # NOT False: the probe must never assert absence on a failed read.
    prov, _ = _provider(
        ConnectionError("public marketdata unreachable"),
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": None, "perp": True}


def test_check_symbol_legs_perp_transport_failure_is_indeterminate():
    prov, _ = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
        OSError("read timed out"),
    )
    assert prov.check_symbol_legs(COIN) == {"spot": True, "perp": None}


def test_check_symbol_legs_uses_correct_public_endpoints():
    prov, fake = _provider(
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
        _Resp(200, {"symbols": [{"symbol": COIN}]}),
    )
    prov.check_symbol_legs(COIN)
    spot_url = [u for u in fake.urls if "fapi" not in u][0]
    perp_url = [u for u in fake.urls if "fapi" in u][0]
    assert spot_url.endswith(f"/api/v3/exchangeInfo?symbol={COIN}")
    assert perp_url.endswith("/fapi/v1/exchangeInfo")


def test_disabled_preflight_provider_has_no_leg_probe():
    # The dry-run default provider exposes no probe -> create_task duck-types it
    # away and never blocks (10-design §2.4b: dry-run unchanged, offline zero-net).
    from backend.hedge_open_tasks.service import DisabledPreflightProvider
    assert not hasattr(DisabledPreflightProvider(), "check_symbol_legs")
