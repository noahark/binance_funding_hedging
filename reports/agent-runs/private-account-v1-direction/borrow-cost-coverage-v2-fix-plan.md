# Borrow Cost Coverage v2 Fix Plan

模型：GPT/Codex  
状态：DRAFT，供 Claude/Fable5 review  
范围：后端数据源与覆盖率修复方案，不修改业务代码，不提交 git  
关联证据：

- `reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md`
- `reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/`
- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `docs/api/public-market-contract.md`

---

## 1. 问题定义

当前 UI 中大量负费率资产的“日借币利率 / 净收益”显示为 `-`，并不是 Binance 没有返回利率数据，而是后端数据链路没有充分使用已验证的数据源。

Kimi 只读摸排已经确认：

1. `GET /sapi/v1/margin/next-hourly-interest-rate` 支持多资产批量查询。
2. 返回字段 `nextHourlyInterestRate` 是 hourly rate，乘以 24 后可以作为开仓前日借币利率估算。
3. 该批量端点对 OPG、0G、AIGENSYN、ALGO、DOGE、BTC、ETH、SOL 等样本有效。
4. `GET /sapi/v1/margin/interestRateHistory` 是单资产端点，权重 `60 UID / asset`，适合 fallback / 校验，不适合常规全量主链路。
5. `GET /papi/v1/margin/maxBorrowable` 只表示统一账户当前实际可借额度，不是利率来源。

当前代码缺陷：

- 当 `next-hourly` 没有作为主链路成功覆盖全部候选资产时，fallback `interestRateHistory` 只查 `borrow_assets[0]`。
- 结果是排序靠前的资产，例如 OPG，能拿到 `daily_interest_account`，其他候选资产保持 `null`。
- `maxBorrowable` 当前按 top-N 预算探测，未命中资产显示 `not_probed_this_round`，没有 round-robin 覆盖机制。

所以本次修复分两层：

1. **必须修复**：用 `next-hourly-interest-rate` 批量结果填充所有命中资产的日借币利率。
2. **建议后续或同阶段扩展**：给 `maxBorrowable` 增加 rotating probe queue，减少长期 `未探测(限速预算)`。

---

## 2. 修复目标

### 2.1 Immediate Fix: 批量利率主链路

后端应把 `next-hourly-interest-rate` 作为开仓前借币日利率主数据源：

```text
daily_interest_account = Decimal(nextHourlyInterestRate) * 24
borrow_rate_source = "next_hourly"
```

匹配规则：

- 以 asset 为 key，不以 symbol 为 key。
- `OPGUSDT` -> borrow asset `OPG`
- `0GUSDT` -> borrow asset `0G`
- bStock 如 `TSLABUSDT` -> asset `TSLAB`，但若 `next-hourly` 缺失且 `maxBorrowable.amount == 0`，继续保持不可借状态，不伪造利率。

输出行为：

- 对 `next-hourly` 命中的资产，填充 `borrow_validation.classic_margin.daily_interest_account`。
- 同步填充 `borrow_rate_source = "next_hourly"`。
- `net_daily_yield` 可正常计算：`abs(daily_funding_rate) - daily_interest_account`。
- 若资产有利率但 `maxBorrowable` 返回 `51061` 或 amount 为 0，应显示“有利率但当前不可借”，不能显示成“无利率”。

### 2.2 Fallback Fix: interestRateHistory 不再只查第一个资产

`interestRateHistory` 不应继续只查 `borrow_assets[0]` 后把其他资产置空。

建议策略：

- 正常情况下不调用 `interestRateHistory` 全量轮询。
- 仅当 `next-hourly` 请求失败、返回空、或单个资产缺失时，对缺失资产启动 bounded fallback。
- fallback 每轮最多查 `K` 个资产，默认 `K=5` 或复用配置项。
- fallback 结果标记 `borrow_rate_source = "rate_history"`。

这避免 50 个资产全量轮询产生 `50 * 60 = 3000 UID weight`，同时让降级路径有覆盖能力。

### 2.3 Coverage Follow-up: maxBorrowable rotating queue

`maxBorrowable` 是逐资产接口，负责“当前是否真的能借”。它和利率主源分离。

现状：

- 每轮只探测 top-N 候选。
- 未探测资产长期可能停留在 `not_probed_this_round`。

建议后续增加 rotating queue：

- 每轮优先探测 abs funding rate top-N。
- top-N 之外增加 round-robin bucket，每轮补探 M 个资产。
- 每个 asset 记录最近探测时间和错误状态。
- UI 区分：
  - `rate_available_borrowable`: 有利率且可借。
  - `rate_available_not_borrowable`: 有利率但当前不可借。
  - `rate_available_borrow_unprobed`: 有利率但可借额度未探测。
  - `rate_unavailable`: 利率不可用。

本项可以单独成后续小阶段；不应阻塞 immediate fix。

---

## 3. 非目标

本次 fix 不做：

- 下单、借币、还币、划转。
- WebSocket 行情接入。
- 手动开仓流程。
- 前端大改版。
- 更改 funding rate 排序基准，除非现有排序依赖 `net_daily_yield` 自动受益。
- 引入新的私有写接口。
- 把 bStock 负费率借币套利重新打开。

---

## 4. 代码边界建议

允许修改：

- `backend/services/private_client.py`
- `backend/services/snapshot_service.py`
- `backend/domain/snapshot.py`
- `backend/tests/test_private_account_v1.py`
- `backend/tests/test_phase2_borrow_sort.py`
- 必要时更新冻结 fixture / 脱敏样本索引

谨慎修改：

- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`

如果 schema 已包含 `borrow_rate_source = "next_hourly"`，不应改 schema。若缺少该枚举，只做 additive enum update，并补兼容测试。

禁止修改：

- API key / `.env`
- 交易、借币、还币、划转相关代码
- 与本次数据源修复无关的 UI 布局

---

## 5. 测试策略

必须增加或调整的测试：

1. `next-hourly` 批量命中多资产
   - 输入 OPG、0G、AIGENSYN、ALGO、DOGE。
   - 断言每个命中资产都有 `daily_interest_account`。
   - 断言 `borrow_rate_source == "next_hourly"`。
   - 断言 daily = hourly * 24。

2. `interestRateHistory` fallback 不只服务第一个资产
   - 模拟 `next-hourly` 缺失部分资产。
   - 对缺失资产 bounded fallback。
   - 断言 fallback 命中的资产 source 为 `rate_history`。
   - 断言未进入 fallback budget 的资产状态清晰，不伪造利率。

3. `maxBorrowable` 与利率分离
   - 有利率但 `maxBorrowable` 返回 `51061` 时：
     - `daily_interest_account` 仍存在。
     - `net_daily_yield` 可计算或按产品口径展示。
     - borrowability 状态显示当前不可借。
   - 不能因为不可借就删除利率。

4. bStock 负费率保护
   - `TSLAB` 无 `next-hourly`，`interestRateHistory` 返回不支持，`maxBorrowable.amount == 0`。
   - 断言仍不可作为负费率借币套利腿。

5. 回归测试
   - `python3 -m pytest backend/tests/test_private_account_v1.py -q`
   - `python3 -m pytest backend/tests/test_phase2_borrow_sort.py -q`
   - `python3 -m pytest backend/tests/test_snapshot.py -q`
   - `python3 -m pytest backend/tests -q`

---

## 6. 验收标准

修复完成后应满足：

1. 当前负费率候选中，`next-hourly` 返回的资产不再大面积显示 `日借币利率 = -`。
2. OPG、0G、AIGENSYN、ALGO、DOGE 等样本资产都能从批量 `next-hourly` 获得日利率。
3. `borrow_rate_source` 能区分：
   - `next_hourly`
   - `rate_history`
   - `cross_margin_tier`
   - `vip0_reference`
   - `null`
4. `maxBorrowable` 的不可借状态不会清空或掩盖利率。
5. bStock 负费率借币套利仍保持禁用。
6. 所有测试通过。
7. 若 live smoke test 启用私有通道，必须只读，不触发交易/借还/划转。

---

## 7. 建议阶段拆分

推荐作为一个后端 fix stage：

```text
stage-id: 2026-07-borrow-cost-coverage-v2
complexity: MEDIUM
owner: claude_glm
review-1: kimi
review-2: codex 或 claude/fable5，按 Harness 规则
```

任务拆分：

1. Task A: `next-hourly` 批量主链路修复。
2. Task B: bounded `interestRateHistory` fallback。
3. Task C: 测试与 live read-only smoke。
4. Follow-up: `maxBorrowable` rotating queue，可视实际复杂度单独开阶段。

如果希望快速解决 UI 上的大量 `-`，可以先只做 Task A + tests，把 rotating queue 延后。

---

## 8. 给 Claude/Fable5 的 Review 启动文案

```text
请只读 review 以下 fix 方案，不修改文件：

reports/agent-runs/private-account-v1-direction/borrow-cost-coverage-v2-fix-plan.md

背景证据：
- reports/agent-runs/private-account-v1-direction/endpoint-recon-kimi-borrow-rate-v2.md
- reports/api-samples/private-account-v1-direction/borrow-rate-endpoint-survey-20260707T120945Z/
- backend/services/private_client.py
- backend/services/snapshot_service.py
- backend/domain/snapshot.py

请重点判断：
1. 把 next-hourly-interest-rate 作为开仓前借币日利率主源是否成立。
2. Immediate fix 和 maxBorrowable rotating queue 是否应该拆阶段。
3. interestRateHistory fallback 的 bounded per-asset 策略是否合理。
4. bStock 负费率保护和“有利率但不可借”状态是否表达清楚。
5. 测试与验收标准是否足够。

输出 ACCEPT / REWORK，并列出必须修正项。
```

---

本地北京时间: 2026-07-07 20:25:15 CST  
下一步模型: Claude/Fable5  
下一步任务: review borrow-cost coverage v2 fix plan
