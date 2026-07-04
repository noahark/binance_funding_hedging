# Fix Start Prompt — rework round 1: spot-leg quoteAsset hardcode

（本文案可直接粘贴给 Claude-GLM controller / Task A owner 启动 rework。）

你是阶段 `2026-07-public-market-bstock-alias-v1` 的 controller 兼 Task A owner
（claude_glm / glm-5.2[1m]）。该阶段在 review-2 recheck ACCEPT 之后，被一次
user-directed 外部 post-review（anthropic / claude-fable-5，本阶段无任何先前参与）
发现一个 P1 回归，现进入 rework 第 1 轮（rework_count=1，max 3）。
`status.json` 已置为 `fixing`。

## 被复审的 diff

- stage_id: `2026-07-public-market-bstock-alias-v1`
- base_sha: `d240e43e75034a6718ede79bc295d39e77cd860e`
- head_sha: `b1894406cf50173fc110f92b63fc3fe2f7ad7fc1`
- stage diff_fingerprint:
  `b1894406cf50173fc110f92b63fc3fe2f7ad7fc1:9d6569d15b987c10eaa008b8b9b344f11c70aeaea7fe84d82dbb6030c89f0aba`

## 原始评审证据（读原文，不要依赖任何转述）

- finding 文件（含可离线重放的验证脚本与全部数字）:
  `reports/agent-runs/2026-07-public-market-bstock-alias-v1/post-review-quote-asset-hardcode-finding.md`
- 证据用 live raw（只读，本阶段 evidence-backfill 已提交）:
  `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/fapi-v1-exchangeInfo.json`
  `reports/api-samples/public-market-bstock-alias-v1/20260703T170827Z/raw/api-v3-exchangeInfo.json`

## Findings（按严重度排序）

1. **[P1] `backend/domain/snapshot.py:70` 把 `resolve_spot_leg` 的 `quote_asset`
   实参硬编码为 `"USDT"`**（应为 `obj.get("quoteAsset", "")`）。
   - 证据：universe 过滤（`backend/services/snapshot_service.py:61-66`）不按
     quoteAsset 过滤；live raw 中符合条件的 691 个永续里有 43 个非 USDT 计价；
     其中 39 行可观测输出被改变（如 `BTCUSDC`→现货腿错配为 `BTCUSDT` 且标
     `exact_symbol`；`ETHBTC`→`ETHUSDT`；`PNUTUSDC` route 从
     `SPOT_ONLY_CANDIDATE` 错误变为 `MARGIN_SPOT_CANDIDATE`）。
   - 影响：对冲腿身份、`spot.min_notional`/`step_size`/杠杆标志取自错误交易对；
     违背本阶段冻结的合约措辞（`docs/api/public-market-contract.md:96-99`）。
   - 建议：见 required_fixes。已验证 live 全集 691/691 满足
     `baseAsset+quoteAsset == symbol`，故该修复与改动前 `spot_by_sym.get(sym)`
     的 exact 行为等价，bStock alias 分支不受影响。

## 用户决策（2026-07-04，已并入本轮 rework）

Phase 1 快照 **仅覆盖 USDT 计价交易对**；USDC/USD1/U 等其他计价的交易对推迟到
未来阶段再议。universe 过滤须新增 `quoteAsset == "USDT"` 条件——这是兑现既有
冻结 schema 的 `row.quote_asset = {"const": "USDT"}` 声明，**不构成合约修订**，
schema 与 docs 均无需改动。原 finding 中"不得顺手修 quote_asset const/universe
过滤问题"的限制，据此决策解除并改为必修项。

## required_fixes

1. `backend/domain/snapshot.py:70` 调用点改为传 `obj.get("quoteAsset", "")`
   （即使过滤后全为 USDT 也要改：保持调用点忠实于合约文字，为未来非 USDT
   阶段排雷）。
2. **用户决策项**：`backend/services/snapshot_service.py` 的 universe 过滤
   （现为 `status=="TRADING"` + `contractType in ELIGIBLE_CONTRACT_TYPES`）
   新增 `s.get("quoteAsset") == "USDT"` 条件。
3. 合成 fixture（`backend/tests/fixtures/bstock-alias-raw/`）新增一个 USDC 计价
   PERPETUAL（期货 `BTCUSDC`，现货同时含 `BTCUSDC` 与 `BTCUSDT`），两层断言：
   - service 层：快照 rows 中**不出现** `BTCUSDC`（被 universe 过滤排除）；
   - `build_rows` 层：直接喂入该 USDC 行时 `spot.symbol=="BTCUSDC"`、
     `match_type=="exact_symbol"`、绝不解析为 `BTCUSDT`（独立于过滤器验证
     调用点修复）。
   既有 bStock alias 与 USDT exact 用例不变。
4. 离线复验（禁止新的 live HTTP）：对已提交的 live raw 重放构建，断言：
   - universe = 648 行且全部 `quoteAsset=="USDT"`（43 个非 USDT 被排除）；
   - 不存在 `match_type=="exact_symbol" && spot.symbol != futures.symbol` 的行；
   - 15/15 bStock alias 解析不变；
   输出追加到 `60-test-output.txt`（新 Section）。
5. 撰写 `40-fix-report.md`：逐条 finding→fix 映射（finding id
   `spot_leg_quote_asset_hardcode` + 用户决策项 → 代码/测试/复验各自的落点
   与结果）。

## 文件边界

允许写：
- `backend/domain/snapshot.py`（仅第 70 行调用点）
- `backend/services/snapshot_service.py`（仅 universe 过滤条件，用户决策项）
- `backend/tests/**`（含 fixtures）
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/40-fix-report.md`
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/60-test-output.txt`（追加）
- `reports/agent-runs/2026-07-public-market-bstock-alias-v1/status.json`（controller 记账）

禁止：
- `backend/domain/normalize.py`（`resolve_spot_leg` 纯函数不改）
- `backend/domain/classify.py`（回归断言 only，逻辑零改动）
- `schemas/**`、`docs/**`（合约文字本就正确；USDT-only 是兑现既有 schema const，
  无需修订）
- `frontend/**`、`agents/**`、`workflows/**`、`scripts/**`
- `reports/api-samples/**`（只读历史证据）
- 任何 live HTTP、API key、signed/private endpoint、order/borrow/repay/transfer、websocket
- `build_rows` 行输出里的 `"quote_asset": "USDT"`（snapshot.py:99）保持原样——
  过滤后它对每一行都为真，无需改动

## 修复后必跑命令

```bash
python3 -m pytest backend/tests -q          # 必须全绿（52 + 新增用例）
grep -rn "float(" backend/domain backend/services   # decimal 纪律复查
node frontend/self-check.js                 # 前端未动，仍须 11/11 PASS
python3 scripts/validate-stage.py 2026-07-public-market-bstock-alias-v1 --phase checkpoint
```

## 收尾协议（fingerprint 与再评审）

- 修复提交为 `H_fix`；按既有单一协议重算 task-A 级与 stage 级
  `diff_fingerprint`（`head_sha + ':' + sha256(git diff --binary base..head --
  . ':(exclude)reports/agent-runs/<stage-id>/status.json')`）。
- review-1（task 级，Kimi）对 fix diff 重新给 verdict；随后 review-2
  （最终门）重跑并绑定新 head。注意：Fable5（anthropic）自 2026-07-04 起可达，
  review-2 决策池按 AGENTS.md 重新评估（不再适用"Fable5 unavailable"记录）。
- 全程 controller 串行提交；`status.json` 状态流转 `fixing` → `review_1` →
  `review_2` → `stage_accepted_waiting_user`；controller 不声明最终验收。
