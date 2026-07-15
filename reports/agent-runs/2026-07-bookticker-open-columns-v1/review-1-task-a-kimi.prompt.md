# Formal Review-1 — Task A Backend — Fresh Kimi Session

你是 stage `2026-07-bookticker-open-columns-v1` 的 Task A formal review-1
reviewer。你必须在**全新 Kimi Session**中以只读方式审查 Claude-GLM 实现的
backend/API/schema/data-semantics diff。你不是本任务实现者；不得复用 Task B
implementation Session `session_727145b3-694a-4467-8277-60a65dd1b1c5`，不得修改
任何文件、运行 formatter、commit、push、merge 或启动其他模型。

## Identity And Reviewed Range

- Reviewer adapter/provider/model: `kimi` / `moonshot_kimi` /
  `kimi-code/kimi-for-coding`
- Skill: `code_reviewer`
- Role: `first_reviewer`
- Task: `task-a-backend-contract-cache`
- Implementer provider: `claude_glm` / `zhipu_glm`
- Base SHA: `7c0c9a21d523425f7380e7f721de03ca0730a17a`
- Head SHA: `01fca8cda4e3ce37ab2b976f1ca060ed9da109a0`
- Required diff fingerprint:
  `01fca8cda4e3ce37ab2b976f1ca060ed9da109a0:a8ad71a421cbf1122ec8bedf123646fcb3606b85fdc2651917519524d33222de`
- Expected captured output:
  `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-a.md`

只审查上述固定 range，不使用 moving `HEAD` 代替。当前 branch 后续包含 Task B
和 bookkeeping commits；它们不属于 Task A reviewed diff。

## Required Raw Reads

亲自读取：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml` 的 review-1 section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`,
  `14-design-review-reconciliation.md`
- `20-implementation-task-a.md`, `20-implementation.md`,
  `60-test-output.txt`
- `schemas/review-verdict.schema.json`
- 实际 committed diff：
  `git diff --binary 7c0c9a21d523425f7380e7f721de03ca0730a17a..01fca8cda4e3ce37ab2b976f1ca060ed9da109a0 -- . ':(exclude)reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json'`
- diff 涉及的 adapter/domain/service/tests/schema/contract docs 源文件。

模型陈述不是证据。核对实际 diff、测试日志、schema 和 committed SHAs。

## Mandatory Review Focus

按严重度检查并给出 file/line evidence：

1. Spot/futures full bookTicker 两请求与归一化：正确 URL、string-only price、
   malformed/zero handling、无逐 symbol 请求。
2. pair atomic commit：任一侧失败不部分替换 map、不推进 success timestamp；
   completion-time timestamp 正确。
3. 60 秒 due、`<120s` last-good usable、`>=120s` 每次 assembly 投影 stale/null，
   不依赖额外失败事件；未改变 Group B/history/private cadence。
4. alias-aware join：futures 用 `row.futures.symbol`，spot 用已解析
   `row.spot.symbol`；bStock B-suffix 正确，无 spot leg 不猜替代资产。
5. forward/reverse Decimal 公式方向、分母、final-only HALF_UP 两位、负零、
   invalid/zero denominator。
6. `opening_quotes` additive optional schema、current producer presence、nested
   closed object、legacy fixture compatibility、number-valued price rejection。
7. selected-symbol click 不新增 bookTicker HTTP，复用 canonical cache。
8. private disabled/legacy stub compatibility、read-only product boundary、无凭据/
   下单副作用。
9. 测试是否能真正失败于上述回归，而非仅检查样例文字。

## Verdict Contract

先输出简洁 review narrative 和 findings；然后输出以下导航 footer；**最后内容必须
是一个且仅一个 JSON object**，匹配
`schemas/review-verdict.schema.json`，JSON 后不得再有文字。

- `schema_version`: `1`
- `stage_id`: `2026-07-bookticker-open-columns-v1`
- `role`: `first_reviewer`
- `model`: `kimi-code/kimi-for-coding`
- `diff_fingerprint`: 必须逐字等于上面的 Task A fingerprint
- `reviewer_prior_involvement`: `none`
- ACCEPT: `required_fixes=[]`, `next_action="continue"`
- REWORK: `next_action="fix"` 且必须包含完整 `fix_start_prompt`
- BLOCKED: 仅证据确实无法取得且无法审查时使用，
  `next_action="human_escalation_required"`

若 verdict 为 REWORK，`fix_start_prompt` 必须直接可发给 Task A 的 Claude-GLM
fix author，包含：本 stage/task/fingerprint、raw review path
`30-review-1-task-a.md`、逐项原始 finding、允许文件边界、禁止 frontend/Harness/
private/history cadence/交易副作用、精确测试命令、以及 `40-fix-report.md` 的
finding-to-fix mapping 要求。不得用一句“按 review 修复”替代。

Footer 中 Session ID 必须来自当前**新** Kimi session 的准确 transcript path，并
以 `state.json.workDir/lastPrompt` 交叉验证；不得使用 Task B implementation ID，
不得按 mtime 猜。

```text
当前 Session ID: <fresh provider-native session_<uuid> | unavailable (reason)>
Session ID 来源: <transcript_path | cli_output | unavailable>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-a.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: codex_bookkeeper
下一步任务: 校验 Task A review-1 JSON、Session/provider isolation 与 fingerprint，并与 Task B review-1 一并门禁
```

时间来自本地 `date`。不要写文件；由 human/bookkeeper 原样捕获输出。
