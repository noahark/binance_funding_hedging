Identity:
- task_id: implementation-frontend-1
- target_role: Implementer（Frontend / HIGH_RISK）
- target_model: Grok
- provider: xai
- status_revision: 9
- required_skill: agents/skills/senior-developer.md

Goal

在费率行情页把「抵押额度已满」标记出来，**纯静态展示**，不碰任何后端代码。

本任务由 Human 明确指定 Grok 实现（`agents/roles.md` Implementer Default Routing 要求 Grok
实现须由 Human 或 dispatch 明确启用）。

**启动前提（已满足且须复核）**：`implementation-backend-2` 已由 Bookkeeper 核验并固定为提交
`04ab07bbcb404c6e1ae73040962111b0e906ff98`。启动时必须确认该 SHA 是当前 `HEAD` 的祖先；你
消费的字段权威是**该提交内**的 `docs/api/public-market-contract.md` v0.9 amendment 与
`schemas/api/public-market/snapshot.schema.json`。不得基于口头描述或本地未提交的字段开发；若工作区
中该 amendment 不存在、与 `implementation-interface-v0.9.md` 不一致，或上述 SHA 不是当前提交的
祖先，停止并报告。

1. **三态 + 不适用渲染**：按 `implementation-interface-v0.9.md` §3 真值表与 §8 的**有序判定
   规则**渲染 `rows[].collateral_cap` 与 `ui_flags`：
   - `COLLATERAL_CAP_EXCEEDED` → 可见中文徽标「抵押额度已满」，高亮打在**「标的」列**
     （资产所在单元格）；
   - `COLLATERAL_CAP_UNKNOWN` → 可见中文「抵押额度未知」，`title` 说明是读取失败、
     **不代表未满**；
   - 未满（`exceeded === false` 且 `checked_at` 非空）→ 常态，不加徽标；
   - 无 `collateral_cap` 键，或 `collateral_cap.asset === null` → 不适用，不显示任何抵押额度徽标；
   - 表外组合 → 一律按**未知**处理（fail-closed），**绝不可**渲染为未满/正常/充足/可用。
2. **截至时间露出**：在市场表上方的摘要/表头区**一处**展示「抵押额度名单截至 `<北京时间>`」
   （`checked_at` 全表同值）；徽标 `title` 也带该时间。`checked_at` 为 `null` 时该处显示
   「未知」，不得为空、不得填当前时间。时间转换沿用既有做法
   `formatBeijing(new Date(iso).getTime())`。
3. **命中资产用后端给的值**：徽标/提示中的资产名取 `collateral_cap.asset`（bStock 为 `TSLAB`），
   **不得**用行顶层 `base_asset`（`TSLA`），**不得**自行从 symbol 推导现货 base asset。
4. **不按费率正负过滤**：命中即高亮，与该行费率正负、`positive_funding_enabled`、
   `route_class`、`negative_funding_status`、`asset_tag` 全部无关。
5. **字段接入方式**：`collateral_cap` 按可选/additive 字段处理（放入 `OPTIONAL_*` 一类的可选
   处理路径），**不得**加入 `REQUIRED_ROW_FIELDS`——否则不含该键的冻结离线快照会直接报错。
6. **fixture 与自检**：在 `frontend/self-check.js` 内对已加载的设计期 fixture 做**内存注入**
   （与既有 `opening_quotes` 注入同法），覆盖已满/未满/未知/不适用/缺键各态；
   `frontend/fixture/public-market-snapshot.json` 仅作浏览器静态预览一并补齐。

Allowed Files

- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`

Inputs

- `AGENTS.md`
- `agents/developer-discipline.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `PROJECT_STATE.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/implementation-interface-v0.9.md`
  （渲染真值表与禁令以它为准）
- `docs/api/public-market-contract.md` v0.9 amendment（**后端已提交版本，字段的对外权威**）
- `schemas/api/public-market/snapshot.schema.json`（同上，字段形状）
- `docs/planning/spot-order-routing-v1.md` §6（展示部分的产品设计）
- `docs/planning/2026-08-02-decisions-routing-and-cap-display.md` §B-3、§B-4、§E-3（已定裁定）
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/task-breakdown-1.md`（顺序与边界）
- 仅为执行本任务读取 `frontend/index.html` 现有渲染逻辑与 `frontend/self-check.js` 现有断言。

Acceptance Checks

`node frontend/self-check.js` 全绿，并新增覆盖以下各点的断言：

- 注入四类行后，「标的」列 DOM 分别：已满行含「抵押额度已满」；未知行含「抵押额度未知」；
  未满行与不适用行不含任何抵押额度徽标。
- 未知行的 DOM **不含**「未满」「正常」「充足」「可用」字样。
- 同一命中资产的**正费率行与负费率行都高亮**（不按方向过滤）。
- bStock 行的徽标/提示展示 `collateral_cap.asset`（如 `TSLAB`），DOM 中该提示不出现合约 base
  （如 `TSLA`）作为判定资产。
- 「借贷状态 / 资产」列单元格 DOM **不含**任何抵押额度文案。
- 摘要/表头区出现「抵押额度名单截至 `<北京时间>`」且与注入的 `checked_at` 一致；
  `checked_at` 为 `null` 时该处显示「未知」。
- 缺 `collateral_cap` 键的行不抛错、不渲染徽标（冻结快照降级）。
- `collateral_cap` **不在** `REQUIRED_ROW_FIELDS` 中。
- 开单/借币按钮的启用状态、行排序与过滤结果**不因** `collateral_cap` 改变（纯展示）。
- 既有断言全部保持：fetch 同源白名单、零 Binance/外域、零新任务定时器（仅
  60000/1000/2000）、localStorage 白名单。

另：将仅上述 Allowed Files 中的交付改动做成**一个本地提交**，并在 `[TASK_RESULT v2]` 中报告
提交 SHA、`node frontend/self-check.js` 的原始输出结论与实际改动文件清单。

Stop

- 不得修改任何后端文件（`backend/**`，**含 `backend/tests/fixtures/private-account-v1-design.json`**）、
  `docs/**`、`schemas/**`、阶段记录、`PROJECT_STATE.md` 或未列出的任何文件。
- 不得调用 Binance 或任何外域、不得新增 `fetch` 目标、不得新增定时器、不得读取或展示凭证、
  不得启动服务、不得发单、不得变更 Start gate、不得部署、合并或推送。
- 不得消费开单预检缓存或任何私有下单状态；本任务只读公共快照 `rows[]`。
- 不得用 `collateral_cap` 驱动排序、过滤或按钮禁用；不得自行推导现货 base asset。
- 后端 v0.9 amendment 缺失、与接口约定不一致，或边界不足 → 停止并报告，不得自行改后端或
  自行扩大文件范围。
- 完成实现、自检与本地提交后停止，由 Human 将原始回执交回 Bookkeeper。
