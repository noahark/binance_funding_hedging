"""Constraint guard: adapter rejects credentials and non-public hosts."""

from __future__ import annotations

import pytest

from backend.adapters.binance_public import PublicAdapterError, validate_public_request


def test_rejects_non_public_host() -> None:
    with pytest.raises(PublicAdapterError, match="Non-public host"):
        validate_public_request("https://evil.example.com/fapi/v1/exchangeInfo")


def test_rejects_non_public_path() -> None:
    with pytest.raises(PublicAdapterError, match="Non-public path"):
        validate_public_request("https://fapi.binance.com/papi/v1/um/order")


def test_rejects_signature_in_query() -> None:
    with pytest.raises(PublicAdapterError, match="Credential"):
        validate_public_request(
            "https://fapi.binance.com/fapi/v1/exchangeInfo?signature=abc"
        )


def test_rejects_timestamp_in_query() -> None:
    with pytest.raises(PublicAdapterError, match="Credential"):
        validate_public_request(
            "https://fapi.binance.com/fapi/v1/exchangeInfo?timestamp=123"
        )


def test_rejects_api_key_header() -> None:
    with pytest.raises(PublicAdapterError, match="Credential"):
        validate_public_request(
            "https://fapi.binance.com/fapi/v1/exchangeInfo",
            headers={"X-MBX-APIKEY": "secret"},
        )


def test_allows_public_exchange_info() -> None:
    validate_public_request("https://fapi.binance.com/fapi/v1/exchangeInfo")
    validate_public_request("https://api.binance.com/api/v3/exchangeInfo")