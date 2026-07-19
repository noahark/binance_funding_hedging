# Direction Draft — Real Borrow Execution v1

**Panel member**: `glm52` (`glm-5.2[1m]` / zhipu_glm via Claude-GLM adapter)
**Skill**: `product_strategist`
**Assigned lens**: existing backend technical architecture, Binance private API semantics to verify, durable scheduler/reconciliation design, idempotency limits of exchange APIs, and deterministic tests/fixtures.

这是一份**独立方向草案**，不写代码、不调用任何真实/模拟私有借币写请求、不写入凭据。所有事实带仓库路径证据；用户已批准的产品文档（PRD / ARCHITECTURE / FROZEN 方向基线）优先于本草案任何设计推断。

---

## Problem Statement

产品要从「前端内存 fake 借币任务」（`state.borrowTasks` 纯数组，`frontend/index.html:982/2084-2126`，无 fetch / 无定时器 / 无持久化）迁移到「后端拥有的真实借币执行」。后端现状（事实）与目标之间的张力就是本阶段的问题：

1. **后端是纯只读、GET-only、零持久化、单行情线程**。
   - 唯一 HTTP 入口 `backend/app/server.py` 只实现 `do_GET`，6 条路由（line 41-55），**无 `do_POST`/`do_PUT`/`do_DELETE`**；`do_POST` 未定义即返回 501。
   - 唯一 HMAC 出口 `backend/services/private_client.py:133-188` 在签名**之前**强制 GET-only（`_require_whitelisted` line 128-129 抛 `PermissionError`），`urllib.request.Request(..., method="GET")` 硬编码（line 154）。
   - `WHITELIST`（line 48-66）12 项全为 GET，deny-by-default，base URL 硬编码不可注入。
   - `backend/__init__.py:4` 明示「no order/borrow/repay/transfer paths」；私有账户 v1 方向基线（FROZEN）将 POST/借还执行列为永久禁令。
   - 零持久化：`PublishedState` 是 `@dataclass(frozen=True)` 进程内存对象（`snapshot_service.py:83-98`），无 sqlite/文件；后端无「任务」概念。
   - 唯一调度源是单线程 daemon `snapshot-worker`（`snapshot_service.py:923-973`），三档 cadence 60s/1800s/cursor-sweep，只刷行情。
2. **真实借币会创建账户负债并调用交易所私有写接口**，与上述只读基线根本性冲突。借币请求一旦成功即产生债务，必须：默认禁用、显式授权、可即时停止、有上限、可幂等防重复、可对账、可审计、可崩溃恢复、可被确定性测试覆盖而永不触碰真实账户。
3. **fake 语义与已冻结 PRD 直接冲突**，必须修正而非照搬：
   - fake：失败等下一间隔，**无限重试**到目标成功数（`frontend/index.html` 任务卡片「每 30 秒尝试一次」）。
   - PRD（Negative Funding，§Hedge Modes）：「After multiple borrow failures, the plan is marked failed and must not keep retrying silently.」
   - PRD（§Binance Interface Baseline）：HTTP 503 未知执行状态不得当普通失败，必须先确认，避免重复。
4. **方向冻结前不得实现、调用、模拟调用或触发任何 Binance 借币写端点**；不得在任何产物中写入凭据。

因此本阶段的中心问题不是「能不能借」，而是：**如何在上述只读后端上，安全、最小、可验证地引入一个会创建负债、自动重试、必须幂等、必须对账的借币执行能力——同时不破坏只读快照契约、不引入下单/还币/划转、且让前端现有 fake UI 视觉平滑接到后端真实任务状态。**

---

## Target User And Workflow

**用户**：单一操作员（自用工程），Binance Portfolio Margin 账户，API key 无提现权限（PRD §Risk Controls）。本地或自部署进程，非多租户。

**目标工作流**（后端拥有状态，前端只读展示 + 受控控制信号）：

1. 操作员在行情表选中一行，其 `base_asset` 作为借币资产（沿用 fake 路径）。
2. 配置任务：单次借币数量、目标成功次数（沿用 fake 两个输入；间隔/上限/caps 由后端契约定义，不暴露为前端自由输入）。
3. 后端创建任务（默认 `paused`/`draft`，**不默认 borrowing**），持久化任务定义与 caps 判定。
4. 操作员**显式启用执行**（双开关：全局 `BINANCE_BORROW_EXECUTION_ENABLED` + 任务级 start）并完成风险确认。
5. 后端借币调度器按 per-task interval 对白名单资产发起 `POST /papi/v1/marginLoan`；每次 attempt 提交前持久化 intent，提交后置 `awaiting_confirmation`。
6. 成功（200 + tranId）→ provisional success 计数；对账（records GET）异步确认 → confirmed。失败 → 区分可重试/终止；可重试退避，终止立即 `failed`。
7. 达目标成功次数 → `completed` 并停止；连续失败达上限 → `failed` 并停止；操作员可 pause / kill switch 即时停止。
8. 全程任务状态、进度、每次 attempt 的 intent/响应/对账、状态跃迁、caps/kill 事件回显前端并持久化审计。

**关键转变**：任务真相源从前端内存迁到后端持久化；前端 `state.borrowTasks` 降级为后端任务 API 的只读镜像 + 控制按钮调用方。

---

## Scope

建议本里程碑冻结范围为 **Phase 0（借币执行能力，单一借币腿）**，后续为显式 non-goal。

**Phase 0 in-scope：**

- **借币任务领域模型 + 持久化**：任务、borrow intents（attempts）、audit_events、reconciliation_log；状态机 `draft/paused → borrowing → (success|failed|paused|deleted)` + per-attempt `submitted → awaiting_confirmation → (confirmed|failed|unknown)`；每次跃迁与 attempt 落盘。
- **独立的借币 POST 签名出口**：与现有 GET-only 出口物理隔离的新出口，deny-by-default 白名单（仅 `POST /papi/v1/marginLoan`），不进 TTL 缓存（借币不可缓存），审计 sanitized 且补 `task_id/attempt_seq` 便于审计链。现有 GET 出口与 `_signed_get` 行为不变。
- **幂等防重复**：提交前持久化 intent（task_id/attempt_seq/asset/amount/status=submitted）→ 提交后 `awaiting_confirmation`，**同一 intent 永不重发** → 超时/503/网络异常后靠对账确认，只有对账明确「未成交」才允许下一次 attempt（新 attempt_seq）。
- **对账**：用 `GET /papi/v1/margin/marginLoan`（`queryMarginLoanRecord`，llms-full.txt:186300，**当前未白名单，本阶段需新增**）+ 现有 `GET /papi/v1/balance`（已白名单 line 61）核对负债是否真实入账。
- **借币调度器**：独立线程/循环，不与 `snapshot-worker` 共用（避免阻塞行情、独立 caps/限频域）；扫描 `borrowing` 任务、按 interval 触发、并发控制、失败计数/退避、达 successTarget 置 `completed`、达失败上限置 `failed`；重启后先扫所有 `awaiting_confirmation` 做对账，再恢复调度（**不立即重发**）。
- **授权与上限**：全局 `BINANCE_BORROW_EXECUTION_ENABLED`（deny-by-default，类比 `BINANCE_PRIVATE_CHANNEL_ENABLED`）、全局 kill switch、per-task amount/successTarget cap、全局并发任务数与未确认 intent 上限、单位时间借币总量上限；超限拒绝，不静默。
- **资产/数量规则**：资产白名单沿用 `assemble_borrow_validation` 的 gate（`classic_margin.asset_borrowable && pair_listed`，`snapshot.py:1081-1083`）；下限 `userMinBorrow`（已透传，`private_client.py:273-275`）；上限 `portfolio_account.max_borrowable`（60s TTL，已装配）；精度/stepSize 待 discovery。
- **API/前端契约**：snapshot wire version `public-market-snapshot/v1` **不变**（additive，只读契约不动）；新增独立借币任务 API（新路径前缀 + 新 wire version）做 CRUD/控制/状态/审计查询；前端保留 fake UI 视觉与交互（intake 要求），把 `state.borrowTasks` 从内存迁到轮询后端任务 API，控制按钮改为调用后端控制端点。
- **确定性测试**：沿用 `monkeypatch urllib.request.urlopen`（`test_private_client.py:45-66`）+ `time.monotonic` mock（`test_background_worker.py`）+ `smoke_server` in-process HTTP；全离线、零真实网络/凭据。

**推荐分阶段交付（Phase 0 内部顺序）：**

1. **discovery（人工授权子阶段，最先）**：抓 records GET（只读，安全）确认对账字段；按需授权**一次极小额真实 `POST /papi/v1/marginLoan`** 抓写响应/错误码/权重样本，**立即人工还币**；样本落 `reports/api-samples/2026-07-real-borrow-execution-v1/`。先于任何执行代码。
2. **持久化 + 领域状态机**（纯领域，无网络）。
3. **POST 出口 + 幂等 + 对账**（mock 驱动）。
4. **调度器 + 授权 + caps**（mock 驱动）。
5. **API 契约 + 前端接入**（保留 fake 视觉）。
6. **真实小额验证**（最后，人工门；不在本草案授权范围内）。

---

## Non-goals

- **不下单、不对冲、不自动开/平仓**（PRD v0.1）：本阶段只做「借币」这一条腿，不引入 `POST /papi/v1/um/order`、`POST /papi/v1/margin/order`、`POST /api/v3/order`。
- **不自动还币**：本阶段不实现 `POST /papi/v1/repayLoan`；产生的负债由人工在 Binance 处理或留给后续还币阶段。是否提供「手动应急还币」按钮为人工门（见 Open Questions）。
- **不引入 websocket / listenKey / user data stream**：私有账户 v1 §8 已表态走独立修正轮；本阶段对账用 GET 轮询。
- **不动现有只读契约**：`public-market-snapshot/v1` wire version 与 6 条 GET 路由保持不变；借币任务走独立 API。
- **不重新打开两个 P3 UI 问题**（intake 明确推迟）：whole-view rerender 清未提交编辑、`tr role="button"` ARIA。注：review-2 残余风险已点名前者在「真实借币下 character changes」——这是前端 lens（Kimi）的决策域，本草案仅标注、不强行纳入后端 scope。
- **不多账户、不多 quote、不自动阈值开/关**（PRD v0.1）。
- **不重写 fake 任务状态机语义的 UI 外壳**：前端生命周期 `borrowing ↔ paused → deleted`、completed 一等状态保留；本阶段只把其后端化并补「失败上限 → failed」「成功 → completed」的真实跃迁。

---

## Domain Assumptions Requiring Confirmation

以下均为**未经验证的接口假设**（llms-full.txt 仅有端点标题级，无参数/返回/权重/错误码表），必须由 discovery 抓真实样本或人工确认后才能冻结实现：

1. **`POST /papi/v1/marginLoan` 是否支持幂等键**（如 `newClientOrderId`/client 标识）。Binance 下单接口有 clientOrderId，但 marginLoan 不一定。**若不支持，交易所侧无原生幂等**——整个防重复必须靠本地 intent 状态机 + 对账，容错窗口=对账延迟。这是本阶段**第一技术风险**。
2. **`POST /papi/v1/marginLoan` 返回字段**（`tranId`/`loanId`/`borrowAmount`/时间戳？）、成功 HTTP 语义、`X-MBX-USED-WEIGHT-*` 权重、归属 IP 还是 order 限频池。
3. **`GET /papi/v1/margin/marginLoan`（records）字段与查询能力**：能否按 `asset`/`startTime`/`txId` 查询、能否唯一对账一笔借币、返回是否含状态（ongoing/repaid）——决定对账可行性。
4. **`POST /papi/v1/marginLoan` 的数量规则**：是否有 stepSize/精度/最小量（区别于 `allAssets.userMinBorrow`）。
5. **错误码语义**：`51061`（池耗尽，已确认 `BORROW_ZERO_BUSINESS_CODES`，`private_client.py:94`）、余额不足、资产不可借、签名错误、timestamp 偏移（`-1021`）各自归类为「可重试」还是「终止」。
6. **rate limit**：Portfolio Margin IP 6000/min、order 1200/min（PRD §Binance Interface Baseline）；marginLoan 权重与归属需 discovery；多任务并发借币的预算需在 stage design 冻结（沿用私有账户 v1 §3.6「全端点限频预算表」纪律）。
7. **recvWindow 冲突**：`.env.example BINANCE_RECV_WINDOW=10000` 与 `config.private_recv_window=10000`（`config.py:59`）vs PRD「Portfolio Margin recvWindow ≤ 5000ms」。写请求对时间窗更敏感（防重放），需冻结借币 POST 是否用 ≤5000ms。
8. **classic vs portfolio margin 借币端点一致性**：现有 `maxBorrowable` 走 papi（line 60），借币应一致用 `POST /papi/v1/marginLoan`（papi）；确认账户模式（Portfolio Margin）下该端点适用。
9. **`sqlite3`（stdlib）作为首个持久化可接受性**：PRD 已列 SQLite 为候选；sqlite3 是 Python 标准库模块，不破坏「运行时依赖仅 jsonschema」精神，但**引入首个状态落盘**是架构跃迁，需人工确认。
10. **API key 权限范围**：除「无提现」外，key 是否需要单独开启「Margin 借币」权限——需用户在 Binance 实际确认 key 权限。

---

## Acceptance Criteria

可测试、可审计、零真实账户接触：

- **默认禁用（deny-by-default）**：未设 `BINANCE_BORROW_EXECUTION_ENABLED=true` 时，后端绝不发出 `POST /papi/v1/marginLoan`——负向单测断言零 POST 调用。
- **POST 出口隔离**：新增独立 POST 签名出口，deny-by-default 白名单仅含 marginLoan；现有 GET-only 出口与 12 项 GET 白名单行为不变；`_signed_get` 仍 GET-only。
- **持久化与重启恢复**：任务/intent/审计/对账落 SQLite（WAL）；进程重启后从盘恢复任务与进度，`awaiting_confirmation` 的 intent 先对账再决定是否继续，**不立即重发任何 intent**。
- **幂等防重复**：mock 测试——`POST /papi/v1/marginLoan` 超时/503 后，调度器不重发同一 intent；对账 records GET 确认「未成交」后才允许新 attempt_seq；对账「已成交」则计 success 且不重发。
- **失败语义符合 PRD**：区分可重试 vs 终止；连续可重试失败达上限 N（可配，建议默认 3）→ 置 `failed` 并停止，**不静默无限重试**；终止错误（51061/资产不可借/签名错误）立即 `failed`。
- **成功定义**（推荐，需冻结证据级别）：`POST 200 + tranId` → provisional success 计数；对账 records 确认 → confirmed；provisional-but-unreconciled 单独告警，不回滚已计数（已借的债不能被忽略）。
- **状态机可审计**：每次任务与 attempt 状态跃迁落盘 + 审计事件（sanitized：endpoint/status/error_code/latency/task_id/attempt_seq，**无 key/secret/signature/query**）。
- **kill switch 即时生效**：全局开关与任务级 pause 能即时停止后续 attempt；已 in-flight 的 HTTP 请求尽力取消，置 `awaiting_confirmation` 走对账。
- **pause/delete race 行为**：pause/delete 只改持久化状态机，**不取消已发出的 intent**；对一条 pause 或软删除时正 `awaiting_confirmation` 的 intent，仍必须完成对账以判定该笔是否真实成交（已借的债不能因删除而消失或重复）；delete 为软删除（沿用 fake），保留 intent/审计供复盘，`borrowing` 态的 delete 等价于先 pause 再 soft-delete。
- **caps 强制**：per-task amount/successTarget、全局并发任务数、未确认 intent 上限、单位时间借币总量超限 → 拒绝创建/拒绝 attempt，返回明确原因。
- **资产/数量规则**：仅 `asset_borrowable && pair_listed` 资产可建任务；数量受 `userMinBorrow` 下限与实时 `max_borrowable` 上限约束（精度规则按 discovery 冻结）。
- **契约 additive**：snapshot wire version 不变；借币任务 API 独立版本 + JSON schema；前端 self-check 扩展（见下）。
- **测试零真实账户接触**：全 mock；覆盖幂等/失败上限/重启恢复/kill switch/对账/caps/状态机/默认禁用；fixture 全离线；负向测试断言无真实 URL/凭据。
- **前端**：保留 fake UI 视觉与生命周期；`state.borrowTasks` 改为后端任务 API 镜像；控制按钮调后端端点；self-check 的「零网络/零定时器」断言扩展覆盖 `setTimeout`（review-2 P3-3 残余），并断言控制动作走受控后端端点而非内存突变。

---

## Open Questions And Human Gates

按「不冻结则不得编码」排列，最高级在前：

1. **【最高门】是否解禁 `POST /papi/v1/marginLoan`**——这修订 FROZEN 私有账户 v1 方向基线的「永久禁令 POST/借还执行」与 `backend/__init__.py:4` 声明。必须用户显式批准，并明确边界：**仅借币**，仍禁下单/还币/划转/提现/listenKey。
2. **【最高门】discovery 授权**：是否授权「一次极小额真实 marginLoan POST 抓样 + 立即人工还币」作为 discovery 子阶段？无此则 marginLoan 写语义只能靠文档假设，风险极高。或确认是否有 Portfolio Margin 测试网可用。
3. **成功证据级别**：计数用 provisional（200+tranId）还是必须对账 confirmed？推荐 provisional 计数 + 异步对账告警（见上），但属产品决策。
4. **失败上限 N、退避策略、默认 interval**：fake 固定 30s；真实需配置化（建议 interval 默认 ≥30s 且可配、退避指数、N 默认 3）。
5. **caps 具体数值**：per-task amount/successTarget 上限、全局并发、未确认 intent 上限、单位时间总量。
6. **资产白名单**：是否仅 `asset_borrowable && pair_listed`，是否额外排除 bStock/特定资产。
7. **还币策略**：本阶段完全不还（人工去 Binance 还）？还是提供手动应急还币按钮（会引入 `POST /papi/v1/repayLoan`，扩大解禁范围）？
8. **持久化选型**：确认 SQLite（stdlib）为首个持久化，或用户指定其他。
9. **recvWindow 冻结**：借币 POST 用 ≤5000ms（与 PRD 一致）还是沿用 10000ms。
10. **与 PRD Manual Execution Flow 的关系确认**：本阶段仅「借币腿」，不触碰对冲下单；确认这与用户「进入真实借币业务」的预期一致（即先有独立借币能力，再谈对冲开仓）。
11. **API key 权限**：用户在 Binance 确认 key 已开 Margin 借币权限、且无提现权限。

---

## 假设、替代方案与权衡（GLM 后端镜头补充）

- **假设**：marginLoan 无原生 clientOrderId（待 discovery 证伪）。若**有**，则幂等可简化为「clientOrderId 去重 + order query 风格确认」，大幅降低对账依赖——discovery 应优先验证此项。
- **替代 A：共用 snapshot-worker 做借币调度**。否决：单线程串行，借币 attempt 会阻塞 60s 行情刷新，且限频域不同。
- **替代 B：marginLoan 走现有 `_signed_get` 出口（改成支持 POST）**。否决：破坏 GET-only 硬约束与「单一 HMAC 出口」的只读语义；应新增独立 POST 出口，保持只读出口不变、便于审计与 review。
- **替代 C：借币任务状态进 snapshot 契约**。否决：污染只读 `public-market-snapshot/v1`；借币任务应独立 API/版本。
- **替代 D：用内存 + 日志做持久化（不引 SQLite）**。否决：重启即丢任务与 `awaiting_confirmation` intent，无法防重复借，违反幂等与崩溃恢复要求。
- **权衡**：provisional 计数 vs confirmed 计数——前者快但对账延迟期间可能「计数已成功、对账却未到」（需告警）；后者稳但拖慢任务并依赖 records 实时性。推荐 provisional 计数 + 异步对账，discrepancy 告警不回滚（已借债不能忽略）。

---

当前 Session ID: unavailable (current runtime does not expose provider-native GLM session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/glm52.md
本地北京时间: 2026-07-19 07:37:04 CST
下一步模型: direction synthesizer (Codex/GPT)
下一步任务: 综合 codex/claude/glm52/kimi27/grok-build 五份独立方向草案为 06-direction-synthesis.md，列出已采纳/延后/冻结项与待人工冻结决策，供用户审批后再进入 stage design
