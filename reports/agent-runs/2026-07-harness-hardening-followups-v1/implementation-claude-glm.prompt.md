<!-- ===== DISPATCH RECEIPT（执行者填写；bookkeeper 稍后补证据） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-harness-hardening-followups-v1/implementation-claude-glm.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md; reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
你是 Claude-GLM，负责实现 Harness stage
`2026-07-harness-hardening-followups-v1`。

请以中文为主撰写报告。必要英文术语首次出现时附中文解释；但命令、路径、JSON key、schema field、代码标识、model name、provider identity 必须保留英文原文。

先阅读：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `scripts/validate-stage.py`
- `scripts/record-checkpoint`
- `scripts/_itbm.py`
- `scripts/tests/itbm_dry_run.py`
- `scripts/tests/test_validate_stage.py`
- `reports/agent-runs/_template/status.json`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/50-review-2.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/70-handoff.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/status.json`

任务：

只实现 `00-task.md` 中的 5 项 acceptance criteria（验收标准）：

1. `scripts/validate-stage.py` 的 `--evidence-out` 写入必须捕获 `OSError`，输出清晰 Harness 错误，不暴露未处理 traceback（回溯）。
2. `scripts/record-checkpoint` 必须在 `--dry-run` 缺少 `--single-owner` 时失败，避免用户误以为 double-owner（双所有者）路径不会 mutate（变更仓库）。
3. `scripts/validate-stage.py` 的 `compute_diff_fingerprint` 必须显式使用 `-c diff.renames=true`，与 `scripts/_itbm.py` 的 canonical fingerprint（规范指纹）一致。
4. `reports/agent-runs/_template/status.json` 必须支持 `review_1.actual_model`，便于记录 review-1（第一轮审查）的实际执行模型。
5. `workflows/templates/stage-delivery.yaml` 必须编码 fix（修复）完成后回到原始 review gate（审查门禁）的路由：review-1 REWORK 后回 review-1；review-2 REWORK 后回 review-2。

允许修改的文件：

```text
scripts/validate-stage.py
scripts/record-checkpoint
scripts/tests/itbm_dry_run.py
scripts/tests/test_validate_stage.py
reports/agent-runs/_template/status.json
workflows/templates/stage-delivery.yaml
reports/agent-runs/README.md
reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md
reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt
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
prototypes/**
.env
.env.example
reports/agent-runs/2026-07-harness-friction-fixes-v1/**
```

执行要求：

- 不要 commit、push、merge、rebase。
- 不要修改 `status.json` 或 `70-handoff.md`；这些由 bookkeeper 更新。
- 不要改产品代码。
- 不要新增 fingerprint protocol（指纹协议）。
- 如果发现必须超出允许文件，停止并在 `20-implementation.md` 记录 blocker（阻塞项）。
- 如果某个 finding（发现项）只适合文档化而非代码修复，必须说明原因并保证 workflow/template 中有可审查的约束。

必须运行并把原始输出写入：

```text
reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt
```

最低命令：

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-hardening-followups-v1 --phase checkpoint
git diff --check
```

测试要求：

- 为 `--dry-run` 缺少 `--single-owner` 增加行为测试。
- 为 `--evidence-out` 写入失败增加行为测试，或记录无法稳定模拟的理由并提供静态/替代验证。
- 为 `diff.renames=true` pinning（固定配置）增加测试或静态断言。
- 为 `review_1.actual_model` 模板字段增加测试或静态断言。
- 为 fix return gate（修复回归审查门禁）增加测试或静态断言。

完成后更新：

- `reports/agent-runs/2026-07-harness-hardening-followups-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-hardening-followups-v1/60-test-output.txt`

最终报告必须包含：

- 修改文件列表。
- 5 项 acceptance criteria 的完成状态。
- 测试命令和结果。
- 未解决风险或后续建议。
- 当前 `git status --short`。

结尾使用本地 `date` 命令生成页脚：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: codex_gpt5
下一步任务: bookkeeper inspect implementation, commit delivery, run pre-review validation, and prepare Kimi review-1
```
