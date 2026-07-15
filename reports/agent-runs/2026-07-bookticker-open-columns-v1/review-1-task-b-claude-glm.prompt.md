# Formal Review-1 — Task B Frontend — Fresh Claude-GLM Session

你是 stage `2026-07-bookticker-open-columns-v1` 的 Task B formal review-1
reviewer。你必须在**全新 Claude-GLM Session**中以 plan/read-only 模式审查 Kimi
实现的 frontend/UI/client-integration diff。你不是本任务实现者；不得复用 Task A
implementation Session `aaba9bdc-5a62-4f9b-b820-d590c58c30a4`，不得修改任何
文件、运行 formatter、commit、push、merge 或启动其他模型。

## Identity And Reviewed Range

- Reviewer adapter/provider/model: `claude_glm` / `zhipu_glm` / `glm-5.2`
- Skill: `code_reviewer`
- Mode: `--permission-mode plan`
- Role: `first_reviewer`
- Task: `task-b-frontend-table-integration`
- Implementer provider: `kimi` / `moonshot_kimi`
- Base SHA: `dff8b4785f43cd9fb82b7fab6214bc8c7d98ac88`
- Head SHA: `0a383f0f8528591898f12690c371108e7582a27e`
- Required diff fingerprint:
  `0a383f0f8528591898f12690c371108e7582a27e:2fa0b74988af0ae96a4a2f252f0aa67346c5b5fd3e89a218c78802bec4a48dce`
- Expected captured output:
  `reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-b.md`

只审查上述固定 range，不用 moving `HEAD` 代替。该 range 包含 Task B frontend
代码、implementation/fix/bookkeeper evidence；产品结论必须以实际 frontend diff
为准，不以 bookkeeper summary 代替 raw evidence。

## Required Raw Reads

亲自读取：

- `AGENTS.md`
- `workflows/templates/stage-delivery.yaml` review-1 section
- `agents/skills/code-reviewer.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
- `10-design.md`, `11-adr.md`, `12-development-breakdown.md`,
  `14-design-review-reconciliation.md`
- `20-implementation-task-b.md`, `20-implementation.md`,
  `21-bookkeeper-task-b-verification.md`, `60-test-output.txt`
- `schemas/api/public-market/snapshot.schema.json` 的 `opening_quotes`
- `schemas/review-verdict.schema.json`
- 实际 committed diff：
  `git diff --binary dff8b4785f43cd9fb82b7fab6214bc8c7d98ac88..0a383f0f8528591898f12690c371108e7582a27e -- . ':(exclude)reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json'`
- `frontend/index.html`, `frontend/self-check.js`,
  `frontend/fixture/public-market-snapshot.json`。

模型陈述不是证据。核对实际 diff、测试日志、schema 和 committed SHAs。

## Mandatory Review Focus

按严重度检查并给出 file/line evidence：

1. 最终表头精确 12 列与顺序，data row 12 `<td>`，blocked/empty colspan，删除
   提示标记/独立负费率状态但保留 `ui_flags`/`route_class` validation。
2. `借贷状态 / 资产`：状态在上、资产在下；行感知 badge 语义不丢失；已探测
   max-borrowable 不受 `borrow_rate_source` 错误门控；额度只在合并格，不在日净
   收益格重复；51061 零额度仍正确。
3. `日净收益`：净值、source badge、日借币成本条件保留；sort basis 文案为
   `日净收益优先`。
4. 正向严格为 futures bid 上 / spot ask 下 / `forward_spread_pct` 右；反向严格为
   spot bid 上 / futures ask 下 / `reverse_spread_pct` 右。
5. 前端不重算 spread、不调用 `formatFundingRate`、不二次乘 100；两位、正负号、
   零/invalid muted 正确。
6. missing/stale/unavailable 降级为 `—`；incomplete 保留单腿且两个方向独立；
   XAU 无 spot leg 不伪造 quote；bStock alias preview 不误连。
7. 60s/120s/非成交保证 wording 正确，未新增 timer、fetch、WebSocket、按钮或交易
   副作用；selected-symbol click/drawer/private panels/filters/refresh 不回归。
8. self-check 的 exact order/cell count/colspan/single-location/explicit dash 断言是否
   真能捕获错误；fixture 与 frozen contract 是否一致。

## Verdict Contract

先输出简洁 review narrative 和 findings；然后输出导航 footer；**最后内容必须是
一个且仅一个 JSON object**，匹配 `schemas/review-verdict.schema.json`，JSON 后
不得再有文字。

- `schema_version`: `1`
- `stage_id`: `2026-07-bookticker-open-columns-v1`
- `role`: `first_reviewer`
- `model`: `glm-5.2`
- `diff_fingerprint`: 必须逐字等于上面的 Task B fingerprint
- `reviewer_prior_involvement`: `none`
- ACCEPT: `required_fixes=[]`, `next_action="continue"`
- REWORK: `next_action="fix"` 且必须包含完整 `fix_start_prompt`
- BLOCKED: 仅证据确实无法取得且无法审查时使用，
  `next_action="human_escalation_required"`

若 verdict 为 REWORK，`fix_start_prompt` 必须直接可发给 Task B 的 Kimi fix
author，包含：stage/task/fingerprint、raw review path
`30-review-1-task-b.md`、逐项原始 finding、允许文件仅限原 Task B frontend/test/
report boundary、禁止 backend/schema/Harness/交易副作用、精确测试命令、以及
`40-fix-report.md` finding-to-fix mapping。不得用 summary 隐藏 raw findings。

Footer 的 Session ID 必须来自当前**新** Claude-GLM Session 的
`CLAUDE_CODE_SESSION_ID` 或精确 transcript/scratchpad cross-check；不得使用 Task A
implementation ID，不得按 mtime 猜，不得暴露 expanded alias environment。

```text
当前 Session ID: <fresh provider-native UUID | unavailable (reason)>
Session ID 来源: <runtime_env | transcript_path | unavailable>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/30-review-1-task-b.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: codex_bookkeeper
下一步任务: 校验 Task B review-1 JSON、Session/provider isolation 与 fingerprint，并与 Task A review-1 一并门禁
```

时间来自本地 `date`。不要写文件；由 human/bookkeeper 原样捕获输出。
