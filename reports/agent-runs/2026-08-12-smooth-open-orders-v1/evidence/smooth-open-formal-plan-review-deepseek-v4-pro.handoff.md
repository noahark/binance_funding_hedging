# Task Handoff: smooth-open-formal-plan-review-deepseek-v4-pro

## Source Report (author-only; immutable after task end)

- task_id / role / target model：`smooth-open-formal-plan-review-deepseek-v4-pro` / Reviewer / `deepseek-v4-pro`（provider `deepseek`）
- stage_id / created_at：`2026-08-12-smooth-open-orders-v1` / 2026-08-13 01:54 CST
- base_sha：`0f19beae98b6909c2a5f0a9764f81f71b474a226`
- delivery_sha：`b474f4ac28fe9534884c66a664d7fb6365305a6d`

### 评审性质与范围

正式、跨 provider、只读计划评审。评审对象是「Human 冻结设计 + Opus 5 实施细拆」，不是尚不存在的实现。细拆作者 provider `anthropic`，本评审 provider `deepseek`，满足跨 provider。评审只读，除本 handoff 外未改动任何文件、`status.json`、`ACTIVE.json`、`PROJECT_STATE.md` 或源码；未 git add/commit/push；未创建 worktree/分支/stage；未安装依赖；未连接网络/凭证/行情/订单接口；未启动服务。

固定受审范围核对通过：`status.json` revision `8`、`current_task.id = smooth-open-formal-plan-review-deepseek-v4-pro`、`base_sha`/`delivery_sha` 与 packet 一致，`git rev-parse --verify` 两 SHA 均有效；主体差异为 `docs/planning/smooth-open-orders-v1-development-checklist.md`（该区间另含 `frontend/index.html`/`frontend/self-check.js` 为 Kimi 前端 fake 前置产物、`04-...dispatch.md` 与 `status.json` 为控制提交，按 §8 评审范围口径视为上下文而非受审交付）。

### 阅读的输入

按 dispatch 06 顺序读取：`AGENTS.md`、dispatch 06、`ACTIVE.json`、`PROJECT_STATE.md`、`status.json`、`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer / Bookkeeper 段）、`agents/skills/code-reviewer.md`、受审细拆（`git show b474f4ac...:docs/planning/smooth-open-orders-v1-development-checklist.md`）、Human 冻结设计（`git show 0f19beae...:docs/planning/smooth-open-orders-v1.md`）、`docs/planning/ccxt-bookticker-recon-2026-08-13.md`、`evidence/ccxt-bookticker-recon-claude-glm.handoff.md`、`evidence/01-advisory-design-reviews.md`；并只读核对固定 base 树源码：`backend/domain/snapshot.py`（`compute_opening_spread_pct`@613）、`backend/hedge_open_tasks/store.py`（`set_task_status`@774、`list_eligible_tasks`@837、`prepare_attempt`@863、`stop_task_fatal`@1928、`pause_task`@1964、`_migrate`@413）、`backend/hedge_open_tasks/service.py`（`post_start/pause/delete`@1001-1042、`post_fill_once`@1043、`ensure_worker`@1470、`_run_task_worker`@1503、`_worker_round`@1592、`_dispatch_one_for_task`@2692、`_pause_task_local`@2274、`_stop_task_fatal_preflight`@2601、`create_task` mode 拒绝@761）、`backend/domain/normalize.py`（`SPOT_SYMBOL_MAP`/`SPOT_MATCH_MULTIPLIER`）、`backend/tests/test_hedge_purity.py`、`backend/tests/test_hedge_cycle_core.py`。

### 结论

**评审结论：REWORK**。三条发现均为 `in-range`（由本次交付 `development-checklist.md` 引入或触碰，阻塞交付），必须由 Planner 改稿后重新评审。另附若干非阻塞观察。

---

### 发现 R1（in-range，阻塞）—— §5.4 用 handoff 替代在途 `current_task` 不合规

细拆 §5.4 与 §4 通用条款规定：A、B 真并行时 `status.json` 只有一个 `current_task`，故「先备 A 的 dispatch → revision N 指 A → 启动 A；再备 B 的 dispatch → revision N+1 指 B → 启动 B；此时 `current_task` 指 B，A 的事实以 `smooth-open-p1-provider-claude-glm.handoff.md` 为准，Bookkeeper 按文件逐条核验」。这实质是在 A 仍处于 `dispatched`（在途）时，把唯一的 `current_task` 覆盖成 B，用 A 的 handoff 文件代替 A 的权威状态。

规则证据（`agents/roles.md`，逐条直接引用）：

- Minimal State And Dispatch Shape：`current_task` 是唯一活动 packet 的指针，schema 只有单个对象，无并行表示。
- Task State Vocabulary：`current_task.state` 只有 `dispatched`/`reported`/`verified` 三态；「An implementer may move only `dispatched` to `reported`. Bookkeeper may move `dispatched` or `reported` to `verified`」。A 被 B 覆盖后，A 的 `reported`/`verified` 闭环在 `status.json` 里无法表达。
- Task Handoff Evidence Contract：handoff「ends by creating exactly one handoff」——它只在任务结束时形成，不能作为在途任务的权威状态。
- Required Behavior：「Prepare the dispatch first, then make the last `status.json` revision point to it. Do not modify that revision before Human starts the target terminal.」——在 A 未结束、Human 未启动 B 终端前，revision 不应被覆盖为 B。

实际影响：A、B 任一在途时，`status.json` 无法同时记录两个活动 packet 的状态转换；用 handoff 替代在途状态违反上述规则，Bookkeeper 无法据此封存。细拆 §5.4 自己也承认「若 Bookkeeper 认为该做法与自身记账规则冲突，应在计划评审阶段提出，由 Human 裁定」。

修复要求（任选其一，改稿后重新评审）：

1. **同一 stage 内顺序 dispatch**：A 完成并 `verified` 后，再 dispatch B（放弃真并行，接受 §2.4 已承认的「阶段 1 有一个终端空闲」）。
2. **为并行 worktree 建各自独立的 stage/`ACTIVE.json`/`status.json` 记账**：A、B 各成一个可独立启动、独立核对的 stage，再定义不越权的集成收口。

不得采用：新增并行数组、第二套状态 schema、临时 ledger、或以 handoff 替代在途状态（dispatch 06 Goal 已列明此边界）。

---

### 发现 R2（in-range，阻塞）—— §3.2 声称 `set_task_status` 是唯一状态迁移收口，与代码事实矛盾，系统 pause/stop 路径会残留 gate

细拆 §3.2 第 4 条：「`set_task_status`（store.py:774）是全仓状态迁移的唯一收口：新状态不是 running 时，同一事务内清空三个 gate 列。pause/delete/done/stopped 由此自动清 gate」。据此，B 只需把 gate 清理折叠进 `set_task_status`，C 不必散落 `clear_smooth_gate`。

代码事实（固定 base 树，`grep -n "UPDATE hedge_open_task SET status" backend/hedge_open_tasks/store.py`）：

- `store.py:789`/`796` —— `set_task_status` 内部（Human 手动 pause/delete/start 与 worker 的 done 走此）。
- `store.py:1950` —— `stop_task_fatal`（fatal preflight 事实 → `stopped`）。
- `store.py:1991` —— `pause_task`（worker 确认 429/余额不足/限流 → `paused`）。

即 `stop_task_fatal` 与 `pause_task` 是两条**不经过 `set_task_status`** 的直接 `UPDATE status` 路径。二者由 `_dispatch_one_for_task` 在 `prepare_attempt` **之前**调用（`service.py:2745` `_stop_task_fatal_preflight`、`service.py:2769/2785/2812` 等 `_pause_task_local`，先 fresh preflight + guard，全部通过后才 `prepare_attempt`@2801 之后）。此时 gate 尚未被 `prepare_attempt` 消费，`smooth_gate_seq`/`started_at_us`/`force_requested` 仍残留；这两条路径直接改 status 不清 gate。

实际影响：smooth 任务 gate 通过后进入 dispatch，preflight 遇 429/余额不足 → 系统 pause，gate 残留。Human 之后 Start 恢复时，`open_smooth_gate` 因旧 gate seq 相同而幂等复用（细拆 §3.2 第 1 条「同 seq 重复调用不重置 started_at_us，也不清 force」），旧 deadline 已过 → 立即形成 timeout 候选，跳过本应「新建完整 5 分钟窗口」。这违反设计 §6.1（「系统因 preflight/限流等暂停……清掉活动 gate；再次 Start 为仍未调度的 seq 建一个新的完整 5 分钟 gate」）与验收矩阵第 11 条。

修复要求：B 必须枚举**全部** `running → 非 running` 状态迁移路径（至少 `set_task_status`、`pause_task`、`stop_task_fatal` 三条），并为每条路径在同一事务内清空 gate 列（或统一到一个内部收口函数）；改稿须逐条列出路径清单与清 gate 的证据。`clear_smooth_gate` 的保留用途（「任务仍 running 但 Start gate 关闭」）也须与这些路径的关系一并写明，不得再以「唯一收口」概括。

---

### 发现 R3（in-range，阻塞）—— §8.1 让 Bookkeeper 建分支并 cherry-pick，越过记账职责且与「C 是唯一集成者」矛盾

细拆 §2/§4.3 称 C 是「唯一集成者」，但 §8.1 第 2 步规定「Bookkeeper 在主 worktree 建集成分支 `smooth/integration`，从 `base_sha` 起，先 cherry-pick A 的 commit，再 cherry-pick B 的 commit」，第 7 步「Bookkeeper 合出最终交付分支」。

规则证据：`agents/roles.md` Bookkeeper 段 Write Authority 只授予「sole normal writer of `status.json`」与「normal writer of `PROJECT_STATE.md`」，Required Behavior 是核验/记账/备 dispatch，**不含执行 git cherry-pick/merge**。`AGENTS.md` §3 Safety Kernel 第 3 条「An implementer may modify only dispatch-approved files. It must not overwrite the human's or another terminal's work」；cherry-pick 是把另一终端的 commit 合入分支，属代码集成动作，非记账。

实际影响：Bookkeeper 执行 cherry-pick 会从「记账者」变成「代码集成者」，与 §2「唯一集成者=C」直接矛盾，owner 不明确；且集成属需明确授权的动作（`AGENTS.md` §9：merge 到 main 无 Human 授权禁止；cherry-pick 虽非 main，仍属集成）。

修复要求（二选一，改稿后重新评审）：

1. 明确 cherry-pick 由**唯一集成者 C** 执行（C 的 Allowed Files 与职责相应扩大，或另立一个显式授权的最小集成步骤），Bookkeeper 只 `git rev-parse` 固定 SHA 并写入 `status.json`。
2. 由 Human 明确授权 Bookkeeper 执行 cherry-pick，并在 dispatch 中记录该授权（含授权范围与集成分支），且与 §2「唯一集成者=C」的表述统一为同一个 owner。

---

### 非阻塞观察（不改变 REWORK 结论，供改稿时一并考虑）

- **O1**：细拆 §3.1 第 2 条「latest 在 invalid 时返回 `None` 或 `status != live` 的快照——二选一由 A 决定」。这是一个尚未钉死的契约分叉。虽已通过「C 只判 `status == live` 且四值 > 0」隔离，但建议在契约里直接钉死一种（如 latest 总是返回快照对象、invalid 时 `status="disconnected"`），避免 A/C 实现分歧与测试口径不一。
- **O2**：细拆 §3.1 「为什么必须放 services 层」的理由写为「CCXT 走 aiohttp，放进该包会直接打破零网络证明」。`backend/tests/test_hedge_purity.py` 的 `_FORBIDDEN_IMPORT_RE` 只禁 `urllib|socket|requests|http.client|hmac|hashlib`，**不含 aiohttp 或 ccxt**；真正把 provider 挡在 `hedge_open_tasks/` 之外的是 `_LIVE_MODULE_RE`（禁止该包 import services 层实盘模块）与零网络包边界的精神。结论（放 services 层）正确，但引用理由应改为准确的正则/边界依据。
- **O3**：细拆 §4.3 要点 5 与测试的衔接——「ccxt 缺失时注入 `None`，smooth 创建 400」与「全部回归使用 fake provider 注入」需要在 C 的 dispatch 里明确区分「生产 dry-run（provider=None → smooth 400）」与「测试（fake provider → smooth 可建并测 gate）」，避免把 dry-run 下 smooth 无法创建误当回归失败。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`；`docs/planning/smooth-open-orders-v1-development-checklist.md`；`docs/planning/smooth-open-orders-v1.md`；`agents/roles.md`（Bookkeeper 段 Minimal State And Dispatch Shape / Task State Vocabulary / SHA Discipline / Required Behavior；Task Handoff Evidence Contract）。
- 执行：Bookkeeper 核验本 handoff（源区块 SHA-256、revision 8、固定 SHA），确认 REWORK 三发现后，把 R1/R2/R3 原样转交 Planner 改稿（修订 `development-checklist.md`），不触碰 `rework_count`（计划评审 REWORK 不递增，`AGENTS.md` §8）。
- 关卡：改稿后的细拆对 R1/R2/R3 逐条给出可执行修订与代码/规则证据，并重新发起正式计划评审（provider ≠ `anthropic`）。
- 不能假设的事实：不得假设「A/B 真并行 + 单 current_task」已被本评审接受；不得假设 `set_task_status` 是唯一状态迁移收口（实际有 `pause_task`/`stop_task_fatal` 两条旁路）；不得假设 Bookkeeper 可自行执行 cherry-pick。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: smooth-open-formal-plan-review-deepseek-v4-pro
执行结果: completed（完成）
结果摘要: 对平滑开单 V1 冻结设计与 Opus 5 细拆做跨 provider 只读计划评审，结论 REWORK：三条 in-range 阻塞发现——§5.4 以 handoff 替代在途 current_task 违反单活动 packet 规则；§3.2 称 set_task_status 唯一收口但 pause_task/stop_task_fatal 直接改 status 会残留 gate；§8.1 让 Bookkeeper 做 cherry-pick 越过记账职责。
产物: [reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md]
检查结果: [pass: status revision 8 与固定 base_sha/delivery_sha 核对一致, pass: 区分 Human 冻结决策与 Opus 实现选择且未重开冻结项, pass: A/B 文件集不相交、C/D 依赖后置有真实调用链证据, fail: §5.4 用 handoff 替代在途 current_task 不合规（R1）, fail: set_task_status 非唯一状态迁移收口致系统 pause/stop 残留 gate（R2）, fail: §8.1 Bookkeeper cherry-pick 与唯一集成者=C 矛盾且越记账职责（R3）, pass: 只读且仅创建唯一 handoff, pass: handoff 按 Task Handoff Evidence Contract 含完整结构]
阻塞项: [R1/R2/R3 三条 in-range 发现须由 Planner 改稿后重新评审]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md
修复要求: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md
本地北京时间: 2026-08-13 01:54:43 CST
下一步模型: Bookkeeper（codex）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md；执行：核验本 handoff 的源区块 SHA-256、revision 8 与固定 SHA，确认 REWORK 后把 R1/R2/R3 原样转交 Planner 修订 development-checklist.md；关卡：改稿对 R1/R2/R3 逐条给可执行修订与证据并重新发起正式计划评审（provider ≠ anthropic）。
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `db1b7d535a288a8b965ae1bfdb2f5ee15f893f79aa5804988affb0f1174c2ba2`
- verified_at: `2026-08-13 02:06:40 CST`
- status_revision_verified: `8`
- verdict: `verified-rework`
- identity_and_range: task/stage/model/provider 与 dispatch 06、status revision 8 一致；`base_sha=0f19beae98b6909c2a5f0a9764f81f71b474a226`、`delivery_sha=b474f4ac28fe9534884c66a664d7fb6365305a6d` 均由 `git cat-file -e <sha>^{commit}` 验证存在。
- closure: `[TASK_RESULT v2]`、`评审结论: REWORK（返工）`、问题记录、修复要求、中文交接三行与闭合标记齐全；Required Reading 与下一步任务均指向具体仓库相对路径。
- findings_verified: R1 与单 `current_task` 三态闭环冲突；R2 的 `pause_task`/`stop_task_fatal` 直接状态写路径经固定 base 源码复核成立；R3 与 Bookkeeper 记账职责及“C 唯一集成者”表述冲突。三项均交 Planner 做最小计划修订。
- commands: `rg` 核验 handoff 结构与 closure；`perl -0ne ... | shasum -a 256` 计算 source SHA-256；`git cat-file -e` 核验固定 SHA；`python3 -m json.tool .../status.json`；`git diff --check`。
- accounting: 本次为实现前计划评审 `REWORK`，按 `AGENTS.md` §8 不增加 `rework_count`。

## Errata (append-only)
