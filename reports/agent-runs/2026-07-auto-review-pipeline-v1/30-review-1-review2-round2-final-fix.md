# Re-review-1 报告：review-2 round-2 FINAL fix FX1–FX7

## 总体印象

本次 fix 单元（`846bec0..a057d06`）针对 gpt-5.6-sol round-2 REWORK 的 5×P1 + 2×P2 code findings 做了七组控制面修复。我独立复算了单元指纹、通读了改动函数全文、重跑了全套件与 FX 独立测试类，并对 FX1 的 `shlex.quote` 生产上下文做了手工探针。结论：**FX1–FX7 全部 closed，无新增 P0/P1/P2 required finding，同意 ACCEPT**。

## 1. FX1–FX7 逐项关闭

| FX | 锚点实现 | 测试覆盖 | 红→绿证据 | Disposition |
|----|----------|----------|-----------|-------------|
| FX1 | `auto-review-runner.py:_default_invoke` 对 `<prompt-file>`/`<repo>`/`@PROMPT@`/`@REPO@` 均先 `shlex.quote()` 再替换；`shell=True` 与 receipt 只记 `command_ref` 不变 | `ShellSafeInvocationTests`（4）：真实 registry 字符串级 + 真实执行探针（空格目录） | 去 quote 后两执行探针 exit 1；还原后 exit 0 | **closed** |
| FX2 | `stage-seal.py:seal(..., commit_guard=...)`；4 个 commit 点（fresh H_snapshot/H_bind、marker 恢复 H_bind、unbound 恢复 H_bind）紧前调 guard；runner `_node_seal` 传 `_check_authorization_expiry` | `CommitGuardTests`（seal 2）+ `SealCommitGuardWiringTests`（runner 2） | 移除 fresh H_bind 前 guard → 测试红；还原后绿 | **closed** |
| FX3 | marker 恢复三分支穷尽；孤儿 marker 经 `_bind_evidence_complete` 验证后清 marker 抛 already-sealed | `SealMarkerHardeningTests`（2） | `_head_is_expected_snapshot_child` 改接受任意 HEAD → 介入提交测试红；还原后绿 | **closed** |
| FX4 | `run()` 锁失败分支零写，返回 `lock_busy`（仅返回值/stderr） | `RunnerLockTests.test_concurrent_runner_lock_is_exclusive` | 恢复 `_handle_preflight_failure` → 全目录 sha256 漂移；还原后字节一致 | **closed** |
| FX5 | 案 A（fail-closed）：resume 时非 ACCEPT 且存在 implementation/cross-check/fix receipt 即 fail-closed 到 awaiting_human | `ResumeIdempotencyTests`（6：五边界 + 干净单元） | 禁用 started-receipt 检测 → 5 边界测试红；还原后绿 | **closed** |
| FX6 | task_ids 双向集合相等；topology/allowed/forbidden 精确；ledger caps（max_stage_rework/max_auto_code_changes）等值绑定 | `AuthorizationExactBindTests`（7） | 禁用双向/ledger bind → 对应测试红；还原后绿 | **closed** |
| FX7 | `_charge_auto_change` 先算 proposed 值，超 cap 时两计数器均不写 | `ReworkLedgerAndExpiryTests`（3 相关） | 禁用前置预检 → escalation 测试红；还原后绿 | **closed** |

## 2. 禁令遵守

- **G1 真实对象测试**：FX1 使用真实 `agents/registry.yaml` 与真实 `shell=True` 执行探针；FX3/FX4/FX5 使用真实执行流注入（monkeypatch/flock/temp repo），未用合成 fixture 替代。
- **G2 既有测试改动**：仅 FX7 指名的一个断言修正（escalation 后计数器保持原值）+ FX4 lock 测试契约被 packet 要求替换（GLM 已 append blocker）。其余 136 项既有测试未改期望值。
- **G3 每个 hunk 可指认 FX**：通读 `scripts/auto-review-runner.py` 与 `scripts/stage-seal.py`，所有改动均标注 FX 编号或在 20-implementation.md 中映射。
- **G4 红→绿证据**：GLM 报告与 60-test-output.txt 均记录逐项破坏性验证；我独立重跑亦全绿。
- **G5 frozen 面未触碰**：fingerprint 公式、AUTO_TRANSITIONS、review-1 路由、seen-diff bind、post-cross-check blocking rerun、pilot 谓词、`git add -A` 禁令均未改动。

## 3. 阻塞点裁定复核

GLM 提出的 3 个 append 阻塞点，bookkeeper 已逐项裁定 ACCEPT，我同意：

1. **FX4 既有测试契约替换**：旧断言 codified 的是缺陷行为（锁 loser 写 status），packet FX4 要求零写，替换为必需。
2. **FX6 runtime caps 不绑定**：既有 frozen 契约 `test_runtime_caps_come_from_authorization_not_status` 主张 runtime caps 权威在 auth；绑定会破坏该契约，且 G2 禁止改既有测试。ledger caps 已绑定。
3. **FX6 max_stage_rework schema-frozen**：schema `const 3` 使 auth 携带非 3 值在 preflight 早期即被 `authorization_invalid` 拒绝，runtime `budget_mismatch` 分支不可达。

## 4. Residual 复核

- **R1（seed receipt call_budget 方向）**：同意 bookkeeper 的非 required 定性。`_unit_has_started_receipts` 只消费 `node` + `review_unit_id`，且 bookkeeper 的 cross-probe 证明生产 receipt 可被识别，无行为影响。
- **R2（FX1 字符串级枚举 5/6）**：同意非 required。GLM 的字符串级测试覆盖了 5 个 runner-reachable 占位符命令，缺 `claude_glm.embedded_read_only_review_command`（形状与已覆盖命令相同）；bookkeeper 独立探针已覆盖 6/6，且生产执行探针通过。

## 5. 回归验证

我独立执行：

```text
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
Ran 161 tests in 18.579s — OK

python3 -m unittest scripts.tests.test_auto_review_runner.ShellSafeInvocationTests \
  scripts.tests.test_auto_review_runner.SealCommitGuardWiringTests \
  scripts.tests.test_stage_seal.CommitGuardTests \
  scripts.tests.test_stage_seal.SealMarkerHardeningTests \
  scripts.tests.test_auto_review_runner.RunnerLockTests \
  scripts.tests.test_auto_review_runner.ResumeIdempotencyTests \
  scripts.tests.test_auto_review_runner.AuthorizationExactBindTests \
  scripts.tests.test_auto_review_runner.ReworkLedgerAndExpiryTests
Ran 30 tests in 5.662s — OK

python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
# exit 0

scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
# STAGE VALIDATION PASSED

git diff --check 846bec0..a057d06
# 在 fix 实现文件（scripts/*.py、20-implementation.md、60-test-output.txt）上干净；
# 其余 trailing whitespace 位于 Grok review 原始落档与证据 diff 中，属 raw model evidence，按 AGENTS.md 不 rewrite。
```

## 范围确认

fix 交付 commit `a057d06` 严格只改 4+2 文件：

```text
scripts/auto-review-runner.py
scripts/stage-seal.py
scripts/tests/test_auto_review_runner.py
scripts/tests/test_stage_seal.py
reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md
reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
```

`846bec0..a057d06` 范围内其余改动为 bookkeeper 机械 commits（status/handoff/review 记录/follow-ups），非 fix 实现漂移。

```text
本地北京时间: 2026-07-12 09:15:59 CST
下一步模型: Claude Fable 5（bookkeeper）
下一步任务: 落档 re-review-1 → 准备 review-2 round 3 packet
```
