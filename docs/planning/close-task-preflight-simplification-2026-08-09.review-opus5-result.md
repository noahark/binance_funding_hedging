# 平仓预检瘦身方案 — Opus 5 独立只读计划评审结果

- **评审对象**：`docs/planning/close-task-preflight-simplification-2026-08-09.review-request-opus5.md`（v1）
- **源码基线**：`dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`（工作树 HEAD 一致，仅多一个未跟踪的请求文稿）
- **评审类型**：`HIGH_RISK` 实现前计划评审（AGENTS.md §8「计划评审」），只读
- **本地北京时间**：2026-08-09 15:07:50 CST

## 0. Reviewer / provider 隔离披露

- **计划作者**：Codex / OpenAI
- **本评审者**：Opus 5 / Anthropic（`claude-opus-5`），由 Human 从独立终端启动
- **隔离依据**：AGENTS.md §3.5「Review isolation follows the model vendor」——作者 provider = OpenAI，评审 provider = Anthropic，跨 provider 成立；AGENTS.md §3.4 自审禁令不适用（本评审者未参与该方案任何撰写）
- **本次动作范围**：只读源码与文档；未修改代码、配置、数据库、服务、gate、凭据；未发起任何交易所请求；未运行测试套件（计划评审阶段无交付物可测）
- **唯一产物**：本文件（新建，未覆盖任何既有文件）

---

## 1. Verdict（结论）

> ## REWORK（返工）

方案的**方向、事实认定和风险取舍基本正确**：§3 的六条现状描述逐条与源码吻合，§9 的取舍诚实，1000x 零下单的边界立场正确，不采用"完全裸发两腿"的判断也正确。

但方案在**四处**会造成错误订单、单腿敞口或不可恢复卡死，必须在实现开始前修正。其中最关键的一条（F1）同时说明：**方案里最激进的那条约束（"close 禁止实时回退"）在缓存充足的正常路径上买不到任何性能收益，只买来一个死锁**——因为那五个数据源在现有代码里**已经是缓存优先**的。删掉兜底不会让快的更快，只会让偶发变成永久。

四条阻塞项（F1–F4）+ 三条必须补齐的说明（F5–F7）见 §3。修正后本方案的实现范围会比现在**更小**。

---

## 2. Opus 5 八问逐项结论

| # | 问题 | 结论 | 依据 |
|---|---|---|---|
| 1 | close create 跳过 snapshot 后，nullable 字段与 dispatch fresh-preflight 是否足以承接；是否有 worker 使用建卡快照的遗漏入口 | **基本可以，一处需补说明** | 见下 §2.1 |
| 2 | cache-only close 是否真能封住所有实时回退 | **能封住，但不该这样封** | 见下 §2.2 / F1 |
| 3 | forward/reverse 的钱包、方向反转、路由、`required` 口径是否正确 | **正确** | 见下 §2.3 |
| 4 | forward base 收敛为单一 service gate 是否存在绕过或重复；总量是否应用 `q_common × remaining` | **存在覆盖缺口** | 见下 §2.4 / F2 |
| 5 | `um_positions` 门能否覆盖"合约拒、现货成"，是否会读反符号 | **会读反，且缺"无行"判据** | 见下 §2.5 / F4 |
| 6 | 缓存缺失即暂停、禁止同步回退是否造成不可恢复卡死 | **会，且是确定性的** | 见下 §2.6 / F1 |
| 7 | 1000x close 零 POST 边界是否完整 | **不完整（NULL 漏判）** | 见下 §2.7 / F3 |
| 8 | 文件范围、测试、活文档是否最小充分，是否误改 open | **接近充分，缺三条断言** | 见下 §2.8 / F5·F6 |

### 2.1 建卡跳过 snapshot 的承接能力（问题 1）

**结论：可以承接。** 核对如下：

- `hedge_open_task` 的 `q_common` / `position_side_mode` / `preflight_snapshot` 三列均可空（`backend/hedge_open_tasks/store.py:51-53`），无需 schema 变更 ✓
- live 发单路径**完全不读**建卡快照：`_dispatch_one_for_task` 在 `live` 分支用 `fresh.q_common` / `fresh.position_side_mode` / `fresh.snapshot_record`（`backend/hedge_open_tasks/service.py:2596-2610`），建卡值只在非 live 分支被读（`service.py:2612-2614`）✓
- 唯一读建卡 `preflight_snapshot` 的发单前门是备款/路由核验（`service.py:2623-2638`），它**已经用 `task_type == D.TASK_TYPE_OPEN` 守住**，close 不经过 ✓
- `tick()` 在 live 模式是 no-op（`service.py:2317-2318`），不存在绕过 worker 的第二条实盘派发入口 ✓
- `post_fill_once` / `post_fill_all` 在 live 模式只置 running + `ensure_worker`，不同步发单（`service.py:997-1018`）✓

**遗漏入口检查结果：无实盘遗漏入口。** 但有一处非实盘的行为变化未在方案中交代 → **F6**。

### 2.2 cache-only 能否封住实时回退（问题 2）

**技术上能封住**，方案点名的入口清单完整，且与源码一一对应：

| 方案点名的读取 | 源码位置 | 现状 |
|---|---|---|
| `check_symbol_legs` | `hedge_preflight_provider.py:935-985` | 缓存优先（2h），miss 退化实时；建卡唯一调用点 `service.py:785-793` |
| 合约 exchangeInfo | `hedge_preflight_provider.py:382-399` | 缓存优先（2h），miss 退化实时（1.06MB 全量） |
| 现货 exchangeInfo | `hedge_preflight_provider.py:356-380` | 缓存优先（2h），miss 退化实时（逐 symbol） |
| 统一账户余额 | `hedge_preflight_provider.py:495-535` | 缓存优先（5min），miss 退化实时 |
| 现货价格 | `hedge_preflight_provider.py:464-493` | 缓存优先（5min），miss 退化实时 |
| position mode | `hedge_preflight_provider.py:537-563` | **无 SnapshotService 缓存**，仅进程内 600s |
| PAPI 限频 | `hedge_preflight_provider.py:565-586` | **无 SnapshotService 缓存**，仅进程内 600s |
| Spot 限频 | `hedge_preflight_provider.py:764-788` | **无 SnapshotService 缓存**，仅进程内 600s |
| 普通现货 USDT | `hedge_preflight_provider.py:649-703` | 缓存优先（5min），miss 退化实时 |
| 普通现货 base free | `hedge_preflight_provider.py:705-762` | 缓存优先（5min），miss 退化实时 |
| collateral-cap | `hedge_preflight_provider.py:876` | **close 已跳过**（方案 §4 说明属实） |

**但这张表暴露了方案的核心误判**：前五项和后两项**已经是缓存优先**。在"缓存充足"的场景下，它们本来就零网络——方案 §8.2 那两条验收标准在当前基线上**已经成立**。真正每次都可能打网络的只有中间那三项（position mode / 两个限频），因为它们只有进程内 600s TTL、没有后台刷新，每 10 分钟必然穿透一次。

所以"禁止 close 实时回退"这条约束的**净收益 = 0**（缓存足时本来就不打网络），**净成本 = 把偶发退化变成永久暂停**（F1）。→ 见 **F1** 的最小修法。

### 2.3 方向、钱包、路由、`required` 口径（问题 3）

**全部正确，无需修改。** 逐条核对：

- 方向反转：`create_task:817-819` 与 `_resolve_fresh_preflight:2434-2439` 用同一套反转规则；两腿动作反转在 `domain.py:739-740`（`spot_side, perp_side = perp_side, spot_side`）✓
- 路由：close+forward → `regular_spot`、close+reverse → `papi_margin`，固定且不读 cap（`domain.py:1087-1090`、`hedge_preflight_provider.py:872-876`）✓
- 钱包：close+forward 走反转后的 reverse 分支，`available = spot_account_base_free`（普通现货账户），不是 PAPI `crossMarginFree`（`domain.py:1296-1299`）✓ —— 方案 §3.3 表格正确
- `required` 口径：forward close → `q_common × target_n`（`domain.py:1295`）；reverse close → 走 forward 分支 `q_common × target_n × est_price`，`available` 取 `balances[USDT]`（`domain.py:1287-1293`），确为统一账户 `crossMarginFree`（`hedge_preflight_provider.py:504`）✓
- 方案 §3.4"前端 `unified_balance` 来自 base 资产 `total_balance`"属实（`domain.py:1927-1928`），与"普通现货 free"确非同一口径 ✓

### 2.4 forward 单一 gate 是否有绕过/重复（问题 4）

**存在重复（方案已识别），也存在方案未识别的覆盖缺口。**

重复属实：`hedge_preflight_provider.py:904` 读 `spot_account_base_free`，`_ensure_close_spot_balance` 又读一次同一钱包（`service.py:1736-1743`）——收敛为一个入口的方向正确。

**但收敛的方式会丢掉一层每轮防护** → 见 **F2**。

关于 `q_common × remaining` vs `single_amount × target_n`：**应当用 `q_common × remaining`**。理由不是精度，是**语义**：`single_amount` 是用户输入，`q_common` 是按两腿公共格点向下取整后的实发量（`domain.py:1202-1203`），实发量恒 ≤ 输入量。用 `single_amount × target_n` 备位会**多划**，多划的零头留在普通现货账户里，而 `_transfer_back_usdt` 只回流 USDT（`service.py:1785-1791`），base 零头**不会自动回流**，需人工收尾——PROJECT_STATE.md:59-60 记录的 TSTUSDT 残余 0.81 正是这个形状。方案 §5.3 说"若重排实现困难可用保守值"——重排并不困难（把门移到 `_dispatch_one_for_task` 里 `fresh` 已算出、`prepare_attempt` 之前的位置即可），不应接受这个降级。

### 2.5 `um_positions` 门（问题 5）

**方向正确，但判据写法有两处会失效** → 见 **F4**。这道门确实是唯一能在发单前预防"合约 reduceOnly 被拒 / 现货腿成交"的手段，值得加；但必须写对符号与"无行"语义，否则它会在最需要它的两种形状上静默放行。

补充一条不阻塞的观察：该门是**按任务**算的。`create_task` 对 close 只校验"存在活跃周期"（`service.py:765-776`），没有"每周期至多一张 close 卡"的约束，因此同一 symbol 可并存两张平仓卡、各自通过这道门、合计超平。这**先于本次交付存在**，本轮不必解决，但方案不应把这道门描述成对该风险的完整防护。

### 2.6 缓存缺失即暂停是否卡死（问题 6）

**会，且不是"等一会儿就好"的那种。** 这是本次评审最重的一条 → **F1**。

方案 §9.5 写的是"任务会快速暂停而不是等待 API；Human 可等待后台快照刷新后恢复"——这句话隐含了一个前提：**后台快照一定会刷新那三个私有源**。该前提不成立，见 F1 的证据链。

### 2.7 1000x 零 POST 边界（问题 7）

**不完整** → 见 **F3**。方案的立场（保持零下单直到换算落地并经独立高风险评审）与 `PROJECT_STATE.md:73-81`、`:178-250` 完全一致，正确；问题只在判据字段选错。

### 2.8 文件范围 / 测试 / 活文档（问题 8）

- **文件范围**：三个必改文件正确且最小。采纳 F1 的最小修法后，`hedge_preflight_provider.py` 的改动会进一步缩小（不再需要 close 专用的 cache-only 开关，只需按 `task_type` 跳过 position-mode / 两个限频 / spot USDT 四项读取）。
- **误改 open 的风险**：`create_task` 的 open 分支（`service.py:805-813` 1000x 拦截、`845-874` 预划转）与 `_dispatch_one_for_task` 的 open 分支（`2623-2658` 备款核验 + 杠杆设置）都已用 `task_type == OPEN` 守住，误改风险低。但 §8 缺一条"open 侧行为不变"的**执行级断言** → **F5**。
- **测试落点**：三个文件正确。缺 dry-run close 的期望变化说明 → **F6**。
- **活文档**：§7 的四项同步正确。`docs/product/PRD.md:149`（"account/position mode, available balance, and rate-limit eligibility"）确实是本次要改的那句 ✓；`PRD.md:100` 关于 position mode 的那句在 close 分流后也会失真，建议一并纳入。
- **验收命令**：`backend/tests/`、`frontend/self-check.js` 均存在 ✓
- **§8.6 那条"可计数 fake client"要求**写得对——只断言耗时确实不能替代调用计数。

---

## 3. 发现（Findings）

范围分类说明：本次是**实现前计划评审**，不存在交付物，因此不适用 AGENTS.md §8「发现的范围三分类」（该分类绑定 `base_sha..delivery_sha` 区间的交付）。以下用「计划内 / 既有」标注问题归属；按 §8「计划评审」条，本 verdict 返回 Planner，不触碰 `rework_count`。

---

### F1 — 阻塞 · 计划内 · 资金/实盘

**cache-only close 依赖的三个私有数据源来自另一套凭证与另一个默认关闭的开关，可能永久取不到值，使平仓能力确定性地不可用。**

**事实链（全部可静态追溯）**：

1. 方案 §5.2 要求 close 发单前从 `unified_balances` / `spot_balances` / `um_positions` 三个缓存取事实，且 §5.2 结尾明确"**不为了补齐预检而同步请求交易所**"。
2. 这三个源**只**由 `SnapshotService` 的只读私有通道填充：`snapshot_service.py:1430-1450` 的 `panel_fetchers` 调用 `self._private.fetch_unified_balances / fetch_um_positions / fetch_spot_balances`。
3. `self._private` 是 `PrivateClient`，用 `BINANCE_API_KEY` / `BINANCE_API_SECRET`，且在 `config.offline or not config.private_channel_enabled` 时**连 key 都不读**（`snapshot_service.py:205-218`）。
4. `private_channel_enabled` **默认 `False`**（`backend/config.py:65`），`.env.example:8` 也是 `false`，`scripts/run-server.sh:26` 需要显式开启。
5. 通道关闭时 `PrivateClient.enabled` 为假，`fetch_um_positions` 直接 `return None`（`backend/services/private_client.py:613-614`），`snapshot_service.py:1449` 的 `if value is not None` 使缓存**永不写入**。
6. 整个 panel 组还额外受 `classic_ref is not None` 门控（`snapshot_service.py:1417`）——只读通道任何持续故障都会让这三个源停止推进。
7. **而预检 provider 的实时回退用的是另一把凭证**：`HedgePreflightProvider(live_client=HedgeOpenLiveClient(api_key=config.binance_hedge_api_key, ...))`（`backend/app/server.py:1327-1337`）。

**后果**：只读通道关闭 / 凭证失效 / 连续失败超过消费端 TTL（余额类 5min，`hedge_preflight_provider.py:56`）时，**下单凭证完全健康，但每一张平仓卡都会在 `preflight_incomplete` 上暂停，且没有任何自愈路径**——Human 点"恢复"也只会立刻再次暂停。这把"平仓"这个**降风险**动作的可用性，绑到了一个与下单无关、默认关闭的展示通道上。开仓路径不受影响（open 保留实时回退），于是系统进入"能开不能平"的状态。

`um_positions` 尤其危险：它在预检链路里**当前没有任何消费者**，是本方案新引入的依赖，一旦通道未开则该门 100% 阻塞。

**§1 Scenario Admission 依据**：当前条目（`config.py:65` 默认值、`.env.example:8`）+ 完整可追溯调用链（server.py:1327 → snapshot_service.py:205/1430/1449 → private_client.py:613 → 新门）+ 影响 §3 保护对象（订单/持仓：平仓能力）。不是裸的未来可能性。

**最小修复要求（择一，必须在方案中写死）**：

- **推荐 (a)**：把"禁止实时回退"的范围**收窄到公开行情**（合约/现货 exchangeInfo、ticker/price）。私有账户三项（统一账户 USDT、普通现货 base free、UM 持仓）保持"缓存优先 + hedge 客户端实时兜底"。
  - 代价：零。这五个源**本来就是缓存优先**（§2.2 表格），缓存足时依然零网络，§8.2 两条验收标准照常成立。
  - 收益：把永久死锁降回偶发的一次小 payload 读取。公开行情才是大而慢的那一块（`fapi/v1/exchangeInfo` 全量 1.06MB），封它才有实际时间收益。
- **(b)**：`um_positions` 若要保留为硬门，必须给它一条不依赖只读通道的取数路径（`LiveHedgeExecutor.query_symbol_um_qty` 已经存在且用 hedge 凭证，`live_hedge_executor.py:540-569`），缓存 miss 时用它兜底一次。
- **无论选哪条**：§8.3 必须补一条验收——"只读私有通道关闭（`private_channel_enabled=false`）时，forward/reverse close 仍能在 hedge 凭证可用的前提下正常发单"。这条如果不能通过，该设计就不该上线。

---

### F2 — 阻塞 · 计划内 · 单腿敞口

**把 forward base 余额门收敛为单一 service gate 后，第 2..N 笔平仓会失去全部现货余额校验。**

**事实链**：

1. **现状是每轮都校验**：live 每个 attempt 都走 `_resolve_fresh_preflight`（`service.py:2596`）→ `compute_preflight` 的 reverse 分支用 `required = q_common × target_n`、`available = spot_account_base_free` 判 `balance_ok`（`domain.py:1295-1300`）→ 不足则 `REJECT_INSUFFICIENT_BALANCE` → `_resolve_fresh_preflight:2468` 的 `balance_ok is False` 返回 `None` → fail-closed 暂停、零 POST。
2. **`_ensure_close_spot_balance` 只在首笔跑**：`service.py:1626-1627` 的调用条件是 `task["scheduled_attempt_count"] == 0`。
3. 方案 §7 让它成为"唯一 base 余额/划转入口"，同时 §7 要 `domain.py`"避免 snapshot 重复 base 检查"——即删掉第 1 条那层门。
4. **方案自身表述矛盾**：§5.2 把资金门列在"仅在任务实际准备发送下一对订单时执行"的序列里（每对订单前），§5.3 却写"首次发单前"。实现者按 §5.3 读，第 2..N 笔就一次余额检查都不做了。

**失败场景**：forward close，`target_n=3`、`q_common=100`。首笔前普通现货 free=300 → 缓存放行、零划转。第 1 笔卖出后 Human 手动把 base 转走 150。第 2 笔发单：现货 SELL 100 被交易所以余额不足拒（-2010），合约 BUY 100（`reduceOnly=true`）成交 → **合约空头被减 100，现货没卖出 100 → 净裸多 100**，且两腿并发无法回滚（`live_hedge_executor.py:861-868`）。这正是方案 §9.2 声明"不接受"的那类可预防单腿风险。

**最小修复要求**：

- 明确 `_ensure_close_spot_balance`（或其继任者）**每对订单发送前都执行**，不是只在首笔；
- 备位/校验量按 `q_common × 剩余未发送次数`（见 §2.4：不接受 `single_amount × target_n` 的保守降级）；
- 保持既有分层语义不变：**缓存充足直接放行（零网络，覆盖绝大多数轮次）→ 缓存不足/未知才实时确认 → 实时仍不足才划差额**（`service.py:1736-1774` 的现有结构已经是这个形状，只需改调用时机与计量）；
- 该门必须落在 `prepare_attempt` 之前（`service.py:2705`），保证暂停时 attempt 数不增加；
- §8.3 补一条："`target_n > 1`，第 2 笔发单前缓存显示 base 不足 → 暂停、attempt 不增、两腿 POST 均为 0"。

---

### F3 — 阻塞 · 计划内 · 资金/实盘

**1000x close 零 POST 的判据字段可能为 NULL，导致拦截静默失效。**

**事实链**：

1. 方案 §5.2 step 1 的判据是 `symbol_match_type == multiplier_strip_alias`。
2. `symbol_match_type` 是后加列：`store.py:434` 的 `("symbol_match_type", "TEXT")`，注释明写"存量行为 NULL，由 `scripts/backfill-spot-identity.py` 回填"（`store.py:431`）。
3. close 建卡的继承分支（`service.py:891-897`）：**只要 origin 的 `spot_symbol` 非空就整体采用 origin 三元组**——`symbol_match_type = origin.get("symbol_match_type")`。若 origin 行的 `spot_symbol` 已回填而 `symbol_match_type` 为 NULL（部分回填、或历史脚本版本差异），close 卡就拿到 `symbol_match_type = None`，而 `else` 分支的查表兜底（`898-905`）根本不会触发。
4. `spot_symbol_of` / `spot_base_of` 对 NULL 都有查表兜底（`domain.py:983-986`、`995-998`），**唯独 `symbol_match_type` 没有任何兜底读取函数**。

**后果**：一张 1000x 平仓卡通过该门 → 两腿共用同一个 `q_common`（`service.py:2663`、`live_hedge_executor.py:820`）→ 现货腿量错 1000 倍 → `PROJECT_STATE.md:73-81` 记录的 999 倍裸空敞口。这直接破坏方案 §9.7 与 §5.2 step 1 自己承诺的边界。

**最小修复要求**：

- 判据改为**双判**：固化值为 `multiplier_strip_alias`，**或** `resolve_spot_identity(task["coin"])[2] == multiplier_strip_alias`。合约 symbol 字符串本身（`1000BONKUSDT`）就是权威信号（`backend/domain/normalize.py:179-184`），不依赖数据库回填状态。
- §8.3 第 7 条补一个存量行用例：`symbol_match_type=None` 且 `coin` 为 1000x 的 close 任务，仍必须暂停、零 POST。

---

### F4 — 阻塞 · 计划内 · 单腿敞口

**`um_positions` 门缺少方向符号判据与"无行 = 未知"判据，会在最危险的两种形状上静默放行。**

**事实链**：

1. 方案 §5.2 step 4 的判据是"确认**绝对**持仓量不少于本任务尚未发送的计划总量"。
2. 一向仓（`BOTH`）下 `positionAmt` 带符号：forward 持仓（现货多 + 合约空）为**负**，reverse 持仓（现货空 + 合约多）为**正**。现有实时核实函数是直接求和不取绝对值的（`live_hedge_executor.py:560-569`），`_verify_close_flat` 只判 `qty == 0`（`service.py:1679`）——即现有代码从未依赖过绝对值语义。
3. 只比绝对值时，**符号与待平方向相反**的持仓会通过该门：合约腿带 `reduceOnly=true`（方案 §8.5.2 要求保持），被交易所拒；现货腿无此保护、正常成交 → 单腿。
4. `fetch_um_positions` 返回 `/papi/v1/um/positionRisk` 原始列表，docstring 明写"Returns the raw list (**empty when flat**) or `None`"（`private_client.py:604-621`）。因此"该 symbol 无行"同时对应"无仓"和"未取到该 symbol"两种含义，**都必须阻塞**，绝不能当成通过。

**最小修复要求**：把 §5.2 step 4 的判据改写为可执行形式：

- 缓存中存在该 symbol 的行，**且** `positionAmt` 符号与待平方向匹配（forward close → 负，reverse close → 正），**且** `abs(positionAmt) ≥ 本任务剩余计划平仓量`；
- 无该行 / 符号相反 / 数值不可解析 / 缓存缺失过期 → 暂停、零 POST；
- §8.3 第 4 条拆成三条：数量不足、符号相反、缓存无该 symbol 行；
- §5.2 step 4 的措辞不要把这道门描述成对"合约拒单+现货成交"的完整防护——它是**按任务**算的，多张并存的平仓卡不会互相扣减（见 §2.5 观察）。

---

### F5 — 需补 · 计划内

**§8 缺一条"open 路径实时回退逐字不变"的执行级断言。**

`_read_perp_filters` / `_read_spot_record` / `_read_est_price` / `_read_balances` / `_read_spot_account_base_free` 全部是 open 与 close 共用方法。无论采用哪种收窄方案，改动都会横切它们。§8.1.4 只说"open create 的既有预检、划转和测试行为逐字不变"，没有覆盖 **open 的发单前路径**。

**最小修复要求**：§8 增加——`get_snapshot(task_type='open')` 在每个源缓存 miss / 坏形状时仍走实时回退且仍打 `_degrade_note`（`hedge_preflight_provider.py:297-305`），逐源各一条断言。若采纳 F1 的 (a) 方案，这条会自动缩小到只覆盖公开行情两项。

---

### F6 — 需补 · 计划内

**建卡不再算 `q_common` 会改变 dry-run close 的发送量，方案未交代。**

`_dispatch_one_for_task` 的非 live 分支读 `task["q_common"]`（`service.py:2612`），为空时 `send_qty` 回退到**未按公共格点取整**的 `single_amount`（`service.py:2663`）。close 建卡跳过 `compute_preflight` 后，dry-run close 的记录传输量就从"取整后的 `q_common`"变成"原始 `single_amount`"。dry-run 不 POST，**无实盘风险**，但会撞既有断言。

**最小修复要求**：§8 明确 dry-run close 的期望（使用 `single_amount`、零 POST），或在 §7「按测试落点修改」里点名要调整的既有断言，避免实现轮把它误当成缺陷再改一次真实路径。

---

### F7 — 需补 · 计划内

**close 装配 snapshot 时 `position_mode` 的取值来源与 NULL 兜底必须写进 §7。**

`compute_preflight:1175-1184` 有一道**致命**门：`snapshot.position_mode != POS_MODE_BOTH` → `REJECT_POSITION_MODE_INVALID` → 经 `PREFLIGHT_FATAL_REASONS` 走 `_stop_task_fatal_preflight`（`service.py:2483-2504`），任务被 **stop**（不是 pause，语义更重）。close 不再实时读 position mode 后，装配出的 snapshot 里这个字段取什么值，直接决定这道门是恒真放行还是误伤 stop。方案 §5.1 只说"继承原开仓任务固化值，缺失时用 `BOTH`"，没写到 §7 的实现边界里。

方案 §9.4 已经把"不再逐卡确认 position mode"的残余风险摊开并给了 reopen trigger，Human 也确认单向持仓是固定运行前提——**该风险取舍本身不阻塞**，只需把取值来源写清楚。

**最小修复要求**：§7 的 `hedge_preflight_provider.py` 行补一句——close 装配 snapshot 时 `position_mode` 取任务固化值，为 NULL 时按已批准前提填 `BOTH`；并在 §8.1.5 补一条：origin `position_side_mode` 为 NULL 的 close 卡不得触发 fatal stop。

---

## 4. 不构成发现的观察（不阻塞，不要求本轮处理）

- **O1**：`_verify_close_flat`（`service.py:1666-1679`）保留实时读的判断正确——它决定"关周期 + 写结算日志"这一不可逆动作，方案 §5.4 不改是对的。
- **O2**：同一 `(coin, direction)` 可并存多张 close 卡（`create_task:765-776` 只校验活跃周期）。**先于本次交付存在**，本轮不必解决；但它会削弱 F4 那道门的强度，方案措辞应避免把该门说成完整防护。
- **O3**：前端策略 **A 是对的**。`frontend/index.html:5196` 现有文案已含"缓存约 60s 旧，以后端校验为准"，改动量确实极小；策略 B（删掉页面硬拦截）在没有前端误拦证据前不应做。
- **O4**：§8.6 的三条命令与 §7 的三个测试文件均存在，路径无误。
- **O5**：方案 §7「明确不改」清单的边界划得干净（不动 open 预检、schema、状态词汇、两腿并发模型、自动补腿、1000x 换算、final flat 实时核实、实盘 gate/凭据）。这是本方案最好的部分，实现轮不应扩张。

---

## 5. 给 Planner 的收口建议

采纳 F1(a) 后，本方案的实现范围会**比现在更小**，且不再需要"close 专用 cache-only 模式"这个新概念：

1. **create（真收益，占绝大部分等待时间）**：close 建卡跳过 `check_symbol_legs` + `get_snapshot` + `compute_preflight`，只做本地校验 + 周期查询 + 身份/position-mode 继承 + 落库。
2. **dispatch（真收益，是仅有的每 10 分钟必穿透网络的三项）**：close 的 snapshot 装配跳过 `position_mode`、`rate_limit_order`、`spot_rate_limit_order`、`spot_account_usdt` 四项读取。
3. **dispatch（不动）**：exchangeInfo / price / balances / base free 保持"缓存优先 + 实时兜底"的现状——缓存足时本来就零网络，不需要为了达成 §8.2 而删兜底。
4. **新增的唯一硬门**：`um_positions`（按 F4 的判据）+ 1000x（按 F3 的双判）。
5. **重排（不是删除）**：forward base 余额/划转门移到 `fresh` 之后、`prepare_attempt` 之前，按 `q_common × remaining` 计量，每对订单前执行（F2）。

这样 §8.2 的两条"缓存充足即零 preflight GET"依然成立，§8.3 的七类暂停依然成立，而 F1 的死锁、F2 的覆盖缺口一起消失。

---

## 6. 授权边界声明

本计划评审**不授权**实现、提交、推送、部署或任何实盘操作。按 AGENTS.md §3.1，后续实现涉及资金路径（划转、下单前置门），仍须 Human 单独授权；按 §8「计划评审」，本 verdict 返回 Planner，不计入 `rework_count`。修正后建议再走一次同 provider 隔离的计划复评，重点只核 F1–F4 四条的落地写法。
