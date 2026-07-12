<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T2-seal-and-validator-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
base_sha:      read status.json tasks[id=T2].base_sha; never substitute moving HEAD
prior_task:    T1 review-1 ACCEPT (Kimi, 30-review-1-T1.md); T1 contract files are now frozen read-only inputs
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# T2 Implementation Packet — `seal-and-validator`

你是 Claude-GLM，作为 Harness stage `2026-07-auto-review-pipeline-v1` 的 T2
implementer（fresh bounded session）。本任务交付确定性机械核心：共享库、
seal 工具、validator 的 auto 模式校验支持，以及它们的 stdlib-only 测试。
**不写 runner**（那是 T3）。

人工 operator 负责调用 adapter；你不得自行 dispatch 任何模型。

## 1. Read First And Authority

按顺序完整阅读：

- `AGENTS.md`（含新 Auto Review Pipeline 段）
- `docs/auto-review-pipeline.md`（T1 交付的 normative 契约）
- `workflows/templates/stage-delivery.yaml`（`auto_review_pipeline` 块与
  `executable_contract`）
- `schemas/auto-review-authorization.schema.json`
- `schemas/runner-receipt.schema.json`
- `scripts/validate-stage.py`（现役 validator 全文）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md`（验收 1–28）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md`
  （§Component Architecture、§Seal And Commit Protocol、§Review Unit Model、
  §Embedded Cross-Check And Seen-Diff Bind、§Test Strategy）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/11-adr.md`（决策 3/4/8）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/12-development-breakdown.md`
  （§4 T2 全节：Contracts produced、Implementation constraints、
  Required tests、Review focus、Risks）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json`

开始前只核对：branch 为 `stage/2026-07-auto-review-pipeline-v1`；
`tasks[id=T2].status` 为 `ready_for_human_dispatch` 且其 `base_sha` 为非空
committed SHA；`auto_review_pipeline.enabled_for_this_stage` 与
`parallel_mode.enabled` 均为 `false`。任一不满足即停止并在报告 append
blocker，不得自行修状态。

## 2. Goal

实现 12-breakdown §4 冻结的 T2 契约：

1. `scripts/harness_stage_lib.py`（新）——纯机械共享库；
2. `scripts/stage-seal.py`（新）——唯一自动 seal 原语（本 stage 不运行它对
   自身 seal；它面向未来 auto 模式，交付物为代码+测试）；
3. `scripts/validate-stage.py`（改）——fingerprint 委托共享库 + auto 模式
   校验；
4. `scripts/tests/test_harness_stage_lib.py` /
   `scripts/tests/test_stage_seal.py` /
   `scripts/tests/test_validate_stage_auto_review.py`（新）。

## 3. Complete Writable Set

只有下列 delivery 文件可创建/修改；这是完整 allowlist：

```text
scripts/harness_stage_lib.py                       # new
scripts/stage-seal.py                              # new
scripts/validate-stage.py                          # amend
scripts/tests/test_harness_stage_lib.py            # new
scripts/tests/test_stage_seal.py                   # new
scripts/tests/test_validate_stage_auto_review.py   # new
```

共享 evidence 例外，仅 append：

```text
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

**不得创建任何其他文件**：无 `conftest.py`、无 `__init__.py`、无独立
fixtures 模块。共享测试 helper（隔离环境的临时 git 仓构造器）定义在
`test_harness_stage_lib.py`，由同目录其他测试模块 import。

## 4. Forbidden Set

所有未在 §3 明列的路径禁止写入。特别禁止：

```text
scripts/auto-review-runner.py                      # T3
scripts/tests/test_auto_review_runner.py           # T3
harness-manifest.yaml                              # T3
AGENTS.md / workflows/** / agents/** / docs/** / schemas/**   # T1 已交付，冻结只读
reports/agent-runs/_template/**                    # T1 已交付
reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json
reports/agent-runs/2026-07-auto-review-pipeline-v1/70-handoff.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/30-review-1-*.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/review-1-*.verdict.json
reports/agent-runs/2026-07-auto-review-pipeline-v1/task-*.prompt.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/2[1-5]-*.md
backend/** frontend/** schemas/api/** docs/product/** docs/architecture/**
reports/api-samples/** reports/agent-runs/2026-07-funding-*/** reports/follow-ups/2026-07-funding-*
```

若实现发现 T1 契约文件（schema/docs/workflow）有缺陷，**停止并记录
blocker**——那是 design-amendment/操作者路径，不得 fix-forward 跨界修改。
不得 commit、push、merge、rebase、创建 branch。`status.json`、
`70-handoff.md`、review 文件、证据 commit 和 fingerprint 仅由 bookkeeper
写入。

## 5. Frozen T2 Contract

### 5.1 `scripts/harness_stage_lib.py` 公开 API（stdlib-only）

- `compute_diff_fingerprint(root, stage_dir, base_sha, head_sha) -> str` ——
  与 `scripts/validate-stage.py` 现行实现**字节等价**（同 git 参数序、同
  `:(exclude)<stage>/status.json`、bytes 上 sha256、返回
  `f"{head_sha}:{digest}"`）。
- 字节保真的 git diff 捕获：`capture_code_scope_patch(root, base_sha,
  pathspecs) -> bytes`（frozen base + 有序 pathspec，`--binary`，不做任何
  文本解码/重编码）。
- `patches_byte_equal(a: bytes, b: bytes) -> bool`。
- `atomic_write_json(path, obj)`（临时文件 + `os.replace`）。
- provider-identity 归一化（validator 现行 `PROVIDER_IDENTITIES` 映射表的
  超集，含 gemini→google）。
- stage/worktree 安全路径解析：拒绝绝对路径、`..` 遍历、symlink 逃逸、
  CR/LF/控制字符。
- **手写结构校验器**（stdlib-only，运行时权威）：
  `validate_authorization_doc(doc) -> list[str]` 与
  `validate_receipt_doc(doc) -> list[str]`，覆盖两个 schema 文件的全部
  约束面：required 集（authorization 16 键、receipt 18 键）、const/enum
  （rework const 3、auto ≤2、invalid-JSON const 2、
  `auto_high_end_dispatch_allowed` const false、`authorized_by` const
  human）、`expires_at` required+nullable 及非空时 ISO8601 可解析、safe
  path 规则、receipt 的 node 条件三组 adapter/ref 配对（review_1 三对
  oneOf 语义）、`next_transition` 集合 = workflow
  `allowed_next_transitions`（9 值 + null）、`call_budget.after ==
  before - 1` 等 cross-field 语义（schema 无法表达、由手写校验补足）。

本库不得包含 workflow 判断或模型路由策略；不 import `jsonschema`/`yaml`
（YAML 消费仅限 T3 runner 的范围问题——T2 内如需读取 workflow 的
`allowed_next_transitions` 做集合相等断言，在**测试**中以文本/结构方式
自行解析该小节或将 9 值集合作为测试内冻结常量并断言 schema 枚举与之相等，
不引入 yaml 库）。

### 5.2 `scripts/stage-seal.py`

实现 10-design §stage-seal.py 的九步协议（修订后版本，含第 3 步
post-cross-check blocking 验证），CLI 形式、非零退出即 fail-closed：

1. 验证 authorization、branch、worktree、status、allowed paths、runner lock；
2. 验证 blocking checks 与必需 embedded cross-check 证据存在；
3. 验证冻结 blocking 命令集在 cross-check 证据落盘后**重跑过**且其输入不
   消费 stage evidence 路径；
4. captured vs regenerated code-scope patch 字节比较（bind；mismatch
   fail-closed，不写任何 hash 进 status）；
5. 创建 review snapshot commit（H_snapshot）；
6. 用共享库函数从 base 到 snapshot head 计算现行 fingerprint；
7. 原子写机械 status 字段 + seal receipt（**路径名
   `runner-<seq>-seal.receipt.json`**，形状由本任务定义并测试；它不是
   adapter invocation receipt、不走 runner-receipt.schema.json、不计入
   P11 adapter-call 分母——在文件 docstring 与测试中写明）；
8. 创建 binding/evidence commit（H_bind，仅 status/handoff 字段/seal
   receipt，不动 code-scope）；
9. 在 clean tree 上运行 `validate-stage.py --phase pre-review`。

崩溃恢复 fail-closed：H_snapshot 前崩溃→无 sealed 单元、重跑 preflight；
H_snapshot 后 H_bind 前崩溃→检测 unbound snapshot、写 escalation、要求用
确切 commit 做确定性 bind 恢复、**决不第二次 code commit**；H_bind 后
崩溃→由 validator/receipt 判定可否进入 review。

### 5.3 `scripts/validate-stage.py` 修改

- `compute_diff_fingerprint` 改为从 `harness_stage_lib` import 并委托
  （单一实现路径）；函数签名与行为不变。
- 新增 auto 模式校验（仅当 status 含 `auto_review_pipeline` 且
  `enabled` 真值链触发；缺失/false = 现行行为逐字节不变）：
  schema_version/runner_version 已知；`dispatch_mode` ∈ 二值；
  `runner_state` ∈ 五枚举或 null（disabled 表示法：enabled=false +
  human_dispatch + null）；未知 substate/transition fail-closed；
  authorization_path 存在且手写校验通过；budgets 数字与冻结值一致、
  `auto_code_changes_used` ≤ 2 ≤ `max_stage_rework`=3 单账本不变式；
  `mode_history` 每项 from/to/event 均在 workflow 八行转移集内；
  review_units 形状（kind ∈ task/tip/integration、author_provider_identities
  非空、required 单元完整性谓词）；receipt/escalation 引用路径存在；
  `parallel_mode.enabled` 与 auto enabled 互斥；本 stage
  `enabled_for_this_stage=false` 保持可通过。
- 现行 manual 校验路径**零行为变化**：所有现有函数/检查/错误消息保持；
  改动集中在新增函数 + fingerprint 委托。

### 5.4 测试（stdlib-only：unittest/tempfile/subprocess/json/os）

`test_harness_stage_lib.py`：
- fingerprint 回归**双锚点**：①本 stage T1 sealed 值——base
  `a385c7ad77da1611c6e952b2219aee56b49f442f`、head
  `25383e86d0b10b3e8bd3e0f51254588826c9601b`、期望
  `25383e86d0b10b3e8bd3e0f51254588826c9601b:242cff3040ac66e79ce2dbb5a13dab6bf92043765884ed9f0288cf8decc80486`
  逐字相等；②另选一个 status.json 含完整 base/head/fingerprint 的历史
  accepted stage 重算相等（报告注明选了哪个；若不存在则记录事实并保留
  锚点①）。
- 共享 helper：`make_temp_repo()` 隔离环境（`GIT_CONFIG_NOSYSTEM=1`、
  `HOME` 重定向、显式 `-c user.name/user.email`、无网络）。
- 授权/receipt 手写校验的正负 fixture 全套（对齐 T1 schema 的约束面：
  正例通过、每个违反面单独报错——含 expires_at 缺失/非法时间戳/null、
  绝对/遍历/换行路径、空 task_ids、rework≠3、三对 review_1 配对的正三例
  与错配负例、`bookkeeper_decision` 拒绝、call_budget 差值错误）。
- 路径安全、patch 字节等价、atomic 写、provider 归一化。

`test_stage_seal.py`（在临时 git 仓上集成测试）：
- 九步顺序执行的 happy path（两商 H_snapshot/H_bind + 指纹落 status）；
- 第 3 步缺失/失败封 seal；evidence-目录写入不改变 blocking 结果；
- bind mismatch fail-closed 且 status 无新 hash 字段；
- 三个崩溃分支各自的检测与恢复/escalation 行为；
- seal receipt 形状（自定义断言，非 runner-receipt schema）。

`test_validate_stage_auto_review.py`：
- **manual 回归矩阵**：无 auto 字段的代表性 status fixtures 在
  checkpoint/dispatch-ready/pre-review/pre-accept 四 phase 行为与现行一致
  （含本 stage 当前真实 status 快照作为 fixture 之一）；
- auto 正例通过、每个 fail-closed 面单独报错（未知 substate、未知
  transition、预算超限、mutex 冲突、缺 authorization、review_units 不完整）；
- validator 逻辑通过 `harness_stage_lib` 导入测试，或对
  `validate-stage.py` 用 `importlib.util.spec_from_file_location` 动态
  加载——不新建文件。

## 6. Required Checks And Raw Evidence

运行并把每条命令、完整原始 stdout/stderr、exit status append 到
`60-test-output.txt`：

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
grep -rn "formal-1" scripts   # expect no matches / exit 1
```

（完整四命令冻结套件的 `py_compile` 含 `auto-review-runner.py` 的形式在
T3 执行；`git diff --check <T2-base>..<T2-head>` 由 bookkeeper 在 delivery
commit 后运行——你不得为生成 head 而 commit，只跑上面的 worktree 等价
检查。）

测试必须全绿才可声明完成；任何失败如实记录并停止。不得运行 live model/
network/产品测试；不得在 evidence 记录凭据、token、expanded alias 或完整
环境。

## 7. Completion Report And Return

完成后只更新 §3 的两个 evidence 文件，然后停止并返回 bookkeeper。在
`20-implementation.md` 末尾 append `T2 Implementation` 一节，必须包含：

- 当前 branch 与开始时读取的 T2 `base_sha`；
- 修改/新建文件列表，确认全部在 allowlist；
- §5.1–5.4 逐项完成状态；
- `validate-stage.py` 的**逐 hunk 修改说明**（现役门文件——每处 diff 的
  动机与"manual 行为不变"论证）；
- fingerprint 回归双锚点的实际结果；
- 全部检查命令、原始结果、exit status；
- `git status --short`；
- blockers、未解决风险、给 review-1 的建议关注点。

不要 commit，不要写 status/handoff/review 文件，不要 dispatch 任何模型。
页脚使用本地 `date`：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 边界检查 → 独立复跑 T2 套件 → T2 delivery commit + 指纹 → pre-review → 准备 T2 Kimi review-1 packet
```
