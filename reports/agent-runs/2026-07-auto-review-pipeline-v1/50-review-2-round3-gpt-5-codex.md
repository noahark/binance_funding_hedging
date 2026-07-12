# Review-2 Round 3 — GPT-5 Codex

- Reviewer model: `gpt-5-codex`（本会话真实标识；OpenAI/Codex）
- Role: `final_reviewer`
- Prior involvement: `design`（OpenAI provider 参与本 stage 的 intake/design；未参与实现或 fix）
- Review range: `a385c7ad77da1611c6e952b2219aee56b49f442f..a057d063523664a2fcfa8cc4db9e9af789f15730`
- Diff fingerprint: `a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e`
- Verdict: **REWORK**
- Landing authorization: 操作者本轮明确要求“并落档 review 内容”；依 packet 只读 carve-out，本会话仅新增本报告与配套 verdict JSON，未触碰任何既有文件、状态、handoff 或交付代码。

## 结论

round-2 的 5×P1+3×P2 均已按冻结反例闭合，FX1–FX7 未发现新的修复内缺陷；fingerprint、161 项全套件、30 项 FX 定向套件、Python 编译与 checkpoint validator 均通过。GLM 的 3 个 append 阻塞点、R1/R2 residual 和原样证据 whitespace 的非 required 定性也成立。

但全 stage 终审发现一项独立 **P1 required finding**：wall-clock budget 只在模型调用开始前检查，模型调用结束后、blocking checks 后和 seal commit 前不检查。真实 temp-repo/fake-clock 反例证明，授权的一秒 wall-clock deadline 已经过期后，runner 仍创建 H_snapshot 与 H_bind 两个权威 commit，直到下一次 review 调用前才升级。它违反 `00-task.md` 验收 17、冻结 P8 与 `docs/auto-review-pipeline.md` 的“wall-clock 包含 running 到 stop/completion 全部自动工作”语义。

因此不能 ACCEPT。rework 账本已经 3/3；依 round-3 packet，本 `REWORK` 不再进入自动修复轮，bookkeeper 应落 `human_escalation_required`。本报告附带的 Fix Start Prompt 只供操作者在显式批准新的有界修复处置后使用。

## 独立检查结果

- 标准 fingerprint 复算：精确匹配 packet/status。
- `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`：Ran 161 tests，OK。
- FX 定向八类：Ran 30 tests，OK。
- `python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py`：通过。
- `scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint`：`STAGE VALIDATION PASSED`。
- 禁止产品路径扫描：冻结 range 未修改 `backend/**`、`frontend/**` 或 `schemas/api/**`。
- default-off/mutex：本 stage `auto_review_pipeline.enabled_for_this_stage=false`，`parallel_mode.enabled=false`。
- `git diff --check <base>..<head>`：报告 8 处 trailing whitespace，均位于原样 Grok review 文本或越权写入原始 diff 证据；与 Kimi residual 注记一致。未把命令结果写成“clean”。

## Round-2 findings 关闭复核

1. FX1：四种 placeholder 均经 `shlex.quote`；真实 registry 空格/metacharacter 和两种 shell 上下文探针通过。
2. FX2：expiry guard 已进入 fresh/recovery 的全部四个 seal commit 点；跨 H_snapshot/H_bind 假时钟测试通过。
3. FX3：marker 恢复验证单一父子关系和 exact path set；介入 commit fail-closed，孤儿 marker 只在 bind evidence 完整时清理。
4. FX4：锁 loser 返回 `lock_busy`，stage evidence/status 全目录字节不变。
5. FX5：采用 fail-closed 案 A；implementation/cross-check/seal/review/fix 五个崩溃边界均不重派 implementation/fix。
6. FX6：task IDs 双向相等，topology/pathspec/ledger caps 精确绑定；runtime caps 继续以 authorization 为权威。
7. FX7：两个拟议计数先过 cap，再同步更新；拒绝路径计数保持原值。
8. round-2 P2#3：旧 review-2 routing 已同步，原 `50-review-2-gemini.md` whitespace 已清理；后来落入的 raw review/evidence whitespace 属下述 residual，不重新解释为该旧 finding 未关闭。

## 裁定与 residual

- FX4 旧锁测试必须被新“loser 零写”合同替换：同意 bookkeeper/Kimi 裁定。
- FX6 runtime caps 不与 status 镜像绑定：同意；权威值在 human-approved authorization，绑定可篡改镜像会反向削弱合同。
- FX6 `max_stage_rework` schema 固定为 3：同意；非法值在 schema preflight 已被拒绝。
- R1 seed receipt 的 call-budget 方向与 production 相反，但被测 predicate 只读取 `node` 和 `review_unit_id`，production receipt 交叉探针已通过：非 required。
- R2 FX1 测试内枚举 5/6，但遗漏命令与已覆盖形状相同且 bookkeeper 6/6 探针通过：非 required。
- full-range whitespace 位于必须原样保存的审查/事故证据。它使 `git diff --check` 非零，需如实保留为 P3 residual；不应为美化检查结果改写原始证据。
- packet 问题 5 写“验收 1–29”，而 `00-task.md` 实际只有 1–28；本次按实际 28 项评审。该 packet 计数笔误不改变交付要求。

## Required Finding

### P1 — wall-clock 过期后 runner 仍可创建 seal commits

`scripts/auto-review-runner.py:734-740` 的 `_check_wall_clock()` 只在四类模型调用开始前调用；`_node_seal()` 在 `scripts/auto-review-runner.py:1556-1564` 传给 `stage-seal` 的 commit guard 仅是 `_check_authorization_expiry`。implementation 返回后也没有 wall-clock 检查，blocking phases 同样没有 deadline guard。

独立反例使用 `scripts/tests/test_auto_review_runner.py` 的真实 temp repo builder 和真实 `stage-seal`：authorization 的 `wall_clock_seconds=1`；implementation 调用前时间为 `12:00:00Z`，invoker 返回时推进到 `12:00:02Z`；作者集合使 cross-check unavailable；blocking 返回 0。记录的 deadline 是 `12:00:01Z`，但 `git rev-list --count HEAD` 从 3 增至 5，`snapshot_commit` 与 `diff_fingerprint` 均已写入。runner 最终仅在 review 调用前返回 `human_escalation_required`。

影响是调用/本地检查耗尽授权 wall-clock 后，自动 runner 仍能进行授权外权威 commit；预算虽最终被发现，却没有 fail closed 在副作用之前。这破坏 P8 cost bound 和验收 17 的机械保障。

## Fix Start Prompt

你是该 stage 的有界 fix implementer。只有在人类操作者明确批准从 `human_escalation_required` 开启新的修复处置后才能执行；不得把本 prompt 视为自动续轮授权。权威 finding 是 `reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-round3-gpt-5-codex.md` 的“P1 — wall-clock 过期后 runner 仍可创建 seal commits”，verdict JSON 为 `review-2-round3-gpt-5-codex.verdict.json`。先读 `00-task.md` 验收 17/28、`docs/auto-review-pipeline.md` §Call and wall-clock accounting、round-3 报告及冻结 range。不得 dispatch 模型、联网、commit、改 status/handoff/review 文件；若操作者未另行冻结 writable set，停止并请求 bookkeeper 绑定新 packet。

建议的最小代码边界为 `scripts/auto-review-runner.py` 与 `scripts/tests/test_auto_review_runner.py`；只有证明现有 `commit_guard` 接口不足时才申请 `scripts/stage-seal.py` / `scripts/tests/test_stage_seal.py`。修复必须让 wall-clock deadline 覆盖 `running` 到 stop/completion 的全部自动工作：至少在每个 adapter 返回后、每次 blocking pass 后、每个 seal commit 紧前、verdict-record commit 紧前以及写 completed_review_1 前检查。seal 的 commit guard 应同时检查 authorization expiry 与 wall-clock，不能只检查 expiry。模型调用已经开始后若跨过 deadline，仍须保存原始输出与 receipt/call charge，但在任何后续代码或权威 evidence commit 前升级并停止；不得通过重置 deadline、扩大授权值或吞掉 timeout 绕过。

必须新增真实 temp-repo/fake-clock 负测试：`wall_clock_seconds=1`，implementation 在调用前合法、返回时推进到 deadline 后，cross-check unavailable，真实 seal 模块启用；断言 H_snapshot/H_bind 均未创建、snapshot/fingerprint 未绑定、产生 timeout escalation。另覆盖 blocking runner 跨 deadline 后不 seal、seal 的 H_snapshot/H_bind 两个 commit guard 均检查 wall-clock、review 返回跨 deadline 后不创建 verdict-record commit、resume 不重置 deadline。保留 FX1–FX7、fingerprint、AUTO_TRANSITIONS、seen-diff、post-cross-check rerun、显式 path git add 与 default-off 语义。

验证命令：`python3 -m unittest discover -s scripts/tests -p 'test_*.py'`；新增 wall-clock 测试类单跑；`python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py`；`scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint`；`git diff --check`。成功标准是上述所有 deadline 后副作用反例在 commit 前 fail closed、全套件通过、只改批准文件，并重新走 committed evidence、review-1 与 full-stage review-2；因原 ledger 3/3，所有状态与新轮授权由 human/bookkeeper 决定。

本地北京时间: 2026-07-12 09:44:47 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 落档 round-3 REWORK 并机械校验 JSON/fingerprint；按终格规则推进 human_escalation_required，等待操作者决定是否授权新的有界修复处置

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-auto-review-pipeline-v1",
  "role": "final_reviewer",
  "model": "gpt-5-codex",
  "verdict": "REWORK",
  "diff_fingerprint": "a057d063523664a2fcfa8cc4db9e9af789f15730:cd68035686acc794aac3065270530ec6d4846da18c25274458f478fd85b84e7e",
  "reviewer_prior_involvement": "design",
  "reviewer_prior_involvement_notes": "OpenAI/Codex provider participated in the stage intake/design chain. This review independently recomputed the frozen fingerprint, reran tests and executable counterexamples, and did not rely on prior design conclusions. The reviewer has no implementation or fix authorship. The operator explicitly authorized landing only this report and its verdict JSON.",
  "reviewed_artifacts": [
    "agents/skills/reality-checker.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/00-task.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/10-design.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/11-adr.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-round2-gpt-5.6-sol.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/review-2-round2-gpt-5.6-sol.verdict.json",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/task-review2-round2-fix-final-claude-glm.prompt.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/30-review-1-review2-round2-final-fix.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/review-1-review2-round2-final-fix.verdict.json",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/52-review-2-round2-panel-disposition.md",
    "reports/agent-runs/2026-07-auto-review-pipeline-v1/status.json",
    "AGENTS.md",
    "workflows/templates/stage-delivery.yaml",
    "agents/registry.yaml",
    "docs/auto-review-pipeline.md",
    "schemas/auto-review-authorization.schema.json",
    "schemas/runner-receipt.schema.json",
    "scripts/auto-review-runner.py",
    "scripts/stage-seal.py",
    "scripts/validate-stage.py",
    "scripts/harness_stage_lib.py",
    "scripts/tests/",
    "git diff a385c7ad77da1611c6e952b2219aee56b49f442f..a057d063523664a2fcfa8cc4db9e9af789f15730"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "Wall-clock expiry is detected only before model calls, allowing seal commits after the authorized deadline",
      "file": "scripts/auto-review-runner.py",
      "line": 734,
      "evidence": "_check_wall_clock is called only before implementation, cross-check, review, and fix adapter starts. _node_seal passes only _check_authorization_expiry as stage-seal's per-commit guard. In an isolated real-git probe with wall_clock_seconds=1, implementation advanced the fake clock from 12:00:00Z to 12:00:02Z, beyond the recorded 12:00:01Z deadline; the runner nevertheless created two commits (rev-list count 3 to 5) and bound snapshot_commit/diff_fingerprint before the next review-call check escalated.",
      "impact": "The deterministic runner can create authoritative H_snapshot and H_bind commits after the human-approved session budget has expired, so the wall-clock cost bound does not fail closed before side effects as required by frozen P8 and acceptance criterion 17.",
      "recommendation": "Use a combined active-session guard for wall-clock and authorization expiry before every seal/verdict commit, check wall-clock after adapter and blocking work and before completion, preserve receipts for calls that crossed the deadline, and add real temp-repo fake-clock tests proving no commit occurs after expiry."
    }
  ],
  "required_fixes": [
    "Enforce the authorized wall-clock deadline across all automatic work and before every authoritative commit, with deterministic counterexample tests proving H_snapshot, H_bind, and verdict-record commits cannot occur after the deadline."
  ],
  "residual_risks": [
    "Full-range git diff --check reports eight trailing-whitespace locations, all in verbatim Grok review artifacts or the raw unauthorized-write evidence diff. This is accurately disclosed and retained as non-required raw evidence rather than rewritten.",
    "R1 seed-receipt call_budget direction and R2 5/6 in-test registry enumeration remain non-required because the predicate ignores budget direction and an independent production-shaped probe covers all six commands.",
    "The round-3 packet says acceptance items 1-29, while 00-task.md contains 1-28; the review used the actual 28-item authoritative list."
  ],
  "fix_start_prompt": "You are the bounded fix implementer for stage 2026-07-auto-review-pipeline-v1 only after explicit human authorization to open a new repair disposition from human_escalation_required; this prompt is not automatic continuation authority. Read reports/agent-runs/2026-07-auto-review-pipeline-v1/50-review-2-round3-gpt-5-codex.md, its verdict JSON, 00-task.md acceptance 17/28, and docs/auto-review-pipeline.md wall-clock accounting. Required finding: scripts/auto-review-runner.py checks wall-clock only before model calls and passes only authorization-expiry into stage-seal's commit guard; an isolated real-git probe with wall_clock_seconds=1 advanced time beyond deadline during implementation and still created H_snapshot and H_bind. Under a newly bookkeeper-frozen packet, prefer a writable set of scripts/auto-review-runner.py and scripts/tests/test_auto_review_runner.py; request scripts/stage-seal.py and its tests only if the existing generic commit_guard is insufficient. Enforce wall-clock from running through stop/completion: check after adapter returns, after blocking work, before every seal commit, before verdict-record commit, and before completed_review_1. Preserve raw output, call charge, and receipt when an already-started adapter crosses the deadline, but stop before subsequent authoritative commits. Add real temp-repo/fake-clock negative tests for implementation crossing deadline with cross-check unavailable and real seal (zero H_snapshot/H_bind commits and no fingerprint bind), blocking crossing deadline, both seal commit points, review crossing deadline with no verdict-record commit, and resume not resetting the deadline. Preserve FX1-FX7, fingerprint, AUTO_TRANSITIONS, seen-diff, post-cross-check rerun, explicit git-add paths, default-off, and provider isolation. Run the full unittest suite, targeted new tests, py_compile of the four Harness scripts, validate-stage checkpoint, and git diff --check. Do not dispatch models, commit, edit status/handoff/review artifacts, expand file boundaries, or resume the exhausted 3/3 ledger without explicit human/bookkeeper authorization. Success requires all post-deadline side effects to fail closed, all tests green, exact approved file boundaries, new committed evidence, review-1, and full-stage review-2.",
  "next_action": "human_escalation_required"
}
```
