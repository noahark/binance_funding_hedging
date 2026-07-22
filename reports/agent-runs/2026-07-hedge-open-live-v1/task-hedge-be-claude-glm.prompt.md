[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的实现依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# 任务 hedge-be：对冲开单后端模块 + API + 测试（stage 2026-07-hedge-open-live-v1，第一轮）

你是 hedge-be 唯一实现者（Claude-GLM，后端域）。这是真实资金执行面的第一轮
（**立即开单**，无 websocket），**默认 dry-run record transport**：绝不真发
下单请求、绝不碰真实 Binance 网络。真实下单路径只能在 `APP_HEDGE_EXECUTOR=live`
且全局 Start 开启时可达（本轮不启用）。

## 先读这些（权威规格，按此实现，不要臆造）
- `reports/agent-runs/2026-07-hedge-open-live-v1/00-task.md`
- `reports/agent-runs/2026-07-hedge-open-live-v1/10-design.md`（尤其 §2 数据模型、
  §3 方向映射、§4 共同网格取整、§5 preflight、§6 立即引擎+可注入 dry-run、
  §7 单腿敞口状态机、§8 限频、§9 安全闸门、§10 API 契约）
- `reports/agent-runs/2026-07-hedge-open-live-v1/11-adr.md`（ADR-1..7）
- `reports/agent-runs/2026-07-hedge-open-live-v1/12-development-breakdown.md`
  （§3 冻结 API 契约、§4 后端内部契约、§6 测试证据、§7 风险点）
- `reports/agent-runs/2026-07-hedge-open-live-v1/design-inputs.md`（DI-1..DI-4）
- 摸排事实：`reports/api-samples/2026-07-hedge-open-live-v1/`
  `{websocket-bookticker-recon.md, order-endpoints-filters-recon.md}`
- **参照模板**：现有 `backend/borrow_tasks/`（domain/store/service/executor 结构、
  durable SQLite、调度线程、禁用/闸门 executor 全部照这套来）；其 API 在
  `backend/app/server.py` 的挂载方式。

## 允许修改的文件（硬边界，越界即无效）
- `backend/hedge_open_tasks/**`（新建模块）
- `backend/app/server.py`（**只新增** hedge-open 路由，与 borrow 路由并列；不改
  borrow 逻辑）
- `backend/tests/**`（只新增 hedge-open 测试）
- `schemas/api/hedge-open/**`（如需新增 schema 文件）

## 禁止
- 改 `frontend/**`、`borrow_tasks`/borrow 路由、`docs/**`、`reports/**`、
  `AGENTS.md`、根配置、`.env*`。
- 任何真实 Binance 网络调用（代码或测试）。任何新依赖。

## 必须精确实现的冻结契约
1. **API**（12-breakdown §3，逐字）：端点、请求/响应 JSON 字段名、错误码
   （`insufficient_balance`/`invalid_field`/`invalid_state`）、软删除语义。
2. **方向映射 + NO_SIDE_EFFECT**（ADR-3/DI-4）：两方向现货腿 `NO_SIDE_EFFECT`；
   反向 preflight 用 `crossMarginFree(base) >= q_common×N`，`maxBorrowable` 不当
   可卖；`positionSide` 查 `/papi/v1/um/positionSide/dual`，不改模式。
3. **共同网格取整**（ADR-2/§4）：decimal 定点，两腿取 `lcm(step)` 成同一
   `q_common`，违反任一腿 min/max/notional 则拒绝；**绝不分别取整**。
4. **preflight**（§5）：exchangeInfo（公开）+ balance + positionSide/dual +
   rateLimit/order；任一读取失败拒绝 Start。
5. **立即引擎 + dry-run record transport**（§6）：1s durable 调度、双腿并发；
   record transport 记录将发的签名参数（**不含密钥/签名**）、filter 版本、
   preflight 快照、client id，**不发 HTTP POST**；模拟结果**可 seed 注入单腿
   失败/敞口**（默认双腿成交）。
6. **单腿敞口状态机**（ADR-4/§7）：不只信 POST 返回；异常时按 client id 查
   order/trades/positionRisk；一腿成交另一腿否 → `exposure_alert`+`leg_exposure`
   +暂停+记录，**不自动补/平**；累计 >3 失败终止+暂停。
7. **安全闸门**（ADR-5/§9）：默认 `DisabledHedgeExecutor`；真实 POST 仅在
   `APP_HEDGE_EXECUTOR=live` 且全局 Start 开启且 preflight 通过时可达。
8. Task/Fill 字段与 `Task.status`（含 `deleted`）沿用 stage 1（§2/§3）。

## 自测命令（必须真实运行并全绿）
```
python -m pytest backend/tests -q
```
覆盖 12-breakdown §6：domain（方向映射、共同网格取整含 step 不等、preflight
接受/拒绝、单腿分类、>3 终止、deleted）、store（持久化往返 + fills 聚合）、
record transport（断言**无网络 POST**、记录参数形状）、安全（双闸门未开时真实
路径不可达）、可注入单腿敞口演练。**任何测试不得发真实 Binance 请求。**

## R10 收尾（逐条照做后停下）
1. 运行自测命令，把**完整输出**贴到
   `reports/agent-runs/2026-07-hedge-open-live-v1/60-test-output.txt`。
2. 写实现报告到
   `reports/agent-runs/2026-07-hedge-open-live-v1/20-implementation-hedge-be.md`：
   改动摘要、每个交付项对应代码位置、契约符合性自查、自测结果、已知限制、
   AGENTS.md「Output Footer」六行（时间戳用本地 `date`，Session ID 看不到写
   unavailable+原因）。
3. **不要** commit、不要改 status.json、不要启动/转派其他模型、不要越边界。
   完成后停下，交 bookkeeper 收证据、R4 diff 核对、串行 commit、算指纹、调度
   review-1（Kimi）。
