# Task Handoff: close-task-preflight-simplification-review-2-kimi

## Source Report (author-only; immutable after task end)

- task_id: `close-task-preflight-simplification-review-2-kimi`
- role: `Reviewer / Review-2`
- target model: `kimi`（Kimi，provider `moonshot`）
- stage_id: `2026-08-09-close-task-preflight-simplification-v1`
- created_at（本地北京时间）：2026-08-09 17:22:36 CST
- base_sha: `dc356cd7f6acdc8502cd6caa44a48f6e3c760cac`
- delivery_sha: `e5f83f1c7f53bba4593a51f843fd1f45f52814bd`
- status_revision（核对时）：`3`，`phase=review-2`，`current_task.id` 与本 task_id 一致，`current_task.state = dispatched`

### 1. 任务背景与只读评审范围

对 Codex/OpenAI 的「平仓两段式建卡 + 启动后预检瘦身」交付做 `HIGH_RISK` 独立只读
**Review-2（现实核验）**：从 Human 已批准需求、真实交付效果、证据、运营风险与发布就绪
五个角度独立判断（`AGENTS.md` §8），不重复 Review-1 的逐行代码 verdict。受审范围固定为
已提交区间 `dc356cd..e5f83f1`（恰好 20 文件），不含本 stage 控制/ledger 提交。评审时
仓库 `HEAD` 为 `be8bf52350fc2b038974d99638b665da6b3ec4e5`（晚于 delivery 的 ledger 提交）；
经 `git diff --name-only e5f83f1..HEAD` 复核，delivery 之后只动了 stage 控制/证据文件，
**工作树产品文件与 delivery_sha 逐字一致**；本评审未以 `HEAD` 或未提交工作树为范围
（`git status --short` 为空）。

**隔离披露**：

- 实现作者：Codex/OpenAI（provider `openai`）；交付范围内无其它实现/修复作者。
- Review-1：Opus 5/Anthropic（provider `anthropic`），曾完成本需求 v1/v2 计划复评
  （v2 `ACCEPT`，含 C1—C3），未写实现；该参与已在其 handoff 披露。
- 本 Reviewer：Kimi/Moonshot（provider `moonshot`）。Review-2 须与交付范围内全部
  实现/修复作者跨 provider：`moonshot ≠ openai`，隔离成立（`AGENTS.md` §3.5、
  `agents/roles.md` Reviewer/Isolation）。**三轮三 provider**：`openai → anthropic →
  moonshot`。本 Reviewer 为独立只读新会话，未参与本需求的计划、设计、实现或 Review-1。
- 默认 Review-2 模型原为 `sonnet5`（DEC-2026-08-04-001）；Human 启动前显式改派 Kimi
  （dispatch Supersession 段），模型选择属 Human 决定；sonnet5 版 dispatch 未启动，
  保留在 git 历史。

### 2. 先验门核验结果（Reviewer 独立复核）

| 先验门 | 结果 | 证据 |
|---|---|---|
| `git rev-parse` 与 `status.json` base/delivery 一致 | 通过 | 两值回显与 `status.json` 逐字相同 |
| 固定范围为已提交、恰好 20 文件 | 通过 | `git diff --name-status dc356cd..e5f83f1` 输出 20 行 |
| 控制/ledger 提交未混入受审范围 | 通过 | 20 文件中无 dispatch、`status.json`、intake、B 证据、`ACTIVE.json`、控制文稿、handoff |
| 实现作者 OpenAI / 本 Reviewer Moonshot | 通过 | dispatch「隔离披露」+ `evidence/stage-intake.md` |
| 唯一 handoff 开始前不存在 | 通过 | `test ! -e <本文件路径>` → ABSENT（17:22 CST 复核，与 Bookkeeper 17:11 CST 预检一致） |
| 未获任何 merge/push/部署/服务/DB/交易所/凭据/gate/订单/划转授权 | 通过 | 本任务全程未执行任何该类动作 |

### 3. 必跑检查（Reviewer 独立复跑的原始结果）

```text
$ PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider backend/tests
1610 passed in 124.99s (0:02:04)
exit=0

$ node frontend/self-check.js
全部自检通过
exit=0

$ git diff --check dc356cd7f6acdc8502cd6caa44a48f6e3c760cac e5f83f1c7f53bba4593a51f843fd1f45f52814bd
（无输出）exit=0
```

三项均与 Bookkeeper B 节原始输出（`evidence/backend-pytest.txt` `1610 passed in
123.95s`、`evidence/frontend-self-check.txt`、`evidence/git-diff-check.txt`）及 Review-1
handoff §3 一致；数值差异仅为耗时，通过数与 exit code 完全相同。

### 4. Review-2 逐项现实核验结论

#### 4.1 需求对齐：v2 三目标在真实运行语义下成立 —— 通过

- **目标 1（卡片立即出现）**：close 分支在 `backend/hedge_open_tasks/service.py:782-849`
  提前 `return 201`，分支内只有纯本地 `resolve_spot_identity`、`store.get_active_cycle`、
  `store.get_task` 与单条 INSERT；测试
  `test_close_create_is_atomic_paused_and_zero_external_reads` 用**调用即抛 AssertionError
  的探针 provider** 证明建卡零外部读取，并断言 `status=paused`、`pause_reason=
  awaiting_manual_start`、中文原因、`q_common=NULL`、attempts 为空。前端把返回卡直接入
  state（self-check 93b：启动可点、fill 禁用、中文原因展示）。
- **目标 2（Start 不阻塞）**：`post_start`（`service.py:952-966`）未被本 diff 修改，
  只 `set_task_status(RUNNING)` + `ensure_worker` + 立即返回；同一测试以爆炸 provider +
  handoff 间谍证明 live Start 只产生一次 `ensure_worker` 交接、同步外部调用为零。
- **目标 3（启动后才校验/发单）**：全部新门位于 worker dispatch 内；四层防绕过成立——
  dry-run `list_eligible_tasks` 只取 RUNNING、`prepare_attempt` 事务内复检 RUNNING、
  `_require_fillable`（`service.py:1084-1095`）对 close+`awaiting_manual_start` 抛 409
  `start_required`（前后端双堵，前端仅为体验层）、新卡 paused 且零腿零 attempt 使
  `_recover_workers`（`service.py:2505-2514` 须 `has_pending or has_gap`）重启时不拉起。

#### 4.2 C1—C3 强制约束在真实运行语义下成立 —— 通过

- **C1（`um_positions` 300s 新鲜度上限）**：
  `HedgePreflightProvider.cached_um_position_qty`（`backend/services/hedge_preflight_provider.py:536-560`）
  走 `self._cached("um_positions", _CACHE_MAX_AGE_BALANCE)`；本 Reviewer 复核该常量为
  `5 * 60.0 = 300` 秒（`hedge_preflight_provider.py:55`），与 `unified_balances`/
  `spot_balances` 同源。新鲜缓存无目标行 → 返回 `Decimal(0)`（权威 flat 而非放行）；
  超龄/坏形状/不可解析 → `None` → 实时兜底 `query_symbol_um_qty`（`live_hedge_executor.py:540-569`，
  按 `symbol` 过滤、**带符号**求和、失败 `None`）。专项测试
  `test_cached_um_position_qty_has_300_second_staleness_ceiling` 断言 `-3`/`0`/`now-301→None`。
  UM 门判据（`service.py:1830-1876`）：能力缺失/实时失败/不可解析/非有限值全 fail-closed；
  forward 须 `positionAmt<0` 且覆盖剩余量、reverse 须 `>0`；`0` 与反号均拦。参数化矩阵
  （forward `-300/300/-299/0/NaN`、reverse `300/-300/299/0`）并断言新鲜缓存时
  `executor.query_calls == []`。
- **C2（单条 INSERT 原子落 paused + 中文原因列）**：`store.py:664-707` 同一 INSERT 写入
  `initial_status`/`initial_pause_reason`/**新加入列清单的 `pause_reason_zh`**；默认值
  `RUNNING`/`None`/`None` 使 open 零变化。不存在「先 running 再 pause」的中间态（计划复评
  C2 要求 2 的 dry-run tick 窗口被结构性排除）。
- **C3（dry-run 两道新门放行且零 POST）**：两道新门都在 `_dispatch_one_for_task` 的
  `if live:` 块内（`service.py:2712-2795`），dry-run 不进入；`test_close_execution_reversed_reduceonly_and_finalize`
  把两门 monkeypatch 成抛 AssertionError 仍完成 dry-run，断言 attempt `q_common=="0.5"`
  （接受原始 `single_amount`，F6 已批准取舍）且 record transport 零 POST。`_ensure_close_spot_balance`
  另有 live 缺能力 fail-closed（比基线更严，方向正确）。

#### 4.3 真实效果与运营风险 —— 通过（诚实且未恶化，部分改善）

- **未部署事实诚实标注**：`PROJECT_STATE.md` Live Risks 明写「**当前运行中服务的** close
  放行 ≠ close 安全……尚未部署……不能把该拦截当作运行时保护」；新增
  `[OPEN][PENDING-REVIEW]` 条目声明未部署、下一关卡双评审。stage-intake「未部署事实」、
  Review-1 handoff「不能假设的事实」同口径。
- **剩余风险披露齐全且未被本交付悄悄恶化**：v2 计划 §9 六条（两腿并发非原子、position-mode
  前提、env-key 前提、多 close 卡竞争、1000x 仅人工、cache miss 实时等待）逐条仍在；
  position-mode/env-key 前提另在 PRD §5 与 DEC-2026-08-09-001 固定。计划复评 §6 的
  「建卡零成本放大 §9.4 竞争面」观察仍是观察级，未产生新风险类别。
- **1000x 仅人工平仓限制保持且收紧**：open 的 P0 拦截未动；close 新增建卡双判（固化值 OR
  当前映射）+ dispatch 双判（`service.py:2712-2736`，**先于一切外部读取**，覆盖历史 NULL 行）。
  `test_create_close_blocks_multiplier_after_active_cycle_lookup`（零卡片落库）与
  `test_dispatch_blocks_legacy_null_multiplier_before_preflight`（`provider.calls == []`、
  精准暂停原因、零 attempt）证明。
- **本交付顺手堵住一个现存漏洞（真实效果改善）**：旧行为下「创建后未启动」的 running
  平仓卡在进程重启时会被 `_recover_workers` 无条件拉起并真实发单；改为初始 paused 后该
  自动发单路径消失（计划复评 §4.1 已识别，代码复核属实）。
- **worker 运行语义无忙循环**：`SIGNAL_CLOSE_GUARD_FAILED` 不在 `SIGNAL_TASK_LOCAL_PAUSE`
  （`domain.py:229` 为 `SIGNAL_INSUFFICIENT + (SIGNAL_COLLATERAL_CAP,)`），精准原因不被覆盖；
  `_worker_round` 该分支 `return False` 后下一轮重读到 paused →
  `_worker_exit(WORKER_EXIT_TASK_NOT_RUNNING)` 退出，无腿故 pacing 不触发，恰好多走一轮、
  零等待零订单。

#### 4.4 证据充分性 —— 通过（本关卡设计内证据等级）

- 资金路径安全声明当前全部由离线证据支撑：1610 后端测试（fake/mock client，含爆炸探针、
  调用捕获、参数化矩阵）、前端 self-check（内嵌 mock，93b 新增两项断言）、固定范围静态
  复核。**无实盘验证**——这一缺口在 PROJECT_STATE、stage-intake、Review-1 handoff 与本
  handoff 均如实标注；实盘验证按流程须两轮 ACCEPT + Human 最终决定并单独授权后才发生，
  故在本评审关卡不构成证据缺失。
- `_verify_close_flat` 未被本 diff 触碰，仍是不可逆结算事实的实时查询（`service.py:1649-1653`
  注释重申「仍实时，禁止读缓存」），`test_close_flat_verify_only_at_target_reached` 保持。
- 缓存时间单位三方同源（`_cached`、SnapshotService 写入、测试均用 `time.monotonic`），
  不存在「测试与实现共用同一个错误假设」。
- open 回归：`compute_preflight` 生产调用点仅两处（`service.py:894` create open 不传新
  kwarg 取默认 `check_balance=True`；`service.py:2560` close-forward 才传 False），kwarg 为
  keyword-only 带默认值；`get_snapshot` 新 kwarg 默认 `None`，open 分支原样调用（`service.py:2545-2549`
  注释标明逐字保留）；1610 全绿含 open 行为断言。

#### 4.5 发布就绪 —— 通过（仍只是本地待评审）

- 本交付未部署、未重启服务、未做实盘操作；在「两轮 ACCEPT + Human 最终决定」前仅为本地
  待评审工作树，本 Reviewer 确认无任何一方把它描述成运行中保护。
- 活文档同步落实计划复评 §4.4 要求：PRD §5（position mode 前提）、§6.1（rate limit 改由
  交易所响应执行）、§6.3 步骤 2 分流 + 新增「Two-stage close creation and dispatch」小节；
  DECISIONS 新增 DEC-2026-08-09-001（含对 DEC-2026-08-07-006 的定向 supersession）；
  ARCHITECTURE 增补两段式段落；`hedge-open-position-cycle-v1.md` §12 只加 supersession
  指针未重写历史。
- 契约回归复核：API 路径/响应字段/schema 未改；create 响应 `status` 取值由 `running` 变
  `paused` 属取值变化——本 Reviewer 独立检索 `docs/api/` 全部 `running/paused/初始/initial`
  命中，无任何文档对建卡初始状态作契约约定，故无需同步 API 契约文档。

### 5. 发现（Findings）

**无 `in-range` 阻塞项，无 `pre-existing-independent` 后续项，无
`pre-existing-release-critical` 上交项。**

Review-1 的四条 💭 nit（防御性不可达分支、forward 共享 `_read_balances()`、NaN 仅 forward
侧参数化、无缓存场景未以名命测试）经本 Reviewer 复核属实，均明确不要求本轮处理，不构成
后续项义务；本 Review-2 未新增 nit。

### 6. 未完成事项

无。dispatch 的五项硬性先验、三条必跑检查、五条现实核验重点均已完成。本 Reviewer 未做、
也无权做：合并、推送、部署、重启、服务控制、live DB、交易所请求、凭据读取、gate 变更、
订单与划转；除本交接件外零写入。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-2-kimi.handoff.md`
  2. `reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/status.json`
  3. `reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-1-opus5.handoff.md`
  4. `PROJECT_STATE.md`
- 执行：Bookkeeper `claude_glm` 按 Task Handoff Evidence Contract 的 Bookkeeper
  Same-File Verification 核验本交接件（计算 `BOOKKEEPER_APPEND_ONLY` 标记前字节的
  SHA-256，核对 task_id/role/stage_id/`base_sha` 与 `status.json` 及 `git rev-parse`
  一致），据 review-2 `ACCEPT` 更新 `status.json`，并向 Human 呈交双 ACCEPT 齐全后的
  最终验收/合并/部署决策点。
- 关卡：本交付为 `HIGH_RISK`，review-1（anthropic）与 review-2（moonshot）双 `ACCEPT`
  齐全后，由 Human 做最终业务验收与合并/部署/实盘启用的单独授权决定（`AGENTS.md` §6
  步骤 9—10、§3.1）；任何评审接受均不等于合并、部署或实盘授权。
- 不能假设的事实：
  - review-1 + review-2 双 `ACCEPT` **不等于**合并、部署、实盘启用或最终业务验收；
  - 本交付**未部署**，当前运行中服务仍是旧行为（创建即 `running` 的平仓卡、close 侧
    无 1000x 拦截），不得把本工作树描述成运行中保护；
  - 两段式创建/启动、UM 持仓门、forward base 门、1000x 拦截全部仅有离线测试证据，
    未做任何实盘验证；
  - sonnet5 版 review-2 dispatch 已被 Human 启动前改派取代、从未启动，不计
    `rework_count`；
  - 本 Reviewer 除本交接件外零写入，未改动 `status.json`、`PROJECT_STATE.md`、交付
    代码、测试或既有文档。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: close-task-preflight-simplification-review-2-kimi
执行结果: completed（完成）
结果摘要: 固定 dc356cd..e5f83f1（20 文件）HIGH_RISK Review-2 现实核验通过。需求真实达成：建卡零外部读取、原子落 paused 立即回显，Start 只交接 worker 不阻塞，启动后才预检发单，fill 经后端 409 无绕过。C1 um_positions 300s 上限+实时兜底、C2 单条 INSERT 含中文原因列、C3 dry-run 两道新门放行零 POST，均在真实运行语义下成立。未部署事实诚实标注；1000x 双判保持并堵住重启自动发单漏洞；无 in-range 阻塞项。
产物: [reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-2-kimi.handoff.md]
检查结果: [pass：SHA 与 status.json 逐字一致、固定 20 文件无控制提交、handoff 开始前 ABSENT；pass：三轮三 provider 隔离成立（openai→anthropic→moonshot）并披露全部参与；pass：必跑三项独立复跑 1610 passed exit=0 / self-check 全通过 exit=0 / diff --check 干净，与 Bookkeeper B 节及 Review-1 一致；pass：需求真实效果——建卡即显、Start 不阻塞、启动后才校验发单、fill 409 无绕过；pass：C1/C2/C3 运行语义成立（300s 常量、单 INSERT、门在 if live 内）；pass：运营风险诚实——未部署标注、§9 剩余风险未恶化、1000x 双判保持、重启自动发单洞被堵；pass：证据充分——资金路径仅离线证据如实披露、_verify_close_flat 仍实时、矩阵与调用捕获强；pass：发布就绪——活文档同步、docs/api 无初始状态契约回归、当前仍为本地待评审]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-2-kimi.handoff.md
修复要求: none
本地北京时间: 2026-08-09 17:22:36 CST
下一步模型: claude_glm（本 stage Bookkeeper，provider zhipu_glm）
下一步任务: 读取：reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-2-kimi.handoff.md；reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/status.json；reports/agent-runs/2026-08-09-close-task-preflight-simplification-v1/evidence/close-task-preflight-simplification-review-1-opus5.handoff.md；PROJECT_STATE.md；执行：按 Task Handoff Evidence Contract 核验本交接件源区块 SHA-256 与 task_id/role/stage_id/base_sha，据 review-2 ACCEPT 更新 status.json 并向 Human 呈交双 ACCEPT 后的最终决策点；关卡：HIGH_RISK 双 ACCEPT 齐全后由 Human 做最终业务验收与合并/部署/实盘启用的单独授权决定，任何评审接受不等于合并或部署授权
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- Bookkeeper: `claude_glm`（provider `zhipu_glm`）
- 核验时间（本地北京时间）：2026-08-09 17:27:49 CST
- 核对的 status revision：`3`（`phase=review-2`、`current_task.state=dispatched`，与本 review-2 返回一致）
- source_sha256（`BOOKKEEPER_APPEND_ONLY` 标记前字节，UTF-8）：`7a4e63ce246944bb04f4ffdd7b4e2f517ed6fb96b72444c8d4218988ca1aa9a4`
- 源边界复核：源区块收口于 Human Brief 闭合代码块（`...[/TASK_RESULT]\n\`\`\`\n\n`），标记独占一行。
- 通过依据（核验结论：**通过，Review-2 ACCEPT 采信；本 stage 双评审 ACCEPT 齐全**）：
  1. 身份一致：`task_id` / `stage_id` / `base_sha` / `delivery_sha` 与 `status.json` 逐字相同，且 `base_sha`/`delivery_sha` 经 `git rev-parse` 复核一致（`dc356cd…` / `e5f83f1…`）；Reviewer 引用的是已固定的 reviewed delivery SHA，非 `pending`。
  2. create-only 成立：本 handoff 在 Bookkeeper 17:11 CST 预检时为 ABSENT，现为本次 review-2 任务新建（`git status --short` 仅此一项 untracked，`HEAD=be8bf52` 未变）。
  3. 结构合规：Human Brief 内 `[TASK_RESULT v2]` 字段齐全、闭合标记为末尾；review-closure 字段 `评审结论: ACCEPT（接受）`、`问题记录` 指向本文件、`修复要求: none` 明确；`本地北京时间` 格式合规；`下一步模型` 为本 stage Bookkeeper `claude_glm`；`下一步任务` 为 `读取／执行／关卡` 形式且读取路径均为具体仓库相对路径。
  4. Reviewer 只读：除本 handoff 外零写入——`status.json`、`PROJECT_STATE.md`、交付代码、测试、既有文档、Review-1 handoff 均未改动（`git status` 仅 handoff 一项可证）。
  5. 必跑检查自洽：Reviewer 独立复跑 `1610 passed exit=0` / 前端自检全通过 / 固定范围 `git diff --check` 干净，与 Bookkeeper B 节及 Review-1 handoff 逐项一致（仅耗时差）。
  6. 隔离成立：实现 `openai`（Codex/OpenAI）→ Review-1 `anthropic`（Opus 5）→ Review-2 `moonshot`（Kimi），三轮三 provider；Review-2 与交付范围内全部实现/修复作者跨 provider，且未参与计划/设计/实现/Review-1。
  7. verdict 可采信：`ACCEPT`，无 `in-range` 阻塞、无 `pre-existing-independent` 后续项、无 `pre-existing-release-critical` 上交项；Review-1 四条 nit 经复核属实且均不要求本轮处理，Review-2 未新增 nit。
- 可复现命令（核验脚本）：`python3 -c "import json,hashlib;raw=open('<本文件>').read();m='<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->';print(hashlib.sha256(raw[:raw.find(m)].encode()).hexdigest())"`，并比对 `status.json` 与 `git rev-parse dc356cd7f6acdc8502cd6caa44a48f6e3c760cac e5f83f1c7f53bba4593a51f843fd1f45f52814bd`。
- 后续状态：Review-1（anthropic）与 Review-2（moonshot）双 `ACCEPT` 齐全，本 stage HIGH_RISK 评审关卡全部通过。Bookkeeper 将 `status.json` 推进至 `review-complete` / `checkpoint=dual-review-accepted`（`revision=4`、`current_task.state=verified`，`delivery_sha` 不变），并向 Human 呈交最终决策点。**合并、部署、重启服务与实盘启用仍须 Human 单独授权**；本交付未部署，当前运行中服务仍是旧行为。

## Errata (append-only)

（暂无。）
