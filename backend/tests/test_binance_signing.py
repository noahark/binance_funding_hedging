"""Tests for the single shared HMAC-SHA256 signing primitive (Boundary C §7).

Pure unit tests (no network). Cross-checks ``binance_signing`` against an inline
``hmac``/``hashlib`` reference computed inside the test (tests may use those
primitives; product code may not). The central invariant: the bytes that are
signed are exactly the bytes that are sent (one serializer, one signer).
"""
from __future__ import annotations

import hashlib
import hmac

from backend.services import binance_signing

SECRET = "test-api-secret-1234"


def _reference_total(params: dict) -> str:
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))


def _reference_signature(total_params: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), total_params.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def test_build_total_params_sorts_by_key():
    params = {"asset": "BTC", "amount": "1.5", "timestamp": "1000", "recvWindow": "60000"}
    assert binance_signing.build_total_params(params) == _reference_total(params)
    # canonical regardless of insertion order
    import collections
    reversed_params = collections.OrderedDict(reversed(list(params.items())))
    assert binance_signing.build_total_params(reversed_params) == _reference_total(params)


def test_sign_is_lowercase_hex_hmac_sha256():
    params = {"asset": "BTC", "amount": "1.5", "timestamp": "1000", "recvWindow": "60000"}
    total = binance_signing.build_total_params(params)
    sig = binance_signing.sign(total, SECRET)
    assert sig == _reference_signature(total, SECRET)
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_signed_payload_appends_signature_last():
    params = {"asset": "ETH", "amount": "2", "timestamp": "2000", "recvWindow": "60000"}
    total = binance_signing.build_total_params(params)
    payload = binance_signing.signed_payload(params, SECRET)
    assert payload == f"{total}&signature={_reference_signature(total, SECRET)}"
    # signature is the last field
    assert payload.endswith("&signature=" + _reference_signature(total, SECRET))


def test_signed_bytes_equal_sent_bytes_invariant():
    # The frozen invariant (§7): the totalParams consumed by sign() must equal the
    # totalParams embedded in the sent payload (everything before &signature=).
    params = {"asset": "BTC", "amount": "0.0001", "timestamp": "999", "recvWindow": "60000"}
    payload = binance_signing.signed_payload(params, SECRET)
    sent_total = payload[: payload.rfind("&signature=")]
    signed_total = binance_signing.build_total_params(params)
    assert sent_total == signed_total
    # And re-signing the sent_total reproduces the embedded signature
    embedded = payload[payload.rfind("&signature=") + len("&signature="):]
    assert binance_signing.sign(sent_total, SECRET) == embedded


def test_signing_is_deterministic_and_order_independent():
    params = {"b": "2", "a": "1", "c": "3"}
    import collections
    other = collections.OrderedDict([("c", "3"), ("a", "1"), ("b", "2")])
    assert binance_signing.sign(binance_signing.build_total_params(params), SECRET) == \
        binance_signing.sign(binance_signing.build_total_params(other), SECRET)
