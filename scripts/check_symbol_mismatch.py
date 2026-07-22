#!/usr/bin/env python3
"""
check_symbol_mismatch.py
------------------------
从币安公共 API 拉取现货和永续合约的交易对列表，
找出所有需要"特殊匹配"的情况：

1. 合约带 1000/10000/100000 前缀，现货不带（或反之）
2. bStock (TRADIFI_PERPETUAL) 合约对应现货带 B 后缀（如 TSLAUSDT -> TSLABUSDT）
3. 合约存在但现货完全不存在（PERP_ONLY）
4. 其他命名不一致的情况

用法：
    python scripts/check_symbol_mismatch.py
    python scripts/check_symbol_mismatch.py --quote USDT   # 只看 USDT 计价
    python scripts/check_symbol_mismatch.py --json         # 输出 JSON
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

FUTURES_API = "https://fapi.binance.com"
SPOT_API = "https://api.binance.com"


# ─────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────

def _get(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "symbol-mismatch-checker/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─────────────────────────────────────────────
# Numeric-prefix helpers
# ─────────────────────────────────────────────

# 合约名字可能带的数字倍率前缀（币安惯例）
_PREFIX_RE = re.compile(r"^(1000000|100000|10000|1000)(.+)$")

def strip_numeric_prefix(symbol: str) -> Tuple[Optional[str], str]:
    """返回 (stripped_prefix, rest)。若无前缀则 prefix=None。"""
    m = _PREFIX_RE.match(symbol)
    if m:
        return m.group(1), m.group(2)
    return None, symbol


# ─────────────────────────────────────────────
# Main analysis
# ─────────────────────────────────────────────

def main(args: argparse.Namespace) -> None:
    print("📡 正在拉取合约 exchangeInfo …")
    futures_ei = _get(f"{FUTURES_API}/fapi/v1/exchangeInfo")
    print("📡 正在拉取现货 exchangeInfo …")
    spot_ei = _get(f"{SPOT_API}/api/v3/exchangeInfo")

    # ── 合约：只保留 PERPETUAL 和 TRADIFI_PERPETUAL
    futures_syms: List[dict] = [
        s for s in futures_ei["symbols"]
        if s.get("contractType") in {"PERPETUAL", "TRADIFI_PERPETUAL"}
        and s.get("status") == "TRADING"
    ]

    # ── 现货：只保留 TRADING 状态
    spot_syms_all: List[dict] = [
        s for s in spot_ei["symbols"]
        if s.get("status") == "TRADING"
    ]

    quote_filter: Optional[str] = args.quote.upper() if args.quote else None
    if quote_filter:
        futures_syms = [s for s in futures_syms if s.get("quoteAsset") == quote_filter]
        spot_syms_all = [s for s in spot_syms_all if s.get("quoteAsset") == quote_filter]

    # 现货 symbol -> 对象
    spot_by_sym: Dict[str, dict] = {s["symbol"]: s for s in spot_syms_all}
    # 现货 baseAsset 集合（用于反查）
    spot_base_by_quote: Dict[str, Set[str]] = defaultdict(set)
    for s in spot_syms_all:
        spot_base_by_quote[s["quoteAsset"]].add(s["baseAsset"])

    # ─────────────────────────────────────────
    # 分类桶
    # ─────────────────────────────────────────
    exact_match: List[dict] = []          # 完全一致（symbol 相同）
    prefix_match: List[dict] = []         # 合约带数字前缀，去掉后能匹配现货
    bstock_match: List[dict] = []         # bStock: baseAsset+B+quote 在现货
    perp_only: List[dict] = []            # 合约有，现货完全没有
    spot_only_base_exists: List[dict] = []  # 现货有 base，但 symbol 格式不同

    for f in futures_syms:
        fsym   = f["symbol"]
        fbase  = f["baseAsset"]
        fquote = f["quoteAsset"]
        ctype  = f.get("contractType", "")

        # 1) exact match
        if fsym in spot_by_sym:
            exact_match.append({
                "futures": fsym,
                "spot": fsym,
                "type": "exact",
                "contract_type": ctype,
            })
            continue

        # 2) bStock alias  (TRADIFI_PERPETUAL: base+B+quote)
        if ctype == "TRADIFI_PERPETUAL":
            alias = fbase + "B" + fquote
            if alias in spot_by_sym:
                bstock_match.append({
                    "futures": fsym,
                    "spot": alias,
                    "type": "bstock_B_suffix",
                    "contract_type": ctype,
                })
                continue

        # 3) numeric prefix  (e.g. 1000SATS -> SATS)
        prefix, rest = strip_numeric_prefix(fbase)
        if prefix:
            # 去掉前缀后对应的现货 symbol
            candidate = rest + fquote
            if candidate in spot_by_sym:
                prefix_match.append({
                    "futures": fsym,
                    "futures_base": fbase,
                    "spot": candidate,
                    "spot_base": rest,
                    "prefix": prefix,
                    "quote": fquote,
                    "type": f"numeric_prefix_{prefix}",
                    "contract_type": ctype,
                })
                continue
            # 前缀去掉后现货不存在，也记为 perp_only（带前缀说明）
            perp_only.append({
                "futures": fsym,
                "futures_base": fbase,
                "note": f"numeric_prefix_{prefix}_no_spot_match",
                "contract_type": ctype,
            })
            continue

        # 4) 没有数字前缀但现货不存在
        # 检查现货里有没有同 base 的其他 quote（说明 base 存在，只是计价不同）
        spot_found_other_quote = any(
            fbase in bases
            for q, bases in spot_base_by_quote.items()
            if q != fquote
        )
        perp_only.append({
            "futures": fsym,
            "futures_base": fbase,
            "note": "spot_base_exists_diff_quote" if spot_found_other_quote else "no_spot_at_all",
            "contract_type": ctype,
        })

    # ─────────────────────────────────────────
    # 打印报告
    # ─────────────────────────────────────────
    if args.json:
        output = {
            "exact_match_count": len(exact_match),
            "bstock_match": bstock_match,
            "prefix_match": prefix_match,
            "perp_only": perp_only,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # 人类可读报告
    print(f"\n{'='*70}")
    quote_label = f"（计价={quote_filter}）" if quote_filter else "（全部计价）"
    print(f"  币安现货 vs 合约 交易对匹配分析 {quote_label}")
    print(f"{'='*70}")
    print(f"  合约永续总数        : {len(futures_syms)}")
    print(f"  现货交易中总数      : {len(spot_syms_all)}")
    print(f"  精确匹配（symbol相同）: {len(exact_match)}")
    print(f"  bStock B后缀匹配    : {len(bstock_match)}")
    print(f"  数字前缀匹配（需转换）: {len(prefix_match)}")
    print(f"  合约有现货无（PERP_ONLY）: {len(perp_only)}")

    # ── 数字前缀匹配
    if prefix_match:
        print(f"\n{'─'*70}")
        print("  【数字前缀匹配】合约有前缀，现货无前缀（匹配规则：去掉前缀）")
        print(f"{'─'*70}")
        by_prefix = defaultdict(list)
        for r in prefix_match:
            by_prefix[r["prefix"]].append(r)
        for pfx, items in sorted(by_prefix.items()):
            print(f"\n  前缀 {pfx}x （共 {len(items)} 个）:")
            for r in sorted(items, key=lambda x: x["futures"]):
                print(f"    合约: {r['futures']:30s}  ->  现货: {r['spot']}")

    # ── bStock 匹配
    if bstock_match:
        print(f"\n{'─'*70}")
        print("  【bStock 匹配】合约 baseAsset，现货 baseAsset+B+quote")
        print(f"{'─'*70}")
        for r in sorted(bstock_match, key=lambda x: x["futures"]):
            print(f"  合约: {r['futures']:30s}  ->  现货: {r['spot']}")

    # ── 合约有现货无
    if perp_only:
        print(f"\n{'─'*70}")
        print("  【PERP_ONLY】合约存在但现货找不到对应交易对")
        print(f"{'─'*70}")
        by_note = defaultdict(list)
        for r in perp_only:
            by_note[r["note"]].append(r)
        for note, items in sorted(by_note.items()):
            print(f"\n  原因: {note} （共 {len(items)} 个）:")
            for r in sorted(items, key=lambda x: x["futures"]):
                print(f"    {r['futures']}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查币安现货与合约交易对命名不匹配")
    parser.add_argument("--quote", default="", help="只分析指定计价货币，如 USDT")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    main(parser.parse_args())
