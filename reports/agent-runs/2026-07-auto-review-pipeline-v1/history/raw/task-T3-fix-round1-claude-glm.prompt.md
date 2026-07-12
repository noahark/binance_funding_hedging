<!-- ===== DISPATCH RECEIPT（执行者/记账者填写；当前人工 DRAFT-2 packet） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-auto-review-pipeline-v1/task-T3-fix-round1-claude-glm.prompt.md)"
adapter_ref:   agents/registry.yaml#adapters.claude_glm.noninteractive_command; docs/model-adapters.md#Claude-GLM
executor:      human
task:          T3 fix round 1 (review-1 REWORK, finding P2: persistent transition-set assertion)
verdict_source: reports/agent-runs/2026-07-auto-review-pipeline-v1/review-1-T3-round1.verdict.json
rework_charge: 1 of 3 (first formal charge this stage)
note:          PROMPT BODY below is the reviewer's fix_start_prompt VERBATIM (AGENTS: bookkeeper adds routing metadata only, never rewrites reviewer evidence). After the fix returns, T3 must be RE-SEALED (code change invalidates the sealed fingerprint) before Kimi re-review.
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-auto-review-pipeline-v1/20-implementation.md; reports/agent-runs/2026-07-auto-review-pipeline-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（reviewer fix_start_prompt, verbatim; immutable） ===== -->

你是 Harness stage `2026-07-auto-review-pipeline-v1` 任务 T3 的 fix implementer（Claude-GLM / zhipu_glm）。本 fix 只修改 `scripts/tests/test_auto_review_runner.py`，其余文件只读。

## 修复目标

T3 review-1 发现：runner 经 `importlib` 复用了 `validate-stage.AUTO_TRANSITIONS` 作为单一转移真源（`scripts/auto-review-runner.py:91-92`），但未交付 T3 dispatch packet §3.1 要求的“以测试断言其与 workflow 集合一致”的持久化测试。请补一个 stdlib-only 的集合级一致性测试。

## 文件边界

- 可写：`scripts/tests/test_auto_review_runner.py`（仅新增一个测试类/测试方法及必要的 stdlib-only 辅助解析函数）
- 禁止：修改 `scripts/auto-review-runner.py`、`scripts/validate-stage.py`、任何 T1/T2 文件、`harness-manifest.yaml`、status.json、handoff、review/packet 文件

## 要求

1. 在 `scripts/tests/test_auto_review_runner.py` 新增测试类（建议名 `TransitionTruthSourceTests`）及一个测试方法。
2. 测试读取 `workflows/templates/stage-delivery.yaml` 的 `auto_review_pipeline.executable_contract.state_transitions` 区段，逐行解析每个 transition 的：
   - `from.dispatch_mode`
   - `from.runner_state`（`null` 对应五元组中的 `None`）
   - `event`（注意 `one_of:` 列表必须展开为多个五元组）
   - `to.dispatch_mode`
   - `to.runner_state`
3. 将解析结果构建为 13 个五元组集合，并与 `runner.AUTO_TRANSITIONS`（即复用的 validator 集合）做 `assertEqual`。
4. **stdlib-only**：不得引入 `yaml`/`PyYAML` 或任何第三方依赖；可用受限行解析器，仅处理当前 workflow 文件结构。
5. 解析失败或集合不一致时测试必须失败（fail-closed）。
6. 不要在测试中硬编码第二份转移矩阵；测试应从 workflow YAML 动态解析真源。

## 验证命令

```text
python3 -m unittest scripts.tests.test_auto_review_runner.TransitionTruthSourceTests
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
python3 -m py_compile scripts/validate-stage.py scripts/harness_stage_lib.py scripts/stage-seal.py scripts/auto-review-runner.py
scripts/validate-stage.py 2026-07-auto-review-pipeline-v1 --phase checkpoint
git diff --check
```

## 验收判据

- 新增测试在本地通过。
- `python3 -m unittest discover -s scripts/tests -p 'test_*.py'` 仍为全部 OK。
- `git diff --check` 无 whitespace/conflict 错误。
- 不修改任何 allowlist 外文件。
- 不引入新依赖。

本地北京时间: 2026-07-11 19:53:37 CST
下一步模型: Kimi（T3 review-1 re-run）
下一步任务: 复跑本 review-1 packet 验证 fix
