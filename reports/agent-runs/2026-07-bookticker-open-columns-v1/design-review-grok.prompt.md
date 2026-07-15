# Grok Advisory Design Review Prompt

你是用户明确启用的补充设计审查者。请对 stage `2026-07-bookticker-open-columns-v1` 的初始文档做严格、独立、只读评审。

## Role Boundary

- Model: `grok-build`
- Provider identity: `xai_grok`
- Mode: plan/read-only
- 本次是 advisory design review（补充设计评审），不是 formal review-1 或 review-2。
- 不写代码、不改文件、不改 stage state、不 commit/push/merge/rebase、不启动其他模型。
- 人工/bookkeeper 会把你的原始输出保存为 stage evidence；你不要自行写 review 文件。

## Repository And Stage

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Expected branch: `stage/2026-07-bookticker-open-columns-v1`
- Base SHA: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939`

若 branch 不匹配，直接返回 blocker。

## Required Raw Read Set

必须亲自读取：

- `AGENTS.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
- `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/evidence-index.md`
- `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/capture.md`
- `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/normalized/bookticker-summary.json`
- evidence index 点名的 raw BTC responses、full response headers 与 futures batch probe
- `schemas/api/public-market/snapshot.schema.json`
- `schemas/api/public-market/symbol-snapshot.schema.json`
- `backend/adapters/binance_public.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

不要联网重新摸排；以 stage 中 raw API evidence 和实际源码为准。

## Frozen Semantics To Check, Not Rewrite

- 正向：上合约买一、下现货卖一；`(F_bid-S_ask)/S_ask*100`。
- 反向：上现货买一、下合约卖一；`(S_bid-F_ask)/F_ask*100`。
- 正数都表示该方向有利，两位小数，后端 Decimal 计算。
- 60 秒 full×2 public fetch；本地 paired atomic commit；两个周期后停止作为可用开单价。
- bStock 使用 resolved `row.spot.symbol`。
- 表格删除提示列、合并借贷状态/资产、新增两开单列后仍为 12 列。
- 只读、无交易副作用。

## Review Focus

请主动寻找，而不是复述设计：

1. 原始 Binance evidence 是否真的支撑 endpoint shape、full-fetch 选择和 decimal string 假设。
2. 两请求顺序执行 + 本地 atomic commit 是否还有跨轮/失败/时间戳漏洞。
3. 60s due / 120s usability cutoff 在 30s worker tick、连续失败和恢复时的精确边界。
4. `opening_quotes` 的 `fresh/incomplete/stale/unavailable` 是否存在不一致或无法实现状态；特别检查 incomplete 行两个方向独立计算是否被测试锁定。
5. 百分数字段已经乘 100 与现有 funding fractional rate 之间是否容易误用，命名/测试是否足够。
6. Spot zero books、missing symbols、bStock B suffix、METAL no exact leg、legacy stubs、selected-symbol click。
7. Schema `additionalProperties=false`、legacy fixture compatibility 和 current-producer presence 的验证是否充分。
8. 前端 DOM 顺序、借贷信息迁移、列索引、旧后端 graceful degradation、accessibility/title。
9. File boundary、owner split和 deterministic test commands 是否遗漏必需文件。
10. 是否有更小但同样安全的实现；若建议替代，必须说明 tradeoff，不得扩大到 WebSocket/执行系统。

## Required Output

返回 Markdown，结构必须是：

```text
# Grok Advisory Design Review

## Verdict
READY | REVISE

## Findings
### [P0|P1|P2] <short title>
- Evidence: <exact file/path/line or raw artifact>
- Risk: <concrete failure>
- Required revision: <bounded actionable change>

## Confirmed Strengths
- ...

## Test Gaps
- ... or None

## Scope/Authority Check
- Confirm no code/file/state changes were made.
- Confirm this is advisory only and does not replace formal review gates.

当前 Session ID: <provider-native id | unavailable (reason)>
原始输出路径: <human/bookkeeper capture target; expected reports/agent-runs/2026-07-bookticker-open-columns-v1/13-design-review-grok.raw.md>
本地北京时间: <from local date> CST
下一步模型: codex_bookkeeper
下一步任务: 收集原始评审输出，处理 findings，并决定是否进入 implementation dispatch
```

P0/P1 finding 存在时 verdict 必须为 `REVISE`。不要提供实现代码，不要输出模型重启命令。Session ID 必须来自当前 CLI/provider 的原生输出或上下文；拿不到时写 `unavailable (<reason>)`，不得猜测。Session ID 不是 credential，也不保证其他 provider 能直接读取本会话；不得输出 token、cookie、credential 或 expanded environment。
