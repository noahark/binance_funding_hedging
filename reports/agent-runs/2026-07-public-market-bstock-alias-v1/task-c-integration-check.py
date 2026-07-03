#!/usr/bin/env python3
"""Task C integration verification (stage 2026-07-public-market-bstock-alias-v1).

Not product code. Reproducible offline check: load the synthetic bstock-alias-raw
fixture, run the SAME domain pipeline the service uses (filter TRADING eligible
-> build_rows -> assemble_snapshot), jsonschema-validate the result, assert the
bStock alias rows, and dump the assembled snapshot next to this script.

Run:  .venv/bin/python reports/agent-runs/2026-07-public-market-bstock-alias-v1/task-c-integration-check.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from backend.domain.normalize import iso_from_ms  # noqa: E402
from backend.domain.snapshot import assemble_snapshot, build_rows  # noqa: E402

STAGE_DIR = Path(__file__).resolve().parent
RAW_DIR = REPO_ROOT / "backend/tests/fixtures/bstock-alias-raw"
SCHEMA_PATH = REPO_ROOT / "schemas/api/public-market/snapshot.schema.json"
ELIGIBLE = ("PERPETUAL", "TRADIFI_PERPETUAL")
_FUNDING_RE = re.compile(r"fapi-v1-fundingRate-(.+)-limit\d+\.json$")


def load_raw():
    def load(name):
        return json.loads((RAW_DIR / name).read_text())

    funding = {}
    for path in sorted(RAW_DIR.glob("fapi-v1-fundingRate-*-limit*.json")):
        m = _FUNDING_RE.search(path.name)
        if m:
            funding[m.group(1)] = json.loads(path.read_text())
    return {
        "futures": load("fapi-v1-exchangeInfo.json"),
        "premium": load("fapi-v1-premiumIndex.json"),
        "spot": load("api-v3-exchangeInfo.json"),
        "funding": funding,
    }


def main() -> int:
    raw = load_raw()
    schema = json.loads(SCHEMA_PATH.read_text())

    futures_symbols = [
        s for s in raw["futures"]["symbols"]
        if s.get("status") == "TRADING" and s.get("contractType") in ELIGIBLE
    ]
    premium_by_sym = {p["symbol"]: p for p in raw["premium"]}
    spot_by_sym = {s["symbol"]: s for s in raw["spot"]["symbols"]}
    funding_by_sym = dict(raw["funding"])

    rows = build_rows(futures_symbols, premium_by_sym, spot_by_sym, funding_by_sym)
    data_time = iso_from_ms(max(p["time"] for p in raw["premium"]))
    snap = assemble_snapshot(
        rows,
        generated_at="2026-07-03T05:17:38Z",
        data_time=data_time,
        source_sample_id="bstock-alias-synthetic",
    )

    # 1. schema-valid (proves match_type + alias fields satisfy the frozen schema)
    jsonschema.validate(snap, schema)
    print("[PASS] assembled snapshot is schema-valid (match_type included)")

    by_sym = {r["symbol"]: r for r in rows}
    print(f"[INFO] rows={len(rows)} symbols={sorted(by_sym)}")

    # 2. bStock alias (positive rate) -> candidate route, BSTOCK still disables neg
    tsla = by_sym["TSLAUSDT"]
    assert tsla["route_class"] == "MARGIN_SPOT_CANDIDATE", tsla
    assert tsla["asset_tag"] == "BSTOCK", tsla
    assert tsla["positive_funding_enabled"] is True, tsla
    assert tsla["negative_funding_status"] == "DISABLED_BSTOCK", tsla
    assert tsla["spot"]["symbol"] == "TSLABUSDT", tsla
    assert tsla["spot"]["match_type"] == "bstock_b_suffix_alias", tsla
    print("[PASS] TSLAUSDT -> alias TSLABUSDT, MARGIN_SPOT_CANDIDATE, DISABLED_BSTOCK")

    # 3. bStock alias (negative rate) -> candidate route open, neg still DISABLED_BSTOCK
    aapl = by_sym["AAPLUSDT"]
    assert aapl["route_class"] == "MARGIN_SPOT_CANDIDATE", aapl
    assert aapl["negative_funding_status"] == "DISABLED_BSTOCK", aapl
    assert aapl["positive_funding_enabled"] is True, aapl
    assert aapl["spot"]["match_type"] == "bstock_b_suffix_alias", aapl
    print("[PASS] AAPLUSDT (neg rate) -> alias candidate, neg still DISABLED_BSTOCK")

    # 4. normal crypto exact, alias never fires
    btc = by_sym["BTCUSDT"]
    assert btc["route_class"] == "MARGIN_SPOT_CANDIDATE", btc
    assert btc["asset_tag"] == "CRYPTO", btc
    assert btc["spot"]["symbol"] == "BTCUSDT", btc
    assert btc["spot"]["match_type"] == "exact_symbol", btc
    print("[PASS] BTCUSDT -> exact_symbol, alias did not fire")

    # 5. TRADIFI with no spot leg -> PERP_ONLY, match_type null
    nvda = by_sym["NVDAUSDT"]
    assert nvda["route_class"] == "PERP_ONLY_EXCLUDED", nvda
    assert nvda["spot"]["exists"] is False, nvda
    assert nvda["spot"]["match_type"] is None, nvda
    assert nvda["negative_funding_status"] == "DISABLED_PERP_ONLY", nvda
    print("[PASS] NVDAUSDT -> no spot leg, match_type null, PERP_ONLY_EXCLUDED")

    # 6. summary aggregates from rows
    from collections import Counter
    s = snap["summary"]
    assert s["total_rows"] == len(rows), s
    assert dict(Counter(r["route_class"] for r in rows)) == s["route_counts"], s
    assert dict(Counter(r["asset_tag"] for r in rows)) == s["asset_tag_counts"], s
    print("[PASS] summary aggregates from rows")

    # 7. funding history flows through for the alias symbol
    assert len(by_sym["TSLAUSDT"]["funding_history"]) == 2, by_sym["TSLAUSDT"]
    print("[PASS] TSLAUSDT alias row carries funding_history (2 entries)")

    # dump integration sample
    out = STAGE_DIR / "integration-snapshot-bstock-alias.json"
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n")
    print(f"[INFO] dumped integration snapshot -> {out.relative_to(REPO_ROOT)}")

    print("\nTask C integration check: ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
