# Dispatch —— plan-hedge-task-lifecycle-v1

```text
Identity:
  task_id:         plan-hedge-task-lifecycle-v1
  target_role:     Planner
  target_model:    claude_glm
  provider:        zhipu_glm
  status_revision: 4
  required_skill:  agents/skills/software-architect.md
```

## Goal

为本 stage 的**四项**产出完整实现方案、关键技术决策记录、以及可交付任务拆分。**只写文档，不写任何代码。**

四项（范围已由 Human 定死，见 `02-scope-decisions.md`，不得增删）：

- **① 合并持仓表** —— 以交易所真实 UM 持仓为骨架，匹配现货/杠杆账户资产与任务卡成交记录，合并成一张表；对不上的两类都要显示并标清楚。
- **② 任务卡卡死修复 + 六种非人工暂停改自动删除** —— `paused` 此后只剩人工手动暂停。
- **③ 订单重查间隔 1 秒 → 100 毫秒**。
- **④ `resolve_leg_from_query` 的 `avg_price` / `quote_amt` 覆盖保护**（无 `COALESCE`，后续查询返回 `None` 会覆盖已知值）。

**展示形状不需要你重新设计** —— 已由 fake UI 交付 `63f5007` 确定并经 Human 认可。你的任务是把它变成可实现、可验证的方案。

### 你必须裁定的九个决策点

方案里每一个都要有明确结论、理由、以及**放弃了什么**（`software-architect.md` 的 trade-off 要求）。含糊或"视情况而定"不算裁定。

- **P1 合并在哪一层做**：前端 join（`state.snapshot.private_account` 与 `state.hedgePositions` 已同时在浏览器内，零新增交易所请求、零新增限频权重）vs 后端合并（口径单一，但 hedge service 目前够不到 `private_account`，且 `private_client.py` 的端点白名单已冻结不可扩展 —— 见 `hedge_preflight_provider.py` 文件头的偏离说明）。**这是本方案最关键的一个决定**，必须出 ADR。
- **P2 同币双向**（Human 要求单独成案，D11）：本地按 `(coin, direction)` 分桶会出两行，币安 UM 只有一个净持仓。两行如何挂到一个真实仓上？不得与 P3 混为一谈论述。
- **P3 手工部分平仓后的偏离**：本地累加数量只增不减，手工卖掉一半现货后本地仍是原数而真实余额减半。差额显示与否、如何显示。
- **P4 ②③ 相撞**（必须解决，不得回避）：`rate_limited`（429）正是六种非人工暂停之一（`domain.py:135`）。② 落地后一次限流即删卡；③ 又把查询量放大 10 倍（10 个任务 × 10 次/秒 = 100 次/秒）。给出解法（限流退避而非删卡 / 429 作为例外保留暂停 / 不做③ / 其他），并说明为何该解法不与 Human 已定的"六种全改"冲突。
- **P5 ② 的死锁修法**：真实残留路径是 `post_start`（`service.py:616`）不检查计划配额就置 `running` + 拉起 worker，而 worker 立刻因 `scheduled_attempt_count >= target_n` 退出（`service.py:1172`），任务留在 `running` 无进展；复现条件 `target_n == failure_pause_threshold`。再武装入口共三个：`post_start`（`:616`）、`post_fill_once`（`:656`）、`post_fill_all`（`:670`），且 `post_start` 不挡 `stopped`。
- **P6 自动删除的边界**：不得终止正在 drain 在途腿的 worker（`post_delete` 现有行为是不打断、drain 到终态再退出，`service.py:645`）。同时说明被自动删除的任务，其已成交的腿如何仍然出现在合并持仓表里（这正是 ① 要解决的）。
- **P7 ③ 的前置与拆分**：`service.py:178` 用 `// 1_000_000` 整除，亚秒值会显示成 `0`，改之前先修显示；现在"下单调度间隔"与"订单重查间隔"共用一个值但语义不同（`store.py:19`、`scheduler.py:5` 注释均为 fixed 1s），是否拆分；是否加下限。
- **P8 占位零的处理**：`price_pnl` / `accrued_funding` / `borrow_interest` / `net_pnl` 在 `store.py:2050-2053` 是字面量 `"0"`，从未计算过。哪些本轮接真值（合约腿未实现盈亏可由 `um_positions[].unrealized_profit` 提供）、哪些画"暂无"、哪些画"未知"。**不得继续渲染成 `0.00`。**
- **P9 交付拆分与顺序**：四项拆成几个可交付任务、各自的文件边界、先后依赖（① 必须在 ② 之前，③ 必须在 ② 之后）、每个任务标 `HIGH_RISK` 还是 `LOW_RISK` 及理由。

## Allowed Files

**只可新建这三份文档，不得修改任何代码文件：**

- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/10-design.md` —— 方案主体，含上述九个决策点的裁定
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/11-adr.md` —— 至少覆盖 P1 与 P2 两个 ADR（`software-architect.md` 的 ADR 模板）
- `reports/agent-runs/2026-07-31-hedge-task-lifecycle-v1/12-development-breakdown.md` —— 可交付任务拆分与验收标准

`backend/`、`frontend/`、`status.json` 及其他任何文件**一律不得改动**。边界不足即为阻塞项，报告并停止。

## Inputs

### 必读

| 文件 | 字节数 | 读什么 |
|---|---|---|
| 本 dispatch | —（当前文件） | 全部 |
| `02-scope-decisions.md` | 7647 | 全部 —— **字段事实与 Human 决策的权威来源** |
| `03-fake-ui-outcome-and-plan-scope.md` | 5346 | 全部 —— D9-D12 与多次开单的已核实事实 |
| `01-intake-brief.md` | 8588 | §「四项待办与依赖关系」与「必须守住的红线」。**注意：该文件的代码行号已全部过期**，一律以本 dispatch 下方的锚点表为准 |
| `20-fake-ui-implementation.md` | 12638 | §5 占位零三分类、§9 接线风险清单 |
| `AGENTS.md` | 16587 | §1 §3 §8 |
| `agents/roles.md` | 12183 | Shared Rules + Planner 段 |
| `agents/skills/software-architect.md` | 6770 | 全部 |

### 代码锚点（已由 Bookkeeper 在当前 HEAD 上逐个校验，简报中的旧行号作废）

**A-1 计划上限家族 —— 完整四站，改动任何一站都必须同时评估其余三站：**

| 位置 | 是什么 |
|---|---|
| `store.py:690` | SQL 调度资格：`scheduled_attempt_count < target_n` |
| `store.py:740` | 预留前守门：`>= target_n` 则 `return None` |
| `store.py:979` | R2-F1 结算收口：`>= target_n` 且 `running` → `done` |
| `service.py:1172` | worker 退出：`>= target_n` → `WORKER_EXIT_TARGET_REACHED` |

**清单外三处，谓词不同，不得并入该家族：** `domain.py:1087`（`accepted_count >= target_n`，受理口径）、`service.py:687`（`success_count >= target_n`，成功口径）、`store.py:811`（仅计数器 `+1`）。

**② 相关：**

| 位置 | 是什么 |
|---|---|
| `service.py:616` / `:656` / `:670` | 三个再武装入口 `post_start` / `post_fill_once` / `post_fill_all` |
| `service.py:632` / `:645` | 人工 `post_pause` / `post_delete`（后者不打断 drain） |
| `domain.py:134-152` | 六种暂停原因常量与 `ALL_PAUSE_REASONS` |
| `domain.py:1061` | `resolve_status_after_attempt`（写 `paused` 的路径之一） |
| `store.py:872` | `_apply_task_counters`（写 `paused` 的路径之一） |
| `store.py:907` | `skip_counters` 限频结算 —— **不走** R2-F1 收口，配额已耗仍可能非终态 |
| `store.py:975-990` | R2-F1 收口块（要求 `new_status == running`，而暂停先落，故暂停优先于收口） |
| `store.py:1739` | `pause_task` |
| `service.py:1150-1157` / `:1174-1180` | worker 内两处 429 → `_pause_task_local(PAUSE_REASON_RATE_LIMITED)` |
| `domain.py:1306-1312` | `_PAUSE_REASON_ZH` 五条现行中文 |
| `domain.py:1315-1324` | **51169 冻结文案** `COLLATERAL_CAP_FULL_REASON_ZH_TEMPLATE` |

**① 相关：**

| 位置 | 是什么 |
|---|---|
| `store.py:1934-2057` | `aggregate_positions`（两条查询均带 `WHERE t.status != deleted`；占位零在 `:2050-2053`） |
| `service.py:924-925` | `get_positions`，不做加工 |
| `snapshot.py:1052-1225` | `assemble_private_account`（`um_positions` 投影在 `:1152-1168`） |
| `snapshot.py:893-895` | `_infer_position_side` 返回**大写** `LONG`/`SHORT`，零仓 `null` |
| `private_client.py:546-610` | `fetch_unified_balances` / `fetch_um_positions` / `fetch_pm_account` / `fetch_spot_balances` |
| `index.html:2908-2918` | 个人账户面板：「UM 持仓」表与真实持仓表**已上下相邻**，是合并的自然落位 |
| `index.html:4500` | `renderHedgePositionsSection`（现有真实持仓表） |
| `index.html:4261` | `renderHedgeTaskCard` |
| `index.html:4593` | fake 预览的六个场景常量 —— **展示形状基准** |

**③④ 相关：** `service.py:178`（整除显示 bug）、`store.py:19` 与 `scheduler.py:5`（fixed 1s）、`resolve_leg_from_query`（④ 的目标，无 `COALESCE`）。

### 不可触碰的红线

1. **51169 文案逐字冻结**（`domain.py:1315-1324`，ADR-T3 契约，注释明写 `must NOT be reworded`）。严禁替换为「保证金不足」话术 —— 平台级抵押上限全平台共享、追加资金无效，「保证金不足」正是它要否认的假事实。只允许**追加**删除后缀。
2. **不得放宽 A-1 计划上限**。`scheduled_attempt_count` 是用户设定的下单次数硬上限；**不得**改成 `accepted` 口径 —— 那会让失败无限重发、突破用户设定的资金上限。
3. **不得新增任务状态枚举**。Human 已决定 `done` 语义本轮不处理（D2）。
4. **不得用账户级数值冒充每币数值**。本项目是统一账户全仓，没有逐仓每币清算价／逐仓账户价值；参考脚本有而本项目没有的列，**不得为对齐而虚构**（见 `02-scope-decisions.md` §2.1）。
5. **不得自动执行任何交易动作**。参考脚本会在判定强平后自动清仓；本项目的对不上两类**只展示、不动作**（D7）。
6. **不得扩大范围**。§1 禁止为假设场景添加抽象、兼容层或防御机制。`software-architect.md` 的 DDD／分层／六边形等模式，只有在解决**已有证据的**耦合或变更问题时才可提出；否则按其自身第 1 条「No architecture astronautics」拒绝。

## Acceptance Checks

每项在 `[TASK_RESULT v2]` 的 `检查结果` 里按 `AGENTS.md` §7 标注 `pass` / `fail` / `contested`。

1. **九个决策点 P1-P9 全部有明确裁定**，每个含结论、理由、放弃了什么；无"视情况而定"式空转。
2. **P1 与 P2 各出一份 ADR**，含 Context / Decision / Consequences，明确写出该决定使什么变容易、什么变难。
3. **P4（②③ 相撞）有可执行解法**，并说明为何不与 Human 已定的「六种全改」冲突。
4. **A-1 家族四站完整覆盖**：方案若改动其中任一站，必须逐站说明其余三站受不受影响；清单外三处须给出不适用的理由（`AGENTS.md` §8 同根因刹车的穷举要求）。
5. **交付拆分可执行**：每个任务有 `Allowed Files` 级别的文件边界、验收标准、`HIGH_RISK`/`LOW_RISK` 标注与理由、以及依赖顺序（① 在 ② 前，③ 在 ② 后）。
6. **非目标显式列出**：本轮明确不做的事情逐条写清（例如资金费与借币利息的数据源、`done` 语义、1000x 符号剥离），避免实现阶段悄悄扩围。
7. **六条红线逐条确认**：在方案里逐条声明遵守，其中 51169 与 A-1 两条须指出方案中哪一处保证了它。
8. **展示形状与 fake 一致**：与 `63f5007` 预览形状不同之处逐条列出并说明原因；未列出的即视为一致。
9. **不引入无证据支撑的抽象**：方案中每个新增模块、层次或接口，都要指出它解决的是哪个**已观察到的**问题。
10. **风险清单**：列出你认为实现阶段最可能出问题的三处，及各自的早期验证方式。

## Stop

- 完成后按 `AGENTS.md` §7 输出 `[TASK_RESULT v2]`，然后**停止**。
- **不要改动 `status.json`**（含 `current_task.state`）—— 本任务的状态由 Bookkeeper 更新。
- 不得写任何代码、不得改动 `backend/` 或 `frontend/`、不得合并、不得推送、不得接触凭证或实盘路径。
- 不得启动、调用、转交或冒充任何其他模型会话（§3 #2）。
- 方案不构成实现、验收、合并、部署或实盘授权（`agents/roles.md` Planner Stop Point）。
- 若发现本 dispatch 的锚点与实际代码不符、或红线之间相互冲突：**停止并报告**，不要自行取舍。
- 若阅读量将显著超出上述锚点范围，按 `agents/developer-discipline.md` §5 停止并报告。三个后端主文件合计约 27 万字节，**禁止整文件读**。
