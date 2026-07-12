<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  kimi / kimi-code/kimi-for-coding (moonshot_kimi)
adapter_cmd:   kimi --model kimi-code/kimi-for-coding -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-fix-round1-review1-kimi.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.kimi.noninteractive_command; docs/model-adapters.md#Kimi
read_only_enforcement: prompt_and_wrapper
executor:      human
review_range:  4c668bb8748c09e7014eac2fbb7a34d3a7c247d5..846bec036d62a3cdb243325f16977bd2c1396ade
round:         1 (review-1 of the review-2 fix unit; code changed -> mandatory re-review-1 before returning to review-2)
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       raw stdout captured by operator -> bookkeeper lands 30-review-1-review2-fix-round1.md + verbatim verdict JSON
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable；packet checkpoint 后不得修改） ===== -->

# Review-2 Fix Round 1 的 Review-1 — 六项 P1 修复验证（fresh read-only Kimi, first_reviewer）

你是 Harness stage `2026-07-auto-review-pipeline-v1` **review-2 修复单元**
的 review-1 评审者（fresh read-only 会话，不得沿用任何先前会话记忆）。
背景：review-2 终审（gpt-5.6-sol）判 BLOCKED，坐实六项代码级 P1
（F2–F7，均带行号与 temp-repo 反例）；Claude-GLM 已按 fix packet 完成
修复（commit `846bec0`，26 个新负测试）。代码已变更，故按 workflow
必须先过 review-1 才能重回 review-2。你的职责：独立验证 F2–F7 逐项
关闭、负测试真实有效、无回归。

**只读纪律（硬规则）：不得创建/修改/删除任何仓库文件；可运行只读命令与
`python3 -m unittest`（unittest 使用自建临时目录，不触仓库）；不得
dispatch 任何模型。**

## 1. Review Subject（committed range）

- Range: `4c668bb8748c09e7014eac2fbb7a34d3a7c247d5..846bec036d62a3cdb243325f16977bd2c1396ade`
- fix 单元 diff_fingerprint（必须原样写入 verdict）:
  `846bec036d62a3cdb243325f16977bd2c1396ade:af3daf4d695f172c8c4d38fddbc6a6c491cfa62369b76a14402ace7615865b0b`
- 代码增量（评审主体）: `git diff 4c668bb..846bec0 -- scripts/`——恰 4
  路径：`scripts/auto-review-runner.py`、`scripts/stage-seal.py`、
  `scripts/tests/test_auto_review_runner.py`、`scripts/tests/test_stage_seal.py`。

**范围角色说明**：区间 4 个 commit 中前 3 个（`909c504`/`bce5152`/
`19eb0bd`）是 bookkeeper 机械落档（panel 评审落档、fix packet 绑定、
handoff/证据同步），全部在 `reports/` 下；实现者产出仅 `846bec0`
（fix 交付 + 2 个证据 append）。status/handoff/review 文件变更均为
bookkeeper 状态记录，不是本轮评审对象。

## 2. Read First

1. `reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-gpt-5.6-sol.md`
   §Findings（F2–F7 原文——修复的验收基准，逐条行号+反例）
2. `reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-fix-round1-claude-glm.prompt.md`
   （fix packet：每项修复的硬性要求与负测试规格）
3. `reports/agent-runs/2026-07-auto-review-pipeline-v1/51-review-2-panel-disposition.md`
   （bookkeeper 复现记录）
4. `reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md`
   「Review-2 Fix Round 1」段（finding→测试映射表 + 风险披露）
5. `agents/registry.yaml`（F3 生产命令形状的对照真源）与
   `schemas/review-verdict.schema.json`（F4 的对照基准）
6. `reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt`
   末两段（GLM 必检原始输出 + bookkeeper 复验证据）

## 3. Review Focus

逐项验证 finding 关闭（sol §Findings 是验收基准，fix packet 是规格）：

1. **F2 authorization 实绑定**：preflight 是否要求 authorization 与
   approval receipt 均 committed（`git cat-file -e`）且无 dirty 覆盖；
   `_verify_authorization_binding` 是否对 task_ids/topology/
   allowed/forbidden pathspecs 逐项精确比对、超出即 fail-closed；运行时
   上限是否改从 authorization 数值取（`_auth_or_status_budget`），status
   仅累计。sol 反例（T1-only 1-call 授权 vs 含 T2 与 99 calls 的 status）
   是否有对应负测试且真实覆盖。
2. **F3 生产 registry 兼容**：`<prompt-file>`/`<repo>` 替换与引号反转义
   （`_unescape_yaml_scalar`）；**测试是否直接加载真实
   `agents/registry.yaml`**（`ProductionRegistryCommandTests`）断言实际
   命令模板替换后无字面占位符——不得再是合成 `@PROMPT@` 模板。
3. **F4 verdict schema 对齐 + 字节保真**：未知顶层字段拒收、
   `required_fixes`/`residual_risks` 项类型校验、finding 约束是否与
   schema 全约束面对齐；`_store_verdict` 是否写**被接受的原始字节 span**
   （`raw_text[span[0]:span[1]]`）而非 `json.dumps` 重序列化；缺 span 是否
   fail-closed。
4. **F5 单账本 + expires_at**：`_charge_auto_change` 是否同步递增顶层
   `rework_count` 并断言 ≤ max，否则 escalation；`expires_at` 是否在每次
   model call 与每次 verdict-record commit 前重查（验收 28），不只
   preflight。
5. **F6 exclusive lock + 崩溃窗**：runner 锁（fcntl flock，git 元数据目录，
   占用 → preflight fail-closed，退出释放）；stage-seal 的 pending-snapshot
   marker 是否在 create_snapshot **之前**落盘、H_bind 后清除；崩溃测试
   `test_snapshot_crash_window_recovers_without_second_code_commit` 是否
   **在真实执行流注入崩溃**（monkeypatch write_unit_and_receipt 在
   snapshot commit 后抛异常），而非手工预放 marker；恢复是否只 +1 个
   H_bind、H_snapshot 计数保持 1、绝无第二次 code commit；两处恢复分支
   的 bind_status 是否改为 `verify_bind` 重算。
6. **F7 restart 幂等 + 错误停机**：`completed_review_1` 重启 no-op；
   `running` 重启 resume（不重授权、不重置 wall-clock）且跳过已 ACCEPT
   单元；implementation/fix adapter 非零退出或超时 → 记 receipt 后
   `TerminalEscalation`，绝不带失败结果继续 blocking/seal。
7. **既有测试调整裁决（GLM 风险①，需你显式表态）**：
   `AccountingTimingTests.test_call_charged_before_adapter_start_even_on_timeout`
   因 F7 语义变化被调整为「implementation/cross-check 成功、仅 review
   超时」。请裁决该调整是否保留了原测试意图（超时也计费 + cap 3 耗尽）
   且与 F7 停机语义一致——这是唯一一处对既有测试的修改。
8. **无回归**：`python3 -m unittest discover -s scripts/tests -p
   'test_*.py'` 全绿（应为 136）；`git diff 4c668bb..846bec0 --stat` 恰
   4 代码路径 + 2 证据 append；`harness_stage_lib.py`/`validate-stage.py`/
   T1 契约/manifest 未被触碰；fingerprint 单一实现、seen-diff bind、
   post-cross-check blocking rerun、三对 review-1 路由不变；stdlib-only
   （无 yaml/jsonschema import）。

建议（不强制）：负测试有效性可在临时副本上自行做破坏性抽验（如去掉
`<prompt-file>` 替换行 → `ProductionRegistryCommandTests` 应红）——
bookkeeper 已做 F3/F5/F4 三组（红 3/3/1，见 60-test-output.txt 末段），
你可换角度抽验 F2/F6/F7，但不得修改真实仓库文件。

## 4. Verdict 输出（硬约束）

评审叙述 + footer 后，**最后**一个（且仅一个）符合
`schemas/review-verdict.schema.json` 的顶层 JSON，此后无任何文本：

- `schema_version`: 1；`stage_id`: `"2026-07-auto-review-pipeline-v1"`；
  `role`: `"first_reviewer"`；`model`: `"kimi-code/kimi-for-coding"`
- `diff_fingerprint`: §1 fix 单元指纹，一字不差
- `reviewer_prior_involvement`: `"none"`
- `reviewed_artifacts` / `findings` / `required_fixes`（无则空数组）
- REWORK 须含完整 `fix_start_prompt`；`next_action`: ACCEPT →
  `"human_gate"`；REWORK → `"fix"`

## 5. Stop Conditions

文件缺失、range/指纹与 status 不符、证据被改写、工作树不 clean——记录
并以 `BLOCKED` 返回。完成后停止；后续（重回 review-2）由 bookkeeper 与
人工操作者执行。
