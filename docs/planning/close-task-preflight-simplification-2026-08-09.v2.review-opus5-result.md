# 平仓“两段式建卡 + 预检瘦身”v2 — Opus 5 独立只读计划复评结果

- **评审对象**：`docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-request-opus5.md`（v2）
- **前序**：v1 计划 `…review-request-opus5.md`；v1 评审 `…review-opus5-result.md`（结论 `REWORK`，F1–F7）
- **源码基线**：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`（工作树 HEAD 一致）
- **评审类型**：`HIGH_RISK` 实现前计划复评（AGENTS.md §8「计划评审」），只读
- **本地北京时间**：2026-08-09 15:42:25 CST

## 0. Reviewer / provider 隔离披露

- **计划作者**：Codex / OpenAI
- **本复评者**：Opus 5 / Anthropic（`claude-opus-5`），由 Human 从独立终端启动；同一评审者完成 v1 评审，未参与 v1/v2 任何计划撰写
- **隔离依据**：AGENTS.md §3.5（隔离按 model vendor）；§3.4 自审禁令不适用
- **本次动作范围**：只读源码与文档；未修改代码、配置、`.env`、数据库、服务、gate、凭据；未发起任何交易所请求；未读取任何凭证内容
- **唯一产物**：本文件（新建，未覆盖 v1 计划、v1 结果或 v2 计划）

---

## 1. Verdict（结论）

> ## ACCEPT（接受）

v2 **逐条闭合了 F1–F7**，我对每一条都做了源码级复核（§3），无一条是口头闭合。两段式设计经查证不但成立，而且**顺手堵掉了一个方案自己都没声称的现存漏洞**（§4.1）——今天创建即 `running` 的平仓卡，在进程重启时会被 `_recover_workers` 自动拉起 worker 并真实发单，无需任何人工点击；改为初始 `paused` 后该路径消失。

同时确认：v2 撤回 cache-only 是对的，`§5.4` 要删的四项读取中**三项在全仓库确无消费者**（纯 fail-closed 负债），第四项是替换而非删除（§3.7）。

**三条约束必须原样进入实现 dispatch 的 `Goal`**（§5，C1–C3）。它们不是设计缺陷，是计划里缺了三个实现者无从默认的取值/语义；其中 **C1 有实际单腿风险**——交付若未落实 C1，review-1 应判不通过。另有一条活文档义务遗漏（§4.4），按 AGENTS.md §7 收口时必须补。

---

## 2. 复评八问逐条结论

| # | 问题 | 结论 |
|---|---|---|
| 1 | `paused + awaiting_manual_start` 能否复用现有状态机，有无 worker/startup handoff/fill 绕过 | **能复用，四层防护，且比现状更安全**（§4.1） |
| 2 | create 全跳过 preflight 后，nullable `q_common/snapshot` 是否只影响已接受的 dry-run 记录量 | **是，已核实无其它消费点**（§4.2） |
| 3 | F1 是否彻底修正 | **是**（§3.1） |
| 4 | F2 helper 重排位置与 remaining 计量 | **正确，公式自洽**（§3.2） |
| 5 | F3 双判是否覆盖新任务与历史 NULL | **是**（§3.3） |
| 6 | F4 方向符号/无行/数量/实时兜底是否完整 | **判据全对，缺一个新鲜度上限 → C1**（§3.4） |
| 7 | 四项删除是否真无 close 消费者，有无误改 open | **三项确无消费者，第四项是替换；open 未动**（§3.7） |
| 8 | 文件范围、验收、活文档是否最小充分 | **文件与验收充分；活文档同步整节丢失 → §4.4** |

---

## 3. F1–F7 闭合核实（逐条源码验证）

### F1 ✓ 已闭合 — cache-only 撤回，兜底恢复

- v2 §1 / §5.3 恢复五个源的“缓存优先 + 实时兜底”，与现有实现一致（`hedge_preflight_provider.py:366/383/471/496/720` 均已是缓存优先，miss 才实时）。
- **§8.2.3 的验收正是我在 v1 评审里要求的那条**：`private_channel_enabled=false` + hedge 凭证可用时 forward/reverse close 仍能完成预检。
- **§2.2 的推理正确且重要**：Human 澄清“两处 env 用同一把 key、权限相同”后，v2 没有据此撤掉兜底，而是指出失败模式是**缓存生产通道关闭/刷新失败**（`snapshot_service.py:205-218` 的 `private_channel_enabled` 门控 + `1417` 的 `classic_ref` 门控），与 key 权限无关。这个区分是对的——我在 v1 评审里把凭证差异当成主因之一，v2 把根因收窄到通道可用性，更准确。
- 结论：F1 彻底闭合。

### F2 ✓ 已闭合 — 每轮执行 + remaining 计量 + 落点正确

- §5.6 三项要求全部到位：每对订单前执行、用 fresh `q_common`、落在 `prepare_attempt` 之前。
- **公式经验证自洽**：`prepare_attempt` 在同一事务内校验并推进 `scheduled_attempt_count`（`store.py:872-899`，docstring “advances the scheduled-attempt counter”），因此门执行时该值 = 已预留的尝试数，`target_n - scheduled_attempt_count` = 真实剩余可发次数。
- 一个我特意验算过的边角：**失败的 attempt 也消耗计数**（`store.py:895-898` 注释明确“consumed once a pair is reserved regardless of its later outcome”）。所以一次拒单后 remaining 减 1、备位量同步减少——这是**正确**的，因为剩余预算确实只够卖 `q × remaining`，不存在少备。
- §8.3 的 3/2/1 序列验收覆盖到位。
- 结论：F2 彻底闭合，且比我在 v1 提的最小要求更完整（补了“任一轮缓存不足时实时确认”）。

### F3 ✓ 已闭合 — 创建期 + 派发期双重双判

- §4.1 步骤 4（创建期）与 §5.2 步骤 1（派发期）各做一次“固化值 OR `resolve_spot_identity(coin)`”。
- `resolve_spot_identity` 是纯查表零 IO（`backend/domain/normalize.py:179-188`），放在创建期不违反 §4.2 的“外部读取为 0”。
- §8.4 两例分别覆盖新建卡与存量 `symbol_match_type=NULL` 行——正是 v1 评审指出的 `store.py:434` 后加列 NULL 洞。
- 结论：F3 彻底闭合。

### F4 ✓ 判据全对 — 但缺一个新鲜度上限（→ C1）

方向符号我按持仓语义反查了一遍，**v2 写对了**：

- forward 周期 = 现货 BUY + 合约 SELL（`domain.py:729-732`）→ 合约为空头 → `positionAmt < 0`；§5.5 要求 forward close 必须 `positionAmt < 0` ✓
- reverse 周期 = 现货 SELL + 合约 BUY（`domain.py:733-736`）→ 合约为多头 → `positionAmt > 0`；§5.5 要求 reverse close 必须 `positionAmt > 0` ✓
- 无行 / 空 / 0 / 反号 / 不可解析 / 缓存与实时双失败 → 暂停零 POST ✓（对应 `private_client.py:604-621` 的“empty when flat”歧义）
- 实时兜底 `query_symbol_um_qty` 确实存在且返回带符号净持仓（`live_hedge_executor.py:540-569`，按 symbol 求和不取绝对值）✓
- §8.5 的 `-300/+300/-299/0/无行` 用例矩阵完整 ✓

**缺口**：v2 §5.3 表格把 `um_positions` 写成“缓存命中 → 直接使用”，但**没有定义“命中”的新鲜度上限**。provider 里每一个缓存源都有显式上限（`hedge_preflight_provider.py:54-58`），唯独 `um_positions` 在预检链路里是本方案**新引入的源**，没有现成常量可用。→ **C1**。

### F5 ✓ 已闭合

§8.2.5 要求 open create 与 open dispatch 在同样 cache miss 下走原实时读取并保留 `_degrade_note`（`hedge_preflight_provider.py:297-305`），逐字不变；§3 的整改表也写明“本轮所有新增分支均限定 `task_type == close`”。这正是 v1 F5 要的那条执行级断言。

### F6 ✓ 已闭合

§8.6.3 明确接受 dry-run close 使用原始 `single_amount` 记录、零 POST，并写明“测试不得把它误当 live `q_common`”。与 `service.py:2612/2663` 的实际回退行为一致。

### F7 ✓ 已闭合，且比我要求的更安全

- §4.1 步骤 5 + §5.2 步骤 3 + §8.6.1 把取值来源写死：origin 固化值，NULL 才填 `BOTH`。
- **我额外验算了一个 v2 没提但对安全性有利的事实**：origin 任务的 `position_side_mode` **不可能是 `hedge`**。若开仓建卡时读到双向持仓，`compute_preflight` 返回 `REJECT_POSITION_MODE_INVALID`（`domain.py:1175-1184`），`create_task` 在 `service.py:835-839` 直接 `raise`，任务根本不会落库。因此可继承值只有 `BOTH` 或 `NULL`，`or BOTH` 的兜底不会把一个真实的 hedge 账户误标成一向仓。
- 残余风险（Human 中途改 position mode）已在 §9.2 挂了 reopen trigger，且 §2.3 是 Human 给定前提——按 AGENTS.md §10 属 Human 决策域，不阻塞。

---

## 4. 复评新增核实

### 4.1 两段式确实无绕过，且堵住一个现存漏洞（问题 1）

**四层独立防护，全部已在基线代码中存在**：

1. dry-run 调度器筛选：`list_eligible_tasks` 只取 `status = RUNNING`（`store.py:843-852`）→ paused 卡不会被 `tick()` 派发；
2. worker 自检：`_worker_round` 对非 running 立即退出（`service.py:1584-1585`）；
3. **事务内复检**：`prepare_attempt` 在同一事务里 `if task["status"] != D.STATUS_RUNNING: return None`（`store.py:891-892`）→ 即使前两层被绕过，也不产生 attempt、不发单；
4. v2 §4.4 新增的 `_require_fillable` 拒绝（`service.py:1032-1038` 目前只拦 deleted/done，确实需要补）。

**fill 绕过是真实的，v2 识别正确**：live 路径 `post_fill_once` 会把 paused 卡 `set_task_status(RUNNING)` 并 `ensure_worker`（`service.py:1001-1003`），确实能跳过“先点启动”。补 `_require_fillable` 是对的。（补充：这是意图/UX 门而非安全门——两条路径都需要 Human 点击，且启动后同样跑完整预检。）

**v2 顺手堵掉的现存漏洞（方案未声称，建议明确记入收益）**：

- `create_task` 全程**从不调用 `ensure_worker`**（全仓仅 `service.py:965/1003/1017/2388/2413` 五处调用），所以今天创建的平仓卡是 `running` 但没有 worker——实际上已经在等人工点击。
- 但 `_recover_workers` 在 **进程重启时对每一个 RUNNING 任务无条件拉起 worker**（`service.py:2382-2388`）。因此今天一张“创建后未启动”的平仓卡，只要服务重启一次，就会**在没有任何人工点击的情况下**进入预检并真实发单。
- 改为初始 `paused` 后：`_recover_workers` 的 paused 分支只在存在未终结腿或未结算 attempt 时才拉起 drain worker（`service.py:2400-2413`），新卡两者皆无 → 不会被拉起。**该自动发单路径被消除。**

同时确认 v2 §4.3 的四条前端复用主张**逐条属实、零前端改动即成立**：paused 卡的“启动”按钮已启用（`frontend/index.html:5496-5499`）、非 running 禁用“暂停”（`5495`）、展示 `pause_reason_zh`（`5517-5518`）、`post_start` 已是“改 running + 启 worker + 立即返回”（`service.py:952-966`，无任何同步交易所调用）。§4.3 关于 `set_task_status` 清空初始 pause reason 的说法也属实：`store.py:781-787` 在转 RUNNING 时同时清 `pause_reason` / `pause_reason_zh` / `last_worker_exit_reason`。

### 4.2 nullable `q_common` / snapshot 的影响面（问题 2）

- 前端渲染已有空值分支：`task.q_common != null ? … : '—'`（`frontend/index.html:5532`），不会崩、不会显示 0；
- `task_to_doc` 原样透传（`service.py:158/169`），无计算；
- live 派发不读建卡值（`service.py:2596-2610` 用 `fresh.*`）；
- 唯一读取点是非 live 分支（`service.py:2612-2614`）→ 即 F6 已明确接受的 dry-run 记录量；
- 备款/路由核验读 `task["preflight_snapshot"]`，但已用 `task_type == OPEN` 守住（`service.py:2623`），close 不经过。

结论：影响面确实只有已接受的 dry-run 记录量。

### 4.3 §5.4 四项删除的消费者核实（问题 7）

我对四项逐一做了全仓库消费点搜索：

| 读取 | 快照字段 | 消费者 | 判定 |
|---|---|---|---|
| PAPI rate-limit | `PreflightSnapshot.rate_limit_order`（`domain.py:905`） | **无**。仅在 `hedge_preflight_provider.py:830/924` 赋值，`848-849` 用于 fail-closed。`store.py` 的同名字段是 `hedge_open_settings` 列，**与快照无关** | 纯负债，删除安全 |
| Spot rate-limit | `spot_rate_limit_order`（`domain.py:931`） | **无**。仅 `provider:900/931` 赋值 + `912-913` fail-closed | 纯负债，删除安全 |
| Spot account USDT | `spot_account_usdt`（`domain.py:930`） | **无**。`domain.py:1289` 的 forward+regular_spot 分支读的是 `snapshot.balances[QUOTE_ASSET]`，**不是这个字段** | 纯负债，删除安全 |
| position mode | `position_mode` | **有**：`compute_preflight:1175` 致命门、`domain.py:1221` 快照指纹、经 `fresh.position_side_mode` 流向 `direction_to_leg_actions` | **替换而非删除**，v2 §5.4 表述正确 |

即：前三项的唯一实际效果是“读失败就把整个快照 fail-closed 掉”——删掉它们只减少故障面，不减少任何判断力。v2 把删除限定在 close、暂不清理 client 方法/字段/open 侧调用（§5.4 末段），这个克制是对的，避免把高风险 diff 摊大。

### 4.4 活文档同步整节丢失（问题 8）

v1 §7 有“实施收口时同步”一节（`docs/product/PRD.md`、`docs/planning/DECISIONS.md`、`hedge-open-position-cycle-v1.md` §12 指针），**v2 §7 把这一节整体删掉了**，“明确不改”里也没有对应豁免。

这不是可选项：AGENTS.md §7 末段规定“任何交付收口（含 Human 直接驱动、无 stage 的改动）都必须检查 `docs/` 下的活文档…并同步之”，无 stage 时由在 `PROJECT_STATE.md` 记录收口的模型执行。

具体确有失真项：`docs/product/PRD.md:149` 现写“每对订单前实时验证 account/position mode, available balance, and rate-limit eligibility”，本轮后 close 三项都不再实时验证；`PRD.md:100` 关于 position mode 的表述同理。（已核查：`docs/api/` 与 `PRD.md` 均未对“建卡初始状态”作契约约定，因此 `paused` 初始态**不需要**同步 API 契约文档。）

→ 见 §5 的第四条。

---

## 5. 必须进入实现 dispatch `Goal` 的约束（C1–C3 + 活文档）

以下四项不改变 v2 的设计、文件边界或验收结构，但必须原样写进实现任务的 `Goal`，否则交付会缺失关键取值或语义。

### C1（有单腿风险，最重要）— 给 `um_positions` 命名新鲜度上限

- **要求**：`um_positions` 必须经 `self._cached("um_positions", <max_age>)` 读取（`hedge_preflight_provider.py:232-250`），`<max_age>` 建议复用 `_CACHE_MAX_AGE_BALANCE`（300s）——与同为私有账户源的 `unified_balances` / `spot_balances` 一致，且相对 SnapshotService 60s 的刷新节奏（`config.py:34` `cache_ttl_seconds=60`，`snapshot_service.py:1443`）有 5 倍余量。
- **走 `_cached` 的好处**：超龄由该 helper 直接返回 `None`，**自动落入 §5.5 已定义的“缓存 miss → 实时兜底”分支**，不需要新写一条陈旧分支。
- **§8.5 增补一条验收**：`um_positions` 超龄 → 走实时 `query_symbol_um_qty` → 实时失败才暂停（零 attempt、零 POST）。
- **为什么本轮必须修**：v2 §9.4 自己承认同 `(coin, direction)` 可并存多张 close 卡且本轮不做仓位预留。一张卡已把仓位平掉、而 `um_positions` 缓存仍是旧的非零值时，另一张卡的门会放行 → 合约腿 `reduceOnly` 被拒（-2022）→ 现货腿单独成交 → 裸腿。这正是该门存在的理由，不能靠未命名的默认值兜。

### C2 — `store.create_task` 必须在**同一条 INSERT** 内写入初始 `paused` + 两个原因列

- **事实**：当前 INSERT 把 `status` 硬编码为 `D.STATUS_RUNNING`、`pause_reason` 硬编码为字面 `NULL`，且**列清单里根本没有 `pause_reason_zh`**（`store.py:671-702`）。v2 §7 的 store 行只写了“可选初始 status/pause reason”，漏了 zh 列。
- **要求 1**：三者一并参数化（默认值保持 `running` / `NULL` / `NULL`，open 行为零变化）。漏掉 zh 列不会崩，但卡片会退化成显示裸枚举 `awaiting_manual_start`（`frontend/index.html:5518` 的回退分支），达不到 §4.1 步骤 5 的中文文案要求。
- **要求 2**：**不要**用“先建 `running` 卡、再调 `pause_task` 改暂停”的两步写法。`pause_task` 虽是 running/paused 条件写（`store.py:1984-1988`）能正确落两列，但两步之间存在一个 `running` 窗口；dry-run 的 `tick()` 会把该窗口内的卡当作 eligible（`store.py:843-852` 只筛 status=running）并生成一条 disabled attempt，令 §8.1.2 的 `attempt=0` 断言不稳定。
- **配套**：`awaiting_manual_start` 的中文文案按现有机制走 `D.pause_reason_zh` 查表（`domain.py:1636`），与 v2 §7 的 domain.py 行一致。

### C3 — 写明两道新门在 dry-run 下的行为

- **事实**：新增的 UM 持仓门与重排后的 forward base 门，在 dry-run 下既没有 SnapshotService 缓存、也没有 `query_symbol_um_qty`（`getattr` → `None`）。v2 §8.5 / §8.3 全部按 live 语义描述，§8.6.3 只覆盖了 dry-run 的 `single_amount`。
- **要求**：明确 dry-run 语义。建议与既有同类约定保持一致——executor 缺少对应方法即视为放行、零 POST，这正是 `_verify_close_flat`（`service.py:1673-1675`）与 `_ensure_close_spot_balance`（`service.py:1728-1729`）现行的写法。
- **不写的后果**：实现者要么让 dry-run close 永久暂停（撞既有回归），要么临时发明一条未记录的规则。

### 活文档 — 恢复 v2 §7 删掉的“收口时同步”一节

至少包含：`docs/product/PRD.md`（`:149` 的“每对订单前实时验证 account/position mode/rate limit”改为 open/close 分流后的真实合同；`:100` 的 position mode 表述同步）、`docs/planning/DECISIONS.md`（记录 Human 接受的两段式启动与固定 position-mode 前提）、`docs/planning/hedge-open-position-cycle-v1.md`（对被取代的章节加指针，不重写历史）。依据 AGENTS.md §7 末段；无 stage 时由在 `PROJECT_STATE.md` 记录收口的模型在收口同时执行。

---

## 6. 剩余风险确认（不阻塞）

v2 §9 的六条我逐条核对，**全部属实且已诚实披露**，无需增补：

1. 两腿并发不可原子回滚 — 属实（`live_hedge_executor.py:861-868`）；
2. position mode 变更需恢复实时校验 — reopen trigger 明确；
3. 两处 env 若不再同 key/权限需重评 — 正确保留；
4. 多张 close 卡竞争同一仓位 — **先于本次交付存在**，本轮不解决是合理的；但它是 C1 的直接动因，两者需一起读；
5. 1000x 仅人工平仓 — 与 `PROJECT_STATE.md:73-81` / `:178-250` 一致；
6. cache miss 仍可能有一次实时等待 — 诚实，且与 §2.4 的体验目标（卡片立即出现、start 不阻塞）不矛盾。

补一条 v2 未列、我认为应记入 §9 的观察（**不阻塞，无需本轮处理**）：建卡变成零外部调用后，创建成本降到接近零，Human 连点会更容易产生多张同 `(coin, direction)` 的待启动卡。这只是放大了 §9.4 已承认的竞争面，不产生新风险类别——但若实际出现，与 §9.4 一并设计即可。

---

## 7. 授权边界声明

本计划复评**不授权**实现、提交、推送、部署、服务控制或任何实盘操作。按 AGENTS.md §3.1，后续实现触及资金路径（划转、发单前置门），仍须 Human 单独授权；按 §8「计划评审」，本 verdict 返回 Planner，不触碰 `rework_count`。

`ACCEPT` 的适用范围是 **v2 计划本身可进入实现**；§5 的 C1–C3 与活文档一节必须原样出现在实现 dispatch 的 `Goal` 中。**交付若未落实 C1（`um_positions` 新鲜度上限），review-1 应判不通过**——它是本方案唯一仍可导致单腿敞口的未定值。C2/C3 与活文档若缺失，按普通评审发现处理即可。

按 AGENTS.md §9，本 `ACCEPT` 不构成合并、部署、实盘启用，也不替代 Human 的最终业务验收。
