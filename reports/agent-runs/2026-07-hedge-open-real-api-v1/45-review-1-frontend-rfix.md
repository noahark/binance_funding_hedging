# Review-1 Frontend 返工复审（rfix）— Hedge Open Real API v1

> 评审者：Claude-GLM（`glm-5.2[1m]`，经 Claude Code 访问，provider = `zhipu_glm`）。
> 角色：正式 Review-1 前端交叉评审者（`role=first_reviewer`），本次为前次 REWORK 裁定后的**有界返工复审**。
> 修复作者：Claude Sonnet 5（Anthropic provider，用户指定的前端 fallback 修复者）。修复作者 Sonnet 5 与
> 复审者 glm-5.2[1m] provider 隔离成立（Anthropic ↔ zhipu_glm），满足 review-1 cross-review 规则。
> 审查模式：只读。本会话未修改任何源码、后端、`status.json`、`70-handoff.md`、前端文件、API 合同或任何
> 其他路径；未 git commit；未调用/转派任何其他模型会话；未发起任何真实 Binance 网络、私有或 POST 请求。
> 唯一写出的产物是本复审文件本身（dispatch 指定的 `outputs` 路径）。唯一执行的命令是只读自检
> `node frontend/self-check.js`（不写文件、不联网）与只读 `git`/`grep` 核对命令。
> 审查锚点：frontend 返工 diff `d873699d4c06f8dec343c9a6dcfa5fecc22d74b5..820dd1e`（修复 commit `820dd1e`
> 「fix(hedge): clarify attempt timeline states」）。

## 0. Provider 与参与披露

- 本复审者 `glm-5.2[1m]` / `zhipu_glm` 与本 stage 的**后端**实现者及 R4 fix 作者同 provider 同模型，但
  本次复审**不评审后端**，只复审前端返工（Task B，owner=Kimi；返工修复者 Sonnet 5）。返工修复作者
  Sonnet 5 与复审者 provider 隔离，满足 review-1 cross-review 规则。
- `glm-5.2[1m]` 亦为本 stage 前次 Review-1 前端评审者（`30-review-1-frontend.md`），并曾作为 direction
  panel 成员提交独立方向稿 `direction-drafts/glm52.md`（panel draft，非方向综合 / breakdown / design）。
  本复审者未参与 `06-direction-synthesis.md`（综合，Codex）、`12-development-breakdown.md`（Opus 4.8）
  或 `10-design.md`/`11-adr.md`（Codex）。schema 三类决策性参与（direction_synthesis / breakdown /
  design）均未发生，故 `reviewer_prior_involvement=none`，与 immutable dispatch 指示一致。「同一模型复审
  自己此前的 review」属 review 行为延续，非 schema 三类决策参与，亦非实现/fix 作者身份（fix 作者为
  Sonnet 5），不构成 review-1 的 hard ban。
- 评审依据：本 prompt 列出的 raw artifact 路径与本会话实际读取的文件（见 verdict `reviewed_artifacts`）。
  后端 `domain.py`/`service.py`/`store.py` 仅用于核对"前端消费的 pair_outcome 真实取值集与投影路径"，
  全程 read-only，未修改任何字节。

## 1. 简洁叙述

前次 Review-1（`30-review-1-frontend.md`）就前端 pair outcome 取值映射裁定 **REWORK**，必须项 P2-1
（`single_leg` 中文标签 + 徽标缺失；`pair_outcome===null` 误显示为「—」而非「查询中」）与 P3-1
（self-check mock 用后端不产生的 `querying` 取值、未覆盖 `single_leg`），建议项 P3-2（`extractHedgeAttempts`
多键合并无去重）。返工修复 commit `820dd1e` 在 `frontend/index.html`（+9/-8 实质行）与
`frontend/self-check.js`（+12/-6 实质行）落地了全部修复，并顺带落实建议项 P3-2。

核对结论：**三项必须项与一项建议项全部正确落实，无回归、无范围外改动、无新缺陷**。具体地：

- `HEDGE_PAIR_OUTCOME_LABELS`/`HEDGE_PAIR_OUTCOME_BADGE` 收录 `single_leg:'单腿成交'`/`'warning'`
  （index.html:3276/3279），后端 `domain.py:142 PAIR_SINGLE_LEG` 经 `store.py:616-619` 落库、
  `service.py:192` 透传，前端能正确把单腿敞口渲染为中文「单腿成交」+ warning 徽标。
- `renderHedgeAttemptCard`（index.html:3821-3826）改为 `pair_outcome===null ? '查询中'/'info' : 查表`；
  `normalizeHedgeAttempt`（index.html:3776）已把 `undefined` 归一为 `null`，故归一化后 `pair_outcome` 只
  会是 `null` 或后端真实字符串枚举，`=== null` 判断精确覆盖后端"未解析/查询中"语义，不会误伤真正缺失
  字段（`hedgeText` 对其它字段的「—」语义未改）。后端"查询中"确实投影为 `null`（`service.py:178-179`
  docstring 明确 unresolved→`pair_outcome=None`；`store.py:605` 默认 None 且 `_apply_task_counters` 只在
  finalize 时写 `accepted_pair/confirmed_failed/single_leg` 三者之一，**从不写 `querying` 字符串**）。
- self-check `attemptB` 的 `pair_outcome` 由后端不产生的 `'querying'` 改为真实的 `null`，新增
  `attemptC={pair_outcome:'single_leg'}`，提取计数 2→3，断言列表补「第 3 组/单腿成交/0.00000200」；
  缺腿降级、空态、503、同源白名单、零 Binance/外域、零新定时器、localStorage 白名单断言全部保留并 PASS。
- 建议项 P3-2 落实为 `extractHedgeAttempts`（index.html:3787）`Array.isArray(doc.attempts) ? [doc.attempts]
  : [doc.fills, doc.logs, doc.entries]`：有 `doc.attempts` 时只消费它，缺失才回退三键，与旧行为等价、
  不破坏兼容性（self-check mock 走 `logs` 回退分支，仍正确提取 3 条）。

本会话实际执行 `node frontend/self-check.js`：退出码 **0**，**111 个 [PASS] / 0 个 [FAIL]**，末行
「全部自检通过」。无新缺陷。裁定 **ACCEPT**。

## 2. 逐条核对（对照 dispatch 必须项 / 建议项）

### 必须项 1 — `single_leg` 显示中文「单腿成交」+ warning 徽标 ✅

- diff（index.html:3276/3279）：`HEDGE_PAIR_OUTCOME_LABELS` 新增 `single_leg:'单腿成交'`；
  `HEDGE_PAIR_OUTCOME_BADGE` 新增 `single_leg:'warning'`。
- 后端真值核对：`domain.py:142 PAIR_SINGLE_LEG="single_leg"`；`store.py:616-619` 在
  `ATTEMPT_SINGLE_LEG_EXPOSURE` 分支写入 `PAIR_SINGLE_LEG`（ADVISORY，§4.5，不动计数器、不冻结调度）；
  `service.py:192 attempt_to_doc` 直接透传 `attempt.get("pair_outcome")`。字段链一致，前端能消费。
- self-check 覆盖：`attemptC`（pair_outcome:'single_leg'）加入 `logs` 数组，断言时间线含「单腿成交」。
- 验证：self-check PASS（111/0）。

### 必须项 2 — `pair_outcome===null` 显示「查询中」+ info 徽标，而非「—」 ✅

- diff（index.html:3821-3826）：
  `outcomeLabel = attempt.pair_outcome === null ? '查询中' : (LABELS[pair_outcome] || String(pair_outcome))`；
  `outcomeBadge = attempt.pair_outcome === null ? 'info' : (BADGE[pair_outcome] || 'muted')`。
- `=== null` 可靠性：`normalizeHedgeAttempt`（index.html:3776）`pair_outcome: src.pair_outcome !== undefined
  ? src.pair_outcome : null` 把 `undefined`→`null`，归一化后该字段只会是 `null` 或字符串，`=== null` 精确
  覆盖后端"未解析/查询中"，不误伤其它字段的 `hedgeText`「—」缺失语义。
- 后端"查询中"= null 的真值核对：`service.py:177-179` docstring 明确 unresolved
  （PREPARED/UNKNOWN_QUERYING/ACCEPTED_OR_QUERYING）attempt 投影 `pair_outcome=None`；
  `store.py:605` `pair_outcome: str | None = None` 默认 None，`_apply_task_counters`（store.py:607-619）只在
  `finalize_attempt` reconcile 时写 `accepted_pair/confirmed_failed/single_leg` 三者之一，**无 `querying`
  写入分支**；`PAIR_QUERYING`（domain.py:141）仅是描述状态机的文档性枚举，store 层从不持久化。故前次
  review P2-1「querying 是死映射、后端用 null 表示查询中」论断成立，修复方向正确。
- self-check 覆盖：`attemptB`（pair_outcome:null）断言「查询中」渲染。
- 验证：self-check PASS（111/0）。
- 附带健壮性（优点，非缺陷）：修复**保留**了 `querying:'查询中'`/`'info'` 映射。虽然 store 层当前不写
  `querying` 字符串，但 `domain.py` 定义了该枚举；保留映射使前端对 `null` 与未来可能的 `"querying"` 字符
  串两种"查询中"表示都正确渲染，属防御性健壮，而非冗余。

### 必须项 3 — self-check 覆盖两个真实状态，保留缺腿/空态/503/同源/禁连 Binance 保护 ✅

- diff（self-check.js）：`attemptB.pair_outcome` `'querying'`→`null`；新增 `attemptC`（single_leg）；
  提取计数 `!== 2`→`!== 3`；断言列表补「第 3 组/单腿成交/0.00000200」。
- 保留项核对（self-check.js 未改动的既有断言块，本会话实跑确认 PASS）：
  - 缺腿降级：`attemptB.perp = null` → 现货腿订单号 `—`（断言块「attempt 时间线」PASS）。
  - 空态 + 503 错误横幅 + 恢复（断言块「attempt 时间线降级」PASS）。
  - 同源白名单、零 Binance/外域、零新任务定时器、localStorage 白名单（仅隐私键）（末断言块 PASS）。
  - `accepted_pair`/`confirmed_failed`（`attemptA` 默认 `accepted_pair`，断言「已受理」仍在列表）未删。
- 验证：self-check 111 [PASS] / 0 [FAIL]，退出码 0。

### 建议项 — 去重不破坏现有兼容性（有 `doc.attempts` 只消费它，否则回退） ✅

- diff（index.html:3787）：`const sources = Array.isArray(doc.attempts) ? [doc.attempts] :
  [doc.fills, doc.logs, doc.entries];`
- 兼容性：`doc.attempts` 存在时只扫它（消除多键重复风险）；缺失时回退 `fills/logs/entries`（与旧逻辑等价）。
  self-check mock 在 `logs` 键下投影（无 `attempts` 键），走回退分支，仍正确提取 3 条 attempt（含 `payload`
  内嵌的 attemptB、直接 attempt 形状的 attemptA/attemptC），非 attempt 日志条目（scheduler tick）仍被
  `isHedgeAttemptShaped` 忽略。行为未回归。

## 3. Findings

无新缺陷。本次复审为对已修复代码的有界核对，三项必须项（P2-1/P3-1）与建议项（P3-2）均已正确落实，
self-check 全绿，未引入浮点 / 签名 / 调度 / 定时器 / POST / Binance 直连，未触及 backend/docs/合同/
status.json/70-handoff.md。findings 为空。

## 4. 证据

### 4.1 指纹验证（本会话独立计算，匹配 dispatch task fingerprint）

```text
$ HEAD_FULL=$(git rev-parse 820dd1e)  # 820dd1ec88f0d2727bb0bd3cd06bc28d6c4afc55
$ git diff --binary d873699d4c06f8dec343c9a6dcfa5fecc22d74b5..820dd1e -- . \
    ':(exclude)reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json' | shasum -a 256
820dd1ec88f0d2727bb0bd3cd06bc28d6c4afc55:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b
```

与 dispatch task fingerprint `820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b`
（短 head 前缀 + 完整 sha256）一致。`820dd1e` 确为当前 HEAD（`a4b9061`）的祖先。

### 4.2 diff 范围（仅前端两文件 + 证据文档，无 backend/docs/合同改动）

```text
$ git diff --stat d873699d4c06f8dec343c9a6dcfa5fecc22d74b5..820dd1e -- frontend/index.html frontend/self-check.js
 frontend/index.html    | 17 +++++++++-------
 frontend/self-check.js | 18 ++++++++++++------
```

完整 stage diff 另含 `reports/agent-runs/2026-07-hedge-open-real-api-v1/` 下证据文档（fix 报告、review、
handoff、status.json 等，均 bookkeeper 证据，不在前端代码审查范围）。`backend/**`、`docs/**`、API 合同
零改动。

### 4.3 self-check 实跑结果（本会话真实执行）

```text
$ node frontend/self-check.js ; echo "EXIT_CODE=$?"
...（前置区块全部 [PASS]）...
[PASS] 任务卡 real-api-v1 新字段：调度/受理/连续失败/阈值渲染 + 暂停原因 + 旧文档逐项降级 —
[PASS] attempt 时间线：logs 取数 + 两腿字段逐字渲染 + payload 内嵌兼容 + 非 attempt 忽略 + 缺腿降级
[PASS] attempt 时间线降级：空态 + 503 错误横幅 + 恢复
[PASS] 开单 API 全部同源、零跨域 fetch
[PASS] fetch 同源白名单（含开单 §3 路由）、零 Binance/外域、零新任务定时器、localStorage 白名单（仅隐私键）
全部自检通过
EXIT_CODE=0
```

断言计数：**111 个 [PASS] / 0 个 [FAIL]**，退出码 0。新增/修改后的 attempt 时间线断言（single_leg +
null→查询中 + 计数 3）与既有缺腿/空态/503/同源/禁连断言均 PASS。

### 4.4 后端 pair_outcome 取值集核对（read-only，核对前端消费的状态取值）

- `backend/hedge_open_tasks/domain.py:139-148`：`PAIR_ACCEPTED/PAIR_CONFIRMED_FAILED/PAIR_QUERYING/
  PAIR_SINGLE_LEG` 四枚举；注释（行 132-138）说明单腿 acceptance 解析为 `single_leg`（ADVISORY）。
- `backend/hedge_open_tasks/store.py:605-619`：`pair_outcome` 默认 `None`；`_apply_task_counters` 仅在
  `ATTEMPT_SUCCESS/ATTEMPT_FAILED/ATTEMPT_SINGLE_LEG_EXPOSURE` 三分支写
  `PAIR_ACCEPTED/PAIR_CONFIRMED_FAILED/PAIR_SINGLE_LEG`，**无 `PAIR_QUERYING` 写入分支**；该方法只在
  `finalize_attempt`（reconcile-time）调用。故落库值 ∈ {None, accepted_pair, confirmed_failed, single_leg}。
- `backend/hedge_open_tasks/service.py:171-197`：`attempt_to_doc` 直接透传
  `attempt.get("pair_outcome")`；docstring（行 177-179）明确 unresolved attempt 投影 `pair_outcome=None`。
- 结论：前端消费的 pair_outcome 真实取值集 = `null/accepted_pair/confirmed_failed/single_leg`，与修复后
  的前端标签/徽标/分支逻辑精确对齐；`querying` 字符串不落库，前端保留其映射为防御性冗余（无害）。

## 5. 遗留风险（residual_risks，均为非阻断观察项，dispatch 明确不作为本次返工要求）

- P3-3（前次观察项）：`attempt_id` 被 `normalizeHedgeAttempt` 提取但未用于渲染或去重（P3-2 已用
  `doc.attempts` 优先返回消除主要重复风险，按 `attempt_id` 去重仍可选）。非阻断。
- P3-4（前次观察项）：`?limit=100` 仅取首页，无分页/加载更多；超 100 条的更早 attempt 不展示
  （实现报告 §6 已披露）。非阻断，已知限制。
- P3-5（前次观察项）：交易所 leg `status`（FILLED/NEW/PARTIALLY_FILLED/…）原样英文展示，未做中文映射；
  合同未要求翻译交易所状态。非缺陷。
- 集成期建议：本复审为静态源码核对 + self-check 实跑，未执行真实浏览器-后端集成；`extractHedgeAttempts`
  与 `attempt_to_doc` 字段对齐建议集成期按后端真实落库形状复核一次（实现报告 §6 风险 1 已提示）。

## 6. 总体结论

返工修复 commit `820dd1e` 在 `frontend/index.html` 与 `frontend/self-check.js` 两个允许文件内，正确、
最小、无回归地落实了前次 Review-1 的全部必须项（P2-1：`single_leg`→「单腿成交」+ warning；
`pair_outcome===null`→「查询中」+ info 而非「—」；P3-1：self-check 覆盖两个真实状态并保留缺腿/空态/
503/同源/禁连保护）与建议项（P3-2：有 `doc.attempts` 只消费它、否则回退，兼容性未破坏）。后端取值集
核对（domain.py/store.py/service.py，read-only）与前端逻辑精确对齐；self-check 实跑 111 [PASS] / 0 [FAIL]，
退出码 0；未触及 backend/docs/合同/status.json/70-handoff.md，未引入 JS 浮点、签名、调度、定时器、POST
或 Binance 直连。无新缺陷。dispatch 明确"不要把额外功能、分页、交易所状态翻译或后端修改作为本次返工
要求"，故 P3-3/P3-4/P3-5 观察项不构成阻断。裁定 **ACCEPT**，前端 Review-1 返工复审通过，交 bookkeeper
按"仅当两个 task 均被接受才进入 final review"的策略推进。

---

当前 Session ID: unavailable（glm-5.2[1m] 经 Claude Code 运行，本会话未暴露 provider-native Session ID）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/45-review-1-frontend-rfix.md
本地北京时间: 2026-07-24 12:17:25 CST
下一步模型: bookkeeper
下一步任务: validate this frontend rfix ACCEPT verdict and move to final review only if both tasks are accepted

---

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "glm-5.2[1m]",
  "verdict": "ACCEPT",
  "diff_fingerprint": "820dd1e:cd44c9a921e4f6bb21697c1a4c3ab776dc860b2791dd38b887cb5b7dc7f44c6b",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Reviewer is glm-5.2[1m] (zhipu_glm). It is the same provider/model as the BACKEND implementer and the R4 fix author, but this re-review reviews only the FRONTEND rework (Task B, owner=Kimi; rework fix author=Sonnet 5/Anthropic). Sonnet 5 and glm-5.2[1m] are provider-isolated (Anthropic vs zhipu_glm), satisfying review-1 cross-review. glm-5.2[1m] was also the prior review-1 frontend reviewer (30-review-1-frontend.md) and a direction-panel draft author (direction-drafts/glm52.md); both are review/panel-draft acts, not direction_synthesis (Codex) / breakdown (Opus 4.8) / design (Codex). The schema's three decision-involvement categories did not occur for this reviewer, hence 'none', consistent with the immutable dispatch instruction.",
  "reviewed_artifacts": [
    "AGENTS.md",
    "agents/developer-discipline.md",
    "schemas/review-verdict.schema.json",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/30-review-1-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-frontend-r1.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json",
    "frontend/index.html",
    "frontend/self-check.js",
    "git diff d873699d4c06f8dec343c9a6dcfa5fecc22d74b5..820dd1e -- frontend/index.html frontend/self-check.js",
    "backend/hedge_open_tasks/domain.py (PAIR_* outcome enum set, read-only cross-check)",
    "backend/hedge_open_tasks/service.py (attempt_to_doc pair_outcome projection, read-only cross-check)",
    "backend/hedge_open_tasks/store.py (_apply_task_counters pair_outcome write sites, read-only cross-check)"
  ],
  "findings": [],
  "required_fixes": [],
  "residual_risks": [
    "P3-3 (prior observation): attempt_id is normalized but unused for render/dedup; P3-2 already removed the main duplicate risk by returning on doc.attempts. Non-blocking.",
    "P3-4 (prior observation): ?limit=100 fetches only the first page with no pagination/load-more; attempts beyond 100 are not shown (implementation report §6 disclosed). Non-blocking known limit.",
    "P3-5 (prior observation): exchange leg status (FILLED/NEW/PARTIALLY_FILLED/...) is shown verbatim in English; contract does not require translating exchange status. Not a defect.",
    "Integration: this re-review is static source cross-check + self-check execution; no live browser-backend integration ran. Field alignment between extractHedgeAttempts and attempt_to_doc is recommended to be re-confirmed against real persisted shapes during integration (implementation report §6 risk 1 noted)."
  ],
  "next_action": "continue"
}
```
