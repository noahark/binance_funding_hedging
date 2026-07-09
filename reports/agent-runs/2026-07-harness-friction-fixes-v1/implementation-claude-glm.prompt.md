<!-- ===== DISPATCH RECEIPT（执行者填写；bookkeeper 稍后补证据） =====
status:        pending
target_model:  claude_glm / glm-5.2
adapter_cmd:   claude-glm --model glm-5.2 -p "$(cat reports/agent-runs/2026-07-harness-friction-fixes-v1/implementation-claude-glm.prompt.md)"
started_at:    n/a
completed_at:  n/a
session_id:    n/a
outputs:       reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md; reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt
next_dispatch: none
===== END RECEIPT ===== -->

<!-- ===== PROMPT BODY（immutable，设计期定稿后不得修改） ===== -->
你是 Claude-GLM，负责实现 Harness stage
`2026-07-harness-friction-fixes-v1`。

请以中文为主撰写报告。必要英文术语首次出现时附中文解释；但命令、路径、JSON key、schema field、代码标识、model name、provider identity 必须保留英文原文。

先阅读：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml`
- `docs/independent-task-branch-mode.md`
- `docs/model-adapters.md`
- `reports/agent-runs/README.md`
- `scripts/validate-stage.py`
- `scripts/record-checkpoint`
- `scripts/_itbm.py`
- `reports/agent-runs/_template/status.json`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/00-task.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/10-design.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/11-adr.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/12-development-breakdown.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/status.json`

任务：

按 `12-development-breakdown.md` 实现 F1-F9。该 breakdown（开发拆解）是本次实现边界的权威文件。

必须覆盖：

1. F1: 未选定的 `review_2.primary_provider` 只是 preference（偏好），不能触发 designer-overlap（设计者重叠）检查；但已选定 reviewer（审阅者）仍必须执行 hard ban（硬禁止）和 disclosure override（披露覆盖）规则。
2. F2: single-owner（单所有者）dispatch/checkpoint（派发/检查点）必须保证 validator evidence（验证器证据）进入 reviewed range（被审范围），或在证据提交后重算 `head_sha` / `diff_fingerprint`。
3. F3: `record-checkpoint --single-owner` 写入或准备 top-level（顶层）`status.json` review metadata（审阅元数据），并提供兼容的 `--dry-run`。
4. F4: 为 `validate-stage.py` 增加 `--evidence-out <path>` 或等价实现，避免 `tee` 仓库内文件导致 clean-worktree（干净工作树）检查自冲突。
5. F5: 文档化 delivery-anchored `head_sha`（交付锚定的 `head_sha`）和 validator fixed-point property（验证器日志自指不动点性质）。
6. F6: 支持记录实际 Claude fallback model（回退模型），不改变 provider identity（提供方身份）规则。
7. F7: 文档化 review output hygiene（审阅输出卫生），尤其是 Kimi 输出噪声处理。
8. F8: 修正 `fix_start_prompt.next_action`，review-1 REWORK 后下一步必须是 fix 后 redispatch review-1（重新派发 review-1），不是直接 review-2。
9. F9: 增加 reporting language preference（报告语言偏好）支持：中文为主，保留精确英文机器字符串，并解释必要英文术语。

允许修改的文件：

```text
scripts/validate-stage.py
scripts/record-checkpoint
scripts/_itbm.py
scripts/tests/itbm_dry_run.py
scripts/tests/test_validate_stage.py
reports/agent-runs/_template/status.json
workflows/templates/stage-delivery.yaml
docs/independent-task-branch-mode.md
docs/model-adapters.md
reports/agent-runs/README.md
agents/skills/stage_operator.md             # 仅当已存在时修改；不要新建
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
prototypes/**
.env
.env.example
```

执行要求：

- 不要 commit、push、merge、rebase。
- 不要修改 `status.json` 或 `70-handoff.md`；这些由 bookkeeper 更新。
- 不要改产品代码。
- 不要新增 fingerprint protocol（指纹协议）。
- 如果发现必须超出允许文件，停止并在 `20-implementation.md` 记录 blocker（阻塞项）。
- 如果某个 friction point（摩擦点）不适合代码修复，必须用文档或模板修正解释取舍，并在 `20-implementation.md` 记录。

必须运行并把原始输出写入：

```text
reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt
```

命令：

```bash
python3 scripts/tests/itbm_dry_run.py
python3 -m py_compile scripts/validate-stage.py scripts/_itbm.py
python3 scripts/tests/test_validate_stage.py
python3 scripts/validate-stage.py 2026-07-harness-friction-fixes-v1 --phase checkpoint
```

如果新增测试文件名或命令需要调整，必须在 `20-implementation.md` 说明原因。

完成后更新：

- `reports/agent-runs/2026-07-harness-friction-fixes-v1/20-implementation.md`
- `reports/agent-runs/2026-07-harness-friction-fixes-v1/60-test-output.txt`

最终报告必须包含：

- 修改文件列表。
- 每个 F1-F9 的完成状态。
- 测试命令和结果。
- 未解决风险或后续建议。
- 当前 `git status --short`。

结尾使用本地 `date` 命令生成页脚：

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST>
下一步模型: codex_gpt5
下一步任务: bookkeeper inspect implementation, commit delivery, run pre-review validation, and prepare Kimi review-1
```
