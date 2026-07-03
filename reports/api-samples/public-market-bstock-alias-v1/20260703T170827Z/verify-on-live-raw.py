#!/usr/bin/env python3
"""Verify the bStock alias rule against LIVE public exchangeInfo captures.

Drives the REAL backend pipeline (``backend/domain/snapshot.build_rows`` +
``assemble_snapshot``) with the live fapi+spot exchangeInfo payloads in
``./raw/``. ``premium_by_sym`` and ``funding_history_by_sym`` are empty: those
feeds do not affect alias resolution, ``route_class``, or
``negative_funding_status``, so the alias verification does not require live
premium/funding capture.

Asserts all 15 user-listed bStocks resolve to ``MARGIN_SPOT_CANDIDATE`` with
``spot.match_type=bstock_b_suffix_alias`` and
``negative_funding_status=DISABLED_BSTOCK``, plus one negative control
(BTCUSDT, a normal PERPETUAL with an exact spot leg, must NOT alias). Validates
the assembled snapshot against the amended ``snapshot.schema.json``.

Run from the repo root with the Harness venv:
    .venv/bin/python reports/api-samples/public-market-bstock-alias-v1/<ts>/verify-on-live-raw.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True, cwd=HERE
    ).strip()
)
sys.path.insert(0, str(ROOT))

from backend.domain.normalize import iso_from_ms  # noqa: E402
from backend.domain.snapshot import assemble_snapshot, build_rows  # noqa: E402

RAW = HERE / "raw"
FAPI = json.loads((RAW / "fapi-v1-exchangeInfo.json").read_text())
SPOT = json.loads((RAW / "api-v3-exchangeInfo.json").read_text())

BSTOCKS = [
    "CRCLB", "MUB", "NVDAB", "SNDKB", "TSLAB", "SPCXB", "AMDB", "EWYB", "INTCB",
    "MSTRB", "LITEB", "METAB", "MSFTB", "PLTRB", "QQQB",
]
# futures_sym -> expected spot_sym
EXPECTED = {b[:-1] + "USDT": b + "USDT" for b in BSTOCKS}

fapi_syms = {s["symbol"]: s for s in FAPI["symbols"]}
spot_by_sym = {s["symbol"]: s for s in SPOT["symbols"]}

# 15 TRADIFI bStock contracts + 1 negative control (BTCUSDT, normal PERPETUAL).
NEG_CONTROL = "BTCUSDT"
futures_subset = [fapi_syms[f] for f in EXPECTED]
neg_present = NEG_CONTROL in fapi_syms and NEG_CONTROL in spot_by_sym
if neg_present:
    futures_subset.append(fapi_syms[NEG_CONTROL])

rows = build_rows(futures_subset, {}, spot_by_sym, {})

print(
    f"build_rows on live raw: {len(rows)} rows "
    f"({len(EXPECTED)} bStock futures + {'1 negative control' if neg_present else 'no neg control'})"
)
print()

hdr = (
    f"{'futures':<11} {'contractType':<20} {'spot_leg':<12} "
    f"{'route':<22} {'match_type':<24} {'neg_status':<18} {'pos_fund'}"
)
print(hdr)
print("-" * len(hdr))

failures = []
for r in sorted(rows, key=lambda x: x["symbol"]):
    sym = r["symbol"]
    print(
        f"{sym:<11} {r['futures']['contract_type']:<20} "
        f"{str(r['spot']['symbol']):<12} {r['route_class']:<22} "
        f"{str(r['spot']['match_type']):<24} {r['negative_funding_status']:<18} "
        f"{r['positive_funding_enabled']}"
    )
    if sym in EXPECTED:
        exp_spot = EXPECTED[sym]
        checks = {
            "route_class==MARGIN_SPOT_CANDIDATE": r["route_class"] == "MARGIN_SPOT_CANDIDATE",
            "positive_funding_enabled==True": r["positive_funding_enabled"] is True,
            "negative_funding_status==DISABLED_BSTOCK": r["negative_funding_status"] == "DISABLED_BSTOCK",
            "asset_tag==BSTOCK": r["asset_tag"] == "BSTOCK",
            "spot.symbol==expected": r["spot"]["symbol"] == exp_spot,
            "spot.match_type==bstock_b_suffix_alias": r["spot"]["match_type"] == "bstock_b_suffix_alias",
            "spot.exists==True": r["spot"]["exists"] is True,
            "PERP_ONLY_NO_SPOT_LEG absent": "PERP_ONLY_NO_SPOT_LEG" not in r["ui_flags"],
            "TRADIFI_BSTOCK present": "TRADIFI_BSTOCK" in r["ui_flags"],
            "margin_public.source==unverified": r["margin_public"]["source"] == "unverified",
            "public_cross_margin_pair is None": r["margin_public"]["public_cross_margin_pair"] is None,
        }
        for k, v in checks.items():
            if not v:
                failures.append(f"{sym}: {k}")
    elif sym == NEG_CONTROL:
        # Negative control: BTCUSDT must exact-match, NOT alias.
        ctrl = {
            "route_class==MARGIN_SPOT_CANDIDATE": r["route_class"] == "MARGIN_SPOT_CANDIDATE",
            "spot.match_type==exact_symbol (not aliased)": r["spot"]["match_type"] == "exact_symbol",
            "asset_tag==CRYPTO (not BSTOCK)": r["asset_tag"] == "CRYPTO",
            "negative_funding_status!=DISABLED_BSTOCK": r["negative_funding_status"] != "DISABLED_BSTOCK",
        }
        for k, v in ctrl.items():
            if not v:
                failures.append(f"{sym} (neg control): {k}")

# Assemble + jsonschema validate (with format checker).
data_time = iso_from_ms(int(FAPI.get("serverTime", 0)))
snap = assemble_snapshot(
    rows,
    generated_at=data_time,
    data_time=data_time,
    source_sample_id=f"live-raw-{HERE.name}",
)
import jsonschema  # noqa: E402

schema_path = ROOT / "schemas" / "api" / "public-market" / "snapshot.schema.json"
schema = json.loads(schema_path.read_text())
validator = jsonschema.Draft202012Validator(
    schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
)
validator.validate(snap)
print()
print(
    "assembled snapshot jsonschema-valid against amended snapshot.schema.json: "
    f"total_rows={snap['summary']['total_rows']}; "
    f"route_counts={snap['summary']['route_counts']}; "
    f"negative_funding_status_counts={snap['summary']['negative_funding_status_counts']}"
)

print()
if failures:
    print(f"RESULT: FAIL ({len(failures)} assertion failure(s))")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print(
    "RESULT: PASS — 15/15 bStocks resolve to MARGIN_SPOT_CANDIDATE via "
    "baseAsset+B+quoteAsset alias against live raw; BTCUSDT negative control "
    "exact-matches (alias does not pollute crypto)."
)
