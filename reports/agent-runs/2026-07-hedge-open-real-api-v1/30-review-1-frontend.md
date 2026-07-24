# Review-1 — Frontend Cross-Review — Hedge Open Real API v1

> 评审者：Claude-GLM（`glm-5.2[1m]`，经 Claude Code 访问，provider = `zhipu_glm`）。
> 角色：正式 Review-1 前端交叉评审者（`role=first_reviewer`）。
> 实现者：Kimi（`kimi-k3`，frontend owner，Task B）。前端实现者与评审者 provider 隔离满足
> review-1 的 cross-review 规则（Kimi ↔ Claude-GLM）。
> 审查模式：只读。本会话未修改任何源码、后端、`status.json`、`70-handoff.md`、前端文件或
> 任何合同；未 git commit；未调用/转派任何其他模型会话；未发起任何真实 Binance 网络、
> 私有或 POST 请求。唯一写出的产物是本评审文件本身（dispatch 指定的 `outputs` 路径）。
> 审查锚点：frontend diff `d90f2f18acec7fe6286f2ae3fc8e187580bf0793..d873699d4c06f8dec343c9a6dcfa5fecc22d74b5`。

## 0. Provider 与参与披露

- 本评审者 `glm-5.2[1m]` / `zhipu_glm` 与本 stage 的**后端**实现者及 R4 fix 作者同 provider 同模型
  （`20-implementation-backend.md`、`40-fix-backend-r4.md`）。本评审**不评审后端**，仅评审前端任务
  （Task B，owner=Kimi）。前端实现者 Kimi 与评审者 provider 隔离，满足 review-1 cross-review 规则。
- `glm-5.2[1m]` 曾作为 direction panel 成员提交独立方向稿 `direction-drafts/glm52.md`（panel draft，
  非方向综合 / breakdown / design）。本评审者未参与 `06-direction-synthesis.md`（综合）、
  `12-development-breakdown.md`（Opus 4.8）或 `10-design.md`/`11-adr.md`（Codex）。因此
  `reviewer_prior_involvement=none`（schema 三类决策性参与均未发生），与 dispatch 指示一致。
- 评审依据：本 prompt 列出的 raw artifact 路径与本会话实际读取的文件（见 verdict
  `reviewed_artifacts`）。后端 `service.py`/`domain.py`/`store.py` 仅用于核对"前端能否真实消费
  后端 R4 additive `attempts` 投影"这一评审重点，未被修改。

## 1. 简洁叙述

Task B 在 `frontend/index.html`（+159）与 `frontend/self-check.js`（+179）以增量方式落地了
Hedge Open Real API v1 的中文前端展示：任务卡新增「已调度 / 已受理 / 连续提交失败 / 暂停阈值」
计数行与「暂停原因」行；新增「尝试时间线」区块消费既有 `GET /api/hedge-open-logs?limit=100`，
渲染每条 attempt 的序号、方向、pair outcome 徽标、关联任务币种、q_common、residual，以及两腿的
订单号 / 客户单号 / 状态 / 累计数量 / 累计成交额 / 加权均价（现货腿含手续费）。

核对结论：**核心数据消费契约成立**——前端 `extractHedgeAttempts`/`normalizeHedgeAttempt`/
`renderHedgeAttemptLeg` 与后端 R4 `attempt_to_doc`/`_leg_to_doc`（`service.py:171-197`）字段名逐字
对齐；所有新 Decimal 字段经 `hedgeText`（`String(v)`，不经过 JS 浮点）原样展示；缺字段 / 缺腿 /
空态 / 503 均优雅降级不崩溃；前端未新增任何签名 / 调度 / 定时器 / POST / Binance 直连，执行徽标
仍为只读投影；self-check 对降级路径与禁止 Binance 直连的负面断言覆盖扎实。

唯一阻断项是 **pair outcome 取值映射与后端真实投影错位**：前端标签表只收录
`accepted_pair/confirmed_failed/querying`，而后端实际投影集为 `null`（未解析 / 查询中）/
`accepted_pair`/`confirmed_failed`/`single_leg`（`domain.py:139-142`，`store.py:611-619` 写入，
`service.py:192` 透传）。后果是 ADR-3 明确认可的真实「单腿敞口」状态（`single_leg`）在前端降级
为英文 key，而合同意图的「查询中」徽标因后端用 `null` 表示查询中、前端把 `null` 显示为 `—`
而永不显示；self-check 还用后端从不产生的 `querying` 取值做了断言，给出虚假覆盖信心。该缺陷
不崩溃、字段消费正确，但损害操作者对单腿敞口 / 在途查询状态的监督可读性，且修复机械、边界
清晰，故裁定 REWORK。

## 2. 逐条核对（对照 dispatch 评审重点）

1. **前端实际能消费后端 R4 的 additive `attempts` 投影，字段名精确且不依赖伪造 legacy log** —
   基本成立。后端 `get_logs` 返回 `{logs, attempts, next_cursor}`（`40-fix-backend-r4.md` §2.2；
   `service.py` get_logs）；`attempt_to_doc` 投影 `task_id/attempt_id/attempt_seq/direction/q_common/
   pair_outcome/spot/perp/residual/ts`，`_leg_to_doc` 投影 `client_order_id/order_id/status/
   cumulative_base_qty/cumulative_quote_amt/avg_price`（+spot `fee_amount/fee_asset`）。前端
   `normalizeHedgeAttempt`（index.html:3790）与 `renderHedgeAttemptLeg`（index.html:3810）字段名
   逐字对齐。`extractHedgeAttempts` 优先扫 `doc.attempts`；legacy `logs` 为 record-transport 形状
   （`log_to_doc` payload = `{transport, params, posted,…}`，非 attempt 形状），被
   `isHedgeAttemptShaped` 判否忽略，**不依赖伪造 legacy log**。**例外**：`pair_outcome` 的取值
   语义未被完整消费（见 P2-1），属本项下的覆盖缺口。
2. **Decimal 显示不发生 JS 浮点重排，缺字段 / 缺腿 / 空态 / 503 不崩溃** — 成立。`hedgeText`
   （index.html:3287）= `String(v)`，所有新字段经此路径；断言 85 以字面量 `0.36210000`、
   `120.70000000`、`0.00000010`、`0.00000100`、`-0.00010000` 逐字断言，任何浮点重排即失败。
   缺腿 `renderHedgeAttemptLeg(leg||{})` 全项 `—`；空态「暂无尝试记录」；503 走 `loadHedgeAttempts`
   catch → 错误横幅并保留缓存（断言 86）。
3. **新 DOM、中文文案、旧页面字段和 API 兼容性** — 成立。新 DOM `hedge-attempt-list`/
   `hedge-attempts-error`（index.html:1151-1152，self-check.js:163）；中文文案覆盖计数 / 阈值 /
   暂停原因 / 尝试时间线 / 现货腿 / 合约腿 / 加权均价 / 累计成交额 / 手续费 / 残差；旧
   `exposureLine`/`terminatedLine`/旧 `q_common` 行保留，旧文档逐项降级 `—`（断言 84）；路由表
   不变，既有 `GET /api/hedge-open-logs?limit=100`。
4. **self-check 是否覆盖真实接口形状、降级路径和禁止 Binance 直连的负面断言** — 降级与禁连
   断言扎实；**接口取值形状有偏差**（P3-1）：mock 用 `pair_outcome:'querying'`（后端不产生），
   未覆盖后端会产生的 `single_leg`。断言 87 的同源白名单、零 Binance/外域、方法白名单、定时器
   白名单（无新定时器）、localStorage 白名单全部通过。
5. **未扩大到前端自动 live 开关、调度或任何交易行为** — 成立。`loadHedgeAttempts` 只读 GET，
   无 POST / 定时器 / 签名 / 调度；执行徽标只读投影；UI 无任何可暗示前端自行开启 live 的入口。

## 3. Findings

### P2-1 — pair outcome 标签映射与后端真实取值集错位（single_leg 缺失 + querying 死映射 + null 误显示为「—」）

- **file**: `frontend/index.html`
- **line**: 3278（`HEDGE_PAIR_OUTCOME_LABELS` / `HEDGE_PAIR_OUTCOME_BADGE`）与 3818-3820
  （`renderHedgeAttemptCard` 的 `outcomeLabel`/`outcomeBadge`）。
- **evidence**:
  - 后端 pair_outcome 取值集：`domain.py:139-142` 定义 `PAIR_ACCEPTED="accepted_pair"`、
    `PAIR_CONFIRMED_FAILED="confirmed_failed"`、`PAIR_SINGLE_LEG="single_leg"`；`store.py:611-619`
    的 `_apply_task_counters` 据两腿 acceptance 写入这三者之一；`store.py:737-739`/`820-821`
    把该值写入 `hedge_open_attempt.pair_outcome`；`service.py:192` `attempt_to_doc` 直接透传
    `attempt["pair_outcome"]`。**未解析 / 查询中的 attempt 投影为 `pair_outcome=null`**
    （`40-fix-backend-r4.md` §2.3 第二个示例；`14-r4-verification.md` R4-1 覆盖 PREPARED/querying）。
  - 前端 `HEDGE_PAIR_OUTCOME_LABELS`（index.html:3278-3281）仅收录 `accepted_pair:'已受理'`、
    `confirmed_failed:'已确认失败'`、`querying:'查询中'`，**未收录 `single_leg`**。
  - `renderHedgeAttemptCard`（index.html:3818-3820）：`outcomeLabel = attempt.pair_outcome ?
    (LABELS[pair_outcome] || String(pair_outcome)) : '—'`；`outcomeBadge = BADGE[pair_outcome] || 'muted'`。
- **impact**:
  1. 后端投影 `pair_outcome:"single_leg"`（恰好一腿 accepted、另一腿 confirmed-absent）时，
     前端 `LABELS["single_leg"]` 为 `undefined` → 走 `String("single_leg")` 显示英文 key
     `single_leg` + `muted` 徽标。这是 ADR-3 / `04-user-execution-policy.md` 明确认可、需人眼
     监督的「单腿敞口」真实结果状态（`domain.py:135` 注释 "ADVISORY only, recorded but never a
     gate"），操作者将看到不可读的英文 key，无法直观识别这是单腿敞口。
  2. `querying:'查询中'` 是死映射：后端从不投影字符串 `"querying"`（未解析时投影 `null`）。
     当后端投影一个 PREPARED/UNKNOWN_QUERYING/ACCEPTED_OR_QUERYING 的在途 attempt
     （`pair_outcome=null`）时，前端把它显示为 `—`，而非实现报告 §2.1 与合同意图的「查询中」
     徽标——即「查询中」徽标实际**永不显示**，操作者无法从徽标区分「该 attempt 正在查询中」
     与「该字段缺失」。
- **recommendation**: 在 `HEDGE_PAIR_OUTCOME_LABELS`/`HEDGE_PAIR_OUTCOME_BADGE` 收录
  `single_leg`（如 `'单腿成交'`，badge `warning`）；将 `pair_outcome===null`（后端在途 / 查询中
  的真实表示）映射为「查询中」而非 `—`（保留 `hedgeText` 对真正缺失字段的 `—` 语义用于其它
  字段）；`querying` 映射可保留（无害）或移除。修复仅触及标签常量与 `renderHedgeAttemptCard`
  的 outcome 取值分支，不动后端、不动合同、不引浮点。

### P3-1 — self-check mock 的 pair_outcome 取值偏离后端真实形状

- **file**: `frontend/self-check.js`
- **line**: 3857（断言 85 的 `attemptB` 用 `pair_outcome:'querying'`）。
- **evidence**: mock 用 `pair_outcome:'querying'` 断言「查询中」徽标渲染；但后端取值集为
  `null/accepted_pair/confirmed_failed/single_leg`（见 P2-1 证据），**不含 `querying`**；mock
  亦未覆盖 `single_leg`。
- **impact**: self-check 对 attempt 徽标路径给了假阳性覆盖信心——测了一个后端不会产生的取值，
  没测后端会产生的 `single_leg`。这削弱了评审重点 4「self-check 是否覆盖真实接口形状」。
- **recommendation**: mock 与断言对齐后端 `domain.py` 取值集：将断言 85 的在途用例改为
  `pair_outcome:null` 并断言其渲染「查询中」（修复 P2-1 后），新增一个 `single_leg` 用例断言其
  渲染中文标签；保留 `accepted_pair`/`confirmed_failed` 用例。

### P3-2 — extractHedgeAttempts 多数组合并无去重（理论重复风险）

- **file**: `frontend/index.html`
- **line**: 3784（`extractHedgeAttempts` 扫描 `doc.attempts/fills/logs/entries` 合并到同一 `out`）。
- **evidence**: `[doc.attempts, doc.fills, doc.logs, doc.entries].forEach(...)` 把每个数组的
  attempt-shaped 条目 push 进同一 `out`，不按 `attempt_id` 去重。当前后端 `get_logs` 仅返回
  `attempts`（无 `fills`/`entries`），且 `logs` 为 record-transport（非 attempt 形状被忽略），
  故**当前无重复**。
- **impact**: 若后端将来在多个候选键下投影同一批 attempt（或在 `logs[].payload` 内嵌 attempt），
  时间线会重复渲染同一 attempt。当前不触发，属韧性缺口。
- **recommendation**: 命中 `doc.attempts` 后即返回，或按 `attempt_id` 去重（`attempt_id` 已被
  `normalizeHedgeAttempt` 提取，见 P3-3）。优先前者（最简）。

### P3-3 — attempt_id 被提取但未用于渲染或去重

- **file**: `frontend/index.html`
- **line**: 3793（`normalizeHedgeAttempt` 提取 `attempt_id`）。
- **evidence**: `attempt_id` 被 normalize 但 `renderHedgeAttemptCard` 仅展示 `attempt_seq`（「第 N
  组」），既不渲染 `attempt_id`，也不用作去重键。
- **impact**: 无功能缺陷；仅是已读字段未充分利用（可用于 P3-2 的去重或调试展示）。
- **recommendation**: 可选——用于 P3-2 去重，或在卡片上以 `mono` 小字展示 attempt_id 便于与
  后端日志对账。非阻断。

### P3-4 — attempt 时间线 ?limit=100 仅取首页，无分页 / 加载更多

- **file**: `frontend/index.html`
- **line**: 3807（`loadHedgeAttempts` 请求 `/api/hedge-open-logs?limit=100`）。
- **evidence**: 后端 `next_cursor` 跟踪 `logs`（legacy 契约），`attempts` 无独立 cursor
  （`40-fix-backend-r4.md` §6.1 有意选择）；前端固定 `limit=100` 且不消费 cursor。
- **impact**: 超过 100 条的更早 attempt 不展示（实现报告 §6 已披露）。非阻断，已知限制。
- **recommendation**: 记为后续增量；当前可接受。

### P3-5 — 交易所 leg status 原样英文展示（观察，非缺陷）

- **file**: `frontend/index.html`
- **line**: 3813（`renderHedgeAttemptLeg` 展示 `l.status`，即后端 `exchange_status`）。
- **evidence**: `FILLED/NEW/PARTIALLY_FILLED/REJECTED/EXPIRED/UNKNOWN` 等 Binance 原始枚举原样
  展示，未做中文映射。
- **impact**: 交易所状态枚举为 Binance 原始值，原样展示可接受（合同未要求翻译交易所状态）。
- **recommendation**: 无需修改；若追求一致性可后续统一，非本阶段阻断。

## 4. 修复要求（required_fixes）

1. **（P2-1，必须）** `HEDGE_PAIR_OUTCOME_LABELS`/`HEDGE_PAIR_OUTCOME_BADGE` 收录 `single_leg`
   中文标签与徽标色；将 `pair_outcome===null` 映射为「查询中」徽标而非 `—`。
2. **（P3-1，必须）** self-check mock / 断言对齐后端真实取值集：在途用例改用
   `pair_outcome:null` 并断言「查询中」渲染；新增 `single_leg` 用例断言中文标签渲染；移除对
   后端不产生的 `querying` 取值的依赖。
3. **（P3-2，建议）** `extractHedgeAttempts` 命中 `doc.attempts` 后即返回，或按 `attempt_id`
   去重，消除多键重复风险。

P3-3 / P3-4 / P3-5 为观察项，非阻断，可在后续增量处理。

## 5. 遗留风险（residual_risks）

- 信封宽容提取（`attempts/fills/logs/entries`）依赖"后端仅在 `attempts` 投影 attempt"这一
  当前事实；若后端契约演进在多键投影，需配合 P3-2 去重。
- 旧 `leg_exposure` 文案「任务已暂停」与新合同「单腿敞口不阻断调度」存在语义张力（实现报告
  §6 已披露，advisory，未改既有文案）——是否修订文案由后续 review / 产品裁定，非本前端任务
  范围。
- `?limit=100` 无分页（P3-4），超 100 条 attempt 不展示。
- 本评审未执行真实集成（浏览器加载运行中的后端）；`extractHedgeAttempts` 与后端
  `attempt_to_doc` 的字段对齐基于源码静态核对 + self-check mock，集成期仍建议按后端真实落库
  形状复核一次（实现报告 §6 风险 1 已提示）。

## 6. 总体结论

核心冻结 UI 合同（只读消费既有后端 API、Decimal 字符串原样、字段缺失 / 空态 / 503 优雅降级、
不签名 / 不调度 / 不直连 Binance、不扩大到 live 开关或交易行为）**全部成立**，self-check 对
降级与禁连的负面断言覆盖扎实。阻断项仅 pair outcome 取值映射错位（P2-1）及其 self-check 取值
偏差（P3-1），二者同源（前端实现时后端 R4 `attempts` 投影尚未落地，pair_outcome 枚举基于
breakdown §3.3 schema 注释的旧猜测），修复机械、边界清晰、不动后端与合同。裁定 **REWORK**，
限缩于 `frontend/index.html` 与 `frontend/self-check.js` 两个允许文件。

---

当前 Session ID: unavailable（glm-5.2[1m] 经 Claude Code 运行，本会话未暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-frontend.md
本地北京时间: 2026-07-23 23:59:42 CST
下一步模型: bookkeeper
下一步任务: validate this Review-1 verdict and route ACCEPT to final Review-2 or REWORK to a bounded human-dispatched fix

---

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "glm-5.2[1m]",
  "verdict": "REWORK",
  "diff_fingerprint": "d873699d4c06f8dec343c9a6dcfa5fecc22d74b5:fd4e7a0a20c5c5dce3f7df8b6488cddfc0b33b245e731b2b8bea1325182a581d",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Reviewer is glm-5.2[1m] (zhipu_glm). It is the same provider/model as the BACKEND implementer and the R4 fix author, but this review reviews only the FRONTEND task (Task B, owner=Kimi, kimi-k3); frontend implementer Kimi and reviewer Claude-GLM are provider-isolated per the review-1 cross-review rule. glm-5.2[1m] also submitted a direction-panel draft (direction-drafts/glm52.md), which is a panel draft, not direction synthesis / breakdown / design; the schema's three decision-involvement categories did not occur for this reviewer, hence 'none', consistent with the immutable dispatch instruction.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "agents/developer-discipline.md",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/05-cadence-resolution.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/06-direction-synthesis.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/13-r4-diff-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/14-r4-verification.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-backend-r4.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/task-B-kimi.prompt.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "frontend/index.html",
    "frontend/self-check.js",
    "git diff d90f2f18acec7fe6286f2ae3fc8e187580bf0793..d873699d4c06f8dec343c9a6dcfa5fecc22d74b5 -- frontend/index.html",
    "git diff d90f2f18acec7fe6286f2ae3fc8e187580bf0793..d873699d4c06f8dec343c9a6dcfa5fecc22d74b5 -- frontend/self-check.js",
    "backend/hedge_open_tasks/service.py (attempt_to_doc/_leg_to_doc, read-only cross-check)",
    "backend/hedge_open_tasks/domain.py (pair_outcome value set, read-only cross-check)",
    "backend/hedge_open_tasks/store.py (pair_outcome write sites, read-only cross-check)"
  ],
  "findings": [
    {
      "severity": "P2",
      "title": "pair outcome 标签映射与后端真实取值集错位：single_leg 缺失、querying 为死映射、null（查询中）误显示为「—」",
      "file": "frontend/index.html",
      "line": 3278,
      "evidence": "后端 pair_outcome 取值集为 null（未解析/查询中）/accepted_pair/confirmed_failed/single_leg：domain.py:139-142 定义 PAIR_ACCEPTED/PAIR_CONFIRMED_FAILED/PAIR_SINGLE_LEG；store.py:611-619 _apply_task_counters 按两腿 acceptance 写入三者之一并经 store.py:737-739/820-821 落库；service.py:192 attempt_to_doc 直接透传 attempt['pair_outcome']；未解析 attempt 投影为 null（40-fix-backend-r4.md §2.3 第二例）。前端 HEDGE_PAIR_OUTCOME_LABELS（index.html:3278-3281）仅收录 accepted_pair/confirmed_failed/querying，未收录 single_leg；renderHedgeAttemptCard（index.html:3818-3820）outcomeLabel = pair_outcome ? (LABELS[pair_outcome]||String(pair_outcome)) : '—'。",
      "impact": "后端投影 single_leg（恰好一腿 accepted，ADR-3 明确认可、需人眼监督的单腿敞口状态）时前端显示英文 key 'single_leg' + muted 徽标，操作者无法识别；querying→'查询中' 为死映射（后端从不发 querying 字符串），后端用 null 表示查询中而前端把 null 显示为 '—'，故合同意图的「查询中」徽标永不显示，操作者无法从徽标区分在途查询中的 attempt。",
      "recommendation": "在 HEDGE_PAIR_OUTCOME_LABELS/HEDGE_PAIR_OUTCOME_BADGE 收录 single_leg 中文标签与徽标色；将 pair_outcome===null 映射为「查询中」徽标而非 '—'；querying 映射可保留或移除。仅触及标签常量与 renderHedgeAttemptCard 的 outcome 取值分支，不动后端与合同。"
    },
    {
      "severity": "P3",
      "title": "self-check mock 的 pair_outcome 取值偏离后端真实形状（测了不会发生的 querying，未测会发生的 single_leg）",
      "file": "frontend/self-check.js",
      "line": 3857,
      "evidence": "断言 85 的 attemptB 使用 pair_outcome:'querying' 断言「查询中」徽标；但后端取值集为 null/accepted_pair/confirmed_failed/single_leg（见 P2-1），不含 querying；mock 亦未覆盖 single_leg。",
      "impact": "self-check 对 attempt 徽标路径给出假阳性覆盖信心——测了一个后端不会产生的取值，未测后端会产生的 single_leg，削弱评审重点 4「self-check 覆盖真实接口形状」。",
      "recommendation": "mock/断言对齐 domain.py 取值集：在途用例改用 pair_outcome:null 并断言「查询中」渲染（P2-1 修复后）；新增 single_leg 用例断言中文标签渲染。"
    },
    {
      "severity": "P3",
      "title": "extractHedgeAttempts 多数组合并无去重，存在理论重复渲染风险",
      "file": "frontend/index.html",
      "line": 3784,
      "evidence": "[doc.attempts, doc.fills, doc.logs, doc.entries].forEach 把各数组 attempt-shaped 条目 push 进同一 out，不按 attempt_id 去重。当前后端 get_logs 仅返回 attempts 且 logs 为 record-transport（非 attempt 形状被忽略），故当前无重复。",
      "impact": "若后端契约演进在多个候选键下投影同一批 attempt（或 logs[].payload 内嵌 attempt），时间线会重复渲染同一 attempt。当前不触发。",
      "recommendation": "命中 doc.attempts 后即返回，或按 attempt_id 去重。优先前者。"
    },
    {
      "severity": "P3",
      "title": "attempt_id 被提取但未用于渲染或去重",
      "file": "frontend/index.html",
      "line": 3793,
      "evidence": "normalizeHedgeAttempt 提取 attempt_id，但 renderHedgeAttemptCard 仅展示 attempt_seq（「第 N 组」），既不渲染 attempt_id 也不用作去重键。",
      "impact": "无功能缺陷；已读字段未充分利用。",
      "recommendation": "可选——用于 P3-2 去重或以 mono 小字展示便于与后端日志对账。非阻断。"
    },
    {
      "severity": "P3",
      "title": "attempt 时间线 ?limit=100 仅取首页，无分页/加载更多",
      "file": "frontend/index.html",
      "line": 3807,
      "evidence": "loadHedgeAttempts 固定请求 /api/hedge-open-logs?limit=100；后端 next_cursor 跟踪 logs（legacy），attempts 无独立 cursor（40-fix-backend-r4.md §6.1 有意选择）。",
      "impact": "超过 100 条的更早 attempt 不展示（实现报告 §6 已披露）。已知限制。",
      "recommendation": "记为后续增量；当前可接受。"
    }
  ],
  "required_fixes": [
    "（P2-1，必须）在 frontend/index.html 的 HEDGE_PAIR_OUTCOME_LABELS/HEDGE_PAIR_OUTCOME_BADGE 收录 single_leg 中文标签与徽标色；将 renderHedgeAttemptCard 中 pair_outcome===null 映射为「查询中」徽标而非 '—'；不动后端、不动 API 合同、不引入 JS 浮点。",
    "（P3-1，必须）在 frontend/self-check.js 将断言 85 的在途用例 pair_outcome 改为 null 并断言「查询中」渲染，新增一个 single_leg 用例断言其中文标签渲染；移除对后端不产生的 querying 取值的断言依赖。",
    "（P3-2，建议）在 frontend/index.html 的 extractHedgeAttempts 命中 doc.attempts 后即返回或按 attempt_id 去重，消除多键重复风险。"
  ],
  "residual_risks": [
    "信封宽容提取依赖后端当前仅在 attempts 键投影 attempt；后端契约若演进需配合 P3-2 去重。",
    "旧 leg_exposure 文案「任务已暂停」与新合同「单腿敞口不阻断调度」存在语义张力（advisory，实现报告已披露），是否修订文案由后续 review/产品裁定，非本前端任务范围。",
    "?limit=100 无分页，超过 100 条 attempt 不展示。",
    "本评审为静态源码核对 + self-check mock，未执行真实浏览器-后端集成；extractHedgeAttempts 与 attempt_to_doc 的字段对齐建议集成期按后端真实落库形状复核一次。"
  ],
  "fix_start_prompt": "[HARNESS-EXECUTOR-CONTRACT v1]\n你是本修复任务的唯一执行者。\n1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于 claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时输出 ESCALATED 及原因并停止。\n2. 禁止编造未实际执行的命令结果或未实际读取的文件内容。\n3. 你的修复依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的文件。\n\n你是 Task B（前端，owner=Kimi）的 Review-1 REWORK 修复者。这是 Review-1 裁定 REWORK 后的有界修复，仅修 pair outcome 取值映射与对应 self-check，不改后端、不改 API 合同、不扩大范围。\n\n当前分支：stage/2026-07-hedge-open-real-api-v1。审查锚点 frontend diff：d90f2f18acec7fe6286f2ae3fc8e187580bf0793..d873699d4c06f8dec343c9a6dcfa5fecc22d74b5。\n\n先阅读（raw artifact 路径）：\n- AGENTS.md、agents/developer-discipline.md；\n- reports/agent-runs/2026-07-hedge-open-real-api-v1/{00-task.md,10-design.md,11-adr.md,12-development-breakdown.md,20-implementation-frontend.md,30-review-1-frontend.md,40-fix-backend-r4.md}；\n- frontend/index.html、frontend/self-check.js。\n\n允许改动仅限：\n- frontend/index.html\n- frontend/self-check.js\n- reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md（追加 R-fix 修复段落，或按 bookkeeper 指示另写 fix 报告）\n\n禁止改动：所有 backend/**、docs/**、status.json、70-handoff.md、API contract、环境/凭据文件和任何其他路径。不得发明后端字段；后端取值集以 backend/hedge_open_tasks/domain.py:139-142 为准（只读核对，不得改后端）。\n\nReview-1 发现与证据（逐条）：\n- P2-1（必须修）：前端 HEDGE_PAIR_OUTCOME_LABELS/HEDGE_PAIR_OUTCOME_BADGE（frontend/index.html 约 3278 行）仅收录 accepted_pair/confirmed_failed/querying，但后端 pair_outcome 真实取值集为 null（未解析/查询中）/accepted_pair/confirmed_failed/single_leg（backend/hedge_open_tasks/domain.py:139-142；store.py:611-619 写入；service.py:192 透传；未解析 attempt 投影为 null，见 40-fix-backend-r4.md §2.3）。后果：single_leg（ADR-3 单腿敞口状态）显示英文 key；querying→「查询中」是死映射；后端用 null 表示查询中而前端把 null 显示为「—」，合同意图的「查询中」徽标永不显示。\n- P3-1（必须修）：frontend/self-check.js 断言 85（约 3857 行）的 attemptB 用 pair_outcome:'querying'，后端不产生此取值；mock 未覆盖 single_leg。\n- P3-2（建议修）：extractHedgeAttempts（frontend/index.html 约 3784 行）多数组合并无去重。\n\n必须完成的修复：\n1. 在 HEDGE_PAIR_OUTCOME_LABELS 收录 single_leg（建议中文「单腿成交」，徽标色建议 warning）；在 HEDGE_PAIR_OUTCOME_BADGE 收录对应徽标。\n2. 修改 renderHedgeAttemptCard 的 outcome 取值逻辑：pair_outcome===null（后端在途/查询中）映射为「查询中」徽标（info），而非「—」；保留 hedgeText 对其它真正缺失字段的「—」语义。\n3. 更新 frontend/self-check.js 断言 85：把在途用例 pair_outcome 改为 null 并断言其渲染「查询中」徽标；新增一个 single_leg 用例（mockHedgeAttempt pair_outcome:'single_leg'）断言其渲染中文标签；移除对 querying 取值的断言依赖（querying 映射可保留为无害冗余或删除）。\n4.（建议）extractHedgeAttempts 命中 doc.attempts 后即返回，或按 attempt_id 去重。\n\nDecimal 纪律不变：所有数值仍走 hedgeText 原样展示，不得引入 JS 浮点格式化。不得新增签名/调度/定时器/POST/Binance 直连；不得暗示前端可开启 live。\n\n必须实际执行并如实记录：\nnode frontend/self-check.js\n\n验收条件（全部满足才算完成）：\n- node frontend/self-check.js 全部断言 PASS，退出码 0；\n- 断言覆盖：single_leg 渲染中文标签；pair_outcome===null 渲染「查询中」徽标；accepted_pair/confirmed_failed 仍正确；缺腿/空态/503 降级不回归；\n- fetch 同源白名单、零 Binance/外域、零新定时器、localStorage 白名单断言仍 PASS；\n- git diff --stat 仅触及 frontend/index.html 与 frontend/self-check.js（及实现报告）；未改 backend/**、docs/**、status.json、70-handoff.md。\n\n完成后将完整修复报告追加到 reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md（或按 bookkeeper 指示的 fix 报告路径），含：实际改动文件、实际执行命令与原样结果、mock/断言变更、验收对照。报告末尾带 footer（时间用本机 date 取得）。然后停止，等待 bookkeeper；不要 commit、不要改 status.json、不要派发或评审其他模型。\n\n当前 Session ID: report provider-native ID, or unavailable with reason\nSession ID 来源: runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable\n原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/20-implementation-frontend.md\n本地北京时间: obtain from local date command\n下一步模型: bookkeeper\n下一步任务: collect the bounded frontend REWORK fix report, rerun node frontend/self-check.js, recompute fingerprint, and re-enter review",
  "next_action": "fix"
}
```
