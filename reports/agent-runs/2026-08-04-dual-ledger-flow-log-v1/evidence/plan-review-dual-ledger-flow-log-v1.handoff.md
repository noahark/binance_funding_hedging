# Task Handoff: plan-review-dual-ledger-flow-log-v1

## Source Report (author-only; immutable after task end)

- task_id: `plan-review-dual-ledger-flow-log-v1`
- role: `Reviewer`（计划评审，只读）
- target model: `deepseek`（provider `deepseek`）
- stage_id: `2026-08-04-dual-ledger-flow-log-v1`
- created_at: `2026-08-04 13:01:39 CST`
- base_sha: `dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8`
- delivery_sha: `none`（本任务为只读计划评审，无交付提交）

### 评审范围与实际动作

按 `AGENTS.md` §8「计划评审」与设计 `docs/planning/2026-08-04-dual-ledger-flow-log-design.md` §17.3，对设计定稿 v1.1（§11–§18）与三份实现 dispatch（A `backend-ledger-store-fetch-v1`、B `backend-ledger-schedule-api-v1`、C `frontend-dual-ledger-flow-log-v1`）做独立跨 provider 只读评审。全程未修改任何受审对象、未启动其他终端、未访问网络、未读凭据、未做实盘操作；唯一写入为本交接件（Bookkeeper 预检 `test ! -e` PASS(absent)，2026-08-04 13:01:39 CST 复验一致）。

已读取证据：设计 §1–§18、三份 dispatch、plan handoff（含勘误 1）、两份 recon、`backend/services/private_client.py`、`backend/services/snapshot_service.py`、`backend/app/server.py`、`backend/borrow_tasks/scheduler.py`、`backend/borrow_tasks/store.py`、`backend/tests/test_private_client.py`、`frontend/index.html`、`frontend/self-check.js`、`docs/api/public-market-contract.md`、`status.json`（revision 3，current_task 与本任务一致）、`ACTIVE.json`。git 核验：`base_sha` 存在，HEAD `801464a` 晚于 base_sha，工作树干净（受审对象已提交入库）。

### 结论：评审结论 `REWORK`

七问中有五问通过、两问（Q2、Q5）需修订后通过；补充核查发现五项「实现必撞」级契约缺口（F1–F5）与一项未定义语义（F6）。按 §17.3「评审不过则实现不得开始」，计划需修订后才可实现。所有发现均为本次交付（设计 v1.1 + 三份 packet）内的契约问题，范围分类全部 `in-range`，无 `pre-existing-independent`（代码尚未实现）、无 `pre-existing-release-critical`。`audit_log` 无上限列表为既有问题，已在设计 §17.4 记录为已知代价，不列为发现。

### 七个必答问题（设计 §17.3）

**Q1「本次新增」按入库时间、手动刷新不移动基准；资金费分批/延迟到账下是否误导？3 小时重叠窗口够不够？—— pass（带观察 O1）**

- 口径自解释充分：基准时刻写死在标题（§15.4）、`delta.complete=false` 时不显示数字（§13.2 规则 10）、「本次新增/今日累计/区间累计」三口径各自标注（§13.7）。「入库时间」语义不会把 10:35 拉到、9:58 发生的资金费算错——它正确地落在「自 11:01 以来新增」（first_seen=12:01 run 时）窗口，这正是该口径的语义。不误导。
- 3 小时重叠 + 每小时 run 的捕获模型：run n 窗口 `[coverage_end(n-1) - 3h, now]`，因此「发生时间 ≥ coverage_end - 3h、可见延迟 ≤ 3 小时」的记录必被下一次 run 捕获。资金费为 4h/8h 结算、晚到为分钟级（recon 证据：原型脚本仅 `Sleep 10s` 再拉一次），3 小时足够。**边界**：可见延迟 > 3 小时、且发生时间早于 `coverage_end - 3h` 的记录永久丢失且无检测（coverage 仍显 complete=true），见 O1——建议在 §17.4 记录此「尽力而为」边界。

**Q2 `coverage` 护栏是否足以防止「本地没拉到」被读成「交易所没发生」？—— 建议修改（F4）**

- 主路径成立：窗口起点恒为 `coverage_end - 3h`，逐小时失败时段会被下一次 run 自动回补（§15.2），不会留下永久空洞；`window.start < coverage.start` → `complete=false` → 前端提示「本地数据只到 <日期>」（§13.2 规则 7、§13.7）。
- **缺口**（F4）：> 30 天停机截断场景，§15.2 规定「`coverage_start_ms` 不变、标为不连续」，但 §13.2 的 `coverage` 只有 `start_ms/end_ms/complete` 三个字段、规则 7 只按 `window.start < coverage.start` 触发 false——**coverage 内部空洞无法表达**：查询完全落在空洞内的窗口时 `complete` 会为 true、结果为空 → 前端渲染「该时间窗无记录」，恰好击穿规则 7「空结果绝不允许被呈现为这段时间没有流水」。需统一 `complete` 语义（修改要求见 F4）。

**Q3 幂等键与「已存在的行绝不覆盖」是否足以保证增量不重复计数？—— pass（带观察 O6）**

- `tx_id` / `(income_type, tran_id)` 主键 + `ON CONFLICT DO NOTHING` + `first_seen_run_id/first_seen_at_ms` 保持首次值（§14 规则 2）→ 重叠回拉旧行不重计；增量判据 `first_seen_at_ms > baseline_ms` 严格成立（run N 写入时刻晚于 run N-1 finished）。manual run 带入的行 first_seen 落在当前窗口内 → 计入下次增量，与 N6 一致。单飞锁（§15.3）消除进程内并发写；跨进程双跑为已记录已知代价（§17.4），SQLite 冲突写入仍原子。
- 观察 O6：`first_seen_at_ms` 用墙钟，系统时钟回拨时可能出现 first_seen ≤ baseline 导致漏计（低概率，NTP 下罕见）。

**Q4 每 20 秒醒一次 +「本自然小时是否已有成功 run」在重启、时钟跳变、休眠唤醒下是否漏跑或重复跑？—— pass（带观察 O6）**

- 判据查询库（`flow_refresh_runs` 本小时成功 scheduled run），天然跨重启（重启后查库）与休眠唤醒（唤醒后 20 秒内补跑）；时钟前跳导致的漏跑小时由 3 小时重叠窗口兜底；时钟回跳可能造成同一自然小时重复执行，但幂等写入 + 单飞锁下无害（仅多耗权重）。分钟判据 `minute ≥ 1` 正确表达「整点后 1 分钟」。多进程双跑语义已记录（§17.4）。

**Q5 三任务文件边界是否真的零重叠？B 对 A 的接口依赖是否已在 §14/§16 写死？—— 建议修改（F3；观察 O2、O3）**

- 文件边界实质零重叠：A（private_client + ledger_flow 底座 + 其测试）、B（service/scheduler/server/snapshot_service 访问器 + 其测试 + 契约文档）、C（index.html/self-check.js）两两不相交。**例外**：三份 dispatch 的 Allowed Files 都含 `status.json`（各自仅改 own `current_task.state` 字段），串行下无冲突——设计 §16「两两不相交」措辞与文件事实不符，见 O2（建议注明 status.json 语义例外）。
- B 对 A 的依赖：§14 SQL schema 与硬规则、§13.2/§13.5 响应契约已冻结；Python 函数签名未冻结，靠 B 的 Inputs 读 A 的 handoff「任务 A 的交付事实与实际接口」传递（O3，串行可控，建议 A 的 handoff 列明 store/domain 公开签名）。
- **F3**：A 的 dispatch 验收 4 写「最近 N 次成功 scheduled run」，与设计 §15.4「倒数第二次成功 scheduled/startup_catchup run」不一致——startup_catchup 被排除会使启动场景增量基准推迟建立、且 B 依赖的 store 查询语义与设计不符。

**Q6 金额全程 TEXT + Decimal、禁止 SQL 聚合——是否有遗漏的精度泄漏点？—— pass（带观察 O4）**

- 设计已闭环：TEXT 存储（§14 规则 1）、`Decimal` 精确求和 + `format(total,'f')`（§13.2 规则 3）、无 SQL `SUM/AVG`、缺失即 `null` 不造 0（规则 4）、分组含不可解析金额时 `*_total=null` 且 `unparsed_row_count>0`（规则 5，同样适用于 delta/today）、`txId` 超 2^53 以字符串下发（规则 1，recon 样本 `2328408217636413776 > 2^53` 核实）。排序用时间戳列（INTEGER）与 TEXT 幂等键，不涉金额运算。前端不重算汇总（C 硬规则 4）。
- 残留风险是实现纪律（`float()`、SQL 聚合、`Decimal(0.1)` 式构造），已由 A 验收 5 / B 验收 6 约束为测试或静态断言。观察 O4：Decimal 默认 context 精度 28 位对币安金额（≤8 位小数、总额 ≤ 数十位整数）足够，建议汇总时仍显式 `localcontext()` 以防未来加总项增多。

**Q7 定时上游拉取新增独立调度线程——边界是否可接受？—— pass**

- 借币调度器（`backend/borrow_tasks/scheduler.py`，monotonic 节拍 + `threading.Event` 停止）已有同类独立线程先例；本设计明确新 fetcher 不走 `_cached_get`（避免与 snapshot worker 共享无锁 TTL 缓存 `_cache`，A dispatch 已写明）、不写 `PrivateClient.last_error`（防污染 `borrow_validation` 降级依据）、审计只记 `audit_log.append`（GIL 下原子）。日常权重约 32/小时（papi 限频约 6000 req/min/IP，recon 实测），无压力。B 的装配沿既有 `_Handler` 类属性注入模式（`server.py:116-119/726-736/856-933` 核实），`build_server` 签名不变。边界可接受。

### 补充核查（dispatch 要求，不限于七问）

**冻结接口契约 `private-ledger/v2` 硬规则自查**：

- ID 字符串化、金额原样透传、缺失即 `null`（含空串 symbol/trade_id 归一化，recon 证实 TRANSFER `symbol=""`、资金费 `tradeId=""`）、`*_total` 含不可解析行即 `null`、`row_limit_applied` 与全量 `row_count`/`summary` 并存、排序即最终展示序——以上规则内部自洽，无矛盾。
- 排序键细节：`tx_id`/`income_type` 为 TEXT，SQLite 按字典序比较；同长度数字字符串字典序 == 数值序，且排序键仅为稳定次序（§4.3「同时间可按 txId 稳定次序」），无正确性影响。
- **F1（in-range，建议修改）事务粒度矛盾**：§13.5「任一页失败 → 该栏本次 run 记为 error 且该栏本次不写库（半截账比没有账更危险）；另一栏不受影响」与 §14 硬规则 5「一次 run 的所有写入（明细 + run 记录 + ledger_meta）在同一个事务内提交；失败则整体回滚，只留 run 记录里的 error」字面冲突——整体回滚时 run 记录也在事务内，无法「只留 error」；若按 run 级回滚则违反「另一栏不受影响」。修改要求：明确事务模型——推荐「run 记录始终写（含两栏 status/error 短码）；仅成功栏产生明细写入；成功栏明细 + coverage 更新 + run 记录在同一事务；失败栏零明细」。
- **F2（in-range，建议修改）`consecutive_failure_count` 无数据源**：§13.2 `last_run` 示例含 `consecutive_failure_count`（规则 9 附近），§15.3 也要求页面显示连续失败次数，但 §14 `flow_refresh_runs` 表无此列。修改要求：明确来源——推荐 service 按 run 表最近连续 error 记录实时计数，不新增列（避免 A 建表与 B 读数脱节）。
- **F5（in-range，建议修改）空库空态形状未冻结**：§13.2 示例恒有非空 `last_run`/`coverage`/`delta`，但「首次启动 / 私有通道未启用 / 从未成功 run」时（§15.3 最后一条：页面显示「私有通道未启用，本地无数据」）`GET flow-log` 中 `last_run`、`coverage`、`delta` 的取值未定义。首次展开即 GET 是必走路径，前端三态「该时间窗无记录 / 上次刷新失败 / 私有通道未启用」（§13.7）需确定性判定依据。修改要求：冻结空态契约——推荐 `last_run: null`、`coverage: {"start_ms": null, "end_ms": null, "complete": false}`、`delta.complete: false`，前端按此渲染。
- **F6（in-range，建议修改）两项未定义语义**：(a) manual run 成功是否更新 `coverage_end` 未写明（决定下次 scheduled 窗口起点与晚到保护范围）；(b) 达到页数上限 `truncated=true` 时，已拉到的页是否部分入库未写明（§14 规则 5 与 §13.5「任一页失败不写库」都未覆盖该分支）。修改要求：写死——推荐「manual 成功同样更新 coverage（kind 记为 manual）；truncated 时该栏不提交明细（整栏回滚）并置 `truncated=true`」，避免 coverage 前移制造空洞。
- 非 200 分支（400/503/409/429）、POST body 丢弃、错误短码集合、GET 零上游 I/O、无 30 天查询上限——均自洽，无矛盾。

**需求 1 按钮移动（设计 §11）对既有 self-check 与 `#private-pm-source-time` 位置约定的影响**：

- 核实通过：`frontend/self-check.js:156` 以 id 注册 `btn-privacy`/`privacy-label`/`privacy-icon-path` 等、`:1499` 以 id 触发点击 listeners——均不断言父元素，移动位置不失效；`#private-pm-source-time` 仍留在 `.panel-title` 内标题下方（设计 11.3）；`.panel-title` 现为 `display:grid`（`index.html:286` 核实），新增 `.panel-title-row` 承载标题与开关的方案与现状吻合；`state.privacyHidden`（`index.html:1424/1587`）、`formatBeijing(ms)`（`:1670`）均存在，C 的复用约束可满足；既有定时器 `refreshState.refreshTimer`/`countdownTimer`（`:2147-2150`）与 C「仅新增一个流水日志专用 60 秒轮询」不冲突（需独立变量并 `clearInterval`）。
- 白名单断言连带更新已识别：`test_private_client.py:135` `== 13` 与 `:148-156` base-url 集合断言，A 验收 1 已要求 15 并同步集合。✓
- 页数上限余量：左栏 40 页 = 4000 行 vs recon 30d = 1647 行（17 页），余量 2.3 倍；右栏 10 页 = 10000 行 vs 30d = 193 行。借款量显著增长时左栏可能触顶 `truncated`，护栏已覆盖（O8 观察）。

### 发现清单与范围三分类

全部为本次交付（设计 v1.1 + 三份 packet）内契约问题，`in-range`；无 `pre-existing-*`。按严重度：

| # | 严重度 | 内容 | 修改要求（可执行） |
|---|---|---|---|
| F1 | 建议修改 | §13.5 栏级失败隔离 vs §14 规则 5 整体回滚，事务粒度矛盾 | 明确事务模型：run 记录始终写；仅成功栏写明细；成功栏明细 + coverage + run 记录同一事务；失败栏零明细 |
| F2 | 建议修改 | `last_run.consecutive_failure_count`（§13.2/§15.3）在 §14 表无列 | 明确来源：service 按 run 表最近连续 error 计数，不新增列 |
| F3 | 建议修改 | A 验收 4「成功 scheduled run」vs §15.4「成功 scheduled/startup_catchup run」 | 统一为含 startup_catchup；`delta.complete` 判定同步（≥2 次成功 run 含 startup_catchup） |
| F4 | 建议修改 | coverage 内部空洞无法表达，截断场景空洞内查询误报「无流水」（Q2 核心） | 统一 `complete` 语义：窗口内覆盖不连续（含 `window.start < coverage.start` 或存在未回补空洞）即 false；前端必须提示 |
| F5 | 建议修改 | 空库/从未成功时 `last_run`/`coverage`/`delta` 形状未冻结 | 冻结空态：`last_run: null`、`coverage: {start_ms: null, end_ms: null, complete: false}`、`delta.complete: false` |
| F6 | 建议修改 | manual 是否更新 coverage_end、truncated 部分写入语义未定义 | 写死：manual 成功同样更新 coverage；truncated 时该栏整栏回滚不提交明细并置 truncated |

观察项：O1（>3h 晚到且发生时间早于 `coverage_end-3h` 的记录永久丢失且无检测，建议 §17.4 记录）；O2（§16「零重叠」措辞 vs status.json 共享的事实，建议注明语义例外）；O3（store/domain Python 签名未冻结，靠 A 的 handoff 传递，建议 A 的 handoff 列明公开函数签名）；O4（Decimal 默认精度 28 位足够，建议汇总显式 `localcontext()`）；O5（`GET flow-log` 的 Cache-Control 未冻结，建议 no-store 与既有路由一致）；O6（时钟回拨对 first_seen/baseline 的错位，低概率观察）；O7（§15.4「不足两次成功 scheduled run」措辞与 baseline 定义不一致，并入 F3 统一）；O8（左栏 40 页上限余量 2.3 倍，借款量增长可能触顶，truncated 护栏已覆盖）。

### 命令与结果（离线，只读）

- `test ! -e reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md` → PASS(absent)（2026-08-04 13:01:39 CST 复验）。
- `git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在，等于 `status.json.base_sha`；`git rev-parse HEAD` → `801464af90ff75d8432e420ce098d44660d43dd7`；`git status --short` → 空（受审对象已提交入库）。
- `date '+%Y-%m-%d %H:%M:%S CST'` → `2026-08-04 13:01:39 CST`。
- 未运行服务、未访问网络、未读取凭据、未执行任何写操作（除本交接件）、未提交。

### 仓库内证据路径

- 受审设计：`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§11–§18）
- 受审 packet：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`、`backend-ledger-schedule-api-v1.dispatch.md`、`frontend-dual-ledger-flow-log-v1.dispatch.md`
- 只读证据：`reports/api-samples/2026-08-borrow-interest-history-recon-v1/20260804T0008Z/recon.md`、`reports/api-samples/2026-08-um-income-funding-recon-v1/20260804T0015Z/recon.md`
- 本交接件：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md`；`docs/planning/2026-08-04-dual-ledger-flow-log-design.md`（§13.2/§13.5/§14/§15.2/§15.4）；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md`（验收 4）；`reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md`
- 执行：Human 将本 verdict 转交 Bookkeeper 落盘（计划评审 REWORK 不触 `rework_count`）；Planner 按 F1–F6 修订设计 §13.2/§13.5/§14/§15.2/§15.4 与 A/B dispatch 措辞
- 关卡：Planner 修订后按 §17.3 重出计划评审（或经 Human 认可缩小至修订增量），ACCEPT 后方可路由 `backend-ledger-store-fetch-v1`
- 不能假设的事实：F1–F6 未修订前不得开始 A；三份实现 packet 的 `status_revision` 为占位符，路由前须由 Bookkeeper 替换为实际 revision；A 的 `test_private_client.py:135` 白名单断言 13→15 未改必红；`#btn-privacy` 移动不破坏既有 self-check（id 定位核实）。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: plan-review-dual-ledger-flow-log-v1
执行结果: completed（完成）
结果摘要: 只读计划评审完成，结论 REWORK：七问中 Q1/Q3/Q4/Q6/Q7 通过，Q2（coverage 内部空洞）与 Q5（A packet 与 §15.4 基准口径不一致）需修订；另发现 F1–F6 六项实现必撞级契约缺口（事务粒度、consecutive_failure_count 无列、空态形状未冻结、truncated/manual 语义未定义）。均为 in-range，不触 rework_count。需求 1 与冻结契约其余硬规则核实通过。
评审结论: REWORK（返工）
问题记录: docs/planning/2026-08-04-dual-ledger-flow-log-design.md（§13.2/§13.5/§14/§15.2/§15.4）；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md（验收 4）
修复要求: docs/planning/2026-08-04-dual-ledger-flow-log-design.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-store-fetch-v1.dispatch.md；reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/backend-ledger-schedule-api-v1.dispatch.md
产物: [reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md]
检查结果: [七问逐条回答且引用 文件:行号/§ 号: pass, 每条发现按范围三分类标注且附证据: pass, 每条发现标严重度且阻塞项附可执行修改要求: pass, 评审结论与问题记录/修复要求齐备: pass, 交接件含 Source Report + Human Brief + TASK_RESULT v2 + 三行中文交接、delivery_sha=none: pass, 全程只读且未触碰受审对象/status/PROJECT_STATE/git: pass]
阻塞项: [none；verdict 经 Human 转交 Bookkeeper 落盘并返回 Planner 修订]
本地北京时间: 2026-08-04 13:01:39 CST
下一步模型: bookkeeper1（本阶段簿记，Human 移交本任务结果）
下一步任务: 读取：reports/agent-runs/2026-08-04-dual-ledger-flow-log-v1/evidence/plan-review-dual-ledger-flow-log-v1.handoff.md；执行：核验并封存本评审，将 REWORK verdict 连同 F1–F6 转交 Planner 修订设计 §13.2/§13.5/§14/§15.2/§15.4 与 A/B dispatch 措辞；关卡：Planner 修订后重出计划评审，ACCEPT 后方可路由 backend-ledger-store-fetch-v1
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（待 Bookkeeper 追加：源区块 SHA-256、核验时间、核对的 status revision、通过或拒收依据、可复现命令与后续状态。）

## Errata (append-only)

（无。）

## Bookkeeper Verification

- 核验时间（本地）：2026-08-04 13:10:00 CST
- source_sha256（marker 前字节）：`ac4b097c0dda04e7318bff6ded0d42da827e118d75990ac5d2a71911e82f540d`
  （复现：读本文件，取 `<!-- BOOKKEEPER_APPEND_ONLY:` 之前全部字节，`hashlib.sha256` 十六进制）
- 核对的 status revision：3（`current_task.id = plan-review-dual-ledger-flow-log-v1`、`state = dispatched`，与评审交接件声明一致；预检 `test ! -e` 于 2026-08-04 12:50 CST 通过，评审在 13:01:39 CST 复验一致）
- task_id / role / stage_id 与 `status.json` 一致：`plan-review-dual-ledger-flow-log-v1` / `Reviewer` / `2026-08-04-dual-ledger-flow-log-v1`
- base_sha 核验：`git rev-parse --verify dc4cc6d9dc629c06cff4a98f98ff7a81a533a3c8` → 存在且等于 `status.json.base_sha`；HEAD `801464a` 晚于 base_sha，符合 SHA Discipline
- delivery_sha：`none`（只读计划评审，无交付提交；git status 仅 `evidence/` 未跟踪本交接件，其余工作树干净）
- 结论：**通过（verified）**。`评审结论: REWORK` 与 `问题记录` / `修复要求` 齐备；七问逐条回答且引用 §/文件:行号；F1–F6 全部 `in-range` 并附可执行修改要求；无 `pre-existing-*` 发现；计划评审 REWORK 按 `AGENTS.md` §8 不触 `rework_count` —— **判定成立**，`rework_count` 保持 0。
- 后续状态：计划评审任务 → `verified`；REWORK verdict 与 F1–F6 返回 Planner（`plan-revise-dual-ledger-flow-log-v1`，opus5）修订设计 §13.2/§13.5/§14/§15.2/§15.4 与 A/B dispatch；修订后按 §17.3 重出计划评审（或经 Human 认可缩小至修订增量），ACCEPT 后方可路由 `backend-ledger-store-fetch-v1`。

## Errata (append-only)

（无。）
