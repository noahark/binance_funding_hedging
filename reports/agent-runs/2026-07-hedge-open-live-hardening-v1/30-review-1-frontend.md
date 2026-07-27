# Review-1 — Frontend — Hedge Open Live Hardening v1

角色：`first_reviewer`（Grok 4.5，只读；用户为本 stage 显式启用 Grok 作 Review-1，见 `15-user-authorized-grok-review-1.md`）。
固定范围：`base_sha=6c5b17002cab189d752177b447ff576356998f58` → `head_sha=319d8317bdf180750197c95078d2ae6c60e6badc`；
`diff_fingerprint=319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd`（本地重算一致）。
前端 diff：`git diff 6c5b170..319d831 -- frontend/` → 仅 `frontend/index.html`（+132）与 `frontend/self-check.js`（+212）。
未评审后端 diff；跨 seam 消费面已对照源码与 `16-r4-diff-reconciliation.md` 做了只读抽查。
实现者报告与 R4 对账均按**被评审证据**对待；结论以 pinned diff 与源码为准。

---

## 逐条评审重点（12-breakdown §3 / dispatch 11 条）

### 1. S2 按钮条件严格性 — **PASS**

`frontend/index.html` `renderHedgeTaskCard` 中：

```js
const startDisabled = (
  task.status !== 'paused' &&
  task.status !== 'exposure_alert' &&
  !(task.status === 'running' && task.worker_active === false)
) ? ' disabled' : '';
```

与 `10-design.md` §2.2 表达式**逐字一致**。关键点是 `=== false`：
`null` / `undefined` 时第三分支恒为 false，running 卡仍 disabled。
dry-run（`worker_active === null`）与改前「仅 paused / exposure_alert 可点」语义一致。
self-check 段落 93 覆盖四象限：dry-run running disabled、live `worker_active:false` enabled、
live `true` disabled、paused enabled。

证据：`frontend/index.html:3793-3798`；`frontend/self-check.js` 段 93（PASS 文案「S2 running 卡启动按钮四象限」）。

### 2. S3 确认弹窗（零请求 / 取消 / 恰好一次 / 无手输确认词）— **PASS**

- 控件点击 → `requestHedgeStartGate`：只设 `state.hedgeGatePending` + `showHedgeConfirm`，**无 fetch**。
- 取消 → `cancelHedgeStartGate`：清 pending + `closeHedgeModal`，**零请求**。
- 确认 → `confirmHedgeStartGate`：读 pending 后清、关弹窗，再 `POST` 一次。
- 无手输确认词；双按钮变体（「取消」+ 动态确认词），「知道了」在确认态隐藏。
- 开/关同一控件 `hedge-start-gate-toggle`，方向取反 `!gateOn`，各方向一次确认。

证据：`index.html:3500-3537`、`3589-3603`、`4306-4310`；self-check 段 95。

### 3. S3 弹窗中文文案 — **PASS**（409 标题见 P3）

与 `10-design.md` §2.3 冻结文案逐字对照（生产代码字面量）：

| 方向 | 标题 | 正文 | 确认按钮 |
| --- | --- | --- | --- |
| 开 | 开启全局开单闸门？ | 开启后，实盘模式（live）下被启动的任务可以向币安发出真实订单。此操作立即生效。 | 确认开启 |
| 关 | 关闭全局开单闸门？ | 关闭后，任务的 worker 将在下一轮检查时退出，不再发出新订单；已提交的订单仍会继续查询到终态。 | 确认关闭 |

「取消」按钮固定文案。

**409 提示正文**冻结为「设置已被其他会话修改，已刷新，请重试」——生产与 self-check 均逐字。
设计**未冻结** 409 提示标题；实现者用中性「开单闸门变更」。可接受，记 P3（非 REWORK）。

证据：`index.html:3500-3505`、`3531`。

### 4. S3 version / 409 路径 — **PASS**

- POST body：`{ enabled, confirm: true, version }`，`version` 取 `state.hedgeSettings.version`。
- 409 `version_conflict`：`await loadHedgeSettings()` 再 GET 刷新 + 单按钮提示；**不自动再 POST**（self-check 断言 `postCount409 === 1`）。
- 无死循环弹窗：确认时先清 `hedgeGatePending` 并关确认弹窗，409 只开一次通知弹窗。

证据：`index.html:3515-3536`；self-check 段 95 body/version/409 分支。

### 5. S4a 展示 — **PASS**

八个退出原因与 `10-design.md` §2.4a 逐字：

| enum | 中文 |
| --- | --- |
| stopped_event | 收到停止信号 |
| task_missing | 任务记录缺失 |
| task_not_running | 任务已非运行态 |
| start_gate_off | 全局开单闸门未开启 |
| target_reached | 计划尝试次数已用完 |
| preflight_incomplete | 预检数据不完整（安全退出） |
| preflight_fatal | 预检发现致命问题 |
| worker_error | worker 异常退出 |

三态：`true`→运行中 / `false`→未运行 / `null`·缺失→—（`hedgeWorkerActiveText` 严格布尔）。
未知值 `String(v)` 原样（与 `hedgeText` 对非空值行为等价）；`null`/`undefined`/`''`→—。
展示行：`执行线程：… · 上次退出原因：…`；退出原因经 `escapeHtml`。

证据：`index.html:3329-3375`、`3805`；self-check 段 94。

### 6. S4b `missing_leg` 展示 — **PASS**

`hedgeApi` 将 `data.detail` → `err.message`、`data.error` → `err.errorCode`。
`submitHedgeOpen` 对非 `insufficient_balance` / `invalid_field` / `invalid_state` 走
`setErr(err.message || '创建失败')`，故 `missing_leg` 中文 detail 经既有通道展示，
**未新增专用错误分支**——与设计 §2.4b 及实现者声明一致且足够。
self-check 段 96 以 400 + 中文 detail mock 钉住就近展示。

证据：`index.html:3410-3423`、`3678-3699`；self-check 段 96。

### 7. M-1 `start_gate_changed` 被 `extractHedgeAttempts` 忽略 — **PASS（非空壳）**

`isHedgeAttemptShaped` 要求 `attempt_seq` / `pair_outcome` / spot|perp 对象；
审计 payload `{enabled, previous_enabled, version, source}` 不满足 →
`normalizeHedgeAttempt` 返回 null → 被忽略。
self-check 段 97：混入一条 `kind: start_gate_changed` + 一条真 attempt，断言
`attempts.length === 1` 且 `attempt_seq === 1`。是真实行为断言。

证据：`index.html:3921-3961`；self-check 段 97。

### 8. M-2 不改 14 处 `hgo-` mock — **PASS（一致）**

pinned 树上 `frontend/self-check.js` 仍恰好 **14** 处 `hgo-` 字面量（fixture + 展示断言引用），
无一被改为新 `hg…` 格式。前端只回显、不推导 clientOrderId；断言只做「渲染包含」同名回显。
选择 leave-all-14 一致且不影响断言正确性（dispatch 允许两种做法）。

### 9. self-check 质量 — **PASS**（一处 P3 紧度）

新增段 93–97 均为行为断言：DOM `disabled`、fetch 计数、POST body 逐字段、
409 只 POST 一次、映射逐字、extract 过滤。白名单段同步允许
`/api/hedge-open-settings/start-gate` POST。
合并态权威输出：`60-test-output.txt` → **122 PASS**、`全部自检通过`。

P3：S3 开/关正文 self-check 用 `includes` 子串而非全文全等；**生产代码**已是完整冻结句，
属测试紧度意见，非产品缺陷。

### 10. 文件边界与副作用 — **PASS**

- 前端 diff 仅两允许文件；无无关卡片重构、无新样式块、无外域请求、无新 setInterval/定时器、
  无新 localStorage 键（段 76 白名单仍仅隐私键）。
- 新增同源路由仅 start-gate POST，符合契约。

### 11. 安全 — **PASS**

- 闸门写入必经确认弹窗 + body `confirm: true`；控件路径无法跳过确认直接 POST。
- 无凭据、无 Binance 直连、无绕过 start-gate 的前端捷径。
- backdrop / close 清 `hedgeGatePending`，等同取消，零请求（实现者 residual 说明合理）。

### 跨 seam（仅消费面）

R4 与源码一致：settings `version`、POST `{enabled,confirm,version}`、`missing_leg` detail 通道。
未见前端消费形状与冻结契约冲突。后端实现正确性属并行后端 review-1 范围。

---

## 总评

前端任务完整覆盖 S2 / S3 UI / S4a / S4b 钉住 / M-1 / M-2，与冻结设计一致；
self-check 与合并态 122 PASS 证据充分。无 P0/P1/P2。**verdict = ACCEPT**。

---

当前 Session ID: unavailable（Grok Build/CLI 会话未向本评审暴露 provider-native session id）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/30-review-1-frontend.md
本地北京时间: 2026-07-27 20:57:52 CST
下一步模型: bookkeeper
下一步任务: 归档本评审原始输出并记录 verdict；待 backend review-1 齐备后推进 pre-review-2 / review-2

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-hedge-open-live-hardening-v1",
  "role": "first_reviewer",
  "model": "grok-4.5",
  "verdict": "ACCEPT",
  "diff_fingerprint": "319d8317bdf180750197c95078d2ae6c60e6badc:2a457c0f559fec81cfba8b9d59602c8630bbec73d7b86b28dddab12c4e554efd",
  "reviewer_prior_involvement": "none",
  "reviewed_artifacts": [
    "git diff 6c5b17002cab189d752177b447ff576356998f58..319d8317bdf180750197c95078d2ae6c60e6badc -- frontend/",
    "frontend/index.html",
    "frontend/self-check.js",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/00-task.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/10-design.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/12-development-breakdown.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/14-implementation-frontend.dispatch.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/16-r4-diff-reconciliation.md",
    "reports/agent-runs/2026-07-hedge-open-live-hardening-v1/60-test-output.txt",
    "schemas/review-verdict.schema.json"
  ],
  "findings": [
    {
      "severity": "P3",
      "title": "409 提示弹窗标题未在设计中冻结",
      "file": "frontend/index.html",
      "line": 3531,
      "evidence": "10-design.md §2.3 仅冻结 409 正文「设置已被其他会话修改，已刷新，请重试」；实现使用中性标题「开单闸门变更」。正文与 self-check 均逐字匹配冻结句。",
      "impact": "无功能或安全影响；标题为未冻结细节，操作者仍能看到正确正文并手动重试。",
      "recommendation": "保持现状即可。若产品希望标题也冻结，由 bookkeeper 升级设计后再改，不阻塞本 gate。"
    },
    {
      "severity": "P3",
      "title": "S3 self-check 对开/关弹窗正文使用 includes 子串而非全文全等",
      "file": "frontend/self-check.js",
      "line": null,
      "evidence": "段 95 对开方向 body 断言 includes「可以向币安发出真实订单」、关方向 includes「任务的 worker 将在下一轮检查时退出」；生产 requestHedgeStartGate 中两句正文与 10-design §2.3 完整冻结句一致。",
      "impact": "测试紧度略弱于「全文全等」；不掩盖生产侧已逐字实现的事实，不构成行为回归风险。",
      "recommendation": "可选后续加固为全文全等；非本 stage 必修复项。"
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "confirm 弹窗下点击 backdrop 等同取消（closeHedgeModal 清 pending），与实现者 residual 说明一致，属合理 UX。",
    "version 依赖后端 settings doc 携带 version；合并态与 R4 已确认跨 seam 匹配，后端 gate 另审。",
    "M-1 仅钉前端半边（extract 忽略）；审计 payload 键集合由后端侧钉住。"
  ],
  "next_action": "continue"
}
```
