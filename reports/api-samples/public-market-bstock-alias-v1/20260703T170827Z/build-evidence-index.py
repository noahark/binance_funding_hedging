#!/usr/bin/env python3
"""Build evidence-index.md from captured PUBLIC exchangeInfo payloads.

Reads ./raw/{fapi-v1-exchangeInfo,api-v3-exchangeInfo}.json (anonymous, no API
key, read-only public endpoints) and cross-verifies the 15 bStock spot/futures
alias pairs, then writes ./evidence-index.md.

Re-runnable: from this capture directory run `python3 build-evidence-index.py`.
No network access; this only reads the already-captured raw files.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "raw"

FAPI = json.loads((RAW / "fapi-v1-exchangeInfo.json").read_text())
SPOT = json.loads((RAW / "api-v3-exchangeInfo.json").read_text())

# User-listed bStock spot baseAssets (trailing "B"). Contract baseAsset = strip "B".
BSTOCKS = [
    "CRCLB", "MUB", "NVDAB", "SNDKB", "TSLAB", "SPCXB", "AMDB", "EWYB", "INTCB",
    "MSTRB", "LITEB", "METAB", "MSFTB", "PLTRB", "QQQB",
]

CAPTURE_ID = HERE.name
STAGE = "2026-07-public-market-bstock-alias-v1"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iso_from_ms(ms: int) -> str:
    # integer-only; mirrors backend/domain/normalize.iso_from_ms
    s = int(ms) // 1000
    import datetime as _dt
    return _dt.datetime.fromtimestamp(s, tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    fapi_syms = {s["symbol"]: s for s in FAPI.get("symbols", [])}
    spot_syms = {s["symbol"]: s for s in SPOT.get("symbols", [])}

    rows = []
    for b in BSTOCKS:
        spot_sym = b + "USDT"
        fut_base = b[:-1]
        fut_sym = fut_base + "USDT"
        spot = spot_syms.get(spot_sym)
        fut = fapi_syms.get(fut_sym)
        quote = fut.get("quoteAsset") if fut else "USDT"
        alias_match = bool(
            fut and (fut["baseAsset"] + "B" + fut["quoteAsset"]) == spot_sym
        )
        rows.append({
            "base": b,
            "spot_sym": spot_sym,
            "spot_exists": bool(spot),
            "margin_ok": bool(spot and spot.get("isMarginTradingAllowed")),
            "fut_sym": fut_sym,
            "fut_exists": bool(fut),
            "contract_type": fut.get("contractType") if fut else None,
            "status": fut.get("status") if fut else None,
            "underlying": fut.get("underlyingType") if fut else None,
            "quote": quote,
            "alias_match": alias_match,
        })

    fapi_total = len(FAPI.get("symbols", []))
    spot_total = len(SPOT.get("symbols", []))
    tradifi_total = sum(
        1 for s in FAPI.get("symbols", []) if s.get("contractType") == "TRADIFI_PERPETUAL"
    )
    tradifi_list = sorted(
        s["symbol"] for s in FAPI.get("symbols", [])
        if s.get("contractType") == "TRADIFI_PERPETUAL"
    )

    out = []
    out.append(f"# Evidence Index — bStock B-suffix alias (public market)\n")
    out.append(f"- Capture id: `{CAPTURE_ID}`")
    out.append(f"- Stage: `{STAGE}`")
    out.append(f"- fapi serverTime at capture: `{FAPI.get('serverTime')}` "
               f"({iso_from_ms(FAPI.get('serverTime'))}); timezone `{FAPI.get('timezone')}`")
    out.append(f"- spot serverTime at capture: `{SPOT.get('serverTime')}` "
               f"({iso_from_ms(SPOT.get('serverTime'))}); timezone `{SPOT.get('timezone')}`")
    out.append(f"- fapi symbols captured: {fapi_total}; spot symbols captured: {spot_total}\n")

    out.append("## Source endpoints (PUBLIC, anonymous, read-only)\n")
    out.append("- `https://fapi.binance.com/fapi/v1/exchangeInfo` (USD-M futures)")
    out.append("- `https://api.binance.com/api/v3/exchangeInfo` (spot / margin)\n")
    out.append("No API key, signature, cookie, or account token was used. The response")
    out.append("headers are preserved alongside each payload.\n")

    out.append("## Capture commands (reproducible)\n")
    out.append("```bash")
    out.append("# from this capture directory (raw/ already created)")
    out.append("curl -sS -m 60 -o raw/fapi-v1-exchangeInfo.json \\")
    out.append("  -D raw/fapi-v1-exchangeInfo.headers \\")
    out.append("  -w 'http=%{http_code} bytes=%{size_download}\\n' \\")
    out.append("  https://fapi.binance.com/fapi/v1/exchangeInfo")
    out.append("curl -sS -m 90 -o raw/api-v3-exchangeInfo.json \\")
    out.append("  -D raw/api-v3-exchangeInfo.headers \\")
    out.append("  -w 'http=%{http_code} bytes=%{size_download}\\n' \\")
    out.append("  https://api.binance.com/api/v3/exchangeInfo")
    out.append("```\n")

    out.append("## NOT called (stage hard constraints)\n")
    out.append("- No signed endpoint, no API key, no private account endpoint, no user")
    out.append("  data stream, no listenKey.")
    out.append("- No `/sapi/*`, no `/fapi/v1/order`, no `/dapi/v1/order`, no borrow, no")
    out.append("  repay, no transfer, no websocket.\n")

    out.append("## Files (raw/)\n")
    out.append("| file | bytes | sha256 |")
    out.append("|---|---:|---|")
    for name in ["fapi-v1-exchangeInfo.json", "api-v3-exchangeInfo.json",
                 "fapi-v1-exchangeInfo.headers", "api-v3-exchangeInfo.headers"]:
        p = RAW / name
        if p.exists():
            out.append(f"| raw/{name} | {p.stat().st_size} | `{sha256(p)}` |")
    out.append("")

    out.append("## Alias rule under test\n")
    out.append("A bStock futures symbol has baseAsset WITHOUT a trailing `B` and")
    out.append("`contractType=TRADIFI_PERPETUAL`; its public spot/margin leg carries a")
    out.append("trailing `B`, joined as `futures_baseAsset + \"B\" + quoteAsset`")
    out.append("(e.g. futures `TSLAUSDT` -> spot `TSLABUSDT`). Backend")
    out.append("`resolve_spot_leg` gates this alias on")
    out.append("`contract_type == \"TRADIFI_PERPETUAL\"`, after exact-symbol matching")
    out.append("fails.\n")

    out.append("## Cross-verification (15 user-listed bStocks)\n")
    out.append("| bstock_base | spot_leg | spot_exists | marginAllowed | futures_leg | fut_exists | contractType | status | underlyingType | quote | alias_match |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        out.append(
            f"| {r['base']} | {r['spot_sym']} | {r['spot_exists']} | {r['margin_ok']} | "
            f"{r['fut_sym']} | {r['fut_exists']} | {r['contract_type']} | {r['status']} | "
            f"{r['underlying']} | {r['quote']} | {r['alias_match']} |"
        )
    out.append("")

    n = len(rows)
    out.append("## Summary\n")
    out.append(f"- spot legs present: {sum(r['spot_exists'] for r in rows)}/{n}")
    out.append(f"- `isMarginTradingAllowed=true`: {sum(r['margin_ok'] for r in rows)}/{n}")
    out.append(f"- futures legs present: {sum(r['fut_exists'] for r in rows)}/{n}")
    out.append(f"- `contractType=TRADIFI_PERPETUAL`: "
               f"{sum(r['contract_type']=='TRADIFI_PERPETUAL' for r in rows)}/{n}")
    out.append(f"- futures_baseAsset + \"B\" + quoteAsset == spot_symbol: "
               f"{sum(r['alias_match'] for r in rows)}/{n}")
    quotes = sorted({r['quote'] for r in rows})
    out.append(f"- quote assets observed in this batch: {quotes} "
               f"(all USDT — consistent with the current USDT-quote assumption in `build_rows`).\n")

    out.append("## Context (recorded for completeness; not the verification set)\n")
    out.append(f"This capture contains `{tradifi_total}` TRADIFI_PERPETUAL contracts in fapi.")
    out.append("The 15 user-listed bStocks above are the verification subset. Full list:\n")
    out.append("```")
    out.append(", ".join(tradifi_list))
    out.append("```\n")

    (HERE / "evidence-index.md").write_text("\n".join(out))
    print(f"wrote {HERE / 'evidence-index.md'}")
    print(f"alias_match={sum(r['alias_match'] for r in rows)}/{n} "
          f"margin_ok={sum(r['margin_ok'] for r in rows)}/{n} "
          f"tradifi_total={tradifi_total}")


if __name__ == "__main__":
    main()
