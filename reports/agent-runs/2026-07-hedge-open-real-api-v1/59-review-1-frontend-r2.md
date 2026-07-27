# Review-1 前端审查（r2） — 2026-07-hedge-open-real-api-v1

<!-- ===== DISPATCH RECEIPT（执行者/记账者填写） =====
status: completed
target_model: claude_glm/glm-5.2[1m]
adapter_cmd:
executor: claude_glm
started_at: 2026-07-24 21:24 CST
completed_at: 2026-07-24 22:02 CST
session_id: unavailable:Codex/Claude-Code runtime 不暴露 provider-native Session ID
outputs: reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md
next_dispatch: bookkeeper
===== END RECEIPT ===== -->

## 0. 审查身份与隔离披露

- 审查者：Claude-GLM（zhipu_glm），model id `glm-5.2[1m]`。
- 被审前端代码的实现/返工作者：Claude Sonnet 5（Anthropic）。provider 隔离成立（GLM ≠ Anthropic），满足
  `workflows/templates/stage-delivery.yaml` Review-1 的 `reviewer_provider_must_differ_from_implementer_provider`。
- 会话：全新只读 session，仅做阅读 + 只读核对 + 独立运行只读测试。**未**调用/启动/转派任何其他模型会话或 adapter；
  **未**修改任何文件、**未** commit、**未**读取凭据、**未**连接 Binance、**未**发送任何真实 POST、**未**启用 live/Start。
- prior involvement：本次被审前端的 direction synthesis / development breakdown / design 我（Claude-GLM）**未参与**。
  我曾编写本 stage 的**后端**，但后端业务正确性不在本轮前端审查范围；本轮我仅在后端 `/api/hedge-open-logs`
  响应字段做**只读核对**（审查重点 3 的契约对照），不审后端业务正确性。故 `reviewer_prior_involvement = "none"`，
  并如实说明“曾写后端、未写被审前端”。

## 1. 审查锚点（不移动 HEAD，与 dispatch 逐字一致）

- base: `28c550d87c1ca90983d5bde9c7102d42cffecd4e`
- head: `8af3f22d92354fdac61a6a057eb25760b924004b`
- diff_fingerprint（**独立计算逐字 MATCH**）：
  `git diff --binary 28c550d..8af3f22 -- . ':(exclude)reports/agent-runs/2026-07-hedge-open-real-api-v1/status.json' | shasum -a 256`
  = `8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320`
  与 dispatch 给定值逐字相等。
- 前端改动范围（diff --stat）：`frontend/index.html`（+389 行）、`frontend/self-check.js`（+592 行），仅这两个文件。

## 2. 审查方法与实际阅读

**实际阅读的契约与上下文**：`AGENTS.md`；`workflows/templates/stage-delivery.yaml`（Review-1 规则 L580–648）；
`docs/product/PRD.md`（§3/§6/§9.1/§9.2）；stage 的 `00-task.md`、`15-immediate-loop-and-open-log-amendment.md`、
`16-replacement-development-breakdown.md`（§4.2 Task B / §5 冻结 entries 契约）、`17-opening-log-pagination-compatibility.md`、
`19-replacement-r4-final-reconciliation.md`、`50-review-2.md`（finding 7 回归基准）、
`40-fix-review-2-frontend.md`、`41-fix-open-log-pagination-frontend.md`、`60-test-output.txt`；
`schemas/review-verdict.schema.json`。

**实际阅读的被审代码**：`frontend/index.html`（全文 4377 行，重点 §对冲开单 3290–4033、开单日志页 3918–4033、
事件绑定 4181–4259、`__appHelpers` 4266+）、`frontend/self-check.js`（全文 4397 行，重点 mock 契约 405–599、
断言 76/81/84/88/89/90/90b/91/92、同源白名单 4313–4388）、完整 `git diff 28c550d..8af3f22 -- frontend/`。

**后端只读核对**：`backend/app/server.py:85,561-575`（`_hedge_open_logs` 路由，仅 GET，解析 `entries_cursor`/`entries_limit`）、
`backend/hedge_open_tasks/service.py:539-574`（`get_logs` 返回 `logs/attempts/entries/next_cursor/entries_next_cursor`）、
`service.py:577-640`（`_entries_page`：`entries_next_cursor` 由本页 entries 统一排序位置派生，独立于 legacy cursor）。

**独立验证（只读，我亲自运行）**：
1. `node frontend/self-check.js` → **117 个 [PASS]，"全部自检通过"，exit 0**。
2. diff_fingerprint 独立 shasum 计算 → 逐字 MATCH（见 §1）。
3. `grep isHedgeTaskTerminated`（index.html / self-check.js）→ **0 命中**（上轮 finding 7 的硬编码终止推断已删）。
4. `grep "成功开单次数" / "fail_count > 3" / "/ 3"` → **无命中**（旧文案/硬编码阈值已清）。

> 说明：**未运行** `scripts/validate-stage.py --phase pre-review`。dispatch 最高契约（HARNESS-EXECUTOR-CONTRACT）
> 要求只读、禁止修改文件，而该脚本在 embedded pre-review 模式下会写 `status.json.session_receipts`
> （`validate-stage.py:690-714`）。改以「独立计算 fingerprint（MATCH）+ 独立运行 self-check（117 PASS）」作为等价完整性证据；
> `60-test-output.txt` 已含 bookkeeper 的 `phase=dispatch-ready` PASS 记录。

## 3. 逐项审查结论（对照 dispatch 5 个重点）

### 重点 1：计划次数 / 连续失败 / 暂停终止原因 / 按钮只服从后端任务文档，未硬编码阈值 — **符合**

- `target_n` 在市场表输入（`index.html:3520` "计划尝试次数"）、empty-state（3657）、任务卡（3704 "计划尝试次数"）均显示为
  **计划尝试次数**，无"成功开单次数"旧文案。`submitHedgeOpen` POST body 逐字 `{coin, direction, mode, single_amount, target_n}`（3568）。
- 连续失败/阈值直接读自后端任务快照字段：`consecutive_submission_failures` / `failure_pause_threshold`（`index.html:3691`）。
  self-check #84（`self-check.js:3958-3988`）刻意用 `failure_pause_threshold=5`（非默认 3）并断言"暂停阈值不应回退成前端硬编码的默认值 3"——
  证明展示直接来自后端，**无硬编码阈值**。
- `pause_reason` 仅做中文标签映射展示（`index.html:3692-3694` + `HEDGE_PAUSE_REASON_LABELS` 3316），未收录取值原样展示，前端不发明语义。
- `stop_reason` 原样展示（`index.html:3680-3681` "任务已终止（致命错误，不再补发）：…"）。
- 按钮矩阵全部从 `task.status` 派生（`index.html:3683-3687`）：`pauseDisabled = status!=='running'`、
  `startDisabled = status∉{paused,exposure_alert}`、`deleteDisabled = status==='deleted'`、`fillDisabled = inactive`。
  self-check #81（`self-check.js:3864-3886`）验证 running/paused/stopped 三态按钮可用性，并断言 paused 的 fill-once **不被前端额外禁用**
  （"后端 `_require_fillable` 只拦截 deleted/done，前端不得比后端更严格"）。invalid_state 409 → 就近中文报错（3888-3892）。
- `isHedgeTaskTerminated` 已整体删除（grep 0 命中），无 `>3`/`/3` 硬编码终止推断。**上轮 Review-2 finding 7 的前端项无回归。**

### 重点 2：single_leg/querying/stopped/paused 中文显示准确，缺字段安全降级为 `—` — **符合**

- 任务状态中文映射（`index.html:3295`）：running→运行、paused→暂停、stopped→已终止、done→完成、exposure_alert→敞口告警、deleted→已删除。
- `single_leg`：任务卡 `exposureLine`（`index.html:3674-3677`）按 `haltedByStatus` 分支——running 时显示
  "任务仍继续调度下一组，系统不自动对冲、不自动平仓"，**绝无**"任务已暂停"假称；仅当后端 status∈{paused,stopped} 才显示"暂不再补发"。
  attempt 卡片 pair_outcome=single_leg→"单腿成交"（`3311`），开单日志 overall_result=single_leg→"单腿成交"（`3323`）。
- `querying`：attempt 卡片 `pair_outcome===null`→"查询中"（`index.html:3872-3877`）；日志 overall_result=querying→"查询中" +
  next_action=waiting_query→"等待查询终态"（self-check #92, `self-check.js:4273-4298`）。
- `stopped`（致命终止）与 `paused`（连续失败/手动暂停）**分别渲染**：stopped 走 `stopReasonLine`（3680-3681）+ danger badge（3296），
  paused 走 `pauseReasonLine`（3692-3694）+ muted badge。self-check #81 三任务场景断言停止/暂停文案区分（3841-3843）。
- 缺字段安全降级：`hedgeText(v)`（`index.html:3337-3340`）null/undefined/''→`—`。旧后端文档缺 real-api-v1 新字段时
  `scheduled_attempt_count/accepted_pair_count/consecutive_submission_failures/failure_pause_threshold` 逐项降级为 `—`（self-check #84 3989-3994）。

### 重点 3：开单日志页只用 entries_limit/entries_cursor/entries_next_cursor，不误用旧 next_cursor，不拼重复 entry_id — **符合**

- `loadHedgeLogs`（`index.html:3978-3996`）：首屏 `path = /api/hedge-open-logs?entries_limit=${HEDGE_LOG_PAGE_LIMIT}`（3982，=50），
  加载更多追加 `&entries_cursor=${encodeURIComponent(cursor)}`（3983）；下一页游标只读
  `state.hedgeLogs.nextCursor = typeof doc.entries_next_cursor === 'string' ? doc.entries_next_cursor : null`（3988）。
  **旧 `doc.next_cursor` 在 entries 翻页路径上完全未被读取**（grep 确认 index.html 中 `next_cursor` 仅出现在借币日志 3194 与本行注释，开单日志路径无引用）。
- 非字符串/缺失 `entries_next_cursor` 安全降级为 null（`index.html:3988` 三元严格 `typeof ... === 'string'`），
  → 加载更多按钮隐藏（4011）且 `loadHedgeLogs(false)` 在无 cursor 时直接返回失败不发请求（3981）。self-check #90b（`self-check.js:4218-4244`）
  用 `entries_next_cursor=123`（非字符串）+ truthy 旧 `next_cursor='legacy-cursor-truthy-but-must-be-ignored'` 作诱饵，断言不回退。
- 不拼重复 entry_id：两页直接 `concat`（3987），self-check #90（`self-check.js:4191-4199`）用两页 fixture（page1=2 条、page2=1 条）
  断言合并后 3 条 `entry_id` 全唯一（`new Set(entryIds).size === entryIds.length`）+ newest-first 跨页保持。两页 fixture 刻意携带
  与 `entries_next_cursor` 不同的旧 `next_cursor`（`self-check.js:570-579`），证明翻页只采信 `entries_next_cursor`。
- 后端契约只读核对一致：`server.py:570-571` 读 `entries_cursor`/`entries_limit`；`service.py:565-573` 返回独立 `entries_next_cursor`，
  且 `_entries_page`（577-640）由本页 entries 统一排序派生，不从 legacy logs cursor 派生。前后端字段逐字对齐。

### 重点 4：任务内尝试时间线 ?limit=100、借币日志与其他原有页面被保留 — **符合**

- attempt 时间线 `loadHedgeAttempts`（`index.html:3849-3858`）→ `/api/hedge-open-logs?limit=100`（固定，无 cursor），self-check #85（`self-check.js:4036`）断言精确 URL。
- 该时间线读取对信封宽容（`extractHedgeAttempts` 3835-3847 扫描 attempts/fills/logs/entries），非 attempt 形状忽略，payload 内嵌兼容（3817-3819）。
- 借币日志（`loadBorrowLogs` 3184+，`?limit=50[&cursor=...]` 读 `next_cursor`）未被触碰，self-check 借币日志分页断言（#73, 3503）仍在。
- 其他原有页面保留：市场表 / 私有面板（含对冲开单持仓 §3.4 逐字）/ 借币任务 / 借币执行控制 / 抽屉年化历史 均在，未删除。

### 重点 5：self-check 覆盖真实交互、503/空态/分页/安全降级，无新增定时器/跨域请求/浏览器签名/前端直连交易所 — **符合**

- 我独立运行 `node frontend/self-check.js` → **117 [PASS]，全部通过**。覆盖：真实交互（任务动作按钮事件委托、创建 POST 冻结 body、
  insufficient_balance 弹框两路径、invalid_field/invalid_state 行内报错）；503（#91 4262-4264 日志、借币/持仓/执行各 503）；空态（#91 4254-4256）；
  分页（#88/#90/#90b entries 三件套 + entry_id 唯一 + 加载更多 + 显式刷新）；安全降级（#90b 非字符串游标、#89 缺腿/task_event 全 `—`、#84 旧文档逐项 `—`）。
- 同源白名单与零泄漏证明（self-check #76 `self-check.js:4313-4388`、#87 4301-4311）：全部 fetch URL 匹配白名单正则（含开单 §3 全部路由）、
  **零 Binance/绝对外域 URL**、**零新任务定时器**（intervalCalls 仅允许 60000 快照 / 1000 倒计时 / 2000 借币执行状态轮询；
  开单执行调度在后端，前端不注册任何开单定时器）、localStorage 白名单（仅 `funding_hedging_privacy_hidden`）。
- 无浏览器签名、无 WebSocket、无前端直连 Binance：`index.html` 全部开单路径走同源 `hedgeApi()`（3375-3393，相对路径 fetch），
  无 `XMLHttpRequest`/`sign(`/`HMAC`/`api.binance.com`。开单任务视图文案保留"浏览器不调度、不模拟、不签名、不请求 Binance"（1137）。

## 4. Findings

### P3-001 — attempt 时间线 single_leg 徽标 CSS 类名拼写不一致（warning vs warn），颜色样式缺失

- **文件/行**：`frontend/index.html:3314`
- **证据**：`HEDGE_PAIR_OUTCOME_BADGE = { accepted_pair: 'success', confirmed_failed: 'danger', single_leg: 'warning', querying: 'info' }`
  （3314），但 stylesheet 仅定义 `.badge.warn`（`index.html:229`），**未定义 `.badge.warning`**（228-231 仅有 success/warn/danger/info）。
  `renderHedgeAttemptCard`（3870-3894）用该映射渲染 attempt 时间线的单腿 outcome 徽标，产出 `<span class="badge warning">`，无匹配样式规则，
  回退到基础 `.badge`（灰白边框，无 warn 配色）。
- **影响**：仅 **attempt 时间线** 的 single_leg 状态徽标缺少黄/橙警示配色（视觉一致性瑕疵）。开单日志页的 single_leg 用的是
  `HEDGE_LOG_OVERALL_RESULT_BADGE.single_leg='warn'`（3327，正确），不受影响。不影响数据正确性、契约字段名、安全性或失败可见性。
- **背景**：此问题在前一轮 `40-fix-review-2-frontend.md`（§residual）已被识别并标注为"超范围未修"的已知项。
- **建议**：将 `index.html:3314` 的 `single_leg: 'warning'` 改为 `single_leg: 'warn'`，与 stylesheet 及其余 badge 取值一致。

无 P0 / P1 / P2 发现。5 个审查重点全部符合冻结契约，上轮 Review-2 前端 finding 7 无回归。

## 5. Verdict 决定

**ACCEPT。**

依据：前端 diff（`frontend/index.html` + `frontend/self-check.js`）逐项满足 dispatch 5 个审查重点与
`16-replacement-development-breakdown.md` §4.2 Task B / §5 冻结 entries 契约、`17-opening-log-pagination-compatibility.md` 5 条规则、
`15-immediate-loop-and-open-log-amendment.md` 开单日志页要求、PRD §3/§6/§9.2 业务契约。diff_fingerprint 独立验证逐字一致；
self-check 117 项独立运行全过；后端 logs 响应字段只读核对一致；回归点（isHedgeTaskTerminated 删除、硬编码阈值清除、旧文案清除）全部确认。

唯一发现 P3-001 为视觉一致性瑕疵、非阻塞、且为前一轮已记录的超范围已知项。按 `stage-delivery.yaml` Review-1 transitions
（`ACCEPT → review-2`），本次 ACCEPT 仅为放行至 Review-2，**非最终验收、不授权实盘**。

## 6. Residual Risks（供 Review-2 / bookkeeper 参考）

1. 开单日志 `loadHedgeLogs` 直接 `concat(entries)` 不做客户端 entry_id 去重（对齐借币日志 `loadBorrowLogs` 设计），依赖后端
   `entries_next_cursor` 正确性。self-check #90 证明两页 entry_id 全唯一；独立 `entries_cursor` 已消除"误用旧 next_cursor"这一根本重复源。
   若后端在并发写入下游标产生重叠，理论上前端会渲染重复条目，但本轮契约与测试未要求客户端去重。
2. `exposure_alert` 任务状态在前端 `HEDGE_TASK_STATUS_LABELS/BADGE`（3295-3296）与按钮矩阵（startDisabled 允许、fillDisabled 归 inactive）有处理，
   但 self-check 无专门渲染断言；属 dead-but-harmless（16-breakdown §5 未将其列为本轮必须状态）。
3. attempt 时间线/日志卡片 `leg.status`（交易所原值如 FILLED）按冻结契约"逐字展示后端字符串"逐字透传，未映射中文
   （符合 16-breakdown §5"Decimal/timestamps/字段逐字"契约，非缺陷）。
4. 未运行 `scripts/validate-stage.py --phase pre-review`（dispatch 禁止写文件，该脚本 embedded 模式会写 status.json.session_receipts）；
   以独立 fingerprint 计算（MATCH）+ 独立 self-check（117 PASS）作为等价完整性证据。

---

当前 Session ID: unavailable (Codex/Claude-Code runtime does not expose a provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/59-review-1-frontend-r2.md
本地北京时间: 2026-07-24 22:02 CST
审查者模型: claude_glm / glm-5.2[1m]
审查角色: first_reviewer（前端）
下一步模型: bookkeeper
下一步任务: validate the frontend Review-1 verdict and route it with the backend verdict

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-real-api-v1",
  "role": "first_reviewer",
  "model": "glm-5.2[1m]",
  "verdict": "ACCEPT",
  "diff_fingerprint": "8af3f22d92354fdac61a6a057eb25760b924004b:cbd0d92f53cbaaaab444812dd6ce5bd4bcc07aa947a923dd2a33014a74e5d320",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Claude-GLM (glm-5.2[1m]) did not participate in the reviewed frontend's direction synthesis, development breakdown, or design. GLM authored backend code for this stage, but backend business correctness is out of scope for this frontend Review-1; backend was used only for read-only cross-check of the /api/hedge-open-logs response fields (audit-focus item 3). Provider isolation holds (GLM != Anthropic; frontend implementer = Claude Sonnet 5).",
  "reviewed_artifacts": [
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "docs/product/PRD.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/15-immediate-loop-and-open-log-amendment.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/16-replacement-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/17-opening-log-pagination-compatibility.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/19-replacement-r4-final-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/50-review-2.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/40-fix-review-2-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/41-fix-open-log-pagination-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt",
    "frontend/index.html",
    "frontend/self-check.js",
    "git diff 28c550d..8af3f22 -- frontend/",
    "backend/app/server.py (read-only field cross-check)",
    "backend/hedge_open_tasks/service.py (read-only field cross-check)",
    "schemas/review-verdict.schema.json"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "attempt 卡片 single_leg 徽标 CSS 类名拼写不一致（warning vs warn）致颜色样式缺失",
      "file": "frontend/index.html",
      "line": 3314,
      "evidence": "index.html:3314 HEDGE_PAIR_OUTCOME_BADGE.single_leg='warning'，但 stylesheet 仅定义 .badge.warn（index.html:229），未定义 .badge.warning；renderHedgeAttemptCard(3870-3894) 用该映射产出 <span class=\"badge warning\"> 无匹配样式。开单日志页的 single_leg 用 HEDGE_LOG_OVERALL_RESULT_BADGE.single_leg='warn'(3327) 正确，不受影响。",
      "impact": "仅 attempt 时间线的 single_leg 状态徽标缺少 warn 配色（视觉一致性瑕疵），不影响数据正确性、契约字段名、安全性或失败可见性。前一轮 40-fix-review-2-frontend.md §residual 已标注为超范围未修的已知项。",
      "recommendation": "将 frontend/index.html:3314 的 single_leg: 'warning' 改为 single_leg: 'warn'，与 stylesheet（.badge.warn）及其余 badge 取值一致。"
    }
  ],
  "required_fixes": [
    "将 frontend/index.html:3314 HEDGE_PAIR_OUTCOME_BADGE.single_leg 由 'warning' 改为 'warn'，使 attempt 时间线单腿徽标获得与 stylesheet .badge.warn 一致的颜色样式（开单日志页已正确使用 'warn'，无需改动）。属 P3 视觉一致性，不阻塞 review-2，可在下一 fix 窗口顺带处理。"
  ],
  "residual_risks": [
    "开单日志 loadHedgeLogs 直接 concat(entries) 不做客户端 entry_id 去重（对齐借币日志 loadBorrowLogs 设计），依赖后端 entries_next_cursor 正确性；self-check #90 证明两页 entry_id 全唯一，独立 entries_cursor 已消除误用旧 next_cursor 的根本重复源。",
    "exposure_alert 任务状态在前端 LABELS/BADGE 与按钮矩阵有处理，但 self-check 无专门渲染断言；属 dead-but-harmless（16-breakdown §5 未列为本轮必须状态）。",
    "attempt 时间线/日志卡片 leg.status（交易所原值如 FILLED）按冻结契约逐字透传，未映射中文（符合 16-breakdown §5 逐字契约，非缺陷）。",
    "未运行 scripts/validate-stage.py --phase pre-review（dispatch 禁止写文件，该脚本 embedded 模式会写 status.json.session_receipts）；以独立 fingerprint 计算（MATCH）+ 独立 self-check（117 PASS）作为等价完整性证据。"
  ],
  "next_action": "continue"
}
```
