"""main + xyz 全部可匹配币安的标的，完整清单。"""
import json, urllib.request, ccxt
S = "/private/tmp/claude-501/-Users-ark-Desktop-ai-code-funding-hedging/bcd0fc57-da24-4dc0-a92a-1df8490c8897/scratchpad/"

def post(b):
    r = urllib.request.Request("https://api.hyperliquid.xyz/info", json.dumps(b).encode(),
                               {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=30))

ALIAS = {"GOLD":"XAU","SILVER":"XAG","PLATINUM":"XPT","PALLADIUM":"XPD","BRENTOIL":"BZ",
         "SP500":"SPY","KR200":"KODEX200","SMSN":"SAMSUNG","SKHX":"SKHYNIX"}
BLOCK = {"xyz": {"BB", "QNT"}}          # 按 dex 生效：xyz 的 BB/QNT 与币安加密标的撞名

um = ccxt.binanceusdm(); um.load_markets()
tk = um.fetch_tickers()
bn = {}
for s, t in tk.items():
    m = um.markets.get(s)
    if m and m["active"] and m["swap"] and m["quote"] == "USDT":
        bn[m["base"]] = dict(vol=t.get("quoteVolume") or 0, id=m["id"],
                             tradfi=m["info"].get("contractType") == "TRADIFI_PERPETUAL")
fi = {x["symbol"]: x["fundingIntervalHours"]
      for x in json.load(urllib.request.urlopen("https://fapi.binance.com/fapi/v1/fundingInfo", timeout=30))}
fr = um.fetch_funding_rates()
bnfr = {um.markets[s]["base"]: v.get("fundingRate") for s, v in fr.items() if s in um.markets}

rows = []
for dex in ("", "xyz"):
    meta, ctxs = post({"type": "metaAndAssetCtxs", "dex": dex})
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            continue
        raw = u["name"].split(":")[-1]
        b = "1000"+raw[1:] if len(raw) > 1 and raw[0] == "k" and raw[1:].isupper() else raw.upper()
        if b in BLOCK.get(dex or "main", set()):
            continue
        tgt = b if b in bn else ALIAS.get(b)
        if tgt not in bn:
            continue
        if (dex == "xyz") != bn[tgt]["tradfi"]:       # 类别不一致 = 撞名
            continue
        iv = fi.get(bn[tgt]["id"])
        rows.append(dict(dex=dex or "main", hl=u["name"], hl_ccxt=("XYZ-" if dex else "")+raw+"/USDC:USDC",
                         bn=bn[tgt]["id"], alias=(tgt != b), hl_vol=float(c["dayNtlVlm"]),
                         bn_vol=bn[tgt]["vol"], oi=float(c["openInterest"])*float(c["markPx"] or 0),
                         hl_f1h=float(c["funding"]), premium=float(c["premium"]),
                         bn_f=bnfr.get(tgt), bn_iv=iv, lev=int(u["maxLeverage"])))
json.dump(rows, open(S+"full.json", "w"), indent=1)
print("main", sum(r["dex"]=="main" for r in rows), "| xyz", sum(r["dex"]=="xyz" for r in rows),
      "| 合计", len(rows), "| 别名", sum(r["alias"] for r in rows),
      "| 币安周期缺失", sum(r["bn_iv"] is None for r in rows),
      "| 币安费率缺失", sum(r["bn_f"] is None for r in rows))
