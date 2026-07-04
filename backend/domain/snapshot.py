"""Snapshot assembly: build rows from raw inputs and assemble the snapshot.

Decimal discipline: rate ranking uses :class:`decimal.Decimal` (never float);
every decimal field is serialized as a string straight from the raw JSON.
``summary`` counts are aggregated FROM ``rows`` (never computed independently).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List

from .classify import classify_route, negative_funding_status
from .normalize import asset_tag_for, filter_of, resolve_spot_leg

SCHEMA_VERSION = "public-market-snapshot/v1"

CONTRACT_WARNINGS = [
    "GET /sapi/v1/margin/allPairs and /sapi/v1/margin/isolated/allPairs return HTTP 400 code -2014 without an API key, so margin_public stays unverified and is not used for route classification.",
    "premiumIndex.lastFundingRate is the real-time estimate for the CURRENT funding period and is charged at nextFundingTime; it drifts until settlement (mid-period divergence from settled history evidenced under reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/). Settled history comes from /fapi/v1/fundingRate; do not present the estimate as a settled value.",
    "TRADIFI_PERPETUAL (bStock) spot legs are joined via the baseAsset+B+quoteAsset alias (e.g. futures TSLAUSDT -> spot TSLABUSDT); bStock collateral ratio is dynamic/unknown and is not hard-coded; asset_tag is independent of route_class.",
]


def _abs_rate(rate_str) -> Decimal:
    try:
        return abs(Decimal(str(rate_str)))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def top_symbols_by_abs_rate(
    futures_symbols: List[dict],
    premium_by_sym: Dict[str, dict],
    top_n: int,
) -> set:
    """Return the set of top-N symbol names ranked by abs(last funding rate).

    Funding history is fetched only for these symbols, bounding
    /fapi/v1/fundingRate call volume.
    """
    ranked = sorted(
        futures_symbols,
        key=lambda obj: _abs_rate(
            premium_by_sym.get(obj["symbol"], {}).get("lastFundingRate", "0")
        ),
        reverse=True,
    )
    return {obj["symbol"] for obj in ranked[: max(0, int(top_n))]}


def build_rows(
    futures_symbols: List[dict],
    premium_by_sym: Dict[str, dict],
    spot_by_sym: Dict[str, dict],
    funding_history_by_sym: Dict[str, List[dict]],
) -> List[dict]:
    """Build snapshot rows from already-filtered futures symbols.

    Callers must pass only TRADING perpetuals/TRADIFI (filter upstream).
    ``funding_history`` is filled for every symbol that has history available in
    ``funding_history_by_sym``. The service restricts LIVE funding-rate fetching
    to the top-N by abs(rate); offline uses all frozen fixtures (no HTTP cost).
    """
    rows: List[dict] = []
    for obj in futures_symbols:
        sym = obj["symbol"]
        contract_type = obj.get("contractType", "")
        asset_tag, asset_src, asset_conf = asset_tag_for(contract_type)
        spot, match_type = resolve_spot_leg(
            contract_type, obj.get("baseAsset", ""), obj.get("quoteAsset", ""), spot_by_sym
        )
        spot_margin = bool(spot and spot.get("isMarginTradingAllowed"))
        route = classify_route(
            contract_type, spot.get("symbol") if spot else None, spot_margin
        )
        neg = negative_funding_status(route, asset_tag)
        prem = premium_by_sym.get(sym, {})

        ui_flags = ["MARGIN_PUBLIC_UNVERIFIED"]
        if route == "PERP_ONLY_EXCLUDED":
            ui_flags.append("PERP_ONLY_NO_SPOT_LEG")
        if asset_tag == "BSTOCK":
            ui_flags.append("TRADIFI_BSTOCK")

        funding_history: List[dict] = []
        if sym in funding_history_by_sym:
            funding_history = [
                {
                    "funding_time": int(entry["fundingTime"]),
                    "funding_rate": entry["fundingRate"],
                }
                for entry in funding_history_by_sym[sym]
            ]

        rows.append(
            {
                "symbol": sym,
                "base_asset": obj.get("baseAsset", ""),
                "quote_asset": "USDT",
                "asset_tag": asset_tag,
                "asset_tag_source": asset_src,
                "asset_tag_confidence": asset_conf,
                "route_class": route,
                "positive_funding_enabled": route
                in ("MARGIN_SPOT_CANDIDATE", "SPOT_ONLY_CANDIDATE"),
                "negative_funding_status": neg,
                "futures": {
                    "symbol": sym,
                    "status": obj.get("status", ""),
                    "contract_type": contract_type,
                    "mark_price": prem.get("markPrice", "0"),
                    "index_price": prem.get("indexPrice", "0"),
                    "last_funding_rate": prem.get("lastFundingRate", "0"),
                    "next_funding_time": int(prem.get("nextFundingTime", 0)),
                    "min_notional": filter_of(obj, "MIN_NOTIONAL", "notional") or "0",
                    "step_size": filter_of(obj, "LOT_SIZE", "stepSize") or "0",
                },
                "spot": {
                    "symbol": spot["symbol"] if spot else None,
                    "status": spot["status"] if spot else None,
                    "exists": spot is not None,
                    "match_type": match_type,
                    "min_notional": filter_of(spot, "NOTIONAL", "minNotional")
                    if spot
                    else None,
                    "step_size": filter_of(spot, "LOT_SIZE", "stepSize") if spot else None,
                },
                "margin_public": {
                    "public_cross_margin_pair": None,
                    "source": "unverified",
                },
                "funding_history": funding_history,
                "ui_flags": ui_flags,
            }
        )
    return rows


def _counts(rows: List[dict], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        value = r[key]
        out[value] = out.get(value, 0) + 1
    return out


def assemble_snapshot(
    rows: List[dict],
    *,
    generated_at: str,
    data_time: str,
    source_sample_id: str,
) -> dict:
    """Assemble the full snapshot. ``summary`` is aggregated from ``rows``."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "data_time": data_time,
        "source_sample_id": source_sample_id,
        "summary": {
            "total_rows": len(rows),
            "route_counts": _counts(rows, "route_class"),
            "asset_tag_counts": _counts(rows, "asset_tag"),
            "negative_funding_status_counts": _counts(rows, "negative_funding_status"),
        },
        "rows": rows,
        "warnings": list(CONTRACT_WARNINGS),
    }
