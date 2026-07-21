"""The single shared HMAC-SHA256 signing primitive for Binance private requests.

This is the ONLY module in the repository permitted to touch ``hmac`` /
``hashlib`` / ``signature`` construction. A static guard in
``backend/tests/test_private_client.py`` asserts both:

* no product module other than this one references those primitives; and
* neither HTTP client (``private_client.py`` for GET reads,
  ``portfolio_margin_borrow_client.py`` for the borrow POST + loan-record GET)
  constructs a signature inline.

One serializer (``build_total_params``) produces the exact ``k=v`` joined string
that is BOTH signed and sent, so signing and sending can never diverge (Boundary
C §7). Binance signs ``totalParams``: for a GET this is the query string; for the
archived borrow POST it is the ``application/x-www-form-urlencoded`` body. The
signature is always appended last.

No network I/O here; this module is pure bytes-in / hex-out.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Mapping


def build_total_params(params: Mapping[str, str]) -> str:
    """Return the canonical ``k=v`` joined string used for signing AND sending.

    Params are sorted by key so the signed bytes are deterministic and independent
    of caller insertion order. Binance signs the exact ``totalParams`` bytes
    regardless of field order, so a single canonical order satisfies both the GET
    query string and the POST form body without splitting a parameter between
    query and body.
    """
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))


def sign(total_params: str, api_secret: str) -> str:
    """Return the lowercase hex HMAC-SHA256 of ``total_params`` under ``api_secret``."""
    return hmac.new(
        api_secret.encode("utf-8"),
        total_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def signed_payload(params: Mapping[str, str], api_secret: str) -> str:
    """Return ``total_params`` with ``&signature=<hex>`` appended.

    The same string is consumed by the signer (``sign``) and by the sender (as a
    GET query string after ``?`` or as a POST ``application/x-www-form-urlencoded``
    body), guaranteeing the signed bytes are the sent bytes.
    """
    total = build_total_params(params)
    return f"{total}&signature={sign(total, api_secret)}"
