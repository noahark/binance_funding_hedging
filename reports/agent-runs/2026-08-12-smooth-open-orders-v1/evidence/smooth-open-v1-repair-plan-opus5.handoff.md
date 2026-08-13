# Task Handoff: smooth-open-v1-repair-plan-opus5

## Source Report (author-only; immutable after task end)

- task_id: `smooth-open-v1-repair-plan-opus5`
- role: `Planner`
- target model: `claude-opus-5` / provider `anthropic`
- stage_id: `2026-08-12-smooth-open-orders-v1`
- created_at: `2026-08-13 09:48:33 CST`
- base_sha: `bfb633799ed904ba6d8364bffef7f048d77137dd`
- delivery_sha: `none`

`delivery_sha: none` 的依据：本 dispatch 明确禁止 commit，Planner 未产生任何交付提交；两份计划文件的改动以未提交工作树内容交给 Bookkeeper 按记账职责固化。

### 启动核对

cwd `/Users/ark/Desktop/ai code/funding_hedging-smooth-v1`、分支 `smooth/v1-fullstack`、`status.json` revision `27`、`current_task.id = smooth-open-v1-repair-plan-opus5`、`target_model=claude-opus-5`、`provider=anthropic`、`base_sha=bfb633799ed904ba6d8364bffef7f048d77137dd`（`git cat-file -e` 通过）、唯一 handoff 路径事先 `test ! -e` 通过、工作树干净——全部一致。`rework_count=1`。`AGENTS.md`、`PROJECT_STATE.md`、`agents/roles.md`（Planner + Task Handoff Evidence Contract）、`agents/skills/task-planner.md` 与 main 分支同版本（`git diff --stat main` 为空）。

### 任务背景

固定交付 `e955bdd..24074b1` 的 Review-2（Sonnet 5）返回 source `ACCEPT`，但 Bookkeeper 核验为 `verified-source-but-nonaccepting`：同一固定交付上另有可执行证据证明五项缺陷，且 Human 随后定下三项接受风险、五项必修，并提出一项改变实盘准入语义的新需求。本任务只做计划增量修订，不实现、不准备实现 dispatch。

### 实际修改范围

仅两份 Allowed planning 文件（277 增 / 15 删）：

**`docs/planning/smooth-open-orders-v1.md`（设计权威，最小增量）**

- 状态行：改为「首轮已交付但 Review-2 source ACCEPT 未被 Bookkeeper 采用」，并写明本轮须先过跨 provider 窄复核。
- 决策表新增 **D15**（smooth 每轮联网 fresh preflight 取消，复用建卡固化 `q_common`/`position_side_mode`/`preflight_snapshot`/route，含 Human 明确接受的代价且注明不得包装成 fail-closed）与 **D16**（smooth 首轮杠杆前移到订阅/gate/首次滑点计算之前，禁止提前到建卡时，不新增持久化列或状态机）。
- **D8 更正**：原「超时不绕过 preflight、路由、余额、限流」对 smooth 已不成立，改为仅对 immediate 成立，smooth 保留的是 Start gate、任务状态与 `prepare_attempt` 原子复核。
- §6.4 尾段更正（smooth 判定分母与实际发送量恒为同一固化 `q_common`；随之失去每轮以交易所最新过滤器复核数量的能力）。
- 新增 **§6.5**：从「开始执行」到「发出订单」的固定顺序图与四条硬约束（放行到两腿提交之间零联网/零设置/零 sleep）。
- §9 两条更正：「不自造第二重退避」不等于允许零等待重试；smooth 放行后 preflight/路由/限流/余额类失败改由交易所拒单与既有单腿处置收口；新增「暂停/删除后仍在 drain/settle 时日志必须继续可见」。
- §13 验收矩阵：更正第 7、12、13、15 条，新增第 16（首轮杠杆前置）、17（放行后零联网顺序型回归）、18（固化数据复用）。
- 新增 **§16**：16.1 三项 Human 接受的具名限制（L1/L2/L3，各含事实、实际影响、临时操作方式、重开条件，并列明不得为其新增的机制）；16.2 五项必修根因的权威描述。

**`docs/planning/smooth-open-orders-v1-development-checklist.md`（开发边界，追加第二轮）**

- 头部：标注第二轮身份、新增 Review-2/Bookkeeper 核验为本轮唯一事实来源、说明 §1–§11 为第一轮内容、第二轮行号基线改为 `bfb6337`。
- §8 启动文稿标注「仅适用第一轮」，§11 标注被 §14 取代（均保留为历史记录，不删除）。
- 新增 **§12 返修任务包**：12.1 任务身份（同实现者 `gpt-5.6-sol`/`xhigh`/`openai`、同 worktree/branch、`rework_count=1`、单 fix commit 不 push）；12.2 收窄的 Allowed Files 与禁止文件（明确 `store.py`、executor、live client、preflight provider、`snapshot.py`、`requirements.txt` 不得改）；12.3 五项必修的证据锚点/根因/修复要求/确定性验收；12.4 D15+D16 实现规格与顺序型回归；12.5 三项接受风险不得修、不得重新纳入验收；12.6 验收命令（含既存白名单勘误口径、未装 ccxt 前提、零 diff 检查）；12.7 失败停止条件。
- 新增 **§13** copy-ready 窄范围计划复核请求（四组问题：三项接受风险是否被错误纳回、五项必修是否覆盖根因且未引入被禁机制、smooth-only preflight 删除是否准确保留 create/immediate/原子 reserve/单腿后续、杠杆是否严格前移且放行后再无联网；provider 须非 `anthropic`；结论 `ACCEPT | REWORK`）。
- 新增 **§14** 第二轮停止线。

### 结论

三项 Human 接受风险已写成具名已知限制（不再是验收失败项），五项必修各自绑定固定基线上的证据锚点与可变红的确定性验收，新需求以「D15 取消每轮联网预检 + D16 杠杆前移」两条决策进入设计权威并配顺序型回归。未新建第三份设计/风险/修复权威，未改任何源码、测试、状态或其他文档。

### 未完成事项与边界

- 未实现任何代码，未准备返修 dispatch，未创建 worktree/分支，未安装依赖，未联网，未启停服务，未读取凭证，未创建任务或下单，未 commit/push/merge/部署。
- 未处理 Review-2 记录的三项非阻塞观察（`clear_smooth_gate` 双调用点表述、日志刷新条件收紧的专门断言、活文档未同步）中与本轮五项必修无关的部分；其中「日志刷新条件收紧」已被必修 5 覆盖，活文档同步仍属 Bookkeeper 阶段收尾职责。
- 本增量本身尚未经跨 provider 复核；`ACCEPT` 前不得据此启动实现。

### 命令与结果

- `git rev-parse HEAD`、`git branch --show-current`、`git status --short`（干净）、`git cat-file -e bfb6337^{commit}`（通过）、`test ! -e <本 handoff 路径>`（通过）。
- `git diff --check` → 无输出。
- `git diff --stat` → 仅 `docs/planning/smooth-open-orders-v1.md`（82 行变更）与 `docs/planning/smooth-open-orders-v1-development-checklist.md`（210 行变更），无第三个文件。
- 只读核对的实现锚点：`best_bid_ask_provider.py::start/subscribe/_watch`、`domain.py::validate_slippage_threshold_pct`、`service.py::_ensure_smooth_subscriptions/_wait_for_smooth_gate/_worker_round/_dispatch_one_for_task/_set_leverage_before_open/post_pause/post_delete`、`server.py::_build_hedge_service`、`config.py` 的 `offline`/`APP_OFFLINE`、`frontend/index.html` 展开日志刷新条件、`frontend/self-check.js:5615-5621` 的既有错误断言。

### 仓库内证据路径

- `docs/planning/smooth-open-orders-v1.md`
- `docs/planning/smooth-open-orders-v1-development-checklist.md`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md`
  2. `docs/planning/smooth-open-orders-v1.md`
  3. `docs/planning/smooth-open-orders-v1-development-checklist.md`
  4. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md`
- 执行：Bookkeeper 核验本 handoff 的 source SHA-256、`base_sha`、Allowed Files 范围与两份计划的增量内容，固化改动并推进 `status.json`，随后按清单 §13 备好 provider 非 `anthropic` 的窄范围计划复核 dispatch。
- 关卡：窄复核返回 `ACCEPT` 后，才准备原 Implementer（`gpt-5.6-sol`/`xhigh`/`openai`）的单一返修 dispatch（`rework_count` 保持 `1`）；`REWORK` 则回到 Planner 继续最小改稿。
- 不能假设的事实：
  - 本增量尚未经任何评审，不构成实现授权；
  - D15 取消的是 smooth 每轮联网 fresh preflight，**不是** `prepare_attempt` 的原子复核，也不改 immediate 与 close 的任何行为；
  - D15 放弃的每轮拦截（余额、交易规则、position mode、限频、路由变化）是 Human 明确接受的代价，不得在任何文档或实现中被描述为 fail-closed；
  - L1/L2/L3 已被 Human 接受，任何复核或实现都不得把它们重新变成修复项；
  - 本轮不授权安装 ccxt、重启服务、联网验证、合并、push、部署或任何真实订单。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: smooth-open-v1-repair-plan-opus5
执行结果: completed（完成）
结果摘要: 计划增量修订完成。设计权威新增 D15（smooth 取消每轮联网 fresh preflight，复用建卡固化数据，代价如实记为 Human 接受非 fail-closed）、D16（首轮杠杆前移到订阅/gate/首次滑点之前）、§6.5 顺序图与零联网硬约束、§16 三项接受风险与五项必修根因，并更正 D8/§6.4/§9/§13 中已被推翻的表述。开发清单新增 §12 返修任务包（同实现者、rework_count=1、收窄 Allowed Files、五项修复的证据锚点与可变红验收、D15/D16 实现规格与顺序型回归）、§13 窄复核请求、§14 停止线。
产物: [docs/planning/smooth-open-orders-v1.md, docs/planning/smooth-open-orders-v1-development-checklist.md, reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md]
检查结果: [pass：启动身份核对（cwd/分支/revision 27/task_id/base_sha bfb6337/handoff 不存在/工作树干净）；pass：三项接受风险写成具名限制含实际影响、临时操作方式与重开条件，并禁止为其新增准入锁/stopping/store 复核/时钟改动/capture 扩展；pass：五项必修各有固定基线证据锚点、根因修复要求与可变红确定性验收，且禁用第二 event loop/manager/指数退避/重试状态机/新配置/新 timer；pass：D15 保留 create 首次 preflight、固化数据、regular_spot 预划转、缺腿与 1000x 拒绝，immediate 逐字不变，原子 reserve 与两腿链原样复用；pass：D16 杠杆严格前移且禁止提前到建卡、禁止 dispatch 内对 smooth 再设置，配 set_leverage→subscribe/open gate→evaluation→prepare→dispatch 顺序型回归；pass：未新建第三份权威，仅两份 Allowed planning 文件变更（277 增 15 删）；pass：窄复核请求 copy-ready 且限定 provider 非 anthropic、结论 ACCEPT|REWORK；pass：git diff --check 无输出，未提交/未改状态/未启动其他模型]
阻塞项: [none]
本地北京时间: 2026-08-13 09:48:33 CST
下一步模型: codex（status.json.bookkeeper，Bookkeeper 核验本 handoff 并准备窄范围计划复核 dispatch；由 Human 启动该终端）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-repair-plan-opus5.handoff.md、docs/planning/smooth-open-orders-v1.md、docs/planning/smooth-open-orders-v1-development-checklist.md、reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-v1-review-2-sonnet5.handoff.md；执行：Bookkeeper 核验 source SHA-256、base_sha 与 Allowed Files 范围，固化两份计划增量并推进 status.json，按清单 §13 备好 provider 非 anthropic（建议 deepseek-v4-pro）的窄范围计划复核 dispatch；关卡：窄复核 ACCEPT 后才准备原 Implementer（gpt-5.6-sol/xhigh/openai，rework_count 保持 1）的单一返修 dispatch，安装 ccxt、重启服务、合并、push、部署与实盘仍须 Human 逐项单独授权
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `07f0483c21ffd77ef1393522d3ef7820bc482c60860c83aaf4ac78e8006e1c38`
- verified_at: `2026-08-13 09:53:56 CST`
- status_revision_verified: `27`
- verdict: `rejected-plan-internal-conflicts`
- identity_and_scope: task/stage/model/provider、`base_sha=bfb633799ed904ba6d8364bffef7f048d77137dd`、`delivery_sha=none`、source marker、完整 `[TASK_RESULT v2]`、唯一新 handoff 与两份 planning Allowed Files 均核对一致；`git diff --check` 无输出，tracked 改动恰为两份计划文件，277 增 15 删。
- rejection_basis: 四处范围内矛盾使计划尚不能进入跨 provider 复核。T1：设计 D5/必修 3 规定 threshold 无产品最大值，却在清单 §12.3 写“超长整数返回 400”；合法正负超长整数应正常规范化并被 API 接受，只有格式非法输入才是 400。T2：设计 D12 与任务卡段仍写“收起或终态停止自动刷新”，与 §9/§13/§16 必修 5 的“任务仍存在且展开时，paused/deleted/done/stopped 继续刷新 drain/settle”冲突。T3：设计 §6.1 重启段仍写 timeout 候选须经过“现有 preflight”，与 D15 smooth 不再每轮 fresh preflight 冲突。T4：清单 §12.2 Allowed Files 用“以及组合根离线断言所需的既有服务器测试文件”占位式范围，未钉死实际所需 `backend/tests/test_service_health.py`，且同一测试列表后续路径未逐项写全。
- reproducible_checks: `rg -n '超长整数返回 400|终态停止自动刷新|终态不再自动取|现有 preflight|服务器测试文件' docs/planning/smooth-open-orders-v1*.md`；`rg -n '_build_hedge_service' backend/tests` 只命中 `backend/tests/test_service_health.py` 的真实组合根用例；`git diff --name-status` 与 `git diff --check`。
- next_gate: 返回同一 Planner 做一次只改 T1–T4 的微型返修；该返修完成并经 Bookkeeper 核验后，才准备 provider 非 anthropic 的窄计划复核。不得实现代码或执行任何外部动作。

## Errata (append-only)

- none；作者 source report 与回执保持不变，Bookkeeper 以追加核验拒收。
