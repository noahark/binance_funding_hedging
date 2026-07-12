<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T3-runner-and-integration-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      read status.json tasks[id=T3].base_sha; never substitute moving HEAD
prior_tasks:   T1 (25383e8) and T2 (a7fd737) both review-1 ACCEPT; their files are frozen read-only inputs
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T3 Implementation Packet — `runner-and-integration`

你是 Claude-GLM，作为 Harness stage `2026-07-auto-review-pipeline-v1` 的 T3
implementer（fresh bounded session）。本任务是最后一个实现包：确定性
runner、其集成测试、以及 harness-manifest 收尾同步。

人工 operator 负责调用 adapter；你不得自行 dispatch 任何模型。

## 1. Read First And Authority

- `AGENTS.md`（Auto Review Pipeline 段）
- `docs/auto-review-pipeline.md`（normative 契约——runner 必须实现它）
- `workflows/templates/stage-delivery.yaml` 的
  `auto_review_pipeline.executable_contract`（activation/state_transitions
  八行/node_transitions/review_1_routes/pilot_predicate——**runner 的行为
  真源**，不得在代码里另行发明策略）
- `schemas/auto-review-authorization.schema.json` /
  `schemas/runner-receipt.schema.json`
- `scripts/harness_stage_lib.py`（T2 交付：指纹/patch 比较/atomic
  JSON/safe path/手写校验器——**必须复用，不得重复实现**）
- `scripts/stage-seal.py`（T2 交付：seal 由 runner 委托调用，不重写）
- `agents/registry.yaml`（adapter 命令引用与 `invocation_owner`）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md`
  （验收 3/4/5/6/11/12/13/14/15/16/17/18/19/23）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md`
  （§auto-review-runner.py、§Transition Model、§Worktree And Task
  Topology、§Review-1 Routing、§Multi-Owner Fix Routing、§Security）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/12-development-breakdown.md`
  §5（T3 冻结契约全节）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/30-review-1-T2.md`
  的 residual risk（P3 `_pathspec_matches`——见 §5.4 测试要求）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

开始前只核对：branch 为 `stage/2026-07-auto-review-pipeline-v1`；
`tasks[id=T3].status` 为 `ready_for_human_dispatch` 且 `base_sha` 非空；
`auto_review_pipeline.enabled_for_this_stage` 与 `parallel_mode.enabled`
均为 `false`。任一不符即 append blocker 并停止。

## 2. Complete Writable Set

```text
scripts/auto-review-runner.py                  # new
scripts/tests/test_auto_review_runner.py       # new
harness-manifest.yaml                          # amend (final sync)
```

共享 evidence 例外，仅 append：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

**其余全部只读**。特别禁止：`scripts/harness_stage_lib.py`、
`scripts/stage-seal.py`、`scripts/validate-stage.py`、T2 三个测试文件、
全部 T1 契约文件（AGENTS/workflows/agents/docs/schemas/templates）、
`status.json`/`70-handoff.md`/review 文件/packet 文件、产品与 funding
路径。发现 T1/T2 交付缺陷即停止记录 blocker（design-amendment 路径），
不得跨界 fix-forward。不得 commit/push/merge/rebase/切 branch。

## 3. Frozen T3 Contract

### 3.1 `scripts/auto-review-runner.py`（stdlib-only）

确定性状态机执行器，实现 10-design §auto-review-runner.py 与 workflow
`executable_contract` 的全部行为：

1. **数据加载注入点**：workflow/registry/status/authorization/task 数据
   通过可注入的加载路径进入（构造参数或 `--config-dir` 类机制），使测试
   能替换假 adapter 定义与假可执行文件；生产默认读真实文件。workflow 的
   `executable_contract` 是转移真源——runner 加载它执行，**不得在代码中
   硬编码第二份转移矩阵**（若 stdlib 无 yaml：允许用受限的结构化解析器
   只解析 `auto_review_pipeline.executable_contract` 所需子集，或将
   T2/validator 已内置的 `AUTO_TRANSITIONS` 通过 import 复用并以测试断言
   其与 workflow 集合一致——二选一，报告里写明选择与理由）。
2. **preflight**：authorization 存在/手写校验通过（复用
   `harness_stage_lib.validate_authorization_doc`）/未过期（null 语义按
   契约）/stage/branch/scope/budget 精确匹配/exclusive worktree（branch
   精确、无 runner lock 冲突、dirty 路径全在活动 task allowlist 内）/
   mode mutex。任一失败：不发起任何 adapter 调用，写证据，置
   `awaiting_human` + 顶层 `paused`（按转移矩阵）。
3. **预算记账**：model call 在 adapter 进程启动前记账（成功/超时/失败/
   invalid JSON/空输出均耗 1）；wall-clock 自 `authorized→running` 起算，
   进程重启不重置 deadline；invalid JSON 每模型最多 2 次尝试（耗 call 不
   耗 rework）；auto code-changing 合计 ≤2 且 `rework_count` 单账本。
4. **节点循环**：implementation → initial blocking（失败允许恰一次
   auto fix，记账 rework；复测仍败 → escalation）→ embedded cross-check
   （run/skip/unavailable 三情形都产 artifact）→ identical post-cross-check
   blocking rerun（失败封 seal）→ 委托 `stage-seal.py` seal → review-1。
5. **review-1 路由**：Grok primary（`optional_review_command` 引用）；
   serial-only fallback（Kimi/GLM embedded read-only 引用，候选 provider
   不在单元 author+fix 集合才 eligible）；parallel tip 无 cross-pool
   fallback，Grok 失败/重复 invalid verdict → `human_escalation_required`
   + `80-*.md`；决不自动调 GPT/Claude。
6. **verdict 解析**：raw stdout 先落盘；枚举顶层 JSON 候选，仅当"恰一个
   schema-valid（用手写校验或按 review-verdict 结构检查）+ 是最后一个
   非空白结构块 + stage/role/fingerprint 匹配活动单元"才接受；接受字节
   原样存 `review-1-<unit>-round<N>.verdict.json`；verdict-record commit
   不改变被审单元 base/head/fingerprint。
7. **receipt**：每次 adapter 调用写
   `runner-<seq>-<node>.receipt.json`（复用
   `harness_stage_lib.validate_receipt_doc` 自检后原子写入）；只记
   registry 命令引用，决不展开命令/环境/秘密。
8. **fix 路由**：保留完整 `fix_start_prompt` + runner 生成的 immutable
   owner header；按 `findings[].file` × 冻结 task ownership 路由；缺失/
   歧义/跨界 → unroutable escalation；v1 多 owner fix 串行写。
9. **escalation**：`80-escalation-<reason>-<UTC>.md` 按 docs §13 内容
   要求；status 记 `last_escalation_path`，substate `awaiting_human`，
   cap/timeout/budget/unroutable/tip-once 置顶层
   `human_escalation_required`。
10. **停止**：所有 required 单元 ACCEPT → `completed_review_1`，决不
    自行进入 review-2。模型文本永不选择命令/路径/转移；禁 `git add -A`
    （staging 只用显式冻结清单）；路径全走
    `harness_stage_lib.resolve_safe_path`。

### 3.2 `harness-manifest.yaml`（最终同步）

`harness_owned` 精确增补（且仅此五项）：

```text
scripts/harness_stage_lib.py
scripts/stage-seal.py
scripts/auto-review-runner.py
scripts/tests/
docs/auto-review-pipeline.md
```

（`schemas/`、`workflows/` 目录条目已覆盖新 schema/workflow 内容；不动
其他行。）

### 3.3 `scripts/tests/test_auto_review_runner.py`（stdlib-only）

复用 `test_harness_stage_lib.make_temp_repo` 等共享 helper（import，不
复制）。fake adapter = 临时目录里的本地假可执行/脚本 + 注入的假 registry
数据；**无网络、无真实 CLI、无凭据**。必须覆盖 12-breakdown §5 的全部
集成场景：

- default-off manual status 不触发 runner 行为；
- preflight 各拒绝面（缺/无效/过期/错 stage/错 branch authorization、
  dirty/共享/错 branch worktree、mutex）在任何 adapter 调用前失败；
- fake implementation → blocking → cross-check → blocking rerun → 两商
  seal（委托 stage-seal）全链 happy path；
- evidence-目录写入不改变第二次 blocking 结果；第二次失败封 seal；
- bind mismatch fail-closed；
- fake Grok ACCEPT 到 `completed_review_1`；
- invalid JSON 恰重试一次后正确路由（serial fallback eligible /
  ineligible 两分支）；
- blocking fix + review REWORK 合计消耗 auto 预算，2 次封顶；
- parallel author set（GLM+Kimi tip）拒绝 cross-pool fallback 并
  escalation；
- 多 owner fix 串行化（无并发写）；
- seal/verdict 各边界崩溃点的确定性 resume 或 escalation；
- verdict-record commit 不改变被审 fingerprint；
- receipt 负测试：断言产物中无 expanded command/env/token 样式内容，
  `next_transition` 只出自 workflow 集合；
- call/wall-clock 记账时点（启动即记、超时也记、重启不重置）；
- **P3 残余风险覆盖（Kimi T2 review 转来）**：parallel topology 下以
  runner→seal 黑盒路径重测 authorization pathspec 边界形态（negation/
  嵌套 glob/大小写等 exotic 形态至少各一例——断言要么正确匹配要么
  fail-closed escalation，不允许静默漏判）。

### 3.4 Required Checks（冻结四命令全量 + 记录）

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" scripts harness-manifest.yaml   # expect no matches / exit 1
```

（committed-range `git diff --check <T3-base>..<T3-head>` 由 bookkeeper 在
delivery commit 后执行；你不得为生成 head 而 commit。）完整原始
stdout/stderr 与 exit status append 到 `60-test-output.txt`。

## 4. Completion Report

在 `20-implementation.md` 末尾 append `T3 Implementation`：branch 与 T3
base_sha；文件清单（确认 allowlist 内）；§3.1 十点逐项状态 + 转移真源的
实现选择及理由；manifest diff 逐行；测试场景清单 → 测试函数映射；全部
命令原始结果；`git status --short`；blockers/风险/review-1 建议关注点。
不要 commit，不要写 status/handoff/review，不要 dispatch 模型。页脚用
本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 边界检查 → 独立复跑全量套件 → T3 seal → T3 Kimi review-1 packet
```
