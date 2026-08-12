# Task Handoff: smooth-open-targeted-plan-rereview-deepseek-v4-pro

## Source Report (author-only; immutable after task end)

- task_id / role / target model：`smooth-open-targeted-plan-rereview-deepseek-v4-pro` / Reviewer / `deepseek-v4-pro`（provider `deepseek`）
- stage_id / created_at：`2026-08-12-smooth-open-orders-v1` / 2026-08-13 02:27 CST
- base_sha：`2e5902347c5f0ac81638c67dc7a1bf20a9141ac9`
- delivery_sha：`8c2cce629a0688440836f07e3d089c35acbadd65`

### 复核性质与范围

对 Opus 5 平滑开单 V1 定向计划返修的窄范围只读复核，只判断 R1/R2/R3 是否关闭、新的单 Implementer 方案是否可执行、Human 冻结语义是否保持。返修作者 provider `anthropic`，本复核 provider `deepseek`，满足跨 provider。我是上一轮 R1/R2/R3 的发现者，已基于固定提交与原始代码事实重新验证。除本 handoff 外未改动任何文件；未 git add/commit/push；未创建 worktree/分支/stage；未安装依赖、联网、读凭证、控制服务或执行行情/订单/账户动作。

固定范围核对通过：`status.json` revision `12`、`current_task.id = smooth-open-targeted-plan-rereview-deepseek-v4-pro`、`base_sha`/`delivery_sha` 与 packet 一致；`git rev-parse --verify` 两 SHA 有效；计划主体差异为 `docs/planning/smooth-open-orders-v1-development-checklist.md`（区间另含 `07-...dispatch.md` 与 `status.json`，属控制上下文）。

### 阅读输入与代码核对

按 dispatch 08 顺序读取 `AGENTS.md`、dispatch 08、`ACTIVE.json`、`PROJECT_STATE.md`、`status.json`、`agents/roles.md`（Shared Rules / Task Handoff Evidence Contract / Reviewer / Bookkeeper 段）、`agents/skills/code-reviewer.md`、上一轮 `smooth-open-formal-plan-review-deepseek-v4-pro.handoff.md`、返修稿（`git show 8c2cce62...:docs/planning/smooth-open-orders-v1-development-checklist.md`）、Human 冻结设计（`git show 2e590234...:docs/planning/smooth-open-orders-v1.md`）。

R2 代码事实核对（固定 base 树 `backend/hedge_open_tasks/store.py`）：
- `grep -n "UPDATE hedge_open_task"` 共 11 处；含 `status` 的写路径恰为四条——`set_task_status`（789/796，无条件 UPDATE）、`stop_task_fatal`（1950，条件 `WHERE status IN (running,paused)`）、`pause_task`（1991，条件同前）、`_apply_task_counters`（1194，含 `status = ?`，无条件）。其余（611/730/811/826/984/1564）分别写 `leg_exposure`/`spot_symbol`/`failure_pause_threshold`/`leg_exposure`/`scheduled_attempt_count`/`last_worker_exit_reason`，均不含 status，且 730 是 spot 身份回填不是状态迁移。任务行初始 status 由 `create_task` INSERT 写入。返修稿 §4.2.3 的四条枚举完整、无第五处。
- `_apply_task_counters`（1046）由 `resolve_attempt`（1372）、`finalize_attempt`（1471）、`settle_attempt_no_counters`（1534）调用，只在 attempt 结算时运行；其 `status` 可被 `resolve_status_after_attempt` 置为 `paused`/`done`，或 fatal 分支置 `stopped`。返修稿把该 UPDATE 行记为 `1192`，固定 base 实际为 `1194`，属 dispatch 08 已指明的非语义行号漂移。
- `_pause_task_local`（service.py:2274→store.pause_task:2293）与 `_stop_task_fatal_preflight`（service.py:2601→store.stop_task_fatal:2608）由 `_dispatch_one_for_task` 在 `prepare_attempt`（service.py:2889 附近）之前调用（2745/2769/2785/2812 等），此时 gate 未被消费，三列仍在——证实 R2 原发现的调用链。
- O2 代码事实：`backend/tests/test_hedge_purity.py` 的 `_FORBIDDEN_IMPORT_RE`（35-39）只禁 `urllib|socket|requests|http.client|hmac|hashlib`，不含 `aiohttp`/`ccxt`；`_LIVE_MODULE_RE`（41-44）禁 `hedge_open_live_client|live_hedge_executor|hedge_preflight_provider`。返修稿 §4.1 的理由改正与真实正则一致。

### 结论

**评审结论：REWORK**。两条发现均为 `in-range`（由本次返修稿引入的缺口），需最小修订后重新复核；其余 R1/R3、单任务范围、冻结语义、O1/O2/O3 均已关闭或通过。

---

### 发现 T1（in-range，阻塞）—— §4.2.4 第 5 条「条件 UPDATE 未命中不误清」存在空断言，未满足 dispatch 08 第 4 项的非空 sentinel 要求

返修稿 §4.2.4 第 5 条：「任务先 `deleted`（或 `done`）→ 再调 `pause_task` / `stop_task_fatal` → 断言返回未命中、`status` 未被改写、且三列保持调用前的值（不被误清，也不复活状态）」。

问题：`deleted`/`done` 由 `set_task_status` 完成，而返修稿 §4.2.3 路径 1 规定 `set_task_status(非 running)` 在命中时清三个 gate 列，故「任务先 deleted（或 done）」之后三列已是 `NULL`。此时「三列保持调用前的值」等于断言 `NULL` 保持不变——即便实现错误地把清 gate 放在条件 UPDATE 之外（无条件清），该断言也照样通过，无法抓住「未命中误清 gate」的回归。这正好是 dispatch 08 第 4 项明确禁止的情形：「若第 5 条使用终态任务，测试必须以非空 sentinel 或受控竞态证明『调用前值保持』，不能以本来就是 NULL 的值形成空断言」。

实际影响：R2 原发现的核心回归（条件 UPDATE 未命中时不误清）被一个空断言伪装成已覆盖，可能漏掉「过期 worker 快照的 pause_task/stop_task_fatal 未命中却误清他人/自身 gate」的缺陷。

修复要求（最小）：把 §4.2.4 第 5 条改为——测试用**非空 sentinel** 直接构造「任务处于 `deleted`/`done`/`stopped` 终态 + 三列非 `NULL`」的 DB 状态（绕过 `set_task_status`，直接对 task 行写入 `smooth_gate_seq`/`smooth_gate_started_at_us`/`smooth_gate_force_requested`），再调 `pause_task`/`stop_task_fatal`，断言返回未命中、`status` 未被改写、且三列**保持非空 sentinel 值**（既不被误清也不复活）；或改用受控竞态等价证明「未命中分支完全不写 gate 列」。不得以「三列本来就是 NULL」通过断言。

---

### 发现 T2（in-range，阻塞）—— §6「此后由 Bookkeeper 维护」措辞会实际授权 Bookkeeper 改依赖文件，未满足 dispatch 08 第 11 项

返修稿 §6：「维护者：本交付创建；此后由 Bookkeeper 在依赖变更交付中维护」。

问题：主语是 Bookkeeper，字面读作「Bookkeeper 负责维护 requirements.txt」，会实际授权 Bookkeeper 修改依赖文件。`agents/roles.md` Bookkeeper 段 Write Authority 只授予 `status.json` 与 `PROJECT_STATE.md`，不授予写代码/依赖清单；依赖文件属于实现者范围。dispatch 08 第 11 项的 pass 判据是「未来依赖变更必须由获 dispatch 的 Implementer 修改、Bookkeeper 只核验」，返修稿措辞未满足。

实际影响：未来依赖变更时可能出现「Bookkeeper 直接改 requirements.txt」的越权解读，破坏 Bookkeeper 只记账的边界（与上一轮 R3 同类）。

修复要求（最小）：把 §6 维护者一句改为——「本交付创建；此后任何依赖变更由获 dispatch 的 Implementer 在专门交付中修改，Bookkeeper 只核验，不改动 requirements.txt」。这只是措辞修订，不改变本交付「创建者=实现者」与「安装须 Human 授权」的既有边界。

---

### 非阻塞观察（不改变 REWORK 结论）

- **T-O1**：返修稿 §3.6 与 §8 启动文稿写「实现者（可）把自己的 status 从 dispatched 改为 reported」，而 §3.3 把 `reports/agent-runs/**/status.json` 列为禁止改动，两处表述有张力。dispatch 08 第 7 项已裁定「以 Allowed Files 为准、实现者不写 status、Bookkeeper 直接 dispatched→verified」，不构成 REWORK；但建议在正式实现 dispatch 里补一句「本 dispatch 的 Allowed Files 禁止 status.json，实现者不写 status，§3.6/§8 的『可改为 reported』仅描述 Harness 一般权限上限，不构成本 dispatch 的实际写权限」，以消除歧义。

### Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md`；`docs/planning/smooth-open-orders-v1-development-checklist.md`；`agents/roles.md`（Task Handoff Evidence Contract、Bookkeeper 段）。
- 执行：Bookkeeper 核验本 handoff（源区块 SHA-256、revision 12、固定 SHA），确认 REWORK 两条后把 T1/T2 原样转交 Planner 最小改稿（仅修订 §4.2.4 第 5 条与 §6 维护者措辞）；不触碰 `rework_count`（计划复核 REWORK 不递增）。
- 关卡：改稿对 T1（非空 sentinel 或受控竞态）与 T2（获 dispatch 的 Implementer 修改、Bookkeeper 只核验）逐条落实后，重新发起定向复核（provider ≠ `anthropic`）。
- 不能假设的事实：不得假设「条件 UPDATE 未命中不误清」已被空断言证明；不得假设 Bookkeeper 有权维护 requirements.txt；R1/R3 与 O1/O2/O3 已关闭、单任务方案与冻结语义已通过，复评不得重开。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: smooth-open-targeted-plan-rereview-deepseek-v4-pro
执行结果: completed（完成）
结果摘要: 对平滑开单 V1 定向计划返修做窄范围只读复核，结论 REWORK：两条 in-range 阻塞缺口——§4.2.4 第 5 条「未命中不误清」以 NULL 形成空断言、未满足非空 sentinel 要求（T1）；§6「由 Bookkeeper 维护」措辞会实际授权 Bookkeeper 改依赖文件（T2）。R1/R3、单任务方案、冻结语义与 O1/O2/O3 均已关闭或通过。
产物: [reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md]
检查结果: [pass: revision 12 与固定 base_sha/delivery_sha 核对一致, pass: R1 关闭——单 Implementer/单 worktree/单 current_task/单 handoff/单 delivery commit、旧 A/B/C/D 作废, pass: R2 路径穷举——固定 base 恰为 set_task_status/pause_task/stop_task_fatal/_apply_task_counters 四条 status 写路径, pass: R2 第四路径豁免成立——_apply_task_counters 仅结算时运行且 gate 已被 prepare_attempt 清空, fail: R2 回归第 5 条以 NULL 空断言、未满足非空 sentinel（T1）, pass: R3 关闭——Bookkeeper 不建分支/cherry-pick/merge, pass: 单任务 Allowed Files 联集与禁止文件、冻结语义、O1/O2/O3 关闭, fail: §6 由 Bookkeeper 维护 requirements.txt 措辞歧义（T2）]
阻塞项: [T1/T2 两条 in-range 缺口须由 Planner 最小改稿后重新复核]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md
修复要求: reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md
本地北京时间: 2026-08-13 02:27:14 CST
下一步模型: Bookkeeper（codex）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/smooth-open-targeted-plan-rereview-deepseek-v4-pro.handoff.md；执行：核验本 handoff 的源区块 SHA-256、revision 12 与固定 SHA，确认 REWORK 后把 T1/T2 原样转交 Planner 最小改稿（仅 §4.2.4 第 5 条与 §6 措辞）；关卡：改稿对 T1/T2 落实后重新发起定向复核（provider ≠ anthropic）。
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `1c8cd5647aa8272e7ccafaa8f0f9d6ea036aef4143e96afb2771c13b19c4f7e7`
- verified_at: `2026-08-13 02:29:14 CST`
- status_revision_verified: `12`
- verdict: `verified-rework`
- identity_and_range: task/stage/model/provider 与 dispatch 08、status revision 12 一致；`base_sha=2e5902347c5f0ac81638c67dc7a1bf20a9141ac9`、`delivery_sha=8c2cce629a0688440836f07e3d089c35acbadd65` 均由 Git 核验存在。
- closure: handoff 结构、`[TASK_RESULT v2]`、`评审结论: REWORK（返工）`、问题记录、修复要求、中文交接三行及闭合标记齐全。
- findings_verified: T1 与 dispatch 08 要求的非空 sentinel 断言不符；T2 的依赖清单维护者措辞会越过 Bookkeeper 写权限。R1/R3、单任务方案、冻结语义与 O1/O2/O3 已通过，不在下一轮重开。
- accounting: 实现前计划复核 `REWORK` 不增加 `rework_count`；Planner 只修 §4.2.4 第 5 条与 §6 维护者一句。

## Errata (append-only)
