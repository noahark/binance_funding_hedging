#!/usr/bin/env python3
"""
check-spot-symbol-map.py
------------------------
维护 `backend/domain/normalize.py` 的 `SPOT_SYMBOL_MAP`——「合约 symbol -> 现货
symbol」的显式例外表（只列名字不同的标的；同名走 exact，不进表）。

与 `check_symbol_mismatch.py` 的分工：那个是人工探索用的分析报告；这个是可挂到
CI/定期任务的校验器，退出码有明确语义，且能直接产出可粘贴的表字面量。

用法：
    python scripts/check-spot-symbol-map.py --verify     # 校验现表，退出码 0/1
    python scripts/check-spot-symbol-map.py --emit       # 输出新表字面量（粘回 normalize.py）
    python scripts/check-spot-symbol-map.py --verify --spot F.json --futures F.json   # 用本地样本

--verify 报三类问题：
  STALE    表内映射的现货对已不可交易（下架/停牌）——该标的会静默失去现货腿
  MISSING  新上架的 bStock / 乘数合约有现货腿但未收录——该标的无法对冲
  SUSPECT  非 TRADIFI 合约存在 base+"B" 现货对——可能是撞车（如 BUSDT vs BB），
           **绝不自动收录**，必须人工确认后再决定是否加表

设计依据见 docs/planning/unified-symbol-resolver-2026-08-07.review-opus5.md：
解析器不做字符串猜测，因为 "B"+"B" == "BB" 这类撞车在规则层面无法区分。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

SPOT_URL = "https://api.binance.com/api/v3/exchangeInfo?permissions=SPOT"
FUT_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
QUOTE = "USDT"
# 乘数前缀按长度降序试，避免 "1000000" 被 "1000" 抢先剥错（旧规则硬剥 4 字符，
# 把 1000000MOG 剥成 000MOG）。
MULTIPLIER_PREFIXES = ("1000000", "100000", "10000", "1000")


def _load(url: str, path: str | None) -> dict:
    if path:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    req = urllib.request.Request(
        url, headers={"User-Agent": "spot-symbol-map-checker/1.0",
                      "Accept-Encoding": "gzip"},
    )
    import gzip
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def build(spot_doc: dict, fut_doc: dict) -> tuple[list, list, list]:
    """Returns (bstock_rows, multiplier_rows, suspect_rows) from exchange truth."""
    spot_by_sym = {s["symbol"]: s for s in spot_doc.get("symbols", [])}

    def tradable(sym: str) -> bool:
        rec = spot_by_sym.get(sym)
        return rec is not None and rec.get("status") == "TRADING"

    perps = [
        s for s in fut_doc.get("symbols", [])
        if s.get("quoteAsset") == QUOTE and s.get("status") == "TRADING"
    ]
    bstock, multiplier, suspect = [], [], []
    for sym in sorted(perps, key=lambda x: x["symbol"]):
        contract, base = sym["symbol"], sym["baseAsset"]
        if tradable(base + QUOTE):
            continue  # 同名现货：走 exact，不进表
        b_alias = base + "B" + QUOTE
        if tradable(b_alias):
            row = (contract, b_alias)
            if sym.get("contractType") == "TRADIFI_PERPETUAL":
                bstock.append(row)
            else:
                suspect.append((contract, b_alias, base,
                                spot_by_sym[b_alias].get("baseAsset")))
            continue
        for prefix in MULTIPLIER_PREFIXES:
            if base.startswith(prefix) and tradable(base[len(prefix):] + QUOTE):
                multiplier.append((contract, base[len(prefix):] + QUOTE))
                break
    return bstock, multiplier, suspect


def emit(bstock: list, multiplier: list) -> str:
    out = ["SPOT_SYMBOL_MAP = {",
           "    # --- bStock：TRADIFI_PERPETUAL，现货/杠杆对带 B 后缀 ---"]
    for contract, spot in bstock:
        out.append('    %-22s (%-22s SPOT_MATCH_BSTOCK),'
                   % ('"%s":' % contract, '"%s",' % spot))
    out.append("    # --- 乘数前缀：合约按 N 倍计价，现货是原币 ---")
    for contract, spot in multiplier:
        out.append('    %-22s (%-22s SPOT_MATCH_MULTIPLIER),'
                   % ('"%s":' % contract, '"%s",' % spot))
    out.append("}")
    return "\n".join(out)


def verify(bstock: list, multiplier: list, suspect: list, spot_doc: dict) -> int:
    sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])
    from backend.domain.normalize import SPOT_SYMBOL_DENY, SPOT_SYMBOL_MAP

    spot_by_sym = {s["symbol"]: s for s in spot_doc.get("symbols", [])}
    expected = {c: s for c, s in bstock} | {c: s for c, s in multiplier}
    problems = 0

    for contract, (mapped, _mt) in sorted(SPOT_SYMBOL_MAP.items()):
        rec = spot_by_sym.get(mapped)
        if rec is None or rec.get("status") != "TRADING":
            status = rec.get("status") if rec else "不存在"
            print("STALE    %-18s -> %-18s 现货已不可交易 (%s)"
                  % (contract, mapped, status))
            problems += 1

    for contract, mapped in sorted(expected.items()):
        if contract not in SPOT_SYMBOL_MAP:
            print("MISSING  %-18s -> %-18s 有现货腿但未收录，该标的当前无法对冲"
                  % (contract, mapped))
            problems += 1

    denied = 0
    for contract, alias, base, alias_base in suspect:
        if contract in SPOT_SYMBOL_DENY:
            denied += 1
            continue  # 已人工确认不可用作对冲腿，不再反复报
        print("SUSPECT  %-18s -?-> %-18s 合约base=%s 现货base=%s —— 人工确认后再决定是否加表"
              % (contract, alias, base, alias_base))
        problems += 1

    print()
    print("表内条目 %d 条；交易所侧应收录 %d 条；已确认拒绝 %d 条；问题 %d 项"
          % (len(SPOT_SYMBOL_MAP), len(expected), denied, problems))
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="校验现表（默认动作）")
    ap.add_argument("--emit", action="store_true", help="输出新表字面量")
    ap.add_argument("--spot", help="本地现货 exchangeInfo JSON")
    ap.add_argument("--futures", help="本地合约 exchangeInfo JSON")
    args = ap.parse_args()

    spot_doc = _load(SPOT_URL, args.spot)
    fut_doc = _load(FUT_URL, args.futures)
    bstock, multiplier, suspect = build(spot_doc, fut_doc)

    if args.emit:
        print(emit(bstock, multiplier))
        return 0
    return verify(bstock, multiplier, suspect, spot_doc)


if __name__ == "__main__":
    sys.exit(main())
