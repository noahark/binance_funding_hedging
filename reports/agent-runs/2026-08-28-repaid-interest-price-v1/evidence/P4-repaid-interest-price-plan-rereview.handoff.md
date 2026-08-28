# Task Handoff: P4-repaid-interest-price-plan-rereview

## Source Report (author-only; immutable after task end)

- task_id: `P4-repaid-interest-price-plan-rereview`
- role: `Reviewer`（实现前只读计划复评，AGENTS.md §8 计划评审门第二轮）
- target model: `opus5`（provider `anthropic`）
- stage_id: `2026-08-28-repaid-interest-price-v1`
- created_at: `2026-08-28 20:20:19 CST`
- base_sha: `4e6f4909dd17eb43c08f0f393258793df24a6ec7`
- delivery_sha: `none`（实现前计划复评，无交付 commit；`status.json.delivery_sha` 为 `null`）
- 复核锚点：`status.json` revision `8`、checkpoint `p3-plan-revision-verified-p4-ready`、
  `ledger_sha` `a532b3fceb4c41e9e6cebf08a089204618c237d8`、评审时
  `git rev-parse HEAD` = `8f46f78bfde14f978621066a31873883e59ed642`、
  `git status --short` 无输出（工作区干净）
- 受审产物：`reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`（P3 修订版）
- 核对基准：`reports/agent-runs/2026-08-28-repaid-interest-price-v1/P1-repaid-interest-price-plan.dispatch.md`
  八条 Acceptance Checks、
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P3-repaid-interest-price-plan-revision.dispatch.md`
  八条 Acceptance Checks、
  `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P2-repaid-interest-price-plan-review.handoff.md`
  的 F1-F4 / O1-O3 与其 Errata 段所载 Human 决定
- required_skill: `agents/skills/reality-checker.md`

### 事前披露（Reviewer Isolation，`agents/roles.md` Reviewer / Isolation）

本会话所属模型在同一 stage 内已有两次前序参与：一次**非正式方向咨询**（无 verdict，
推荐"计提时冻价"，Human 已否决），一次**正式 P2 计划评审**（`REWORK`，产出 F1-F4 与
O1-O3）。本会话**不是**受审计划的作者——P1 与 P3 均由 Planner `claude_glm`（zhipu_glm）
撰写；本会话至今对本 stage 的源码零改动（`git status --short` 无输出）。

本次复评按 P4 dispatch 要求**从 Inputs 重新独立核验**，未沿用窗口内旧结论：下列每一条
裁定都重新读取了对应仓库文件并在文中给出行号锚点。计提时冻价方案**不作为**任何裁定
依据、默认值或回退。全部发现均落在 Human 两项固定决定**之内**，不要求改写口径。

### 评审结论

`REWORK`。

P2 的 F1、F2、F3、F4 **均已解决**，O1-O3 **均已具名**，Human 两项固定决定在计划字面上
**忠实落实**，P1 八条与 P3 八条验收中有 15 条通过。但修订在解决 F2 的同一条缝隙上**新增**
了一个签名网络观测，把还款终态落库延迟最多 15 秒（F5）；历史归零推定缺一道本仓库既有的
覆盖率闸门（F6）；并把"推定"表述为"可确认"（F7）。三条均为 `in-range`、均落在资金/账务
含义上，修复要求可执行且范围有界。

### 一、P2 F1-F4 逐项裁定

| P2 发现 | 裁定 | 独立核验依据 |
|---|---|---|
| **F1**（"结清"表述与所引证据相反；无法区分全额/部分还款） | **已解决** | 修订版 §1.3 与 §3.1「领域事实如实陈述」段已改称**资本化**并复述 SNX `0.10709571` 仍留债务内；§3.1 明文「`status='succeeded'`、`amount="0"`、`repaid_amount` 缺失均不被等同为归零事实」；终态改锚在 `repay_after_borrowed`/`repay_after_interest` 双零证据。我重读 `PROJECT_STATE.md` 371-380 与 `backend/domain/snapshot.py:1202-1205`、`1393-1397`，两处对资本化的表述与修订版一致 |
| **F2**（捕获插在写路径、无异常保护） | **就其原始范围已解决** | §3.2.1 观测 1 为纯内存快照读，整体包 `try/except Exception`，`SnapshotNotReady` 只留 NULL；§3.2.1「硬约束」明文 `resolve` 无条件执行；测试 16 断言异常下仍 `succeeded` 且 `resolve` 恰一次。**但修订在同一缝隙新增观测 2（签名网络 GET），产生新发现 F5** |
| **F3**（回退结算时刻字段不可达） | **已解决** | §3.4 明文 `list_records()` 返回 `_row_to_doc` 全部键**外加** `updated_at_us`（int）与 5 新列；§3.3 `settlement_ms(record)` 使用该字段；测试 8 覆盖。核对 `backend/margin_repay/store.py:51-63` 确认 `_row_to_doc` 现确无 `updated_at_us`，故该补充是必要且充分的 |
| **F4**（价格定义强于代码可证语义） | **已解决** | §3.2.1-1 改称 `snapshot_spot_bid_at_capture`「捕获时刻内存快照里的现货买一价，可能滞后」，并引 `backend/domain/snapshot.py:806-808`。我独立重读该处：`status = "fresh" if four_valid else "incomplete"`，`four_valid` 仅为四个价格非 None——`fresh` 确无时效含义，修订版引用准确 |

### 二、O1-O3 与 Human 两项决定

- **O1 已具名**（§7 首条）：本表不覆盖交易所侧手动/自动还款，相关利息永远留开放桶；
  明确本轮不改用 `margin_capital_flow_rows` 并给出理由。未因此扩围。**pass**
- **O2 已具名**（§6.2）：`ssh funding-prod` → 定位数据卷 → 写前 `.backup`/`cp` 并留证 →
  `docker cp` + `docker exec` → `--dry-run` 先行。**pass**（缺一项，见 F6 子项）
- **O3 已具名**（§8.4）：点明 `pnlCostsIncomplete()` 判 `unpriced_assets` 非空即整条净收益
  「暂无」，任何一行缺价都全局遮蔽。**pass**
- **Human 决定一（部分还款绝不锁价 / 仅可确认归零才切终态 / 资本化不是结清证据 /
  re-borrow 重开）**：**忠实落实**。§1.1-1.4 逐条对应；§3.1「覆盖形态」段列全五种形态；
  测试 2（部分还款不锁，用 SNX `"50.10709571"` 资本化形态复刻）、3（切换恰一次）、
  4（re-borrow 重新开放）、5、6 存在且断言方向正确。**pass**
- **Human 决定二（F2 路径 A）**：**就价格捕获忠实落实**（观测 1 为零 I/O 内存读、双层
  异常隔离、如实命名）。**但该决定只覆盖价格捕获**；修订新增的余额观测 2 不在该决定
  范围内，且破坏了该决定意在保护的"绝不影响终态落库"性质——见 F5。**pass（价格）/
  见 F5（新增观测）**

### 三、新发现（AGENTS.md §8 范围三分类 + 证据锚点）

#### F5 `in-range` — 归零证据观测把签名网络 GET 插在"钱已出去"与"终态落库"之间，最长延迟 15 秒；计划自述与其自身设计矛盾（资金路径）

修订版 §3.2.1 观测 2 规定：在 `_dispatch_margin_repay` 返回 `succeeded` 后、
`store.resolve` 调用前，调 `fetch_unified_balances(force=True)`。同段「硬约束」写道
「不存在『取价失败 → 跳过/**延迟** resolve → 记录永久停在 pending』的路径」。

独立核验（不接受计划自述）：

- `backend/services/private_client.py:579-601`：`fetch_unified_balances` 在 `force=True`
  时 `_evict` 后走 `_cached_get`，即**一次新鲜签名 GET**，非内存读。
- `backend/services/private_client.py:171`：`urllib.request.urlopen(req, timeout=self._timeout)`。
- `backend/services/snapshot_service.py:216-224`：该 `PrivateClient` 以
  `timeout=config.request_timeout` 构造。
- `backend/config.py:58`：`request_timeout: float = 15.0`。
- `backend/services/private_client.py:23-24`：429/-1003 立即失败、**无周期内重试**——
  故上限为一次往返，但该次往返最长 15 秒。

因此异常隔离确实排除了「**跳过** resolve」，但**没有**排除「**延迟** resolve」；计划把两者
一并否认，与其自身设计不符。观测 1（内存快照）无此问题，问题只在观测 2。

实际影响（可追溯代码路径）：`backend/app/server.py:1017-1032` 现有序列是
`begin()`（短事务）→ 一次外发 → `resolve()`（短事务）；`backend/margin_repay/store.py`
模块说明把「必须落终态，否则记录会永远停在 `pending`」列为设计红线，并声明「外发调用
永远不在持锁期间发生」。插入观测 2 后，`pending` 窗口从「一次本地 sqlite 写」扩大到
**最多约 15 秒的网络等待**。窗口内进程重启、部署切换或被杀 → 真钱已还、本地永久 `pending`；
按 `begin()` 幂等契约，同 `client_request_id` 重试只会回放 `pending`、永不收敛，而换一个
新 `client_request_id` 会**真的再还一次**。

Scenario Admission（AGENTS.md §1）：属 §3 Safety Kernel 保护范围（money / repayment）；
当前前提为修订版 §3.2.1 明文规定的插入位置；证据为上列可追溯代码路径与配置值，非裸的
未来可能性。必须本轮修而非留作观察：缺陷在资金写路径的**设计**中，事后观察意味着用一笔
真实还款去触发；且修法不新增状态、契约或依赖。

**修复要求（可执行）**：
1. §3.2.1 把归零证据观测移到 `store.resolve` **之后**：先无条件写还款终态（价格列按
   观测 1 结果或 NULL），再执行余额观测，并用 §3.2.2 已有的 NULL-only 条件更新形态补写
   `repay_after_*` 三列。不新增状态机、不新增表、不改 `begin()`/幂等契约。
2. §3.2.1「硬约束」段改写：分别陈述观测 1（零 I/O，不延迟）与观测 2（网络，故置于
   `resolve` 之后），删除现有把两者一并否认延迟的表述。
3. §5 测试 16 增加**顺序断言**：余额观测桩记录被调用时刻，断言 `store.resolve` 在其之前
   已完成；并保留现有异常隔离断言。
4. 若 Human 更倾向完全不做实时归零观测（只靠 §3.2.2 脚本补齐），那是等价可接受的更小
   方案，但属 Human 取舍，本评审不代为决定。

#### F6 `in-range` — 归零推定条件 b 把"账本里没有行"当作"没有计息"，缺覆盖完整性闸门；与本仓库既有纪律及一处同形守卫相矛盾

修订版 §3.2.2-2 条件 b：「其结算时刻之后该资产**无新利息行**（若未归零，小时级计息必然
继续出现）」。该条把 `interest_rows` 的**缺席**当作正向事实，未要求该区间账本覆盖完整。

独立核验：本仓库已有明确相反纪律，且有一处逐字同形的守卫——

- `backend/app/server.py:1589-1596`：持仓统计在 `cov = lsvc.coverage_for_window(start_ms,
  end_ms)` 后，`if not cov.get("complete")` 即把三列置 `None` 并标 `stats_incomplete`，
  **拒绝把覆盖不足的窗口当成真值**。
- `backend/ledger_flow/service.py:533-561`：`_build_coverage` 产出 gap-aware 的 `complete`。
- `backend/ledger_flow/store.py`：`coverage_gaps` meta 与按源覆盖端点已存在，停机/拉取
  失败会被记为 gap。

实际影响：账本在「结算时刻 → 脚本运行时」之间存在覆盖空洞时，「无新息行」不成立；
a+b+c 会把**仍有负债**的还款推定为归零，写下 `repay_after_*="0"` → 假终态 → 该资产历史
利息被永久锁在错误价格，且此后真正的归零事件不再触发切换（索引只取第一条带证据者）。
这不是新假设场景：它是**遗漏了一道本仓库对同类判断已经强制要求的检查**。

子项（同条件的可执行性缺口）：条件 b 需读 `interest_rows`，它在
`ledger-flow.sqlite3`（`backend/app/server.py:1925`）里，而脚本写的是
`margin-repay.sqlite3`（`backend/app/server.py:1949-1951`）——两个不同的 sqlite 文件。
§6.2 的运维步骤只提到定位与备份 `margin-repay.sqlite3`，未提脚本还需读账本库。

**修复要求（可执行）**：
1. §3.2.2 条件 b 增加「且该区间 `coverage_for_window(结算时刻, now).complete` 为真」
   （复用 `backend/ledger_flow/service.py` 既有方法，不新增状态或契约）；不满足 →
   保持 NULL、保持开放。
2. §5 回补脚本用例增加「覆盖不完整 → 不推定、保持 NULL」。
3. §6.2 补上脚本对 `ledger-flow.sqlite3` 的只读访问路径（与 `margin-repay.sqlite3` 的
   定位/备份并列说明）。

#### F7 `in-range` — a/b/c 被表述为可"确认"归零，实际只能推定到"至多一个计息周期之后"；§8.1 命名的残余窗口不是真实残余窗口；`debt_cleared()` 无法区分推定零与观测零

修订版 §2 写「完全归零可由回补规则推定」，§3.2.2 把 a/b/c 的结果直接写入与实时观测
**同名同语义**的两列，§8.1 把残余风险描述为「资产恰好在极低息率下长时间不计息」。

独立核验后的实际推理强度：给定覆盖完整，b+c 只能推出「自结算时刻 T 之后的每个计息时点
债务为零」。T 与 T 之后第一个计息时点之间，债务仍可能非零并被**本表之外**的还款清零——
这正是计划 §7 自己具名的 O1 通道（币安 App／网页／交易所自动还款不入表）。此时真正的
归零事件是另一笔、发生在另一时刻、对应另一价格，而条件 a（"本地表最后一条 succeeded"）
**依然成立**，a+b+c 全部通过 → 假终态。§8.1 命名的是另一种残余（低息率不计息），**没有**
命名这条与 O1 的交互。对 STORJ 具体案例，该残余窗口 = 结算 `14:31:03` 至下一个计息时点，
约 29 分钟——是一个可量化、可写进文档的界，而不是「恰好完整命中 a+b+c」。

另两处同源的表述/判定问题：

- §3.4 把 `repay_after_borrowed` 注释为「还款后 `crossMarginBorrowed` **原样字符串**」，
  但回补写入的 `"0"` 并非该端点在该时刻的任何一次观测原样值。
- §3.3 `debt_cleared(record)` 只检查两个数值列是否均解析为 `0`，**不看** `repay_after_source`；
  因此 `backfill_inferred`（推定）与 `live_balance_after_repay`（观测）在终态判定点上完全
  等权。来源列提供了事后审计能力，但没有进入判定。

**修复要求（可执行）**：
1. §2 与 §3.2.2 改写：a/b/c 明确称为**推定**而非确认，写明残余窗口上界（≤ 一个计息周期）
   与其成因（O1 通道），并对 STORJ 给出具体窗口值。
2. §8.1 用上述真实残余窗口替换现有描述（现描述指向另一种情形）。
3. §3.4 修正 `repay_after_borrowed`/`repay_after_interest` 的列注释：说明该列可能承载回补
   推定值，实际来源以 `repay_after_source` 为准。
4. §3.3 二选一并写明理由：显式声明「推定零与观测零在 `debt_cleared()` 中等权」是有意
   决定，或让 `debt_cleared()` 区分来源。不得留作未言明的默认。

### 四、同根因刹车提示（AGENTS.md §8）

按规则「根因由评审者在 `问题记录` 中命名」，本评审命名两个根因家族，二者均已**连续两轮**
出现（P2 → P4）：

- **根因 A：把"没有观测到"或"可以推断"当作"已被证明"。** P2 F1（把交易所资本化行为当作
  结清证据）→ P4 F6（把账本无行当作无计息，且缺覆盖闸门）、F7（把推定表述为可确认，
  且判定点不区分推定与观测）。
- **根因 B：在"钱已出去、终态未落库"这条缝隙上追加观测动作。** P2 F2（新增观测未做异常
  隔离，可跳过 `resolve`）→ P4 F5（新增观测已隔离异常，但引入最长 15 秒延迟）。

因此下一轮修订**不得再对单点打补丁**：修订任务须对这两个家族各做一次穷举扫描——枚举
计划内**全部**以缺席/推断作为事实的判定点（含已改与未改），以及**全部**落在还款写路径
缝隙上的动作，并对清单外站点给出不适用理由。扫描本身仍算一轮。本提示不新增计数器、
数值限额或 `status.json` 字段；计划评审不触碰 `rework_count`。

### 五、P1 dispatch 八条 Acceptance Checks 复核

| # | 裁定 | 依据 |
|---|---|---|
| 1 确定性匹配规则、不臆造字段语义 | **pass** | §3.1 归零证据判定 + 三态排除 + 五形态覆盖 |
| 2 单一还款时价格权威定义、未来捕获、历史证据、取不到的行为 | **pass** | §3.2.1-1 / §3.2.2-1；命名已如实（F4 已解决） |
| 3 终态稳定、开放按当前价、切换恰一次、单一折算权威 | **pass** | §3.3 五个纯函数 + 双消费者改调；`_finalize_close_task` 不触碰的声明 P2 已核实为真 |
| 4 迁移/回补/幂等/回滚/生产验证 | **pass** | §3.4 + §6；`PRAGMA table_info` + 逐列 `ALTER ADD` 与 `backend/hedge_open_tasks/store.py:493-505` 既有模式一致（已重读确认）；缺口见 F6 子项 |
| 5 bounded 文件/测试清单，覆盖八类场景，拒绝投机抽象 | **pass** | §4 九行表 + §5 十九条用例；§7 明确拒绝外键/数量账本/缓存表 |
| 6 切换恰一次的时序断言 | **pass** | §5 测试 3 三段断言完整 |
| 7 复评派单合规 | **pass** | P4 packet 只读、`opus5`/anthropic、单一 skill、create-only 路径 `test ! -e` 已复核为 ABSENT、回 Bookkeeper `codex` |
| 8 零产品源码/测试/schema/状态/数据库/生产/活文档改动 | **pass** | `git status --short` 无输出 |

### 六、P3 dispatch 八条 Acceptance Checks 复核

| # | 裁定 | 依据 |
|---|---|---|
| 1 F1 corrected（资本化非结清；不把 succeeded/`amount="0"`/缺 `repaid_amount`/部分还款当全额证明） | **pass** | §1.3、§3.1 |
| 2 为"债务可确认归零"定义唯一可审计来源与存储证据，未来事件与证据不可得时的 fail-closed；处理各形态与历史行含 STORJ 且不虚构平仓单 | **fail** | 未来事件路径成立且可审计；**历史路径给出的是推定而非"verifiably zero"，且计划以"可确认"表述之**（F7），推定本身还缺覆盖闸门（F6）。不虚构平仓单关系一项成立 |
| 3 归零前全部按当前价；归零事件切换一次并稳定；测试证明部分不切、全额切一次、re-borrow 重开 | **pass** | §1.1-1.4；测试 2/3/4 |
| 4 F2 路径 A 可执行：异常边界、`resolve` 保证、缺价 `succeeded`+NULL、可执行异常测试 | **pass** | §3.2.1 + 测试 16 字面满足（"guaranteed" 指不被跳过）。修订新增观测带来的延迟记为独立新发现 F5，不折算为本条失败 |
| 5 F3/F4 解决；来源命名不强于代码可证 | **pass** | §3.4 `list_records()` 形状；§3.2.1-1 命名与 `snapshot.py:806-808` 引用已独立核实 |
| 6 schema/匹配权威/双消费者/迁移/NULL-only 幂等回补/回滚/fail-closed 一致；未来 NULL 如何恢复且不重发还款 | **pass** | §3.2.1「NULL 的恢复」段明文不重发、不改 `status`/`repaid_amount`/`update_time`，只填 NULL 列 |
| 7 O1-O3 具名；不扩围 | **pass** | §7 / §6.2 / §8.4；未见无当前证据支撑的扩围 |
| 8 P4 packet 合规 | **pass** | 同上表第 7 行 |

### 七、对修订版新增设计的独立代码依据核实（不接受计划自述）

1. **`fetch_unified_balances(force=True)` 语义** — 计划称「`force` 只驱逐该端点单一缓存键、
   触发一次新鲜签名 GET——既有机制」。核实
   `backend/services/private_client.py:588-598`：文档与实现均为 `_evict("GET",
   "/papi/v1/balance")` 后 `_cached_get`，且明文「`_cache.clear()` is never used」。
   **计划自述准确**。但同处证明它是网络调用——构成 F5。
2. **缺席语义（列表非 `None` 但无该 asset → 记 `"0"`）** — 核实
   `backend/services/private_client.py:593-601`：`not self.enabled` → `None`；
   `PrivateEndpointError` → `None`。软失败不会退化成空列表，故"缺席即零"只在真正成功的
   响应上生效。与 `backend/app/server.py:1069-1091` `_margin_repay_borrowed_assets`
   （要求 `cross_margin_borrowed > 0` 才算借款）确为同一列表的互补读法。**成立**。
3. **归零证据两列的字段名与语义** — 核实 `backend/domain/snapshot.py:1393-1397`：
   `crossMarginBorrowed`（全仓负债本金）与 `crossMarginInterest`（已计提未付利息，
   **独立**负债、不并入前者）确为 `/papi/v1/balance` 行上的原始字段；`1202-1205` 复述
   资本化事实。**计划取字段正确**。
4. **5 列 additive 迁移** — 核实 `backend/hedge_open_tasks/store.py:493-505` 的
   per-column 追加列表 + 循环 `ALTER` 模式确实存在，计划照此描述。**成立**。
5. **`list_records()` 形状让回退时刻可达** — 核实 `backend/margin_repay/store.py:51-63`
   `_row_to_doc` 现确无 `updated_at_us`；`updated_at_us` 在表中为 `INTEGER NOT NULL`
   （`_SCHEMA`），故恒有值。**F3 修复充分**。
6. **回补推定 a/b/c** — 见 F6、F7。条件 c 的实时核验是硬门且有效；条件 b 缺覆盖闸门；
   a+b+c 的合成推理强度弱于计划表述。
7. **双消费者单一折算权威** — 核实 `backend/ledger_flow/domain.py:496`
   `build_pnl_series` 与 `backend/ledger_flow/service.py:475` `sum_interest_by_asset`
   为仅有的两条利息折算路径（`backend/hedge_open_tasks/service.py:2779` 的第三处调用只取
   币本位合计入 close-log，不折 U）。修订版把两处 U 折算收口到同一组纯函数，**成立**。

### 未完成事项 / 本复评未做

- 未运行任何测试（计划阶段无可执行交付物）；§5 的十九条用例是**计划**，其可执行性以
  测试名与断言方向判断，未实际编写或运行。
- 未访问生产环境、数据库或凭据；未验证 `STORJUSDT` 公共 1m K 线在 `2026-08-20 14:31 CST`
  附近的实际可得性（计划 §6.1 已把该验证安排在实现阶段并要求存证，此安排合理）。
- 未验证 `scripts/` 是否在直连守卫扫描范围内（计划 §3.2.2 末段已自述该点待实现任务确认）。
- 未对前端零改动做运行时验证；依据为 wire 形状 additive 且 §3.4 明确归零证据三列不进
  `_row_to_doc`。

### 命令与结果

```text
git rev-parse HEAD                                  -> 8f46f78bfde14f978621066a31873883e59ed642
git status --short                                  -> （空，工作区干净）
test ! -e <本 handoff 路径>                          -> ABSENT_OK（写入前）
grep -n "def fetch_unified_balances" -A 55 backend/services/private_client.py
                                                    -> 579-601：force 只 _evict 单键；失败返回 None
sed -n '216,232p' backend/services/snapshot_service.py -> timeout=config.request_timeout
grep -n "request_timeout" backend/config.py          -> 58: request_timeout: float = 15.0
sed -n '1589,1596p' backend/app/server.py            -> coverage_for_window(...).complete 既有守卫
sed -n '493,505p' backend/hedge_open_tasks/store.py  -> per-column ALTER 追加模式
grep -rn "crossMarginInterest|crossMarginBorrowed" backend/ --include=*.py
                                                    -> domain/snapshot.py:1202-1205, 1393-1397
grep -n "MarginRepayStore(|LedgerStore(" -A 3 backend/app/server.py
                                                    -> 1925 ledger-flow.sqlite3 / 1949 margin-repay.sqlite3
sed -n '780,815p' backend/domain/snapshot.py         -> 806-808: fresh = four_valid（无时效含义）
```

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md`
  2. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  3. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P3-repaid-interest-price-plan-revision.dispatch.md`
  4. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P2-repaid-interest-price-plan-review.handoff.md`
  5. `backend/app/server.py`
  6. `backend/services/private_client.py`
  7. `backend/services/snapshot_service.py`
  8. `backend/config.py`
  9. `backend/ledger_flow/service.py`
  10. `backend/margin_repay/store.py`
- 执行：Bookkeeper `gpt-5.6-sol`（label `codex`）核验本 handoff 与 `status.json`
  revision 8 一致后，将 verdict `REWORK` 与本报告第四节命名的两个根因原样带入下一个修订
  dispatch 的 `Goal`；修订任务须按同根因刹车做穷举扫描，而非逐条点补。F5 修复要求第 4 项
  （是否完全取消实时归零观测）是 Human 取舍，须作为具名决策项上交。
- 关卡：Planner 修订后重新进入实现前计划评审；未经新一轮计划评审通过，不得进入实现
  dispatch。
- 不能假设的事实：
  - 不得假设 `fetch_unified_balances(force=True)` 是内存读——它是签名网络 GET，超时上限
    由 `backend/config.py:58` 的 `request_timeout`（默认 15.0 秒）决定。
  - 不得假设异常隔离等于不延迟；`resolve` 未被跳过不代表未被推迟。
  - 不得假设 `interest_rows` 无行即无计息；本仓库对同类判断已强制要求
    `coverage_for_window(...).complete`。
  - 不得假设 a+b+c 证明"那次还款时点已归零"；它只能推定到至多一个计息周期之后，
    残余窗口的成因是计划 §7 自己具名的 O1 通道。
  - 不得假设 `repay_after_source` 参与终态判定；§3.3 `debt_cleared()` 目前只看两个数值列。
  - 不得把「利息计提时冻价」作为任何默认或回退（Human 已否决）；本 `REWORK` 的全部修复
    要求均在 Human 两项固定决定之内。
  - 本复评未运行测试、未访问生产、未验证 `STORJUSDT` 历史 K 线可得性。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

复评结论是**返工**，但比上一轮好很多。

上一轮我提的四个问题**全部改好了**：不再说"还过款就算结清"、改成只认"债务真的归零"；
取价那一步的异常防护加上了；两个小问题（取不到还款时间的回退字段、把取到的价说得太满）
也都改对了。三条不拦路的观察也都写进计划了。你定的两条口径——部分还款绝不锁价、以及
取价必须异常隔离——在计划字面上都落实了，测试也都排上了。

但修订过程中冒出三个新问题，都跟钱和账有关：

**一、为了拿"债务归零"的证据，计划新加了一次向币安查余额的网络请求，而且把它放在"钱已经
还出去"和"记下还款成功"这两步的中间。** 我去查了这个请求的超时设置，是 **15 秒**。也就是说
最坏情况下，钱已经还了，但"还款成功"这条记录要等最多 15 秒才写下来。这段时间里如果服务
重启、部署或者进程被杀，这笔还款就永远卡在"处理中"——拿同一个请求号去查只会一直看到
"处理中"，而换一个新请求号会**真的再还一次钱**。

计划里还专门写了一句"不存在延迟落库的路径"，这句话对上一个观测（读内存，不联网）是对的，
对这个新加的联网请求是错的。

修法很简单：**先把还款结果记下来，再去查余额**，查到了用现成的补写机制填进去就行。计划里
本来就有这个补写机制，不用新加东西。

**二、判断"历史上那笔还款是不是把债还清了"，计划用的一条依据是"之后再没产生新利息"。
但它没检查那段时间账本有没有断档。** 这个项目里对同类判断本来就有硬规矩——持仓统计那边
就是这么做的：账本覆盖不全的时间段，一律不当真值。这条漏了。后果是：如果账本那段时间
有空洞，一笔其实**没还清**的还款会被判成"已还清"，然后把利息成本永久锁在错的价格上，
而且以后真正还清时也不会再纠正了。

顺带一个小的：这条判断要读的是**另一个数据库文件**（账本库），而计划的运维步骤只写了怎么
找和备份还款库，没提账本库。

**三、计划说历史那笔 STORJ 还款"可以确认归零"，实际上只能"推定"。** 它的三条依据合起来
能证明的是"这笔还款之后最多一个计息周期内债务归零了"，不是"就在那一刻归零"。中间那段
空隙（STORJ 这笔大约 29 分钟）里，债务有可能是被**在币安 App 上手动还的**——那种还款我们
表里根本没记录（这正是计划自己写下的那条限制）。真那样的话，归零的其实是另一笔、另一个
价格，而计划的三条依据**照样全部通过**。计划在风险那一节提到了另一种残余风险，恰好没提
这一种。

这个不一定要改逻辑，但**必须把话说准**：写清是推定不是确认，写清那段空隙有多长、为什么
会有。另外计划把推定出来的"0"写进了一个标注为"交易所原样返回值"的字段里，判断的时候
也不区分这个 0 是推定的还是真查到的——这两点要么改，要么明说是有意为之。

**还有一件我必须点出来的事**：这两轮返工的病根是同两个。一个是"没看到"或"能推出来"被当成
"已经证明"（上轮是把资本化当结清，这轮是把没记录当没欠债）；另一个是往"钱已出去、结果没
记下"那条缝里加动作（上轮是加了个没防护的，这轮是加了个会拖时间的）。按项目规矩，
**下一轮不能再一条条打补丁了**，必须把计划里所有"靠推断下结论"的地方和所有塞在还款流程
缝里的动作各自列全一遍，逐个说清楚。

要你拍板的只有一件：第一个问题除了"先记录再查余额"，还有个更省事的选择——**干脆不在还款
当下查余额，全部交给补价脚本事后补**。哪个都行，是取舍不是对错，我不替你定。

本次复评全程只读，除本交接件外未写任何文件，未改计划、状态、代码，未提交，未接触生产。
按规矩再披露一次：本模型此前在同一 stage 做过一次非正式方向咨询和上一轮正式计划评审，
但**不是**这份计划的作者（计划由 Planner claude_glm 撰写）；本轮所有事实都从仓库重新核过。

[TASK_RESULT v2]
任务 ID: P4-repaid-interest-price-plan-rereview
执行结果: completed（完成）
结果摘要: 计划复评返工。P2 的 F1-F4 全部解决、O1-O3 具名、Human 两项决定落实。但新增三个 in-range 发现：F5 归零证据观测把 15 秒超时的签名 GET 插在还款与落终态之间（计划自称无延迟路径，与设计矛盾）；F6 推定条件 b 缺 coverage_for_window.complete 闸门，账本断档会造成假终态；F7 a/b/c 只能推定到一个计息周期后，被表述为可确认。命名两个连续两轮的同根因，下轮须穷举扫描。
产物: [reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md]
检查结果: [只读全新会话、唯一写入为 create-only handoff、Human Brief 内含完整 TASK_RESULT v2 起止标记、marker 前无重复 — pass; verdict 明确 REWORK，F1/F2/F3/F4 逐项裁定为已解决并引用修订版章节，三条新发现均标注 in-range 且带可追溯证据锚点与落章节的修复要求 — pass; Human 两项决定核对：部分还款不锁价（测试 2 断言存在）、归零才切终态、资本化表述已改、价格命名为捕获时刻快照买一 — pass; Human 决定二的 resolve 保证在字面上成立，但修订新增的余额观测破坏其所保护性质 — fail（记为 F5）; O1-O3 已具名且未扩围（§7/§6.2/§8.4） — pass; P1 八条全 pass；P3 八条中第 2 条 fail（历史路径是推定而非 verifiably zero），其余 pass — fail; 修订版新增设计七项逐一独立核实代码依据（force 语义、缺席语义、字段名、ALTER 模式、list_records、a/b/c、双消费者收口），未接受计划自述 — pass; 零源码/状态/生产改动，git status --short 无输出 — pass]
阻塞项: [none（复评已完成；F5 修复要求第 4 项"是否完全取消实时归零观测"须 Human 取舍后 Planner 才能定稿）]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md
修复要求: reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md
本地北京时间: 2026-08-28 20:20:19 CST
下一步模型: Bookkeeper gpt-5.6-sol（label codex）——评审者交回，由其核验后返给 Planner
下一步任务: 读取：reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P4-repaid-interest-price-plan-rereview.handoff.md；reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md；reports/agent-runs/2026-08-28-repaid-interest-price-v1/P3-repaid-interest-price-plan-revision.dispatch.md；执行：核验本交接件与 status.json revision 8 一致后把 REWORK 返回 Planner claude_glm，并把本报告第四节命名的两个根因原样写入下一个修订 dispatch 的 Goal、要求按同根因刹车做穷举扫描，同时把 F5 修复要求第 4 项作为具名 Human 决策项上交；关卡：Human 定下该取舍后 Planner 修订计划，修订稿须重新通过实现前计划评审才可进入实现 dispatch
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `7e1755f3ee7f73d98b91eac2c4b0541aecc431778af5d4503bc80e1cec88af32`
- verified_at: `2026-08-28 20:27:06 CST`
- status_revision_checked: `8`
- identity_check: `pass`（task_id、role、target model、stage_id、base_sha、HEAD 与 P4 派单一致）
- source_structure_check: `pass`（Human Brief 内唯一完整 `[TASK_RESULT v2]`；摘要 222 字符；
  8 项检查；明确 `REWORK`；问题记录、修复要求、读取/执行/关卡齐全）
- evidence_check: `pass`（Required Reading 十条路径均存在；F5-F7 均为 `in-range`，含代码锚点、
  实际影响与可执行修复要求；F1-F4/O1-O3 逐项复核）
- scope_check: `pass`（Reviewer 仅创建派单允许的 handoff；未改计划、代码、测试、schema、状态、
  PROJECT_STATE、其他文档或生产环境）
- verdict: `REWORK`（已核验，不代表计划接受）
- same_root_brake: 下一轮 Planner dispatch 的 Goal 必须原样携带两个根因家族并做穷举扫描：
  `根因 A：把"没有观测到"或"可以推断"当作"已被证明"。`；
  `根因 B：在"钱已出去、终态未落库"这条缝隙上追加观测动作。`
- next_state: `status.json.current_task.state = verified`；等待 Human 决定是否完全取消实时归零观测，
  或保留但移到 `store.resolve` 之后再以 NULL-only 条件补写。
- rework_count_effect: `0`（实现前计划评审 `REWORK` 不计正式交付返工轮次）。

## Errata (append-only)
