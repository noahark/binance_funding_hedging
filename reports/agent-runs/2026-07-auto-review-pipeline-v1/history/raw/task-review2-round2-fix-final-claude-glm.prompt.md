<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-round2-fix-final-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
task:          review-2 round-2 FINAL fix (gpt-5.6-sol REWORK record: 5xP1 + 2xP2 code findings, all bookkeeper-confirmed)
findings_source: reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-round2-gpt-5.6-sol.md + review-2-round2-gpt-5.6-sol.verdict.json（§findings/fix_start_prompt 权威）
rework_charge: 3 of 3 — THE FINAL SLOT. 若本交付后仍需任何 code-changing rework，stage 直接 human_escalation_required。
note:          sol P2#3（status 残段 + gemini 报告 whitespace）已由 bookkeeper 清毕（commit aa9f7c1），不在本 packet。本 packet 覆盖 FX1–FX7 七组代码修复。
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# Review-2 Round 2 Final Fix — 七组控制面修复（最后一格 rework，零漂移要求）

你是本 stage 的 fix implementer（Claude-GLM，fresh bounded session）。这是
**最后一格 rework（3/3）**：本交付若再留任何 P0/P1/P2 required finding，
stage 进入 human_escalation_required。findings 原文是修复权威：
`50-review-2-round2-gpt-5.6-sol.md` 与其 verdict JSON 的
`fix_start_prompt`。本 packet 在其上叠加**精确机械路由与防漂移禁令**，
两者冲突时以 sol 原文为准并 append blocker 说明，不得自行取舍。

不得 dispatch 任何模型；不得 commit；不得联网；测试确定性、stdlib-only。

## Read First（顺序执行）

1. `50-review-2-round2-gpt-5.6-sol.md` §Findings + verdict `fix_start_prompt`（权威）
2. `52-review-2-round2-panel-disposition.md` §2（bookkeeper 8/8 复现记录——每项的确认方式即复验判据）
3. `scripts/auto-review-runner.py` / `scripts/stage-seal.py` 现状（改前通读相关函数全文）
4. `agents/registry.yaml`（真实命令形状——**只读**，FX1 不得以改 registry 回避）
5. `docs/auto-review-pipeline.md` + `workflows/templates/stage-delivery.yaml` `executable_contract`（frozen 契约）
6. `00-task.md` 验收 16/21/26/27/28

前置核对（不符即 append blocker 停止）：branch
`stage/2026-07-auto-review-pipeline-v1`；status 顶层 `fixing`、
`rework_count` = 3；`review_2.round2.verdict` = `REWORK`。

## Writable Set（完整清单，不多不少）

```text
scripts/auto-review-runner.py
scripts/stage-seal.py
scripts/tests/test_auto_review_runner.py
scripts/tests/test_stage_seal.py
```

仅 append：`20-implementation.md`、`60-test-output.txt`。其余一切只读——
特别是 `harness_stage_lib.py`、`validate-stage.py`、`agents/registry.yaml`、
schemas、workflow、manifest、status/handoff/review/packet。**若你认定某项
修复必须触碰只读文件（含"cursor 需要 schema 扩展"场景），停止该项、
append blocker 写明路径与理由，改走该项的 fail-closed 替代路线（见 FX5）；
绝不 fix-forward。**

## 全局防漂移禁令（每一项都适用）

- **G1**：不得用合成 fixture 替代 packet 指名的"真实对象"测试（真实
  registry、真实执行流崩溃注入、真实 flock 竞争）。上一轮 F3 的教训
  就是合成模板掩盖生产断层。
- **G2**：不得以"调整既有测试的期望值"消化新行为，除非该项修复明确
  要求（仅 FX7 涉及一个既有测试）；任何其他既有测试改动 = 漂移，须
  append blocker 说明而不是直接改。
- **G3**：不得重构、重命名、移动与 findings 无关的代码；diff 最小化，
  每个 hunk must 可指认到 FX 编号。
- **G4**：每项修复必须先写（或先跑）负测试证明缺陷可复现（红），再修
  （绿）；20-implementation.md 里逐项给出红→绿证据（测试名 + 修前
  失败摘要一行 + 修后 OK）。
- **G5**：fingerprint 公式、AUTO_TRANSITIONS、review-1 三对路由、
  seen-diff bind、post-cross-check blocking rerun、pilot 谓词、显式
  路径 git add——全部不得触碰。

## 修复项（FX 编号对应 sol §Findings 顺序；每项四段：锚点/要求/禁止/判据）

### FX1 — adapter 命令 shell 安全（sol P1#1）

**锚点**：`scripts/auto-review-runner.py` `_default_invoke`（~:865-880，
裸 `.replace()` 后 `shell=True`）。

**要求**：
1. 每个被替换值（`<prompt-file>`/`<repo>`/`@PROMPT@`/`@REPO@`）以
   `shlex.quote()` 包裹后再替换。真实 registry 的两种占位符上下文——
   双引号内命令替换 `"$(cat <prompt-file>)"`（claude_glm/kimi）与裸词
   `--cwd <repo> --prompt-file <prompt-file>`（grok）——`shlex.quote`
   在两种上下文均产生合法安全结果（`$()` 内部是全新解析上下文，单引号
   有效），实现说明里写明这一论证。
2. 新测试类 `ShellSafeInvocationTests`：
   a. **真实 registry 字符串级**：加载真实 `agents/registry.yaml`，对
      claude_glm/kimi/grok 全部含占位符命令，用含**空格**与含 shell
      metacharacter（至少 `$`、`;`、单引号）的路径替换，断言
      `shlex.split` 解析后替换路径以单 token 完整出现、无字面占位符。
   b. **真实执行探针**（本地无害命令，无网络无模型）：构造与生产同
      形状的模板 `x "$(cat <prompt-file>)"` 与 `x <prompt-file>`（x=
      echo/cat），prompt 文件放在**名字含空格的 tempfile 目录**（如
      `repo with space/`），经 `_default_invoke` 真实 `shell=True`
      执行，断言 exit 0 且 stdout 含文件内容——修前该探针必须失败
      （`No such file or directory`），红→绿入证。

**禁止**：改 registry 回避；只做字符串断言不做执行探针；探针路径无
空格；用 `shell=False` 全量改造（改变既有 invoker 契约——本轮只要求
quoting 修复；若你论证 argv 化更优，仅允许在 `_default_invoke` 内部
实现且外部行为/receipt 记录完全不变，并在报告里单列风险）。

**bookkeeper 复验判据**：在本仓（根路径天然含空格 `ai code`）跑
执行探针测试直接通过；手工再验一次
`shlex.quote('/tmp/a b') 注入后 $(cat …) 展开正确`。

### FX2 — seal 每 commit 前 expiry 重查（sol P1#2）

**锚点**：`scripts/auto-review-runner.py` `_node_seal`（~:1485-1500，
现仅 seal 前查一次）；`scripts/stage-seal.py` 的两个 commit 点
`create_snapshot`（:328）与 `create_bind`（:394）。

**要求**：
1. `stage-seal.py` `seal()` 增加可选参数
   `commit_guard: Callable[[], None] | None = None`（默认 None =
   现行为，CLI 手动路径完全不变）。在**每次 git commit 紧前**调用
   guard：fresh 路径的 create_snapshot 前与 create_bind 前、两条
   恢复路径的 create_bind 前——共覆盖全部 commit 点。
2. runner `_node_seal` 传
   `commit_guard=self._check_authorization_expiry`。
3. 新测试（`test_stage_seal.py` + runner 侧各一）：fake-clock 场景——
   H_snapshot 落地后、H_bind 前时钟越过 `expires_at`，断言：H_bind
   commit **未创建**（`git rev-list --count` 不变）、异常为 expiry
   fail-closed、状态未被写成 sealed。runner 侧用注入 now() 驱动。

**禁止**：把 guard 只放 seal() 入口；改 `harness_stage_lib`；改
fingerprint/receipt 结构；guard 里做除"检查即抛"外的任何副作用。

**bookkeeper 复验判据**：`grep -n "commit_guard" scripts/stage-seal.py`
命中全部 commit 点紧前；fake-clock 测试单跑；破坏性验证（去掉
create_bind 前那次调用 → 测试必须红）。

### FX3 — marker 恢复硬化 + 孤儿 marker（sol P1#3）

**锚点**：`scripts/stage-seal.py` `seal()`：`unit_is_sealed` 抛出
（~:495）先于 marker 处理（~:500-524）；恢复分支只判
`current_head != parent_sha`，从不校验 `expected_paths`。

**要求**：
1. **恢复条件收紧**（三分支，穷尽）：
   - `HEAD == marker.parent_sha` → snapshot 未落，stale marker：清除、
     走 fresh seal（现行为保留）；
   - `HEAD != parent_sha` 且 `git rev-parse HEAD^` == parent_sha 且
     `git diff-tree --no-commit-id --name-only -r HEAD` 的路径集合 ==
     marker.expected_paths 集合 → 真崩溃窗，按现恢复路径续 bind；
   - 其余一切（隔多个 commit、单 commit 但路径集不符）→ **fail-closed
     抛 SealError**（不清 marker、不 commit、不走 fresh——介入提交
     污染需人工裁决）。
2. **孤儿 marker**：`unit_is_sealed` 为真且 marker 存在时——先机械
   验证 bind 完整（unit 的 `snapshot_commit`+`diff_fingerprint` 非空
   且对应 receipt 文件存在）→ 验证通过则清 marker 后照常抛
   already-sealed；验证不过则 fail-closed 抛错并保留 marker。
3. 新测试（真实执行流注入，沿用 round-1 monkeypatch 模式）：
   a. 崩溃后插入无关 commit（在 temp 仓里 commit 一个无关文件）→
      第二次 seal() 必须抛 SealError 且 `rev-list --count` 不变、
      marker 仍在；
   b. H_bind 后 marker 残留（monkeypatch `_clear_pending_marker` 首次
      调用为 no-op）→ 下一次 seal() 清掉 marker、不产生任何新 commit、
      抛 already-sealed。

**禁止**：手工构造 marker 文件内容代替真实执行流注入；把"其余一切"
分支实现为清 marker 走 fresh（那会造成第二次 code commit——正是
finding 的事故形态）；放松 `expected_paths` 为子集比较。

**bookkeeper 复验判据**：介入提交测试单跑；破坏性验证（把路径集合
比较改回"任意 HEAD 接受"→ 测试 a 必须红）。

### FX4 — 锁竞争失败方零写（sol P1#4）

**锚点**：`scripts/auto-review-runner.py` `run()`（~:1097-1105）——
锁失败现走 `_handle_preflight_failure`（写 status paused/awaiting_human
并 persist）。

**要求**：
1. 锁获取失败改为：**零状态写**——不调 `_handle_preflight_failure`、
   不 `_persist`、不记 transition、不写任何 receipt/evidence；直接
   `return RunResult(ran=False, terminal="lock_busy", reason=...)`
   （新增 terminal 字面量仅存在于返回值/stderr，不进入 status 与
   workflow 状态机——锁竞争发生在任何状态转换之前，语义上 run 未
   开始）。可向 stderr 打一行诊断。
2. 新测试 `RunnerLockTests` 扩展：进程内以 `fcntl.flock` 先行占用同
   一 lock 文件（或启动持锁的第二 runner 实例），随后 run()：断言
   (a) 返回 terminal=="lock_busy"；(b) **status.json 与 stage 目录
   全部文件的字节哈希 before/after 完全一致**（逐文件 sha256 对比，
   不是抽查）；(c) 无新增文件。

**禁止**：先写后回滚；把 lock_busy 记进 status 的任何字段；改
workflow/AUTO_TRANSITIONS 来"容纳"新状态（不需要——它不是状态机
事件）。

**bookkeeper 复验判据**：字节不变断言存在且为全目录；破坏性验证
（恢复 `_handle_preflight_failure` 调用 → 测试必须红）。

### FX5 — running 恢复幂等（sol P1#5）

**锚点**：`scripts/auto-review-runner.py` `_run_body` resume 循环
（~:1142-1153，仅跳过 review_1.verdict==ACCEPT）；receipt 命名
`runner-<seq>-<node>.receipt.json`（机械痕迹）。

**要求（两案二选一，报告里显式声明选择及理由）**：
- **推荐案 A（fail-closed，改动最小）**：resume（`runner_state ==
  "running"`）时，对每个非 ACCEPT 单元检查磁盘 receipt——存在该单元
  任何 `implementation`/`embedded_cross_check`/`fix` 节点 receipt 即
  证明"已开始未完成"→ 该单元**不重派**，整个 run fail-closed 到
  awaiting_human（此转换走既有 preflight-failure/recoverable 路径的
  合法 workflow 事件，不发明新 transition），escalation detail 写明
  `resume_unverifiable_unit` 与单元 id。干净单元（零 receipt）允许
  正常从头执行。
- **案 B（node cursor）**：仅当不需要触碰 schema/workflow/validator
  （全只读）时允许：unit 内新增 `node_cursor` 字段，每节点完成后
  立即 persist；resume 按 cursor 精确续点；cursor 缺失或与 receipt
  痕迹矛盾 → 同案 A fail-closed。若发现需要契约文件变更，立即放弃
  案 B 改走案 A 并 append blocker 说明。
- 无论何案，新测试 `ResumeIdempotencyTests` 必须覆盖 sol 指名的
  **五个崩溃边界**：implementation 后 / cross-check 后 / seal 后 /
  review 后 / fix 后崩溃再 resume——逐一断言 implementation（与 fix）
  adapter 的 invoker 调用计数为 **0**（绝无重复 model call），且
  终态符合所选方案（案 A：awaiting_human；案 B：从正确节点续）。

**禁止**：伪幂等（重派后结果去重）；只测 implementation 一个边界；
案 B 下静默扩展 schema；把"干净单元从头执行"也 fail-closed（过度
收紧会破坏合法 fresh resume）。

**bookkeeper 复验判据**：五边界测试逐个单跑；破坏性验证（恢复
"仅跳过 ACCEPT"旧逻辑 → implementation-后-崩溃测试必须红）。

### FX6 — authorization 精确绑定（sol P2#1）

**锚点**：`scripts/auto-review-runner.py`
`_verify_authorization_binding`（~:1015-1040，现仅拒 `live - auth`）。

**要求**：task_ids 改为**双向集合相等**（`auth - live` 非空同样
`PreflightFailed("scope_mismatch")`，detail 写 `authorized_but_absent`）；
并补齐 topology/allowed_pathspecs/forbidden_pathspecs/budget 数值的
精确等值负测试（每个 divergence 至少一个：auth 多 task、topology 不等、
allowed 列表不等、forbidden 列表不等、每个 budget 字段不等）。现有
`live - auth` 方向与全部既有测试不得放松。

**禁止**：把等值实现为"排序后字符串比较"以外还带 normalize 的宽松
比较（列表语义按集合/等值，路径不做通配展开）。

**bookkeeper 复验判据**：auth=[T1,T2] vs live=[T1] 负测试单跑；破坏性
验证（去掉新方向 → 该测试红）。

### FX7 — 账本预检后更新（sol P2#2）

**锚点**：`scripts/auto-review-runner.py` `_charge_auto_change`
（~:693-706，先递增后判 cap）。

**要求**：先计算拟议值（`auto_used+1` 与 `rework_count+1`），任一超
cap → **两个计数器均不写**、直接 TerminalEscalation；允许时两计数器
一次性同步更新。相应修正现有测试
`test_charge_auto_change_escalates_past_max_stage_rework` 的断言：
escalation 后 `rework_count` 与 `auto_code_changes_used` **均保持
原值**（这是 G2 允许的唯一既有测试改动）。

**禁止**：改 max 语义（`>` 与 `>=` 边界保持现契约：恰达 max 合法、
超 max 拒绝）；触碰 bind/seal 处的人工记账路径。

**bookkeeper 复验判据**：拒绝分支双计数器不变断言；破坏性验证（改回
先递增 → 测试红）。

## Required Checks（全部原始输出 append 到 60-test-output.txt）

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" scripts harness-manifest.yaml   # expect exit 1
git status --short                                  # 只允许 4+2 文件
```

每个 FX 的新测试类单独可跑并在报告列出 FX→测试函数映射。全量套件
全绿（136 + 新增）。

## Non-Regression（除 G5 外）

不得破坏：既有 136 测试（FX7 指名的一个断言修正除外）、round-1 F2–F7
的全部 26 个负测试、TransitionTruthSourceTests、receipt 卫生、
`_default_invoke` 的 receipt 只记 command_ref 不记展开命令。

## Completion Report（20-implementation.md 末尾 append `Review-2 Round 2 Final Fix`）

必含：①FX1–FX7 逐项 disposition + **红→绿证据**（G4）；②FX5 方案
声明（A/B + 理由）；③FX→测试函数映射表；④修改文件确认在 writable
set；⑤全部命令原始结果；⑥`git status --short`；⑦风险与"若仍有
residual 该如何走 human_escalation"一句确认。页脚：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 复验 FX1–FX7（含逐项破坏性验证）→ re-seal（新指纹）→ 正式 re-review-1 → review-2 round 3
```
