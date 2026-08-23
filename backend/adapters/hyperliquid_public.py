"""Public Hyperliquid REST client (no key, POST /info).

Stage 2026-08-23-hyperliquid-funding-compare-v1. Fetches the two
``metaAndAssetCtxs`` snapshots (``dex=""`` main perps and ``dex="xyz"`` HIP-3
xyz perps) as ONE atomic group: any transport/shape failure raises so the
service treats the whole source as failed (design §6.1 D6 — no per-dex partial
success, no warm last-good projection). Decimal-safe: every ``funding`` value
must parse to a finite :class:`~decimal.Decimal` (a non-numeric value fails
the WHOLE source, design §5 rev3) and is carried as the raw string.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Dict, List

_HL_DEXES = ("", "xyz")


def _entry_key(dex: str, name: str) -> str:
    """Canonical full HL key incl. dex prefix (``xyz:BB``) — the exact form
    ``HL_SYMBOL_DENY`` is keyed on. The wire name for xyz entries already
    carries the prefix (probe 2026-08-23); the prefix check only covers a bare
    name so the DENY lookup never silently misses."""
    if dex and not name.startswith(f"{dex}:"):
        return f"{dex}:{name}"
    return name


class HyperliquidPublicClient:
    """Fetches only the public, no-key ``POST /info`` funding-compare seams."""

    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        timeout: float,
    ):
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.request_log: Dict[str, int] = {}

    def _bump(self, key: str) -> None:
        self.request_log[key] = self.request_log.get(key, 0) + 1

    def _http_post_json(self, body: dict) -> object:
        req = urllib.request.Request(
            f"{self.base_url}/info",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
            info = resp.info() if hasattr(resp, "info") else getattr(resp, "headers", None)
            encoding = info.get("Content-Encoding") if info is not None else None
            if encoding == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            elif encoding == "deflate":
                import zlib
                raw = zlib.decompress(raw)
            return json.loads(raw.decode("utf-8"))

    def _fetch_dex(self, dex: str) -> List[dict]:
        """One ``metaAndAssetCtxs`` POST -> normalized non-empty entry list.

        Raises ``ValueError`` on any shape violation (non-2-list payload,
        missing/empty ``universe``, length mismatch, non-dict row, non-string
        name, or a ``funding`` that does not parse to a finite Decimal) so the
        caller fails the whole source — never returns a partial dex view.
        """
        payload = self._http_post_json({"type": "metaAndAssetCtxs", "dex": dex})
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValueError("metaAndAssetCtxs payload must be a 2-element list")
        meta, ctxs = payload
        if not isinstance(meta, dict) or not isinstance(ctxs, list):
            raise ValueError("metaAndAssetCtxs payload shape invalid")
        universe = meta.get("universe")
        if not isinstance(universe, list) or not universe:
            raise ValueError("metaAndAssetCtxs universe must be a non-empty list")
        if len(universe) != len(ctxs):
            raise ValueError("metaAndAssetCtxs universe/ctxs length mismatch")
        out: List[dict] = []
        for u, c in zip(universe, ctxs):
            if not isinstance(u, dict) or not isinstance(c, dict):
                raise ValueError("metaAndAssetCtxs row must be objects")
            name = u.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("metaAndAssetCtxs universe entry missing name")
            funding = c.get("funding")
            # Whole-source failure on any non-Decimal funding (design §5 rev3):
            # a batch with one bad value is not trusted for any symbol. The wire
            # value must be a STRING (same Decimal discipline as bookTicker: a
            # JSON number is float-poisoned and is rejected, never str()-coerced)
            # that parses to a finite Decimal.
            if not isinstance(funding, str) or funding == "":
                raise ValueError(
                    f"metaAndAssetCtxs funding missing/non-string for {name}: {funding!r}"
                )
            try:
                if not Decimal(funding).is_finite():
                    raise InvalidOperation
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError(
                    f"metaAndAssetCtxs funding not a finite decimal for {name}: {funding!r}"
                )
            out.append(
                {
                    "key": _entry_key(dex, name),
                    "name": name.split(":")[-1],
                    "is_delisted": bool(u.get("isDelisted")),
                    "funding": str(funding),
                }
            )
        return out

    def fetch_funding_compare(self) -> dict:
        """Atomic main+xyz group: ``{"main": [...], "xyz": [...]}`` or raises.

        Exactly one POST per dex on success. The main POST runs first; if it
        fails the xyz POST is never issued (the group is already failed —
        design §6.1 / acceptance A13).
        """
        main = self._fetch_dex("")
        self._bump("POST /info metaAndAssetCtxs (main)")
        xyz = self._fetch_dex("xyz")
        self._bump("POST /info metaAndAssetCtxs (xyz)")
        return {"main": main, "xyz": xyz}
