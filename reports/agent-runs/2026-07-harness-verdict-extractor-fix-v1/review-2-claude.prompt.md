[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Task H — Final Review-2 Reality Check

你是本 Harness 维护阶段的 independent final reviewer，使用
`reality_checker` 角色。默认运行模型是 Anthropic
`claude-fable-5`；只有 human operator 在真实 Anthropic endpoint 上观察到
Fable5 quota/unavailability 后，bookkeeper 另行记录失败证据并路由
`opus4.8`。你不得自行调用备用模型。

Codex/GPT 是 workflow 的默认 review-2 primary，但 Codex 在本阶段编写了
Task H 设计并担任 bookkeeper，因此按 anti-self-review 路由不适格。
Anthropic Claude 未参与本 stage 的方向、设计、breakdown、实现、fix
或 review-1，且与实现/fix 作者 `zhipu_glm` 不同 provider。最终 verdict
必须写 `reviewer_prior_involvement: "none"`。

## 严格只读和安全边界

- 只读/plan 评审。禁止编辑、创建、删除、暂存、提交、推送、合并、
  rebase、部署或切换分支。`50-review-2.md` 由 human operator 捕获，
  你不得写入仓库。
- 禁止读取 `.env*`、key file、cookie、credential store、打印/过滤整体
  environment 或展开 adapter 环境。禁止网络请求。
- 这是 CLI/Harness parser 修复，没有 UI 改动；视觉截图、Playwright 和部署
  证据不适用。必须以固定 diff、parser 语义、schema、测试和 gate 证据为准。
- 不得因 review-1 ACCEPT 而推定通过；必须独立检查原始工件。
- 当前 `HEAD` 包含晚于被审 head 的纯记账/review evidence 提交。代码审查
  范围必须固定为下述 `base_sha..head_sha`，不得用移动 `HEAD`。

## 固定审查身份与指纹

- Stage: `2026-07-harness-verdict-extractor-fix-v1`
- Role: `final_reviewer`
- Base SHA: `4b1fcdd5fb0562eb00467437bf2ec9ad0286581a`
- Reviewed Head SHA: `569be63a6f467e4e5e255a4713f94a08e37cd9b8`
- Diff fingerprint:
  `569be63a6f467e4e5e255a4713f94a08e37cd9b8:397f66903914de11923195e8831f3192f725dc771fd04893a790075c9765b655`
- Implementation/fix provider: `zhipu_glm`
- Review-1 provider: `moonshot_kimi`
- Final-review provider: `anthropic`
- Reviewer prior involvement: `none`
- Raw output destination（human operator verbatim capture）:
  `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md`

## 必读原始工件

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml` 的 test、review-1、fix、review-2、
   terminal state 段
3. `schemas/review-verdict.schema.json`
4. `agents/skills/reality-checker.md`
5. `docs/product/PRD.md`
6. `docs/architecture/ARCHITECTURE.md`
7. `docs/parallel-development-mode.md` 的 R11–R12
8. `reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/status.json`
9. `00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`
10. `20-implementation.md` 与 `20-implementation.bookkeeper-audit.md`
11. `task-H-claude-glm.{prompt,dispatch}.md`
12. `task-H-bookkeeper-fix-1.{prompt,dispatch}.md`
13. `60-test-output.txt` 和 `70-handoff.md`
14. `review-1-kimi.{prompt,dispatch}.md`
15. `30-review-1.md` 与 `30-review-1.bookkeeper-intake.md`
16. `scripts/validate-stage.py`
17. `scripts/tests/test_validate_stage_dispatch_protocol.py`
18. 固定历史回归样本
    `9ee24399ee664bb5e4aec890b72c0a57e1bad52a:reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.md`

`docs/product/PRD.md` 和 architecture 文档是上层权威，用于确认本 Harness
修复未篡改产品或执行边界；Task H 设计本身是被审证据，不是超越
repository authority order 的最高规范。

## 必须独立执行的固定检查

```text
git diff --binary 4b1fcdd5fb0562eb00467437bf2ec9ad0286581a..569be63a6f467e4e5e255a4713f94a08e37cd9b8 -- . ":(exclude)reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/status.json"
git diff --stat 4b1fcdd5fb0562eb00467437bf2ec9ad0286581a..569be63a6f467e4e5e255a4713f94a08e37cd9b8
git diff --check 4b1fcdd5fb0562eb00467437bf2ec9ad0286581a..569be63a6f467e4e5e255a4713f94a08e37cd9b8
git diff 569be63a6f467e4e5e255a4713f94a08e37cd9b8..HEAD -- scripts/ docs/parallel-development-mode.md
python3 -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
python3 -m pytest scripts/tests -q
python3 -m py_compile scripts/validate-stage.py
python3 scripts/test-validate-all-stages-compare.py --repo-root .
python3 scripts/validate-stage.py 2026-07-harness-verdict-extractor-fix-v1 --phase pre-review
```

独立重算完整指纹。后置记账/review evidence 可作为 gate 证据读取，
但不得加入被审 code diff 或改写固定 fingerprint。

## Final Reality-Check 重点

1. 不要只重复 Kimi 结论。独立证明 findings 为 0/1/多项、含嵌套 metadata
   时，返回值始终是完整最外层 verdict，而不是末尾 finding。
2. 核验 dict/list decoded span containment：list 只可用于嵌套判定而绝不能被返回；
   `[verdict]`、`[[verdict]]` 和更深 list wrapper 必须 fail closed。
3. 提取器必须 schema-independent；最后非嵌套 dict 即使 schema-invalid 也必须在
   downstream fail closed，不得 fallback 到更早 ACCEPT。
4. 核验 prose、Markdown fence、footer、Unicode、whitespace、字符串内括号/转义引号、
   malformed trailing brace 与 harmless brackets 的兼容性；检查伪 span/重叠 span
   是否存在未覆盖的 fail-open。
5. 核验 `_parse_review_artifact`、review schema、receipt、Session-ID footer、reviewer identity、
   fingerprint、clean-worktree 和 historical compare gate 没有被弱化。
6. 核对 implementation/fix report 与 committed code、测试名、真实命令输出；
   检查 52/128 tests、11/11 sentinel 和实际 Boundary C five-findings artifact。
7. 审计 review-1 本身：最终 JSON 是否由修复后 extractor 正确提取，指纹、
   provider isolation、fresh-context transcript evidence、unavailable-class footer/receipt 是否一致；
   原始 final text 恢复过程是否保留原文且没有将环境输出带入 artifact。
8. 检查冻结范围：只有 extractor、其 tests、R12 契约和当前 stage evidence；
   无 product code、schema、workflow、registry、AGENTS.md、Boundary C 或 `_proposals/**` 改动。
9. 评估已披露 residual risks：O(n·k) worst-case 、malformed outer container 的规定语义、
   pre-existing unavailable token 分类差异是否只是非阻塞风险，还是存在必须先修的
   gate 正确性问题。

如发现问题，必须给出 severity、文件/行、可复现证据、影响与最小修复建议。
`ACCEPT` 仅表示该 Harness 修复可进入 `stage_accepted_waiting_user`，不授权
合并 `main`、同步 Boundary C、部署或产品验收。证据不可读或不足时返回
`BLOCKED`，不得猜测通过。

## 输出合同

输出简洁但完整的 final-review narrative。若为 `REWORK`，JSON 前必须有与
JSON 完全一致的人类可读 `Fix Start Prompt` 小节。然后输出六行页脚，最后
输出一个且仅一个可解析 JSON object；JSON 后不得再有文本：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | cli_output | transcript_path | active_session_registry | operator | unavailable>
原始输出路径: reports/agent-runs/2026-07-harness-verdict-extractor-fix-v1/50-review-2.md
本地北京时间: <本会话实际 date 命令，YYYY-MM-DD HH:MM:SS CST>
下一步模型: <bookkeeper | human operator → original Claude-GLM>
下一步任务: <specific next task>
```

最终 JSON 必须严格匹配 `schemas/review-verdict.schema.json`，并固定：

- `schema_version: 1`
- `stage_id: "2026-07-harness-verdict-extractor-fix-v1"`
- `role: "final_reviewer"`
- `model`: 使用实际执行模型，默认 `claude-fable-5`；经记录的 fallback 才可写
  `opus4.8`
- `diff_fingerprint`: 本 prompt 的完整固定值
- `reviewer_prior_involvement: "none"`

`reviewed_artifacts` 必须列出实际读取的 raw artifacts 和固定 diff。
若 verdict 为 `ACCEPT`，`next_action` 必须是
`stage_accepted_waiting_user`。若为 `REWORK`，`next_action: "fix"` 且
`fix_start_prompt` 必须是可直接交给原 Claude-GLM fix author 的完整 prompt，包含：

- stage、完整 fingerprint、raw `50-review-2.md` 与 findings；
- 允许修改 `scripts/validate-stage.py`、
  `scripts/tests/test_validate_stage_dispatch_protocol.py`、
  `docs/parallel-development-mode.md`、`40-fix-report.md` 与 append-only
  `60-test-output.txt`；
- 禁止 product code、schema、workflow、registry、`status.json`、
  `70-handoff.md`、`ACTIVE.json`、其他 stage、`_proposals/**`；
- 禁止 credential/environment dump、network request、commit/push/merge/rebase 和模型转派；
- 本 prompt 中的全部精确测试命令与逐 finding 验收标准；
- 要求 `40-fix-report.md` 逐 finding 映射、append-only test evidence，然后停给
  bookkeeper。

不得把 `fix_start_prompt` 省略或替换为“见上文”。
