"""Snapshot assembly: build rows from raw inputs and assemble the snapshot.

Decimal discipline: rate ranking uses :class:`decimal.Decimal` (never float);
every decimal field is serialized as a string straight from the raw JSON.
``summary`` counts are aggregated FROM ``rows`` (never computed independently).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from .classify import classify_route, negative_funding_status
from .normalize import asset_tag_for, filter_of, resolve_spot_leg

SCHEMA_VERSION = "public-market-snapshot/v1"

# §1.2 sort_basis enum. The wire schema_version stays v1 (additive v0.3 contract);
# these name the two snapshot-level ranking bases.
SORT_BASIS_NET = "net_daily_yield"
SORT_BASIS_ABS = "abs_daily_funding_rate"

# §1.4 valuation: stablecoins priced at 1 USD (spec literal: USDT/USDC).
_STABLE_USD_ASSETS = {"USDT", "USDC"}
_PRIVATE_ACCOUNT_PRICE_SOURCE = "api_v3_ticker_price"

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
    *,
    funding_interval_by_sym: Optional[Dict[str, int]] = None,
) -> List[dict]:
    """Build snapshot rows from already-filtered futures symbols.

    Callers must pass only TRADING perpetuals/TRADIFI (filter upstream).
    ``funding_history`` is filled for every symbol that has history available in
    ``funding_history_by_sym``. The service restricts LIVE funding-rate fetching
    to the top-N by abs(rate); offline uses all frozen fixtures (no HTTP cost).

    ``funding_interval_by_sym`` (symbol -> fundingIntervalHours from public
    ``/fapi/v1/fundingInfo``) populates ``funding_interval_hours`` and drives the
    ``daily_funding_rate = Decimal(lastFundingRate) * (24/interval)`` computation.
    Symbols absent from fundingInfo default to 8 (Binance default); ``None``/empty
    means all symbols use the 8h default.
    """
    interval_map = funding_interval_by_sym or {}
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
        interval_hours = int(interval_map.get(sym, 8))
        daily_rate = compute_daily_funding_rate(
            prem.get("lastFundingRate", "0"), interval_hours
        )

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
                "funding_interval_hours": interval_hours,
                "daily_funding_rate": daily_rate,
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
    private_channel_status: str = "disabled",
    sort_basis: Optional[str] = None,
    private_account: Optional[dict] = None,
    borrow_validation_summary: Optional[dict] = None,
    extra_warnings: Optional[List[str]] = None,
) -> dict:
    """Assemble the full snapshot. ``summary`` is aggregated from ``rows``.

    ``private_channel_status`` is ``"enabled"`` when the private borrow-validation
    channel returned a classic reference; otherwise ``"disabled"`` (env missing or
    endpoint failure), in which case every row's ``borrow_validation.verified``
    is false with null data fields.

    v0.3 additive top-level fields (all optional so the v0.1 frozen fixture, which
    carries none of them, still validates):
    - ``sort_basis`` (§1.2): ``net_daily_yield`` when the private cost leg is
      available (incl. vip0_reference), else ``abs_daily_funding_rate``.
    - ``private_account`` (§1.4): the three-state aggregated-asset block.
    - ``borrow_validation`` (top-level aggregate, §1.5): ``coverage`` +
      ``chain_hit_tier``/``chain_hit_source`` snapshot-level diagnostics. This is
      a different shape from the per-row ``rows[].borrow_validation`` (same JSON
      key, different path).

    ``extra_warnings`` are runtime degradation warnings (e.g. the E1 fundingInfo
    fallback, private_account no-price lines) appended after the fixed
    ``CONTRACT_WARNINGS``. §1.5 also requires a top-level warnings entry whenever
    borrowability was not fully probed (``coverage.skipped > 0``) — derived here
    from ``borrow_validation_summary`` so the gap is never silent. Rate coverage
    is unaffected (the borrow rate is still filled for those rows).
    """
    warnings = list(CONTRACT_WARNINGS) + list(extra_warnings or [])
    coverage = (borrow_validation_summary or {}).get("coverage") or {}
    if coverage.get("skipped", 0) > 0:
        warnings.append(
            f"borrow_validation: {coverage['skipped']} asset(s) borrowability not "
            f"probed (rate still covered) — 部分资产可借额度未探测（利率仍覆盖）"
        )
    snap = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "data_time": data_time,
        "source_sample_id": source_sample_id,
        "private_channel": private_channel_status,
        "summary": {
            "total_rows": len(rows),
            "route_counts": _counts(rows, "route_class"),
            "asset_tag_counts": _counts(rows, "asset_tag"),
            "negative_funding_status_counts": _counts(rows, "negative_funding_status"),
        },
        "rows": rows,
        "warnings": warnings,
    }
    if sort_basis is not None:
        snap["sort_basis"] = sort_basis
    if private_account is not None:
        snap["private_account"] = private_account
    if borrow_validation_summary is not None:
        snap["borrow_validation"] = borrow_validation_summary
    return snap


def compute_daily_funding_rate(
    last_funding_rate, interval_hours: int
) -> Optional[str]:
    """``Decimal(lastFundingRate) * (24 / interval)`` as a fixed-point string.

    8-place quantization (``Decimal('1E-8')``), no scientific notation; negative
    zero is normalized to ``"0.00000000"``. Missing/empty/non-numeric input or a
    non-positive interval -> ``None`` (rows with ``None`` sort last). Decimal-only;
    float never touches a value path.

    Vectors (10-design §3.3):
      ``"0.00010000"`` x24/8 -> ``"0.00030000"``;
      ``"0.00010000"`` x24/4 -> ``"0.00060000"``;
      ``"-0.00005000"`` x24/4 -> ``"-0.00030000"``;
      ``"0.00002000"`` x24/1 -> ``"0.00048000"``;
      ``"-0.00000000"`` x24/8 -> ``"0.00000000"`` (negative-zero normalization);
      missing/``""`` -> ``None``.
    """
    if last_funding_rate is None or last_funding_rate == "":
        return None
    try:
        rate = Decimal(str(last_funding_rate))
    except (InvalidOperation, ValueError, TypeError):
        return None
    try:
        interval = int(interval_hours)
    except (TypeError, ValueError):
        return None
    if interval <= 0:
        return None
    daily = rate * (Decimal(24) / Decimal(interval))
    if daily == 0:  # normalize negative zero before quantize
        daily = Decimal(0)
    daily = daily.quantize(Decimal("1E-8"))
    return format(daily, "f")


def _quantize_rate(value: Decimal) -> str:
    """8-place fixed-point string; negative zero normalized to ``"0.00000000"``.

    Shared by every v0.3 rate computation so the format is identical to the
    Phase 2 ``daily_funding_rate`` style (no scientific notation, no float).
    """
    if value == 0:
        value = Decimal(0)
    return format(value.quantize(Decimal("1E-8")), "f")


def compute_daily_from_hourly(hourly_rate) -> Optional[str]:
    """``Decimal(hourlyInterestRate) × 24`` as an 8-place string (§1.3 tier①).

    Normalizes the E2 next-hourly estimate to a daily account interest rate.
    Missing/empty/non-numeric -> ``None``. Decimal-only; float never touches it.

    Vector (10-design §3.4 #4): ``"0.00000500"`` -> ``"0.00012000"``.
    """
    if hourly_rate is None or hourly_rate == "":
        return None
    try:
        hourly = Decimal(str(hourly_rate))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return _quantize_rate(hourly * Decimal(24))


def compute_net_daily_yield(daily_funding_rate, daily_borrow_rate) -> Optional[str]:
    """Opportunity-quality score (§0/§1.1) as an 8-place string or ``None``.

    - ``daily_funding_rate`` null -> null.
    - ``daily_funding_rate >= 0`` -> ``daily_funding_rate`` (no borrow leg).
    - ``daily_funding_rate < 0`` -> ``abs(daily_funding_rate) - daily_borrow_rate``
      (may be negative; output as-is); ``daily_borrow_rate`` null/non-numeric
      -> null.

    Decimal-only; negative zero normalized. Vectors (§3.4 #1-3,#5,#6):
      ``-0.0006``/``0.0002`` -> ``0.00040000``; ``-0.0006``/``0.0008`` ->
      ``-0.00020000``; ``0.0003`` -> ``0.00030000``; ``-0.0006``/None -> None;
      None -> None.
    """
    if daily_funding_rate is None or daily_funding_rate == "":
        return None
    try:
        dfr = Decimal(str(daily_funding_rate))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if dfr >= 0:
        return _quantize_rate(dfr)
    if daily_borrow_rate is None or daily_borrow_rate == "":
        return None
    try:
        borrow = Decimal(str(daily_borrow_rate))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return _quantize_rate(abs(dfr) - borrow)


def select_borrow_candidates(
    rows: List[dict], max_calls: int
) -> dict:
    """§1.5 borrow probe sets + coverage.

    Probe range = rows with ``daily_funding_rate < 0`` AND
    ``route_class == MARGIN_SPOT_CANDIDATE`` AND ``asset_tag == CRYPTO``, de-duped
    by ``base_asset``. Truncation priority is abs daily rate DESC (symbol ASC
    tie-break). The pool is split into THREE sets so the rate budget and the
    borrowability budget are decoupled (borrow-cost-coverage-v2):

    - ``rate_probe_assets``: the FULL de-duped pool (abs rate DESC, symbol ASC),
      NOT capped — drives the next-hourly interest-rate coverage (cost leg). A
      candidate outside the borrowability cap still gets its borrow rate here.
    - ``borrowability_probe_assets``: the first ``max_calls`` of the pool — drives
      the per-asset ``fetch_max_borrowable`` (bounded) loop.
    - ``borrowability_unprobed_assets``: the remainder (rate covered, but
      borrowability NOT probed) — their rows render ``verified=false`` /
      ``error="borrowability_not_probed"`` while keeping the borrow rate.

    ``coverage`` is the borrowability coverage (NOT rate coverage):
    ``probed = len(borrowability_probe_assets)``,
    ``skipped = len(borrowability_unprobed_assets)``.
    """
    cap = max(0, int(max_calls))
    candidates = [
        r
        for r in rows
        if r.get("daily_funding_rate")
        and r.get("route_class") == "MARGIN_SPOT_CANDIDATE"
        and r.get("asset_tag") == "CRYPTO"
        and Decimal(str(r["daily_funding_rate"])) < 0
    ]
    candidates.sort(
        key=lambda r: (-abs(Decimal(str(r["daily_funding_rate"]))), r.get("symbol", ""))
    )
    rate_probe: List[str] = []
    seen: set = set()
    for r in candidates:
        asset = r.get("base_asset", "")
        if not asset or asset in seen:
            continue
        seen.add(asset)
        rate_probe.append(asset)
    borrowability_probe = rate_probe[:cap]
    borrowability_unprobed: set = set(rate_probe[cap:])
    skipped = len(borrowability_unprobed)
    return {
        "rate_probe_assets": rate_probe,
        "borrowability_probe_assets": borrowability_probe,
        "borrowability_unprobed_assets": borrowability_unprobed,
        "coverage": {
            "probed": len(borrowability_probe),
            "skipped": skipped,
            "reason": "rate_limit_budget" if skipped else None,
        },
    }


def resolve_cost_leg_rate(asset: Optional[str], cost_leg: Optional[dict]) -> Optional[str]:
    """Per-asset daily borrow rate from the snapshot-level hit tier (§1.3).

    ``cost_leg`` is the ``PrivateClient.fetch_cost_leg_chain`` result. Tier①
    (``next_hourly``) holds raw hourly strings and is normalized here via ×24;
    tiers ②/③/④ already carry daily rates and are only re-quantized for format.
    Asset absent from the hit tier's table, or chain broken -> ``None``.
    """
    if not cost_leg or asset is None:
        return None
    raw = cost_leg.get("daily_by_asset", {}).get(asset)
    if raw is None or raw == "":
        return None
    if cost_leg.get("chain_hit_source") == "next_hourly":
        return compute_daily_from_hourly(raw)
    try:
        return _quantize_rate(Decimal(str(raw)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _add_dec(a, b) -> Optional[str]:
    """Sum two raw decimal strings -> raw string (Decimal), or None if both null."""
    sa = "" if a is None else str(a)
    sb = "" if b is None else str(b)
    if sa == "" and sb == "":
        return None
    try:
        return str((Decimal(sa) if sa else Decimal(0)) + (Decimal(sb) if sb else Decimal(0)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _usdt_value(asset, amount, price_map: Dict[str, str], warnings: List[str]) -> Decimal:
    """USD(T) value of one balance line for total_value_usdt (§1.4).

    Stable US assets (USDT/USDC) price at 1. Other assets use the
    ``{asset}USDT`` ticker price (full map, fetched once). No price / bad price
    / zero amount -> 0 and a warning (asset still listed, never dropped).
    """
    if asset is None or amount is None or amount == "":
        return Decimal(0)
    try:
        amt = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)
    if amt == 0:
        return Decimal(0)
    if asset in _STABLE_USD_ASSETS:
        return amt
    price = price_map.get(f"{asset}USDT")
    if price is None or price == "":
        warnings.append(f"private_account: no USDT price for {asset}, counted at 0")
        return Decimal(0)
    try:
        return amt * Decimal(str(price))
    except (InvalidOperation, ValueError, TypeError):
        warnings.append(f"private_account: bad USDT price for {asset}, counted at 0")
        return Decimal(0)


def _usdt_value_optional(asset, amount, price_map: Dict[str, str], warnings: List[str]) -> Optional[Decimal]:
    """Per-balance USDT valuation for row-level ``value_usdt`` (v0.4 additive).

    Differs from ``_usdt_value`` in nullability: missing/bad amount or price
    returns ``None`` (with warning) so the UI can distinguish "cannot value"
    from "priced zero". A valid zero amount or a valid computation that equals
    zero returns ``Decimal(0)`` (serialized as ``"0.00000000"``).

    Stable USD assets (USDT/USDC) price at 1.
    """
    if asset is None or amount is None or amount == "":
        warnings.append(f"private_account: missing amount for {asset}, value_usdt unavailable")
        return None
    try:
        amt = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        warnings.append(f"private_account: bad amount for {asset}, value_usdt unavailable")
        return None
    if asset in _STABLE_USD_ASSETS:
        return amt
    price = price_map.get(f"{asset}USDT")
    if price is None or price == "":
        warnings.append(f"private_account: no USDT price for {asset}, value_usdt unavailable")
        return None
    try:
        return amt * Decimal(str(price))
    except (InvalidOperation, ValueError, TypeError):
        warnings.append(f"private_account: bad USDT price for {asset}, value_usdt unavailable")
        return None


def _balance_sort_key(row_with_index):
    idx, row = row_with_index
    raw = row.get("value_usdt")
    asset = str(row.get("asset") or "")
    try:
        value = Decimal(str(raw)) if raw not in (None, "") else None
    except (InvalidOperation, ValueError, TypeError):
        value = None
    if value is None:
        return (1, Decimal("0"), asset, idx)
    return (0, -value, asset, idx)


def _infer_position_side(position_amt) -> Optional[str]:
    """§2.A.3 E4 open item: papi positionRisk has no positionSide field; infer
    from positionAmt sign (LONG>0 / SHORT<0 / None when flat). To be re-verified
    live when a real position appears (R3 upgrade口, 10-design §2.A.3)."""
    if position_amt is None or position_amt == "":
        return None
    try:
        amt = Decimal(str(position_amt))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amt > 0:
        return "LONG"
    if amt < 0:
        return "SHORT"
    return None


def assemble_private_account(
    unified: Optional[List[dict]],
    spot: Optional[List[dict]],
    um_positions: Optional[List[dict]],
    price_map: Dict[str, str],
    *,
    checked_at: Optional[str],
    error: Optional[str],
) -> dict:
    """Three-state ``private_account`` block (§1.4).

    ``unified`` (E3), ``spot`` (E6), ``um_positions`` (E4) are the raw lists, or
    ``None`` when that fetch was disabled/failed. Disabled state (channel off or
    both balance sources failed -> ``unified is None and spot is None``):
    ``verified=false``, three arrays empty, ``total_value_usdt`` null, error
    filled. Otherwise ``verified=true`` with available arrays (a failed single
    source degrades to an empty array, not a block-level failure).

    Anti-double-count hard rule (§1.4, asserted in tests): ``total_value_usdt``
    = ``Σ(unified totalWalletBalance priced) + Σ(spot free+locked priced)``;
    the unified ``totalWalletBalance`` already includes um/cm/crossMargin
    sub-accounts (never re-added), and ``um_positions`` is an exposure view whose
    nominal value is NEVER counted. Returns ``(block, warnings)``.

    v0.4 additive: each balance row carries ``value_usdt`` (8-place decimal
    string | null) computed by the same price map. Missing/bad amount or price
    -> null with warning; valid zero -> ``"0.00000000"``. The frontend must not
    re-derive ``total_value_usdt`` from row values.
    """
    warnings: List[str] = []
    if unified is None and spot is None:
        return (
            {
                "verified": False,
                "balances_unified": [],
                "balances_spot": [],
                "um_positions": [],
                "total_value_usdt": None,
                "valuation": {
                    "price_source": _PRIVATE_ACCOUNT_PRICE_SOURCE,
                    "priced_at": None,
                },
                "checked_at": None,
                "error": error or "private_channel_disabled",
            },
            warnings,
        )
    unified_list = unified or []
    spot_list = spot or []
    um_list = um_positions or []
    unified_out = []
    for x in unified_list:
        if not isinstance(x, dict):
            continue
        asset = x.get("asset")
        value = _usdt_value_optional(
            asset, x.get("totalWalletBalance"), price_map, warnings
        )
        unified_out.append(
            {
                "asset": asset,
                "total_balance": x.get("totalWalletBalance"),
                "value_usdt": _quantize_rate(value) if value is not None else None,
            }
        )
    spot_out = []
    for x in spot_list:
        if not isinstance(x, dict):
            continue
        asset = x.get("asset")
        amount = _add_dec(x.get("free"), x.get("locked"))
        value = _usdt_value_optional(asset, amount, price_map, warnings)
        spot_out.append(
            {
                "asset": asset,
                "free": x.get("free"),
                "locked": x.get("locked"),
                "value_usdt": _quantize_rate(value) if value is not None else None,
            }
        )
    um_out = [
        {
            "symbol": p.get("symbol"),
            "position_side": _infer_position_side(p.get("positionAmt")),
            "position_amt": p.get("positionAmt"),
            "entry_price": p.get("entryPrice"),
            "mark_price": p.get("markPrice"),
            "unrealized_profit": p.get("unRealizedProfit"),
            "liquidation_price": p.get("liquidationPrice"),
        }
        for p in um_list
        if isinstance(p, dict)
    ]
    # v1.1-ui-polish-2: private account balance arrays are sorted by value_usdt
    # DESC, nulls last, asset ASC tie-break, original input order for same asset.
    unified_out = [row for _, row in sorted(enumerate(unified_out), key=_balance_sort_key)]
    spot_out = [row for _, row in sorted(enumerate(spot_out), key=_balance_sort_key)]
    total = Decimal(0)
    for x in unified_list:
        if isinstance(x, dict):
            total += _usdt_value(
                x.get("asset"), x.get("totalWalletBalance"), price_map, warnings
            )
    for x in spot_list:
        if isinstance(x, dict):
            total += _usdt_value(
                x.get("asset"), _add_dec(x.get("free"), x.get("locked")), price_map, warnings
            )
    return (
        {
            "verified": True,
            "balances_unified": unified_out,
            "balances_spot": spot_out,
            "um_positions": um_out,
            "total_value_usdt": _quantize_rate(total),
            "valuation": {
                "price_source": _PRIVATE_ACCOUNT_PRICE_SOURCE,
                "priced_at": checked_at,
            },
            "checked_at": checked_at,
            "error": None,
        },
        warnings,
    )


def sort_rows(rows: List[dict], basis: str = SORT_BASIS_ABS) -> List[dict]:
    """Deterministic total order — this IS the payload order the frontend renders
    (the frontend must not reorder; filters only hide). Uses Decimal, never float.

    - ``abs_daily_funding_rate`` (default; Phase 2 behavior): abs(daily) DESC,
      nulls last, symbol ASC tie-break. The Phase 2 regression suite pins this.
    - ``net_daily_yield`` (§1.2; private cost leg available): net DESC (signed),
      nulls last, symbol ASC tie-break. Lets a negative-funding row with cheap
      borrow rank above a higher-abs-rate row with expensive borrow (§3.5).
    """

    def key(r: dict):
        sym = r.get("symbol", "")
        if basis == SORT_BASIS_NET:
            n = r.get("net_daily_yield")
            if n is None:
                return (1, Decimal(0), sym)
            try:
                return (0, -Decimal(str(n)), sym)  # negate -> net DESC
            except (InvalidOperation, ValueError, TypeError):
                return (1, Decimal(0), sym)
        d = r.get("daily_funding_rate")
        if d is None:
            return (1, Decimal(0), sym)  # nulls sort last
        try:
            neg = -abs(Decimal(str(d)))
        except (InvalidOperation, ValueError, TypeError):
            return (1, Decimal(0), sym)
        return (0, neg, sym)  # neg ascending == abs descending; symbol asc

    return sorted(rows, key=key)


def assemble_borrow_validation(
    row: dict,
    classic_ref: Optional[dict],
    portfolio_by_asset: Dict[str, dict],
    checked_at: Optional[str],
    error: Optional[str],
    *,
    daily_interest_account: Optional[str] = None,
    borrowability_truncated: bool = False,
) -> dict:
    """Three-state borrow-validation block (parallel output; never alters classify).

    - ``classic_ref is None`` (private channel disabled/failed): ``verified=false``,
      every data field null, ``error`` carries the reason.
    - ``borrowability_truncated`` (§1.5: borrow candidate beyond the
      maxBorrowable budget, but the rate IS covered): ``verified=false``,
      ``error="borrowability_not_probed"``. classic_margin is filled normally
      (pair_listed/asset_borrowable/daily_interest_vip0/daily_interest_account —
      the borrow rate is KEPT), checked_at is KEPT, and ONLY the portfolio_account
      amount fields are cleared. Distinct from the legacy
      ``error="not_probed_this_round"`` (rate also absent).
    - verified, pair not listed in the classic list: ``verified=true``,
      ``pair_listed=false``, asset/interest fields null.
    - verified, pair listed: ``verified=true``, ``pair_listed=true`` + asset/interest.

    ``daily_interest_account`` is the v0.3 account-level daily borrow rate for a
    probed negative-funding candidate whose cost-leg tier produced a rate (else
    null). ``portfolio_account`` carries values only for bounded candidates
    present in ``portfolio_by_asset``; other rows keep null amount fields (the
    block is still present with its ``source``). ``checked_at`` is the
    request-success moment.
    """
    base = row.get("base_asset", "")
    sym = row.get("symbol", "")
    if classic_ref is None:
        return {
            "verified": False,
            "classic_margin": {
                "pair_listed": None,
                "asset_borrowable": None,
                "daily_interest_vip0": None,
                "daily_interest_account": None,
                "source": "sapi_reference",
            },
            "portfolio_account": {
                "max_borrowable": None,
                "borrow_limit": None,
                "source": "papi_max_borrowable",
            },
            "checked_at": None,
            "error": error,
        }
    pair_listed = classic_ref.get("pair_listed_by_symbol", {}).get(sym)
    if pair_listed:
        asset_borrowable = classic_ref.get("asset_borrowable_by_name", {}).get(base)
        daily_vip0 = classic_ref.get("daily_interest_vip0_by_coin", {}).get(base)
    else:
        asset_borrowable = None
        daily_vip0 = None
    if borrowability_truncated:
        # Borrowability NOT probed (beyond the maxBorrowable budget) but the
        # classic reference is valid and the borrow rate IS covered: keep the
        # classic_margin fields (incl. daily_interest_account) and checked_at,
        # clear ONLY the portfolio_account amount fields, mark verified=false.
        return {
            "verified": False,
            "classic_margin": {
                "pair_listed": bool(pair_listed),
                "asset_borrowable": asset_borrowable,
                "daily_interest_vip0": daily_vip0,
                "daily_interest_account": daily_interest_account,
                "source": "sapi_reference",
            },
            "portfolio_account": {
                "max_borrowable": None,
                "borrow_limit": None,
                "source": "papi_max_borrowable",
            },
            "checked_at": checked_at,
            "error": "borrowability_not_probed",
        }
    portfolio = portfolio_by_asset.get(base, {})
    return {
        "verified": True,
        "classic_margin": {
            "pair_listed": bool(pair_listed),
            "asset_borrowable": asset_borrowable,
            "daily_interest_vip0": daily_vip0,
            "daily_interest_account": daily_interest_account,
            "source": "sapi_reference",
        },
        "portfolio_account": {
            "max_borrowable": portfolio.get("max_borrowable"),
            "borrow_limit": portfolio.get("borrow_limit"),
            "source": "papi_max_borrowable",
        },
        "checked_at": checked_at,
        "error": None,
    }
