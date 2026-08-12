#!/usr/bin/env python3
"""CCXT public bookTicker reconnaissance proof (smooth-open V1 P0).

Read-only, no credentials, no private / signed / order / account / position
endpoints. Two INDEPENDENT asyncio watchers (spot ``binance`` + USDⓈ-M
``binanceusdm``) consume ``watchBidsAsks`` for one ordinary pair, capture the
normalized bid/ask/bidVolume/askVolume, exchange timestamp and local receive
time, inspect ``market.contractSize``, demonstrate that cancelling one watcher
does not stop the other, and document ``close()``/exception behavior. One
secondary exchange is inspected only far enough to show what later per-exchange
proof would require.

Bounded: explicit overall timeout (``OVERALL_TIMEOUT``) and finite samples
(``SAMPLES_PER_SIDE`` / ``POST_CANCEL_SAMPLES``); every client is closed in a
``finally``. No product imports, no daemon, no dependency-file edit, no order
API call. Intended to run inside an ISOLATED temporary venv outside the repo.

Command:
    python reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py
"""
from __future__ import annotations

import asyncio
import importlib.metadata as md
import json
import sys
import time

import ccxt
import ccxt.pro as cpro

SPOT_SYMBOL = "BTC/USDT"
PERP_SYMBOL = "BTC/USDT"  # binanceusdm normalizes this to "BTC/USDT:USDT"
SAMPLES_PER_SIDE = 5
POST_CANCEL_SECONDS = 6
WATCH_TIMEOUT = 40
OVERALL_TIMEOUT = 180


def banner(title: str) -> None:
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def line(k: str, *parts) -> None:
    v = " ".join(str(p) for p in parts) if parts else ""
    print(f"  {k}: {v}")


async def section_meta() -> None:
    banner("A. RUNTIME + PACKAGE METADATA")
    line("python", sys.version.split()[0])
    line("ccxt.__version__", getattr(ccxt, "__version__", "?"))
    line("ccxt.__license__ attr", getattr(ccxt, "__license__", "?"))
    try:
        meta = md.metadata("ccxt")
        line("PyPI License", meta.get("License"))
        line("PyPI Home-page", meta.get("Home-page"))
        line("PyPI Author", meta.get("Author"))
        line("PyPI Requires-Python", meta.get("Requires-Python"))
    except Exception as e:  # noqa: BLE001
        line("PyPI metadata", f"unavailable ({type(e).__name__})")
    deps = {}
    for pkg in ("ccxt", "aiohttp", "requests"):
        try:
            deps[pkg] = md.version(pkg)
        except Exception:  # noqa: BLE001
            deps[pkg] = "n/a"
    line("installed deps", deps)
    line("ccxt.pro importable", "yes")
    sp = cpro.binance()
    pu = cpro.binanceusdm()
    line("binance.has['watchBidsAsks']", sp.has.get("watchBidsAsks"))
    line("binanceusdm.has['watchBidsAsks']", pu.has.get("watchBidsAsks"))
    line("binance.watch_bids_asks attr", hasattr(sp, "watch_bids_asks"))
    line("binanceusdm.watch_bids_asks attr", hasattr(pu, "watch_bids_asks"))
    await sp.close()
    await pu.close()
    line("doc links",
         "https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual ; "
         "https://github.com/ccxt/ccxt/blob/master/python/ccxt/pro/binance.py")


async def _one_sample(exchange, symbol):
    r = await asyncio.wait_for(
        exchange.watch_bids_asks([symbol]), timeout=WATCH_TIMEOUT
    )
    mono = time.monotonic()
    wall_ms = int(time.time() * 1000)
    item = None
    key = symbol
    if isinstance(r, dict):
        if symbol in r:
            item = r[symbol]
        elif len(r) == 1:
            key = next(iter(r.keys()))
            item = next(iter(r.values()))
    info = (item or {}).get("info") or {}
    return {
        "key": key,
        "bid": item.get("bid"),
        "ask": item.get("ask"),
        "bidVolume": item.get("bidVolume"),
        "askVolume": item.get("askVolume"),
        "ts_ms": item.get("timestamp"),
        "datetime": item.get("datetime"),
        "local_wall_ms": wall_ms,
        "local_mono": round(mono, 3),
        "raw_B": info.get("B"),
        "raw_A": info.get("A"),
        "raw_E": info.get("E"),
        "raw_T": info.get("T"),
        "raw_u": info.get("u"),
        "raw_keys": sorted(info.keys()),
    }


def _print_sample(tag: str, s: dict) -> None:
    from decimal import Decimal as D, InvalidOperation

    def _dec(x):
        try:
            return D(str(x))
        except (InvalidOperation, ValueError, TypeError):
            return None

    nb, na = _dec(s["bidVolume"]), _dec(s["askVolume"])
    rb, ra = _dec(s["raw_B"]), _dec(s["raw_A"])
    numeric_eq = (nb is not None and rb is not None and nb == rb
                  and na is not None and ra is not None and na == ra)
    str_eq = (str(s["bidVolume"]) == str(s["raw_B"])
              and str(s["askVolume"]) == str(s["raw_A"]))
    print(f"    [{tag}] key={s['key']} bid={s['bid']} (type={type(s['bid']).__name__}) "
          f"ask={s['ask']}")
    print(f"      bidVol={s['bidVolume']} (type={type(s['bidVolume']).__name__}) "
          f"askVol={s['askVolume']} (type={type(s['askVolume']).__name__})")
    print(f"      raw B={s['raw_B']} (str) A={s['raw_A']} (str) | "
          f"numeric_eq={numeric_eq} str_eq={str_eq}")
    print(f"      ts_ms={s['ts_ms']} datetime={s['datetime']} "
          f"raw_E={s['raw_E']} raw_T={s['raw_T']} local_wall_ms={s['local_wall_ms']}")
    print(f"      raw_keys={s['raw_keys']}")


async def section_two_watchers():
    banner("B. TWO INDEPENDENT WATCHERS (spot binance + USDⓈ-M binanceusdm)")
    spot = cpro.binance()
    perp = cpro.binanceusdm()
    spot_samples = []
    perp_samples = []
    try:
        async def collect(exchange, symbol, sink, n):
            for _ in range(n):
                sink.append(await _one_sample(exchange, symbol))

        await asyncio.gather(
            collect(spot, SPOT_SYMBOL, spot_samples, SAMPLES_PER_SIDE),
            collect(perp, PERP_SYMBOL, perp_samples, SAMPLES_PER_SIDE),
        )
        line("spot samples", len(spot_samples))
        for s in spot_samples:
            _print_sample("spot", s)
        line("perp samples", len(perp_samples))
        for s in perp_samples:
            _print_sample("perp", s)
        sp = spot_samples[-1]
        pe = perp_samples[-1]
        sp_has_exch_ts = sp["raw_E"] is not None or sp["raw_T"] is not None
        line("spot raw has E/T (exchange ts)", sp_has_exch_ts)
        if not sp_has_exch_ts and sp["ts_ms"] is not None:
            line("spot CCXT timestamp source",
                 "LOCAL receive (raw has no E/T; CCXT ts %d vs local_wall %d, delta %d ms)"
                 % (sp["ts_ms"], sp["local_wall_ms"], sp["ts_ms"] - sp["local_wall_ms"]))
        line("perp raw has E/T (exchange ts)",
             pe["raw_E"] is not None or pe["raw_T"] is not None)
    finally:
        await spot.close()
        await perp.close()
    return spot_samples, perp_samples


async def section_contract_size():
    banner("C. CONTRACT SIZE + MARKET METADATA")
    perp = cpro.binanceusdm()
    spot = cpro.binance()
    try:
        await perp.load_markets()
        await spot.load_markets()
        pm = perp.market(PERP_SYMBOL)
        sm = spot.market(SPOT_SYMBOL)
        line("perp market symbol", pm.get("symbol"))
        line("perp market type", pm.get("type"))
        line("perp linear", pm.get("linear"), "inverse", pm.get("inverse"))
        line("perp settle", pm.get("settle"))
        line("perp contractSize", pm.get("contractSize"))
        line("perp precision.amount", (pm.get("precision") or {}).get("amount"))
        line("perp precision.price", (pm.get("precision") or {}).get("price"))
        line("spot market symbol", sm.get("symbol"))
        line("spot market type", sm.get("type"))
        line("spot contractSize (expected absent on spot)", sm.get("contractSize"))
        for cand in ("1000PEPE/USDT:USDT", "1000PEPE/USDT", "PEPE/USDT:USDT"):
            try:
                m = perp.market(cand)
                line(f"secondary perp {cand} contractSize", m.get("contractSize"),
                     "linear", m.get("linear"))
                break
            except Exception as e:  # noqa: BLE001
                line(f"secondary perp {cand}", f"not resolvable ({type(e).__name__})")
        cs = pm.get("contractSize")
        if cs is None or cs == 1:
            line("UNIT RULE (ordinary BTC/USDT perp)",
                 "contractSize is %r -> 1 contract == 1 base unit; bookTicker qty "
                 "is already in base asset == q_common unit" % (cs,))
        else:
            line("UNIT RULE (ordinary BTC/USDT perp)",
                 "contractSize=%r is NOT 1 -> qty is in CONTRACTS; must multiply by "
                 "contractSize to compare with q_common" % (cs,))
    finally:
        await perp.close()
        await spot.close()


async def _drain(exchange, symbol, sink):
    try:
        while True:
            r = await asyncio.wait_for(
                exchange.watch_bids_asks([symbol]), timeout=WATCH_TIMEOUT
            )
            sink.append((round(time.monotonic(), 3),
                         next(iter(r.values())).get("bid") if isinstance(r, dict) and r else None))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        sink.append(("ERR", f"{type(e).__name__}: {str(e)[:120]}"))


async def section_cancel_independence():
    banner("D. ONE-WATCHER CANCEL DOES NOT STOP THE OTHER")
    spot = cpro.binance()
    perp = cpro.binanceusdm()
    spot_sink: list = []
    perp_sink: list = []
    st = asyncio.create_task(_drain(spot, SPOT_SYMBOL, spot_sink))
    pt = asyncio.create_task(_drain(perp, PERP_SYMBOL, perp_sink))
    try:
        await asyncio.sleep(POST_CANCEL_SECONDS)
        spot_before = len(spot_sink)
        perp_before = len(perp_sink)
        line("before cancel: spot updates", spot_before, "perp updates", perp_before)
        st.cancel()
        try:
            await st
        except asyncio.CancelledError:
            pass
        line("spot watcher cancelled", "yes")
        await asyncio.sleep(POST_CANCEL_SECONDS)
        line("after cancel: spot updates", len(spot_sink),
             "perp updates", len(perp_sink))
        line("perp kept updating after spot cancel",
             len(perp_sink) > perp_before)
        pt.cancel()
        try:
            await pt
        except asyncio.CancelledError:
            pass
    finally:
        await spot.close()
        await perp.close()


async def section_close_and_secondary():
    banner("E. close() + LEFTOVER-TASK CHECK")
    ex = cpro.binanceusdm()
    try:
        await ex.load_markets()
        await asyncio.wait_for(ex.watch_bids_asks([PERP_SYMBOL]), timeout=WATCH_TIMEOUT)
        line("watch succeeded before close", "yes")
    finally:
        await ex.close()
        line("binanceusdm.close() returned", "yes")
    loop = asyncio.get_event_loop()
    cur = asyncio.current_task()
    alive = [t for t in asyncio.all_tasks(loop) if not t.done()]
    own = [t.get_name() for t in alive if t is cur]
    others = [t.get_name() for t in alive if t is not cur]
    line("asyncio tasks still alive after close", len(alive))
    line("  caller/current task", own or "none")
    line("  other tasks", others or "none")
    line("note", "in-process self-check cannot cleanly isolate CCXT-internal watcher "
                 "tasks from the caller chain; close() returned normally, and proving "
                 "zero internal survivors needs source isolation, not this check")

    banner("F. SECONDARY EXCHANGE (shallow: capability + market metadata only)")
    okx = cpro.okx()
    try:
        line("okx.has['watchBidsAsks']", okx.has.get("watchBidsAsks"))
        line("okx.has['watchOrderBook']", okx.has.get("watchOrderBook"))
        try:
            await asyncio.wait_for(okx.load_markets(), timeout=30)
            try:
                om = okx.market("BTC/USDT:USDT")
                line("okx BTC/USDT:USDT type", om.get("type"),
                     "contractSize", om.get("contractSize"),
                     "linear", om.get("linear"))
                line("okx precision.amount", (om.get("precision") or {}).get("amount"))
                line("okx requires its own per-exchange proof (symbol set, "
                     "contract metadata, channel, reconnect)", "yes")
            except Exception as e:  # noqa: BLE001
                line("okx BTC/USDT:USDT market", f"unresolved ({type(e).__name__})")
        except Exception as e:  # noqa: BLE001
            line("okx load_markets", f"failed ({type(e).__name__}); has-flag only")
    finally:
        try:
            await okx.close()
        except Exception as e:  # noqa: BLE001
            line("okx close", f"{type(e).__name__}")


async def main() -> None:
    print("CCXT bookTicker reconnaissance proof — public, read-only, no creds")
    print("utc_start: %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    for name, fn in (
        ("A meta", section_meta),
        ("B two_watchers", section_two_watchers),
        ("C contract_size", section_contract_size),
        ("D cancel_independence", section_cancel_independence),
        ("E+F close_and_secondary", section_close_and_secondary),
    ):
        try:
            await fn()
        except Exception as e:  # noqa: BLE001
            print("\n[SECTION %s FAILED: %s: %s]"
                  % (name, type(e).__name__, str(e)[:200]))
    banner("DONE")
    print("utc_end: %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=OVERALL_TIMEOUT))
    except asyncio.TimeoutError:
        print("\n[OVERALL TIMEOUT %ds reached — proof stopped]" % OVERALL_TIMEOUT)
        sys.exit(130)
