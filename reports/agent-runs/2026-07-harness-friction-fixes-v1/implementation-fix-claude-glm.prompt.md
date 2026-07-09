<!-- ===== DISPATCH RECEIPT（执行者填写；bookkeeper 稍后补证据） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-harness-friction-fixes-v1/implementation-fix-claude-glm.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md; reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，返修派发后不得修改） ===== -->
你是 Claude-GLM，继续修复 Harness stage
`2026-07-harness-friction-fixes-v1`。

请以中文为主撰写报告。必要英文术语首次出现时附中文解释；但命令、路径、JSON key、schema field、代码标识、model name、provider identity 必须保留英文原文。

先阅读：

- `AGENTS.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/21-bookkeeper-inspection.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json`
- `scripts/record-checkpoint`
- `scripts/tests/itbm_dry_run.py`
- `docs/independent-task-branch-mode.md`
- `workflows/templates/stage-delivery.yaml`
- `reports/agent-runs/README.md`

返修任务：

修复 P1：`record-checkpoint --single-owner --dry-run` 目前仍会调用 `git add -A`
并可能创建 pending content commit（待提交内容提交），这违反
`12-development-breakdown.md` 中 "`--dry-run` 模式只打印不修改文件" 的验收条件。

必须完成：

1. `--dry-run` 必须在任何 repository mutation（仓库状态修改）之前处理：
   - 不执行 `git add`；
   - 不执行 `git commit`；
   - 不写 `status.json`；
   - 不改变 `HEAD`；
   - 不改变 index（暂存区）；
   - 不改变 worktree（工作树）。
2. 更新相关文档，删除或修正 "dry-run keeps the older behavior (commit pending + print fingerprint)" 这类表述。
3. 加强 `scripts/tests/itbm_dry_run.py`：
   - dry-run 前记录 `git rev-parse HEAD`；
   - dry-run 前记录 `git status --short`；
   - dry-run 后断言 `HEAD` 不变；
   - dry-run 后断言 `git status --short` 不变；
   - 继续断言 `status.json` metadata 没有写入。
4. 更新 `20-implementation.md` 和 `60-test-output.txt`，说明这是 F3 dry-run 语义返修。

允许修改：

```text
scripts/record-checkpoint
scripts/tests/itbm_dry_run.py
docs/independent-task-branch-mode.md
workflows/templates/stage-delivery.yaml
reports/agent-runs/README.md
reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md
reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt
```

禁止修改：

```text
backend/**
frontend/**
docs/product/**
docs/architecture/**
reports/api-samples/**
AGENTS.md
agents/registry.yaml
schemas/**
reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json
reports/agent-runs/2026-07-harness-friction-fixes-v1/70-handoff.md
```

必须运行并把原始输出写入 `60-test-output.txt`：

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-friction-fixes-v1 --phase checkpoint
```

不要 commit、push、merge、rebase。完成后报告：

- 修复摘要；
- 更新后的 dry-run 语义；
- 新增/加强的测试断言；
- 测试结果；
- 当前 `git status --short`。

结尾使用本地 `date` 命令生成页脚：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: codex_gpt5
下一步任务: bookkeeper re-inspect implementation and prepare delivery commit if clean
```
