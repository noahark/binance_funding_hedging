"""Pure normalization helpers.

No I/O. Decimal fields are passed through as strings straight from the raw
JSON (Binance already returns them as strings); no float touches any
price/rate/quantity path.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def filter_of(symbol_obj: Optional[dict], filter_type: str, key: str) -> Optional[str]:
    """Return the value of ``key`` under filterType ``filter_type``, or None.

    Futures symbols use ``MIN_NOTIONAL``/``notional``; spot symbols use the new
    ``NOTIONAL``/``minNotional`` filter. Observed and frozen in the contract
    stage.
    """
    if not symbol_obj:
        return None
    for f in symbol_obj.get("filters", []):
        if f.get("filterType") == filter_type:
            return f.get(key)
    return None


# Real-metal futures baseAssets (stage 2026-07-ui-filter-balance-metal-v1).
# Evidence: reports/api-samples/2026-07-ui-filter-balance-metal-v1/
# 20260708T0928Z/normalized/metal-symbol-summary.json — all five listed as
# contractType=TRADIFI_PERPETUAL on Binance public /fapi/v1/exchangeInfo. A metal
# TRADIFI_PERPETUAL is METAL, not BSTOCK, so the base_asset check runs BEFORE the
# TRADIFI_PERPETUAL -> BSTOCK mapping.
REAL_METAL_BASE_ASSETS = {"XAU", "XAG", "COPPER", "XPT", "XPD"}


def asset_tag_for(contract_type: str, base_asset: str = "") -> tuple:
    """Map contractType/baseAsset -> (asset_tag, asset_tag_source, asset_tag_confidence).

    Order (first match wins):
    1. ``base_asset`` in :data:`REAL_METAL_BASE_ASSETS` -> ``METAL`` (checked
       before TRADIFI so a metal TRADIFI_PERPETUAL is never tagged BSTOCK).
    2. ``contractType == TRADIFI_PERPETUAL`` -> ``BSTOCK``.
    3. ``contractType == PERPETUAL`` -> ``CRYPTO``.
    4. otherwise -> ``UNKNOWN``.

    ``base_asset`` defaults to ``""`` so existing single-argument callers and
    tests keep working; pass the symbol's ``baseAsset`` to enable METAL detection.
    """
    if str(base_asset).upper() in REAL_METAL_BASE_ASSETS:
        return ("METAL", "base_asset_metal_symbol", "HIGH")
    if contract_type == "TRADIFI_PERPETUAL":
        return ("BSTOCK", "futures_contractType_tradifi_perpetual", "HIGH")
    if contract_type == "PERPETUAL":
        return ("CRYPTO", "futures_contractType_perpetual", "HIGH")
    return ("UNKNOWN", "rule_default_unmapped_contractType", "LOW")


def iso_from_ms(ms_epoch: int) -> str:
    """Render a millisecond epoch as a second-precision UTC ISO string.

    Uses integer division so no float touches the time path.
    """
    seconds = int(ms_epoch) // 1000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _tradable_spot(spot_by_sym: dict, symbol: str) -> Optional[dict]:
    """Return the spot record for ``symbol`` only when it is currently tradable.

    A record resolves only when its ``status == "TRADING"``. Absent, a missing
    ``status``, ``BREAK``, ``HALT``, and every other value fail closed (return
    None): Binance keeps non-trading symbols in ``exchangeInfo`` (frozen evidence
    under ``reports/api-samples/2026-07-tradable-spot-leg-v1/20260718T042314Z/`` —
    AERGOUSDT/XMRUSDT/LITUSDT sit there with ``status="BREAK"`` and a zero
    bookTicker while their perpetuals quote normally), but such a record is not a
    usable spot leg.
    """
    spot = spot_by_sym.get(symbol)
    if spot is not None and spot.get("status") == "TRADING":
        return spot
    return None


SPOT_MATCH_EXACT = "exact_symbol"
SPOT_MATCH_BSTOCK = "bstock_b_suffix_alias"
SPOT_MATCH_MULTIPLIER = "multiplier_strip_alias"

# 本表与 resolve_spot_identity 只处理 USDT 计价（全项目唯一计价资产）。
# 与 hedge_open_tasks.domain.QUOTE_ASSET 同值，本地定义以免 domain 层反向依赖上层。
_QUOTE_ASSET = "USDT"

# 合约 symbol -> (现货 symbol, match_type) 的显式例外表（2026-08-07）。
#
# 只列「合约名 != 现货名」的标的；名字相同的走 exact，不进表。查不到就是查不到——
# 解析器不再用字符串规则去猜，因为猜会撞车：合约 BUSDT 的 baseAsset 是 B，
# base+"B"+quote 恰好等于 BBUSDT，而那是另一个币 BB(BounceBit) 的现货对。规则
# 层面无法区分（"B"+"B" == "BB"），只有显式表能表达「B 没有现货腿」。
#
# 表由 `scripts/check-spot-symbol-map.py --emit` 从 exchangeInfo 生成，勿手工编辑；
# 同一脚本的 `--verify` 校验表与交易所现状是否一致，并列出应补录的新标的。
# 未列入 = 无现货腿 = 该标的不可对冲（fail-closed，安全的失败方向）。

# 已人工确认「形似的现货对属于别的币，不可用作对冲腿」的合约。仅供校验脚本消费，
# 使其不再把这些反复报成待确认项；解析器本身不需要它（表里没有就是没有）。
SPOT_SYMBOL_DENY = {
    "BUSDT": "BBUSDT 是 BB(BounceBit) 的现货对，与合约 B 无关（2026-08-07 人工确认）",
}

# Hyperliquid 同名撞名显式拒绝表（stage 2026-08-23-hyperliquid-funding-compare-v1
# 设计 §3）。键是完整 HL key（含 dex 前缀）。类别校验（main 只配 PERPETUAL、xyz 只配
# TRADIFI_PERPETUAL）已自动拦截跨类别撞名；本表是已人工确认案例的显式回归防线——
# 同类别同名撞名类别校验挡不住，仍需人工发现后收录（设计 §8 rev3 表述收窄）。
HL_SYMBOL_DENY = {
    "xyz:BB": "币安 BB 是 BounceBit（加密），与黑莓无关",
    "xyz:QNT": "币安 QNT 是 Quant（加密），xyz:QNT 是股票",
}
SPOT_SYMBOL_MAP = {
    # --- bStock：TRADIFI_PERPETUAL，现货/杠杆对带 B 后缀 ---
    "AAOIUSDT":            ("AAOIBUSDT",           SPOT_MATCH_BSTOCK),
    "AAPLUSDT":            ("AAPLBUSDT",           SPOT_MATCH_BSTOCK),
    "ALABUSDT":            ("ALABBUSDT",           SPOT_MATCH_BSTOCK),
    "AMATUSDT":            ("AMATBUSDT",           SPOT_MATCH_BSTOCK),
    "AMDUSDT":             ("AMDBUSDT",            SPOT_MATCH_BSTOCK),
    "AMZNUSDT":            ("AMZNBUSDT",           SPOT_MATCH_BSTOCK),
    "ARMUSDT":             ("ARMBUSDT",            SPOT_MATCH_BSTOCK),
    "ASMLUSDT":            ("ASMLBUSDT",           SPOT_MATCH_BSTOCK),
    "ASTSUSDT":            ("ASTSBUSDT",           SPOT_MATCH_BSTOCK),
    "AVGOUSDT":            ("AVGOBUSDT",           SPOT_MATCH_BSTOCK),
    "AXTIUSDT":            ("AXTIBUSDT",           SPOT_MATCH_BSTOCK),
    "BABAUSDT":            ("BABABUSDT",           SPOT_MATCH_BSTOCK),
    "BEUSDT":              ("BEBUSDT",             SPOT_MATCH_BSTOCK),
    "BMNRUSDT":            ("BMNRBUSDT",           SPOT_MATCH_BSTOCK),
    "CBRSUSDT":            ("CBRSBUSDT",           SPOT_MATCH_BSTOCK),
    "COHRUSDT":            ("COHRBUSDT",           SPOT_MATCH_BSTOCK),
    "COINUSDT":            ("COINBUSDT",           SPOT_MATCH_BSTOCK),
    "CRCLUSDT":            ("CRCLBUSDT",           SPOT_MATCH_BSTOCK),
    "CRDOUSDT":            ("CRDOBUSDT",           SPOT_MATCH_BSTOCK),
    "CRWVUSDT":            ("CRWVBUSDT",           SPOT_MATCH_BSTOCK),
    "DELLUSDT":            ("DELLBUSDT",           SPOT_MATCH_BSTOCK),
    "DRAMUSDT":            ("DRAMBUSDT",           SPOT_MATCH_BSTOCK),
    "EWYUSDT":             ("EWYBUSDT",            SPOT_MATCH_BSTOCK),
    "FLNCUSDT":            ("FLNCBUSDT",           SPOT_MATCH_BSTOCK),
    "GLWUSDT":             ("GLWBUSDT",            SPOT_MATCH_BSTOCK),
    "GOOGLUSDT":           ("GOOGLBUSDT",          SPOT_MATCH_BSTOCK),
    "GSUSDT":              ("GSBUSDT",             SPOT_MATCH_BSTOCK),
    "HOODUSDT":            ("HOODBUSDT",           SPOT_MATCH_BSTOCK),
    "IBMUSDT":             ("IBMBUSDT",            SPOT_MATCH_BSTOCK),
    "INTCUSDT":            ("INTCBUSDT",           SPOT_MATCH_BSTOCK),
    "INTWUSDT":            ("INTWBUSDT",           SPOT_MATCH_BSTOCK),
    "IRENUSDT":            ("IRENBUSDT",           SPOT_MATCH_BSTOCK),
    "KORUUSDT":            ("KORUBUSDT",           SPOT_MATCH_BSTOCK),
    "LITEUSDT":            ("LITEBUSDT",           SPOT_MATCH_BSTOCK),
    "METAUSDT":            ("METABUSDT",           SPOT_MATCH_BSTOCK),
    "MRVLUSDT":            ("MRVLBUSDT",           SPOT_MATCH_BSTOCK),
    "MSFTUSDT":            ("MSFTBUSDT",           SPOT_MATCH_BSTOCK),
    "MSTRUSDT":            ("MSTRBUSDT",           SPOT_MATCH_BSTOCK),
    "MUUSDT":              ("MUBUSDT",             SPOT_MATCH_BSTOCK),
    "MUUUSDT":             ("MUUBUSDT",            SPOT_MATCH_BSTOCK),
    "MVLLUSDT":            ("MVLLBUSDT",           SPOT_MATCH_BSTOCK),
    "NBISUSDT":            ("NBISBUSDT",           SPOT_MATCH_BSTOCK),
    "NFLXUSDT":            ("NFLXBUSDT",           SPOT_MATCH_BSTOCK),
    "NOKUSDT":             ("NOKBUSDT",            SPOT_MATCH_BSTOCK),
    "NVDAUSDT":            ("NVDABUSDT",           SPOT_MATCH_BSTOCK),
    "ORCLUSDT":            ("ORCLBUSDT",           SPOT_MATCH_BSTOCK),
    "PLTRUSDT":            ("PLTRBUSDT",           SPOT_MATCH_BSTOCK),
    "PYPLUSDT":            ("PYPLBUSDT",           SPOT_MATCH_BSTOCK),
    "QCOMUSDT":            ("QCOMBUSDT",           SPOT_MATCH_BSTOCK),
    "QQQUSDT":             ("QQQBUSDT",            SPOT_MATCH_BSTOCK),
    "RKLBUSDT":            ("RKLBBUSDT",           SPOT_MATCH_BSTOCK),
    "SKHYUSDT":            ("SKHYBUSDT",           SPOT_MATCH_BSTOCK),
    "SMCIUSDT":            ("SMCIBUSDT",           SPOT_MATCH_BSTOCK),
    "SMHUSDT":             ("SMHBUSDT",            SPOT_MATCH_BSTOCK),
    "SNDKUSDT":            ("SNDKBUSDT",           SPOT_MATCH_BSTOCK),
    "SNXXUSDT":            ("SNXXBUSDT",           SPOT_MATCH_BSTOCK),
    "SOXLUSDT":            ("SOXLBUSDT",           SPOT_MATCH_BSTOCK),
    "SOXSUSDT":            ("SOXSBUSDT",           SPOT_MATCH_BSTOCK),
    "SPCXUSDT":            ("SPCXBUSDT",           SPOT_MATCH_BSTOCK),
    "SPYUSDT":             ("SPYBUSDT",            SPOT_MATCH_BSTOCK),
    "TQQQUSDT":            ("TQQQBUSDT",           SPOT_MATCH_BSTOCK),
    "TSLAUSDT":            ("TSLABUSDT",           SPOT_MATCH_BSTOCK),
    "TSMUSDT":             ("TSMBUSDT",            SPOT_MATCH_BSTOCK),
    "USARUSDT":            ("USARBUSDT",           SPOT_MATCH_BSTOCK),
    "WDCUSDT":             ("WDCBUSDT",            SPOT_MATCH_BSTOCK),
    # --- 乘数前缀：合约按 N 倍计价，现货是原币 ---
    "1000BONKUSDT":        ("BONKUSDT",            SPOT_MATCH_MULTIPLIER),
    "1000FLOKIUSDT":       ("FLOKIUSDT",           SPOT_MATCH_MULTIPLIER),
    "1000LUNCUSDT":        ("LUNCUSDT",            SPOT_MATCH_MULTIPLIER),
    "1000PEPEUSDT":        ("PEPEUSDT",            SPOT_MATCH_MULTIPLIER),
    "1000SHIBUSDT":        ("SHIBUSDT",            SPOT_MATCH_MULTIPLIER),
    "1000XECUSDT":         ("XECUSDT",             SPOT_MATCH_MULTIPLIER),
}


def resolve_spot_identity(contract_symbol: str) -> tuple:
    """合约 symbol -> ``(spot_symbol, spot_base_asset, match_type)``。纯查表零 IO。

    **永不返回 None** —— 它只回答「这个合约的现货腿叫什么」，不回答「有没有
    现货腿」。后者是 ``check_symbol_legs`` 的职责：身份来自静态表（稳定、可随
    任务固化），存在性必须实时探测（会变——``KORUUSDT`` 曾无现货腿，币安后来
    上线了 ``KORUBUSDT``）。二者混为一谈会让「无腿」的判定退化成查表查不到，
    而表外绝大多数恰恰是同名有腿的普通币。

    表内取映射值；表外即同名（``BTCUSDT`` -> ``BTCUSDT``/``BTC``）。
    ``spot_base_asset`` 由 ``spot_symbol`` 剥去 ``USDT`` 得到，因此恒满足
    ``spot_symbol == spot_base_asset + "USDT"``。

    输入必须是 ``USDT`` 计价的**合约** symbol；否则抛 ``ValueError``。这条 fail-fast
    是针对方案 §1.3 那类「类型混淆」的护栏——把现货 base（``SNXXB``）或别的计价对
    喂进来时当场炸，而不是静默返回一个看似合理的身份。

    设计见 ``docs/planning/symbol-identity-unification-2026-08-07.opus5.md`` §2.2。
    """
    if not isinstance(contract_symbol, str) or not contract_symbol.endswith(_QUOTE_ASSET) \
            or len(contract_symbol) <= len(_QUOTE_ASSET):
        raise ValueError(
            f"contract_symbol must be a {_QUOTE_ASSET}-margined contract symbol, "
            f"got {contract_symbol!r}"
        )
    entry = SPOT_SYMBOL_MAP.get(contract_symbol)
    if entry is not None:
        spot_symbol, match_type = entry
    else:
        spot_symbol, match_type = contract_symbol, SPOT_MATCH_EXACT
    base = (
        spot_symbol[: -len(_QUOTE_ASSET)]
        if spot_symbol.endswith(_QUOTE_ASSET)
        else spot_symbol
    )
    return spot_symbol, base, match_type


def resolve_spot_leg(
    contract_type: str,
    base_asset: str,
    quote_asset: str,
    spot_by_sym: dict,
) -> tuple:
    """Resolve the public spot leg for a futures symbol.

    Returns ``(spot_obj|None, match_type|None)``:

    1. ``exact_symbol`` — ``spot_by_sym[base_asset + quote_asset]``, the normal
       case where the futures and spot symbols are identical.
    2. the :data:`SPOT_SYMBOL_MAP` entry for this contract symbol — the explicit
       exception table for bStocks (``TSLAUSDT`` -> ``TSLABUSDT``) and
       multiplier-prefixed contracts (``1000BONKUSDT`` -> ``BONKUSDT``). Its
       ``match_type`` is carried from the table.
    3. ``(None, None)`` — no currently tradable public spot leg.

    Every candidate is gated on ``status == "TRADING"`` via
    :func:`_tradable_spot`, so a delisted/halted record is never used as a leg.

    NO string-derived guessing (2026-08-07): the previous ``base + "B" + quote``
    and ``base[4:]`` fallbacks are gone. They mis-resolved futures ``BUSDT``
    (baseAsset ``B``) onto spot ``BBUSDT`` (baseAsset ``BB``, BounceBit) — a
    different coin — because ``"B" + "B" == "BB"`` is indistinguishable from a
    real bStock suffix at the string level. The prefix strip was likewise wrong
    for the ``1000000``-prefixed family (it stripped 4 chars, yielding
    ``000MOG``). An unlisted symbol now resolves to ``(None, None)``: a missing
    hedge leg, never a wrong one.

    ``contract_type`` is unused by the lookup (the table is keyed on the exact
    contract symbol) and retained only for signature stability with callers that
    pass it positionally.
    """
    exact = _tradable_spot(spot_by_sym, base_asset + quote_asset)
    if exact is not None:
        return exact, SPOT_MATCH_EXACT
    entry = SPOT_SYMBOL_MAP.get(base_asset + quote_asset)
    if entry is not None:
        mapped = _tradable_spot(spot_by_sym, entry[0])
        if mapped is not None:
            return mapped, entry[1]
    return None, None
