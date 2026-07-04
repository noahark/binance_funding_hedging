# Implementation Report — Task A: lastFundingRate warning semantic amendment

- **Stage**: `2026-07-public-market-ui-cn-v1`
- **Task**: A — 合约 warning 语义修订（owner `claude_glm` / `glm-5.2[1m]`, `senior_developer`）
- **Base**: `b84a342` (H_intake)
- **Scope**: `backend/domain/snapshot.py`（仅 `CONTRACT_WARNINGS[1]` 字符串）、
  `docs/api/public-market-contract.md`（lastFundingRate 段落 + Open Verification Items 对应项）、
  `backend/tests/**`（warning 文本断言同步）
- **No logic change**: `classify.py` / `normalize.py` / `snapshot_service.py` / `schemas/**` 全程
  零改动；API 载荷中除 `warnings[1]` 文本外零变化（rows 结构与数值冻结，Task C 复验）。

## 证据（实证依据，H_intake 已随本阶段落盘）

`reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/`
（`evidence-index.md` + `verify-funding-semantics.py`，离线重放 exit 0 = PASS）：周期中段
（本周期 00:00→08:00 UTC，抓取于 04:49Z）ETHUSDT/SOLUSDT 的 `premiumIndex.lastFundingRate`
与 `/fapi/v1/fundingRate` 最新**已结算**记录不相等；SOLUSDT 在 04:34Z 会话即席值
0.00006456 vs 04:49Z 抓取 0.00006761（15 分钟内漂移）。→ 证明该字段是**本周期的实时预估值**
（结算前持续漂移），非已结算历史回显。BTCUSDT 钉在钳制默认 0.0001、TSLAUSDT 为 0，相等属
预期（无区分度样本）。

## 改动 1：`backend/domain/snapshot.py` — `CONTRACT_WARNINGS[1]`（仅一处字符串）

替换为（英文，与另两条合约层语言一致；逐字来自 `00-task.md` Task A 节）：

> "premiumIndex.lastFundingRate is the real-time estimate for the CURRENT funding
> period and is charged at nextFundingTime; it drifts until settlement (mid-period
> divergence from settled history evidenced under
> reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/). Settled
> history comes from /fapi/v1/fundingRate; do not present the estimate as a settled
> value."

`git diff backend/domain/snapshot.py` 确认**仅此一处 -1/+1**，无其他行变化。

## 改动 2：`docs/api/public-market-contract.md`

1. **Funding semantics 段落**：从「`lastFundingRate` 文档为 'most recently updated funding
   rate'，settled-vs-estimate `ambiguous`」升级为实证措辞——明确为「本周期实时预估值，于
   `nextFundingTime` 结算收取，结算前漂移」，引用同一证据路径（周期中段 ETHUSDT/SOLUSDT
   预估值 ≠ 已结算记录 + 15 分钟漂移）；明确已结算历史唯一来源 `/fapi/v1/fundingRate`，预
   估值不得展示为已结算值。
2. **Open Verification Items**：原 `PARTIALLY RESOLVED: lastFundingRate ... ambiguous` 项
   升级为 `RESOLVED (2026-07-04, stage 2026-07-public-market-ui-cn-v1)`，引用
   `verify-funding-semantics.py` PASS 证据。其余项（margin key、bStock alias、private
   borrowability）不动。

## 改动 3：`backend/tests/test_snapshot.py` — `test_three_contract_warnings_preserved`

保留既有 `len==3` + joined 断言（注释微调）；新增对 `snap["warnings"][1]` 的精确断言：
`"real-time estimate" in w1` 与证据路径关键词 `"2026-07-public-market-ui-cn-v1/20260704T044945Z"
in w1`。逻辑测试零改动；测试函数数不变（54）。

## 验证（post-change）

```
$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider backend/tests -q
......................................................  [100%]
54 passed in 0.76s          # 新断言通过；测试数不变

$ grep -rn "float(" backend/domain backend/services
CLEAN                        # decimal 纪律保持

$ git diff --name-only
backend/domain/snapshot.py
backend/tests/test_snapshot.py
docs/api/public-market-contract.md
                            # 仅 3 个产品文件；frontend/schemas/classify/normalize/services 全空
```

## Files changed（boundary-respecting）

- `backend/domain/snapshot.py` — **仅** `CONTRACT_WARNINGS[1]` 字符串（-1/+1）。
- `docs/api/public-market-contract.md` — lastFundingRate 段落 + Open Verification Items 对应项。
- `backend/tests/test_snapshot.py` — warnings[1] 断言增强。
- `reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-backend.md`（本文件）。

## Untouched（forbidden，已核验空 diff）

`frontend/**`、`schemas/**`、`backend/domain/classify.py`、`backend/domain/normalize.py`、
`backend/services/**`、`backend/adapters/**`、`agents/**`、`workflows/**`、`scripts/**`、
`reports/api-samples/**`（含本阶段 intake 证据，阶段内只读）。无 live HTTP / key / 签名 /
order / borrow / repay / transfer / websocket。

## Semantic fidelity check（措辞不偏离 10-design.md §5 要点）

- ✓ 「本周期实时预估值」，于 `nextFundingTime` 结算收取；
- ✓ 结算前漂移，不是已锁定下次收取值，也不是已结算历史；
- ✓ 已结算历史唯一来源 `/fapi/v1/fundingRate`；
- ✓ 不得把预估值展示为已结算/已确定值。

本地北京时间: 2026-07-04 (Task A)
下一步模型: Claude-GLM (controller) → 派发 Task B (Kimi)
下一步任务: 回填 status.json (H_A bookkeeping)，提交，跑 checkpoint，派发 Task B。
