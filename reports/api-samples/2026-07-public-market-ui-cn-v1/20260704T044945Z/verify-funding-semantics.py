#!/usr/bin/env python3
"""Offline verification: premiumIndex.lastFundingRate is a real-time in-period
estimate, NOT an echo of the last settled funding rate.

Replays ONLY the committed raw files in ./raw/ (no HTTP). Capture time
2026-07-04T04:49:45Z sits mid-period (settlements for these symbols are
00:00/08:00/16:00 UTC), so:

- if lastFundingRate were the last SETTLED rate, it would equal the newest
  /fapi/v1/fundingRate history entry for every symbol;
- observed: it DIFFERS for symbols whose rate is not pinned at the interest
  clamp (ETHUSDT, SOLUSDT), while nextFundingTime points at the upcoming
  settlement. Together with the pairing of lastFundingRate+nextFundingTime in
  one payload, this grounds the amended wording: "real-time estimate for the
  current period, charged at nextFundingTime, drifts until settlement".

Run from this directory: python3 verify-funding-semantics.py
Exit 0 = PASS.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAW = Path(__file__).parent / "raw"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "TSLAUSDT"]
CAPTURE_MS = 1783140585000  # 2026-07-04T04:49:45Z (from the raw response Date header)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%d %H:%M UTC")


def main() -> int:
    premium = {p["symbol"]: p for p in json.load(open(RAW / "fapi-v1-premiumIndex.json"))}
    diverged = []
    failures = []
    for sym in SYMBOLS:
        hist = json.load(open(RAW / f"fapi-v1-fundingRate-{sym}-limit3.json"))
        settled = max(hist, key=lambda e: int(e["fundingTime"]))
        pi = premium[sym]
        last_rate = pi["lastFundingRate"]
        next_ts = int(pi["nextFundingTime"])
        settled_ts = int(settled["fundingTime"])
        # capture must sit strictly inside a period: last settlement < capture < next settlement
        if not (settled_ts <= CAPTURE_MS < next_ts):
            failures.append(f"{sym}: capture not mid-period (settled {iso(settled_ts)}, next {iso(next_ts)})")
        equal = last_rate.rstrip("0") == settled["fundingRate"].rstrip("0")
        if not equal:
            diverged.append(sym)
        print(
            f"{sym:9s} lastFundingRate={last_rate:>13s} | settled={settled['fundingRate']:>13s}"
            f" @ {iso(settled_ts)} | next={iso(next_ts)} | equal={equal}"
        )
    if not diverged:
        failures.append("no symbol diverged from settled history; evidence inconclusive")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print(f"PASS: {len(diverged)}/{len(SYMBOLS)} symbols diverge mid-period ({', '.join(diverged)});"
          " lastFundingRate is NOT a settled-history echo -> in-period real-time estimate,"
          " charged at nextFundingTime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
