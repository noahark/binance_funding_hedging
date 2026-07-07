# Borrow Cost Coverage v2 Gate A Live Check

模型：GPT/Codex  
状态：COMPLETED  
目的：验证 DRAFT-3 Gate A，即实盘负费率候选数是否超过 `borrow_check_max_calls`。若不超过，根因 A 不成立，方案应退回诊断根因 B。  
执行方式：只读调用本地服务 `GET http://127.0.0.1:8787/api/public-market/snapshot`，仅统计聚合数据，不落档 API key、secret、余额、可借数量或签名信息。

---

## 1. 判定结果

```text
negative_margin_spot_crypto_candidate_unique_assets = 66
borrow_check_max_calls = 50
would_truncate = true
expected_skipped_assets = 16
```

结论：**Gate A PASS，根因 A 成立。**

当前实盘负费率 `MARGIN_SPOT_CANDIDATE + CRYPTO` 去重资产数为 66，超过 `borrow_check_max_calls=50`。因此 `borrow_check_max_calls` 截断确实会触发，DRAFT-3 的 immediate fix 具备实际触发条件，不应退回为“只诊断根因 B”。

---

## 2. 服务快照证据

```text
snapshot_rows = 648
source_sample_id = 20260707T132757Z
generated_at = 2026-07-07T13:27:57Z
private_channel = enabled
borrow_validation.coverage.probed = 50
borrow_validation.coverage.skipped = 16
borrow_validation.coverage.reason = rate_limit_budget
borrow_validation.chain_hit_tier = 2
borrow_validation.chain_hit_source = rate_history
```

说明：

- `coverage.skipped=16` 与 `66 - 50 = 16` 一致，证明当前快照确实发生预算截断。
- 当前快照 `chain_hit_source=rate_history`，说明实现阶段仍必须保留 DRAFT-3 Gate B / next-hourly 可用性检查；但这不推翻 Gate A，二者可以同时成立。

---

## 3. 统计口径

候选口径：

```text
daily_funding_rate < 0
route_class == "MARGIN_SPOT_CANDIDATE"
asset_tag == "CRYPTO"
dedupe by base_asset
```

候选资产：

```text
BLUR,0G,ACH,AGLD,AIGENSYN,ALGO,ARB,ARKM,ARPA,ATOM,AXS,BANANA,BARD,BCH,BEL,CETUS,EPIC,FET,FLUX,GALA,GRAM,GRT,GTC,HBAR,HEI,HOME,ID,INJ,JOE,JST,JUP,LA,LAYER,LQTY,ME,MINA,MIRA,OGN,ONG,OPG,OP,PENGU,PLUME,PROVE,RESOLV,RE,RPL,SEI,SENT,SLP,SOL,SPELL,TLM,TRUMP,TST,TWT,USDC,VANRY,VTHO,WIF,WLD,XLM,XRP,XVS,YFI,ZK
```

---

## 4. 下一步

进入 DRAFT-3 的 Gate B：

```text
验证 next-hourly-interest-rate 对上述 66 个候选资产的单次 assets 参数是否成功。
如果成功，实施 rate_probe_assets 与 borrowability_probe_assets 解耦。
如果失败，先实现 next-hourly 分批合并，且分批合并必须发生在 _select_chain_tier() 之前。
```

---

本地北京时间: 2026-07-07 21:28:26 CST  
下一步模型: Claude-GLM  
下一步任务: 执行 Gate B 只读验证，并在通过后实现 borrow-cost coverage v2 fix
