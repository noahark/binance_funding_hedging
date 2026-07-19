# Direction Draft — Claude (Anthropic)

- Stage: `2026-07-real-borrow-execution-v1`
- Panel member: `claude` / Anthropic（claude-fable-5，经 Claude Code 运行时）
- Skill: `product_strategist`（`agents/skills/product-strategist.md`）
- Lens: 风险受控的产品行为、状态机、交易所异常/未知结果、让无人值守借币循环可被接受的最小人工决策集
- 独立性声明：本稿仅基于 `AGENTS.md`、workflow `direction-drafts`/`direction-synthesis` 节、两个 stage intake 与仓库源码撰写；未读取 `direction-drafts/` 下任何其他面板成员草案。
- 本稿不含任何代码实现，未触发、模拟或准备任何私有写请求。

## Problem Statement

已验收的 `2026-07-borrow-task-ui-fake-v1` 交付了纯前端会话内存的借币任务原型（`frontend/index.html:2084` 起：`state.borrowTasks`，字段 `id/asset/amountPerAttempt/successTarget/successCount/status`，状态仅 `borrowing/paused/deleted`，无 fetch、无定时器、无持久化）。用户现在要求把它接入真实借币：任务可持久保存与恢复，"借币中"任务按固定间隔自动尝试借入，失败按策略重试，累计成功次数达标后停止，状态回显 UI。

而当前系统是严格只读的：后端 `backend/app/server.py` 只有 `do_GET` 路由；`backend/services/private_client.py` 是仓库唯一签名通道，`_require_whitelisted` 硬编码 deny-by-default 白名单且强制 GET-only（`private_client.py:123-131`）；全仓库没有任何持久化任务存储。真实借币是本仓库第一个外部副作用面：一次成功请求即产生真实账户负债，且自动重试意味着在用户不在场时继续产生负债。核心问题不是"怎么调借币 API"，而是：**在什么授权、上限、幂等和恢复保证下，一个无人值守的循环被允许创建债务，并且事后可以被完整审计与对账。**

## Target User And Workflow

单一本地操作者（账户所有者本人），在本机 127.0.0.1 工作站上：

1. 在费率行情表发现机会，从行内操作列创建借币任务（延续 fake UI 的创建入口与参数：资产、单次数量、目标成功次数）。
2. 创建时看到并确认最坏情况总负债（单次数量 × 目标次数）后任务才进入可执行状态。
3. 任务由后端持有并持久化；关浏览器、重启进程后任务与进度不丢失。
4. 任务页查看每个任务的状态、成功进度、最近一次尝试结果与失败原因；可暂停/恢复/删除/编辑（沿用 fake UI 交互）。
5. 出现未知结果或连续失败时，任务自动冻结并醒目提示，等待人处理；操作者随时可用全局停止开关叫停一切后续尝试。

## Scope

本 milestone（分阶段，见 Phased Delivery）的推荐范围：

1. **后端任务存储与恢复**：本地持久化任务与"尝试"两级记录（推荐 SQLite 单文件，或退而求其次的 append-only JSONL journal + 快照；无论哪种都必须是崩溃安全的 write-ahead 语义）。重启后任务恢复到确定状态。
2. **任务 API**：后端新增任务读写接口（列表/创建/暂停/恢复/删除/编辑），前端从 `state.borrowTasks` 内存迁移为消费该 API；保留现有 UI 语义与筛选。注意这是 `server.py` 第一次引入非 GET 路由，仍限 127.0.0.1 同源。
3. **调度器**：进程内单线程串行调度（同一时刻全局至多一个在途借币请求），固定间隔、失败等待下一间隔、达标停止；受全局 kill switch 与各级上限约束。
4. **独立写通道**：与现有只读 `PrivateClient` 分离的专用写客户端，白名单只含唯一一个借币 POST 端点、base URL 硬编码不可注入，保持"签名面只出现在受控文件"的既有 grep 级不变量（`private_client.py:6-8`）。
5. **对账读取**：新增所需的只读端点（借币记录/负债查询）进入现有 GET 白名单，用于确认未知结果与核对成功计数。
6. **审计**：append-only 尝试日志（参数、响应码、交易所事务 ID、时间戳；绝不含 key/secret/签名，沿用 `private_client.py` 现有脱敏审计风格）。

## Non-goals

- 还币、划转、下单、平仓、任何借币以外的写操作。
- 对冲策略自动化、机会自动开仓（借到币之后做什么不在本阶段）。
- 多账户、远程部署、对外网络暴露（维持 127.0.0.1 本地单进程）。
- 通知渠道（短信/推送）；本阶段可观测性以 UI 状态 + stderr lifecycle 事件为限。
- 上一阶段 Review-2 记录的两项 P3（同页未提交编辑值丢失、行内可访问性）——用户已明确 deferred，不重开。
- 不追求交易所侧幂等键（下文说明：按"不存在"设计）。

## 核心方向建议（对应派发六项）

### 1. "真实借币任务"的定义与成功语义

- 任务 = 持久记录：不可变任务 ID（UUID，替代前端自增序号）、资产、单次数量、目标成功次数、重试间隔、创建时间、各级上限快照、状态。
- 尝试 = 独立持久记录，自己的状态机：`INTENT_WRITTEN → SUBMITTED → CONFIRMED_SUCCESS | CONFIRMED_FAILED | UNKNOWN`。发送请求**之前**必须先落盘 intent（write-ahead），这是崩溃恢复与防重复的根基。
- **成功的定义（建议冻结为两级）**："交易所已确认"= 响应携带交易所事务 ID；"已对账"= 随后通过借币记录/负债读数核实。**成功计数以对账确认为准**，UI 可先显示"已提交待确认"。理由：计数直接驱动"还要不要再借"，宁可慢一拍，不可多借一次。
- 审计必须能回答：每一分负债对应哪次尝试、哪个任务、什么时间、交易所返回了什么。

### 2. 授权与确认模型

- **默认关死，两级开关**：新增独立的 `borrow_execution_enabled`（默认 `false`），与现有 `private_channel_enabled`（`backend/config.py:62`，默认 false）分离——允许读账户不等于允许创建负债。写通道未启用时，任务 API 仍可用但任务只能处于"已创建未武装"状态。
- **创建即确认最坏情况**：确认框展示 `单次数量 × 目标次数` 的最坏总负债与资产名，操作者显式确认后任务才可启动。自动重试的授权边界就是这个数字：调度器在任何情况下不得使累计成功借入超过它。
- **全局 kill switch**：一个立即生效的全局停止开关（API + UI 按钮），调度器在每次发送前最后一刻检查；触发后所有任务转入 `halted`，已在途请求照常等待结果并对账，但不再有新请求。
- **上限（全部在方向冻结时定数值）**：单任务最大尝试次数；单任务最大累计借入（即上面确认值）；全局并存活动任务数上限；全局单日尝试次数上限；资产白名单（仅 `borrow_validation` 证据可借的资产）；数量下限（≥ `user_min_borrow`）与单次数量上限。
- **重试与失败策略**：固定间隔且有下限（防手滑配成高频）；连续失败 N 次自动转 `halted` 并留原因；错误分级——可重试类（限频、暂时性 5xx）等下一间隔，**不可重试类（鉴权失败、权限不足、参数拒绝、抵押不足）立即冻结任务**，绝不对鉴权类错误重试。
- **暂停/删除竞态**：暂停/删除只承诺"下一次尝试之前生效"；已在途的请求不可撤销，必须等它到达终态并计入。删除沿用 fake UI 的软删除，且仅当无在途尝试时才完成删除，否则先进入 `deleting` 待定态。UI 文案要如实告知这一语义。

### 3. 正确性：幂等、状态机、对账、未知结果

- **按"交易所无客户端幂等键"设计**（待 GLM 侧核实 Binance 借币端点是否支持 client id；在证实之前一律假设不支持）。因此幂等只能靠本地纪律保证：
  - 全局串行：同一时刻至多一个在途借币请求（单写线程）。
  - write-ahead intent：先落盘再发送。崩溃后重启，凡有 `SUBMITTED`/无终态的尝试，所属任务锁死在 `reconciling`，调度器不得为它发新请求，直到对账完成。
  - **未知结果永不自动重试**。超时/连接中断 ≠ 失败——钱可能已经借出。冻结任务 → 用时间窗 + 资产 + 数量在借币记录/负债读数中匹配 → 能确认则按确认结果计数并解锁；无法确认则停在 `reconciling` 等人工裁决。这是本方向最重要的一条安全规则。
- **任务状态机（后端权威）**：`created(未武装) → borrowing ⇄ paused → completed | halted(原因) | deleted`，加 `reconciling` 作为叠加锁定态。前端现有 `borrowing/paused/deleted` 映射进来，UI 只读后端状态，不再自己持有状态机。
- **对账是常规动作而不只是异常处理**：每次 CONFIRMED 之后、每次启动时、以及周期性地用借币记录/负债读数核对累计成功数；对不上即冻结并报告，绝不"以本地计数为准继续借"。

### 4. 安全与运维

- **凭据与权限**：沿用 env 注入（`config.from_env`），但必须换用开通 margin 借币权限的 key；文档明示：禁用提现、开启 IP 白名单。key/secret/签名/完整 query 永不落盘、永不进日志、永不进 stage 产物（延续 `private_client.py:14-16` 审计纪律与 intake 红线）。
- **写通道隔离**：不要给现有 `PrivateClient` 放开 POST。单独的写客户端文件、独立白名单（唯一条目）、硬编码 base、发送前强制检查 `borrow_execution_enabled` 与 kill switch。签名代码面从"仅一处"变为"仅两处且各自单一职责"，grep 级测试同步更新。
- **进程模型**：维持现有单进程 + 后台线程模式（`snapshot_service.start_worker` 先例），launchd KeepAlive 重启已存在（`server.py:209-212`）。崩溃恢复 = 启动时 journal 回放 + 对账，完成前调度器不武装。独立服务进程是备选（见 Alternatives），本阶段不推荐。
- **限频**：借币端点的 weight/池归属先核实（sapi 与 papi 是不同池，`private_client.py:47`）；调度间隔下限应远高于限频约束，使限频只是防御而非常态。
- **可观测**：任务/尝试状态变化写入 stderr lifecycle 事件（沿用 `_emit_lifecycle` 的"只记事件名与非敏感字段"风格）；UI 顶部横幅显示 `halted/reconciling` 任务数。
- **测试永不碰真实账户**：写客户端构造时注入 transport（现有测试已用 fake transport 模式，见 `backend/tests/test_private_client.py`）；调度器/状态机/恢复/对账全部用确定性 fixture 与时钟注入测试；崩溃恢复测试用"intent 已落盘但无响应"构造。**不设连接真实端点的'演练'模式**；任何针对真实账户的首次验证由人工按 Phased Delivery 的 B 阶段流程执行。

### 5. API/前端契约与 rollout

- 契约以现有 fake 字段为基线做加法：`asset/amountPerAttempt/successTarget/successCount/status` 保留，新增 `id(UUID)/interval/lastAttempt{time,outcome,reason}/haltReason/armed`。前端把 `createBorrowTask/pause/resume/delete/edit`（`frontend/index.html:2106-2207`）改为调用后端并以轮询刷新任务列表（现有 60s 快照轮询先例；任务页可用更短间隔）。
- 现有 UI 的创建入口、任务卡片、筛选、编辑交互全部保留；只是状态来源换成后端。编辑仍限 `borrowing/paused`（与现有 `editBorrowTask` 规则一致），且编辑等同重新确认最坏总负债。

### Phased Delivery（推荐分三段，各自独立可验收）

- **Phase A（无副作用）**：任务存储 + 任务 API + 前端迁移 + 调度器骨架（kill switch、上限、状态机齐全），但写客户端不存在，调度器到"该发请求"处只落盘记录。全程零外部写风险，可完整验收持久化、恢复、UI 契约。
- **Phase B（人工单发）**：加入写客户端与真实端点，但不开自动循环——只提供"立即尝试一次"的人工按钮，每次点击都要确认。用最小金额在真实账户验证：请求、成功语义、对账、审计各环节闭环。**这是让无人值守循环可被接受的关键台阶：先证明单次正确，再谈自动。**
- **Phase C（自动循环）**：打开调度循环，caps/kill switch/未知结果冻结已在 A/B 验证过。首个自动任务仍建议最小金额观察一轮。

## Domain Assumptions Requiring Confirmation

按 skill 纪律，以下均为**待证实假设**，不得由模型凭记忆写死：

1. **账户/保证金模式（最高优先）**：用户实际借币走 classic cross margin、isolated，还是 portfolio margin？仓库同时存在 sapi classic 链路与 papi 读端点，借币端点与语义随模式完全不同。
2. 借币端点的准确 path/参数/错误码/weight/所属限频池，须以 raw 样本或官方文档核实（GLM 侧 lens）。
3. 借币端点是否支持任何客户端幂等键；是否存在按事务 ID 查询单笔借币结果的读端点（决定对账精度：精确匹配 vs 时间窗推断）。
4. 数量精度/步进规则；`user_min_borrow`（已装配于 `rows[].borrow_validation.classic_margin.user_min_borrow`）是否就是写端点的实际下限。
5. 借币记录/负债读端点的延迟特性（成功后多久可见），决定对账等待窗口。
6. 用户对"成功"的业务口径：以交易所确认为准（本稿建议），还是以到账余额变化为准。

## Acceptance Criteria

1. 创建任务后重启后端进程，任务与进度完整恢复且状态确定（测试注入构造各中间态）。
2. `borrow_execution_enabled=false` 时，全系统任何路径都无法发出借币请求（测试断言写 transport 永不被调用）。
3. 任一时刻在途借币请求 ≤ 1；每次发送前存在先行落盘的 intent 记录（journal 断言）。
4. 模拟超时/无响应后：任务进入 `reconciling`，无新请求发出；注入可对账 fixture 后计数被正确修正并解锁；注入不可对账 fixture 后保持冻结待人工。
5. kill switch 触发后无新请求；在途请求结果仍被正确记录与计数。
6. 累计成功借入在任何测试路径下不超过创建时确认的最坏总负债；各级上限（尝试数、日尝试、活动任务数、资产白名单、数量上下限）越界均被拒绝且有明确原因。
7. 鉴权/权限类错误导致任务立即冻结且零重试（测试断言）。
8. 审计 journal 对每次尝试可追溯到请求参数、响应、事务 ID、时间戳；grep 级测试证明 key/secret/签名不出现在任何日志、journal、API 响应中。
9. 前端任务页所有既有交互（创建/暂停/恢复/删除/编辑/筛选）在后端契约上行为一致；暂停/删除的"下一次尝试前生效"语义在 UI 有如实文案。
10. 全部验收测试零真实网络调用（transport 注入断言）。

## Open Questions And Human Gates

冻结前必须由用户裁决（对应 intake Human Gates）：

1. 账户/保证金模式（假设 1）——决定端点与后续一切语义。
2. 各上限的具体数值：单任务最大尝试、日尝试上限、活动任务数、资产白名单、单次数量上限、间隔下限。
3. 成功计数口径：交易所确认即计数，还是对账确认才计数（本稿建议后者）。
4. `reconciling` 无法自动裁决时的人工流程：UI 上人工"判定成功/失败"按钮是否属于本阶段范围。
5. 凭据操作规程：换 key、权限核对、IP 白名单由用户线下执行，仓库只记录"已核对"结论。
6. Phase B 人工单发验证的资产与金额（建议最小可借量）。
7. 是否接受"Phase A 先行合并、B/C 各自独立验收"的分段节奏（本稿强烈建议，理由：每段独立可回退，副作用面最后才出现）。

## Alternatives Considered

- **独立借币服务进程** vs 进程内调度线程：独立进程隔离更好，但引入 IPC、双份凭据面与双份运维；当前单机单人场景下进程内 + write-ahead journal 足够，保留演进空间。**推荐进程内。**
- **成功=交易所确认即计数** vs 对账后计数：前者 UI 反馈快，但超时窗口内可能多借。**推荐对账后计数**，UI 用"待确认"态弥补反馈延迟。
- **直接进入自动循环** vs 先人工单发（Phase B）：跳过 B 少一个阶段，但等于用自动循环做首次真实验证，把未验证语义交给无人值守。**推荐保留 B。**
- **SQLite** vs JSONL journal：SQLite 事务性强、查询便利；JSONL 零依赖、与仓库"stdlib-only"取向一致（`server.py:14-15` ADR-1 先例）。倾向 JSONL + 原子重写快照即可满足本阶段规模，交设计阶段定夺。

当前 Session ID: 8a5c4194-53d4-4aad-809f-7f05d14d21e1
Session ID 来源: runtime_env（Claude Code 会话 scratchpad 路径中的会话 UUID）
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/direction-drafts/claude.md
本地北京时间: 2026-07-19 07:30:26 CST
下一步模型: human operator
下一步任务: 派发剩余三个面板成员（GLM52、Kimi27、Grok Build）的方向草案提示词并保存原始输出；四稿齐备后由 Codex 执行 direction-synthesis
