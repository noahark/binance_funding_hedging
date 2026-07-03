#!/usr/bin/env python3
"""Build a schema-valid public-market-snapshot from captured raw public samples.

This is a reproducibility artifact, not backend implementation. It reads the raw
no-key public responses captured in ../raw/ and emits one normalized snapshot
that validates against schemas/api/public-market/snapshot.schema.json.

It deliberately keeps the row set small but covers every route_class and the
asset_tag != route_class case (TRADIFI rows are BSTOCK + PERP_ONLY_EXCLUDED).
All field values are real observed values from the raw payloads; none are
invented except generated_at, which is the capture timestamp passed in.
"""
import json
import sys
from datetime import datetime, timezone

RAW = "../raw"
SAMPLE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "XVGUSDT", "XMRUSDT", "MSTRUSDT", "TSLAUSDT"]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def iso_from_ms(ms):
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def filter_of(s, ftype, key):
    for f in s.get("filters", []):
        if f.get("filterType") == ftype:
            return f.get(key)
    return None


def asset_tag_for(contract_type):
    if contract_type == "TRADIFI_PERPETUAL":
        return ("BSTOCK", "futures_contractType_tradifi_perpetual", "HIGH")
    if contract_type == "PERPETUAL":
        return ("CRYPTO", "futures_contractType_perpetual", "HIGH")
    return ("UNKNOWN", "rule_default_unmapped_contractType", "LOW")


def classify(contract_type, spot_sym, spot_margin):
    # route_class uses the PUBLIC spot isMarginTradingAllowed indicator only.
    # The /sapi margin pair lists are NOT used (they require an API key).
    if contract_type in ("PERPETUAL", "TRADIFI_PERPETUAL"):
        if spot_sym is None:
            route = "PERP_ONLY_EXCLUDED"
        elif spot_margin:
            route = "MARGIN_SPOT_CANDIDATE"
        else:
            route = "SPOT_ONLY_CANDIDATE"
    else:
        route = "PERP_ONLY_EXCLUDED"
    return route


def negative_status(route, asset_tag):
    # Documented priority: PERP_ONLY -> BSTOCK -> SPOT_ONLY -> MARGIN.
    if route == "PERP_ONLY_EXCLUDED":
        return "DISABLED_PERP_ONLY"
    if asset_tag == "BSTOCK":
        return "DISABLED_BSTOCK"
    if route == "SPOT_ONLY_CANDIDATE":
        return "DISABLED_SPOT_ONLY"
    return "PRIVATE_BORROW_VALIDATION_REQUIRED"


def main():
    generated_at = sys.argv[1] if len(sys.argv) > 1 else "2026-07-03T05:17:38Z"

    fapi = load(f"{RAW}/fapi-v1-exchangeInfo.json")
    prem = {p["symbol"]: p for p in load(f"{RAW}/fapi-v1-premiumIndex.json")}
    fr = load(f"{RAW}/fapi-v1-fundingRate-BTCUSDT-limit10.json")
    spot_curated = {s["symbol"]: s for s in load(f"{RAW}/api-v3-exchangeInfo-curated-BTCETHXVG.json")["symbols"]}

    fapi_by_sym = {s["symbol"]: s for s in fapi["symbols"]}

    data_time_ms = max((p.get("time", 0) for p in prem.values()), default=0)

    rows = []
    for sym in SAMPLE_SYMBOLS:
        f = fapi_by_sym[sym]
        p = prem[sym]
        sp = spot_curated.get(sym)
        contract_type = f["contractType"]
        asset_tag, asset_src, asset_conf = asset_tag_for(contract_type)
        spot_margin = bool(sp and sp.get("isMarginTradingAllowed"))
        route = classify(contract_type, sp.get("symbol") if sp else None, spot_margin)
        neg = negative_status(route, asset_tag)

        ui_flags = ["MARGIN_PUBLIC_UNVERIFIED"]  # /sapi margin lists require key; unverifiable in Phase 1
        if route == "PERP_ONLY_EXCLUDED":
            ui_flags.append("PERP_ONLY_NO_SPOT_LEG")
        if asset_tag == "BSTOCK":
            ui_flags.append("TRADIFI_BSTOCK")

        funding_history = []
        if sym == "BTCUSDT":
            funding_history = [
                {"funding_time": int(e["fundingTime"]), "funding_rate": e["fundingRate"]}
                for e in fr
            ]

        rows.append({
            "symbol": sym,
            "base_asset": f["baseAsset"],
            "quote_asset": "USDT",
            "asset_tag": asset_tag,
            "asset_tag_source": asset_src,
            "asset_tag_confidence": asset_conf,
            "route_class": route,
            "positive_funding_enabled": route in ("MARGIN_SPOT_CANDIDATE", "SPOT_ONLY_CANDIDATE"),
            "negative_funding_status": neg,
            "futures": {
                "symbol": sym,
                "status": f["status"],
                "contract_type": contract_type,
                "mark_price": p["markPrice"],
                "index_price": p["indexPrice"],
                "last_funding_rate": p["lastFundingRate"],
                "next_funding_time": int(p["nextFundingTime"]),
                "min_notional": filter_of(f, "MIN_NOTIONAL", "notional"),
                "step_size": filter_of(f, "LOT_SIZE", "stepSize"),
            },
            "spot": {
                "symbol": sp["symbol"] if sp else None,
                "status": sp["status"] if sp else None,
                "exists": sp is not None,
                "min_notional": filter_of(sp, "NOTIONAL", "minNotional") if sp else None,
                "step_size": filter_of(sp, "LOT_SIZE", "stepSize") if sp else None,
            },
            "margin_public": {
                "public_cross_margin_pair": None,
                "source": "unverified",
            },
            "funding_history": funding_history,
            "ui_flags": ui_flags,
        })

    def counts(key):
        out = {}
        for r in rows:
            out[r[key]] = out.get(r[key], 0) + 1
        return out

    snapshot = {
        "schema_version": "public-market-snapshot/v1",
        "generated_at": generated_at,
        "data_time": iso_from_ms(data_time_ms),
        "source_sample_id": "20260703T051738Z",
        "summary": {
            "total_rows": len(rows),
            "route_counts": counts("route_class"),
            "asset_tag_counts": counts("asset_tag"),
            "negative_funding_status_counts": counts("negative_funding_status"),
        },
        "rows": rows,
        "warnings": [
            "GET /sapi/v1/margin/allPairs and /sapi/v1/margin/isolated/allPairs return HTTP 400 code -2014 without an API key, so margin_public stays unverified and is not used for route classification.",
            "premiumIndex.lastFundingRate is documented by Binance as the most recently updated funding rate; whether it equals the last settled rate or a forward estimate is not proven from local docs, so do not label it as a guaranteed settled or upcoming value.",
            "All 118 observed TRADIFI_PERPETUAL symbols have no spot leg, so they are PERP_ONLY_EXCLUDED with asset_tag=BSTOCK; asset_tag is independent of route_class.",
        ],
    }

    with open("public-market-snapshot.json", "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("wrote public-market-snapshot.json rows=", len(rows))


if __name__ == "__main__":
    main()
