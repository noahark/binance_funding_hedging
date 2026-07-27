# 实现报告 — 任务 B（前端）— Hedge Open Live Hardening v1

作者角色：前端实现者（任务 B，claude_glm / glm-5.2[1m]）。本报告为原始实现证据，未 commit、
未改 `status.json`、未改 `70-handoff.md`。实现期未访问凭据、未发起任何 Binance 请求、
未启动 HTTP 服务、未触碰 durable Start 闸门数据（intake 状态 `start_gate=0`、服务已停保持不变）。

决策权威（照做，未重新设计）：
`10-design.md`（§2.2 S2、§2.3 S3 前端与冻结弹窗文案、§2.4a S4a 与冻结中文映射、§3 文件边界、
§4 冻结契约、§6 测试策略）、`11-adr.md`（ADR-H2/H3）、`12-development-breakdown.md` §3、
`AGENTS.md`、`agents/developer-discipline.md`、`14-implementation-frontend.dispatch.md`。

## 文件边界确认

本任务只修改了两个允许文件：

- `frontend/index.html`（+132 行）
- `frontend/self-check.js`（+212 行）

`git diff --stat` 同时显示的 `backend/**` 改动（`server.py`、`executor.py`、`service.py`、
`store.py`、`hedge_preflight_provider.py`、`backend/tests/test_hedge_*`、`test_live_hedge_executor.py`、
新建 `wire_constraints.py` / `test_hedge_wire_constraints.py` / `reports/api-samples/...`）是
**任务 A（后端）在同一个工作区并行实现**的产物，不属于本任务，本会话未读取、未修改其中任何一行。
合并态自测结果见下文「自测命令与输出」。

## 改了什么（逐项，含锚点）

### B-1 (S2, P1)：running 卡启动按钮条件 — `frontend/index.html`

`renderHedgeTaskCard` 内 `startDisabled`（原 `index.html:3685`）照 `10-design §2.2` 表达式逐字改：

```js
const startDisabled = (
  task.status !== 'paused' &&
  task.status !== 'exposure_alert' &&
  !(task.status === 'running' && task.worker_active === false)
) ? ' disabled' : '';
```

- 严格用 `=== false`：`worker_active` 为 `null`/`undefined` 时第三分支恒为 `false`，落在 disabled
  一侧；dry-run（`worker_active === null`）按钮条件与改动前逐字一致。
- live 下：running 且 worker 未在跑 → 「启动」可点（点击走既有 `post_start` → `ensure_worker`，
  人工动作，不构成自动派单）；running 且 worker 在跑 → 仍置灰。
- `task.worker_active` 直接取自 task doc（后端 `task_to_doc` 已产出该 additive 字段）。

### B-3 (S4a)：执行线程行 + 退出原因中文映射 — `frontend/index.html`

1. 新增冻结映射常量 `HEDGE_WORKER_EXIT_REASON_LABELS`（紧邻 `HEDGE_PAUSE_REASON_LABELS`），
   八个枚举逐字照 `10-design §2.4a`：`stopped_event`→「收到停止信号」、`task_missing`→「任务记录缺失」、
   `task_not_running`→「任务已非运行态」、`start_gate_off`→「全局开单闸门未开启」、
   `target_reached`→「计划尝试次数已用完」、`preflight_incomplete`→「预检数据不完整（安全退出）」、
   `preflight_fatal`→「预检发现致命问题」、`worker_error`→「worker 异常退出」。
2. 新增两个文本降级 helper（紧邻 `hedgeText`）：
   - `hedgeWorkerActiveText(v)`：`true`→「运行中」/ `false`→「未运行」/ `null`·`undefined`→「—」
     （严格布尔判定）。
   - `hedgeWorkerExitReasonText(v)`：已知枚举映射、未知值 `String(v)` 原样、`null`/`undefined`/`''`→「—」
     （与 `hedgeText` 同降级约定）。
3. `renderHedgeTaskCard` 的 `borrow-task-lines` 内、`countersLine` 之后新增恒展示行：
   `执行线程：<strong>…</strong> · 上次退出原因：<strong>…</strong>`。
   `worker_active` 文本为内部固定字面量不 escape；退出原因经 `escapeHtml` 包裹（未知值可能含特殊字符），
   与既有 `pauseReasonLine` 的 escape 纪律一致。dry-run 恒显示「—」（`worker_active === null`）。

### B-2 (S3)：开单闸门控件 + 对称确认弹窗 — `frontend/index.html`

复用既有 `#hedge-modal` 扩展出双按钮变体（`10-design §2.3` 允许「复用或新增同构小弹窗，语义不变」，
本实现选复用）。

- DOM：执行徽标行（`borrow-execution-row`，badge + detail 之后）新增单一控件
  `<button id="hedge-start-gate-toggle">`，初始 `display:none`，由 `renderHedgeExecutionStatus`
  控制 label 与可见性。`#hedge-modal` 的 `modal-actions` 增 `#hedge-modal-cancel`（取消）与
  `#hedge-modal-confirm`（动态确认词），均默认 `display:none`。
- `renderHedgeExecutionStatus(doc)`：除既有徽标/detail 外，按 `doc.start_gate` 切换控件 label
  （关→「开启开单闸门」/ 开→「关闭开单闸门」）并显示；`doc` 缺失时隐藏控件。
- 弹框两态：`showHedgeModal(title, body)`（单按钮「知道了」，用于余额不足/409 提示等通知，
  清空 `hedgeGatePending`）；新增 `showHedgeConfirm(title, body, confirmLabel)`（双按钮，显示取消+
  动态确认、隐藏「知道了」）。`closeHedgeModal` 同时清空 `hedgeGatePending`。
- 闸门三函数：
  - `requestHedgeStartGate(enabled)`：设置 `state.hedgeGatePending = { enabled }` 并弹一次确认
    （冻结文案逐字）。**不发任何请求**。
  - `cancelHedgeStartGate()`：清 pending + 关闭弹窗。**零请求**。
  - `confirmHedgeStartGate()`：读 pending → 清 → 关闭弹窗 → POST
    `/api/hedge-open-settings/start-gate`，body `{ enabled, confirm: true, version }`，
    `version` 取自最近一次 GET 缓存的 `state.hedgeSettings.version`；200 → 用响应 doc 刷新徽标与按钮；
    `version_conflict`（409）→ `await loadHedgeSettings()` 重新 GET 刷新 + 单按钮提示
    「设置已被其他会话修改，已刷新，请重试」，**不自动重试 POST**（无死循环）；其他错误按既有
    `hedgeApi` 错误路径就近展示 `err.message`。
- 控件点击：按当前 `start_gate` 取反方向调用 `requestHedgeStartGate`。confirm/cancel 按钮分别绑定
  `confirmHedgeStartGate` / `cancelHedgeStartGate`。
- 开/关方向冻结文案逐字（标题/正文/确认词）：
  - 开：标题「开启全局开单闸门？」/ 正文「开启后，实盘模式（live）下被启动的任务可以向币安发出真实订单。此操作立即生效。」/「确认开启」。
  - 关：标题「关闭全局开单闸门？」/ 正文「关闭后，任务的 worker 将在下一轮检查时退出，不再发出新订单；已提交的订单仍会继续查询到终态。」/「确认关闭」。
- 新增 `state.hedgeGatePending`；`resetHedgeStateForTest` 同步清空该字段（测试隔离）。
- 新增 `els`：`hedgeStartGateToggle` / `hedgeModalConfirm` / `hedgeModalCancel`。
- `__appHelpers` 暴露：`requestHedgeStartGate` / `confirmHedgeStartGate` / `cancelHedgeStartGate` /
  `getHedgeGatePending`。

### B-4 (S4b)：missing_leg 错误展示 — 确认既有通道天然支持

`hedgeApi`（`index.html:3375` 附近）已把 `data.detail`→`err.message`、`data.error`→`err.errorCode`、
`data`→`err.payload`。`submitHedgeOpen` 的错误兜底 `setErr(err.message || '创建失败')` 对未被前述分支
（`insufficient_balance` / `invalid_field` / `invalid_state`）命中的错误码一律就近展示 `err.message`。
因此 `missing_leg` 的中文 `detail` 经既有通道天然展示，**无需新增错误展示逻辑**（符合 `10-design §2.4b`
与 dispatch B-4「若既有 hedgeApi 错误通道已天然支持，就用 self-check 用例把它钉住」）。以 self-check
段落 96 钉住。

### B-5 + M-1：self-check 扩展 — `frontend/self-check.js`

- mock 基础设施：`ids` 数组加 `hedge-modal-confirm` / `hedge-modal-cancel` / `hedge-start-gate-toggle`
  （否则 mock `getElementById` 抛「未 mock 的元素」）；默认 `hedgeSettingsGetResponse` 补 `version: 1`
  （反映冻结契约 settings doc 含 version）；新增响应槽 `hedgeStartGatePostResponse` 与 fetch 路由
  `/api/hedge-open-settings/start-gate`（POST，未设置时 503）。
- 白名单同步：段落 76 的同源 `allowedPatterns` 加 `/^\/api\/hedge-open-settings\/start-gate$/`；
  方法白名单加该路由→POST 分支（否则 S3 测试触发的 POST 会让白名单断言 fail）。
- 新增五个测试段落（编号 93–97，插在段落 87 之后、段落 76 白名单之前），均为行为断言，非 static-text-only：
  - **93 (S2 四象限)**：dry-run running（`worker_active:null`）→ disabled；live running+`worker_active:false`
    → enabled；live running+`worker_active:true` → disabled；paused → enabled。逐卡解析 start 按钮
    `disabled` 属性。
  - **94 (S4a)**：八个退出原因逐字映射 + `worker_active` 三态（true 运行中 / false 未运行 / null 与
    字段缺失 undefined 均 —）+ 未知值原样展示。逐卡切片断言。
  - **95 (S3)**：label 随 `start_gate` 切换；确认前零 POST；取消零请求 + pending 清空 + 弹窗关闭；
    开/关两方向冻结文案与确认词；确认后 POST 冻结 body `{enabled, confirm:true, version}` 逐字段；
    成功后用响应 doc 刷新 label；**409 → 重新 GET 刷新 + 冻结提示 + 只 POST 一次（断言无死循环）**。
  - **96 (S4b)**：建卡返回 `missing_leg` 400 → 中文 `detail` 就近展示。
  - **97 (M-1)**：喂一条 `start_gate_changed` 审计日志条目（`payload` 为
    `{enabled, previous_enabled, version, source}`，不含 `attempt_seq`/`pair_outcome`/`spot`/`perp`）
    给 `extractHedgeAttempts`，断言只保留混入的真 attempt、审计行被忽略（钉住前端侧隐含依赖：
    审计行经全量投影进入 legacy `logs` 数组但不会渲染成畸形 attempt 卡）。

## 自测命令与输出（全量执行）

```text
node frontend/self-check.js
.venv/bin/python -m pytest backend/tests -q
git diff --check
```

### `node frontend/self-check.js` — 主判据，全绿

全量计数：**122 个 [PASS]**（改动前 117，新增段落 93–97 共 5 段，合计 122；既有 117 段无回归）。
末行输出 `全部自检通过`。新增段落输出摘录：

```text
[PASS] S2 running 卡启动按钮四象限：dry-run/worker_active 三态 + paused（严格 === false）
[PASS] S4a 执行线程行：worker_active 三态 + 八个退出原因中文映射逐字 + 未知原样 + 缺失降级 —
[PASS] S3 开单闸门对称确认：label 随状态 + 冻结文案 + 确认前/取消零请求 + POST 冻结 body(含 version) + 409 刷新提示无死循环
[PASS] S4b 建卡 missing_leg 错误：中文 detail 经既有 hedgeApi 通道就近展示
[PASS] M-1 start_gate_changed 审计行被 extractHedgeAttempts 忽略（不渲染畸形 attempt）
[PASS] fetch 同源白名单（含开单 §3 路由）、零 Binance/外域、零新任务定时器、localStorage 白名单（仅隐私键）
```

### `.venv/bin/python -m pytest backend/tests -q` — 合并态全绿

**963 passed in 51.12s**（无 failed / error / warning 行）。本次运行的工作区为合并态
（本任务前端改动 + 任务 A 后端并行改动共存）。后端测试当前无暂态红；按 dispatch，bookkeeper 在
两任务都停止后的合并态复跑才是权威判定。

### `git diff --check` — clean

无输出（无行尾空白、无冲突标记）。

## M-2 选择：不改 14 处 `hgo-` client_order_id 字面量

`frontend/self-check.js` 中 14 处 `hgo-` 开头的 `client_order_id` 字面量（行 461/471/499/510/534/
556/560/4011/4046/4048/4134/4180/4281/4285）为纯展示用 mock fixture。**本任务选择不改**，理由：

1. dispatch M-2 明确「作为任意实参并不影响正确性，不要求你改」；这些值只出现在 attempt/log 卡的
   「客户单号」展示位，原样回显后端值，无任何断言依赖其具体格式（仅 4046/4048/4134/4180 四处在
   断言里引用同名值用于「渲染包含」校验，与推导格式无关）。
2. 后端真实推导改为 `hg{attempt_id}s|p`（35 字符）属任务 A 范围（A-1）；前端不推导、不解析该前缀，
   只展示。fixture 值与后端新格式是否一致不影响前端正确性。
3. 改动需同步更新 4 处断言字符串，引入无收益的回归面；违反 `agents/developer-discipline.md` 的
   surgical changes 原则（每行改动须直接追溯到任务请求）。

两种做法 dispatch 均接受；本任务取「不改」。

## 遗留风险与说明

1. **409 提示弹窗标题非冻结文案**：`10-design §2.3` 只冻结了 409 提示的正文
   「设置已被其他会话修改，已刷新，请重试」（逐字实现）；标题设计未给定，本实现用结构性中性标题
   「开单闸门变更」承载该提示（正文逐字）。如评审要求标题也冻结，需 bookkeeper 升级设计。
2. **`version` 字段依赖后端实现**：前端按冻结契约（`10-design §4.1` settings doc 含 `version`）
   从 `state.hedgeSettings.version` 取值上送；若后端 settings doc 未携带 `version`（后端 A-3 负责），
   POST 会传 `version: undefined`（JSON 序列化后缺该键），后端将 400 `invalid_field`。这是契约依赖、
   非前端缺陷；合并态自测（任务 A 已实现 `settings_to_doc` 加 version）当前为 963 passed。
3. **backdrop 点击在确认弹窗等同取消**：既有 `hedge-modal-backdrop` 点击绑定 `closeHedgeModal`
   （清 `hedgeGatePending`），故双按钮确认弹窗下点 backdrop 等同取消（零请求）。这是合理 UX；
   若产品要求确认弹窗 backdrop 点击不取消，需后续调整。
4. **M-1 仅钉前端半边**：M-1 的断言验证「非 attempt 形状的 `start_gate_changed` 条目被
   `extractHedgeAttempts` 忽略」；该审计行的实际 payload 键集合由后端侧（任务 A）另有断言钉住
   （dispatch M-1「两边各钉一半」）。本任务未越界读后端代码，仅按冻结契约描述构造 mock 条目。

## 安全红线确认

实现期未发任何真实 POST、未访问凭据、未发任何 Binance 私有请求、未启动 HTTP 服务、未触碰 durable
Start 闸门数据。所有网络经 self-check mock 假件；`start_gate=0`、服务已停保持不变。

---

当前 Session ID: unavailable（Claude Code 未向本会话暴露 provider-native session id）
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/20-implementation-frontend.md
本地北京时间: 2026-07-27 20:32:18 CST
下一步模型: bookkeeper
下一步任务: R4 diff 对账与证据 commit；不要自行 commit 或进入评审
