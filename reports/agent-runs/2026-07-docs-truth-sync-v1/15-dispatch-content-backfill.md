# Dispatch Packet — 内容回填（executor: human operator → claude_glm）

操作者：在 Claude-GLM 终端执行下面 PROMPT BODY（read-file-and-execute 或整段粘贴）。
执行后把原始输出落到 `reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md`
与 `60-test-output.txt`，并回填 `status.json.session_receipts`。

Bookkeeper 不执行本 dispatch。

---

## PROMPT BODY

你是本 stage 的实现者（`claude_glm`，backend/契约/data-semantics owner）。任务：把
仓内项目文档追平到已存在的 schema/代码/前端真值，**只改文档文本，不改任何代码、
schema、契约行为**。系统保持只读。

先读（真值来源与边界）：
- `reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md`
- `reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md`
- 对照物：`schemas/api/public-market/snapshot.schema.json`、`funding-history.schema.json`、
  `symbol-snapshot.schema.json`、`backend/app/server.py`、`backend/config.py`、
  `backend/tests/`、`scripts/service-control.py`

改这些文件（Allowed，且仅限这些）：
1. `docs/api/public-market-contract.md` — 补 `annualized_funding_24h/7d/30d` 字段
   语义；为 `GET /api/public-market/funding-history` 与 `GET /api/public-market/
   symbol-snapshot` 各补一个独立端点契约小节（method/path/入参/返回/schema 链接），
   严格对照 schema 现状，**不得引入 schema 里不存在的字段**。
2. `reports/follow-ups/README.md` — auto-review-pipeline 条目改为「retired by
   DEC-2026-07-14-002；`docs/auto-review-pipeline.md` 与 `scripts/auto-review-runner.py`
   已删除」，删除把已删文件当「current normative contract」的措辞与死链。
3. `docs/planning/DECISIONS.md` — DEC-2026-07-14-001 的 Source 列对两个已删文件加
   历史注释（指向 DEC-2026-07-14-002 退役说明）。不改其它决策行。
4. `docs/product/PRD.md` — as-built 补 `opening_quotes`/年化列/后台刷新/launchd；
   删除或改写「manual open preview: simulation only」等描述现存 UI 的措辞（前端已无
   任何交易/开仓票据）；技术栈标注 as-built(stdlib+静态前端) vs future(React/TS) 分层；
   Status 日期推进到今天。
5. `docs/development/DEVELOPMENT_GUIDE.md` — 补 `test_funding_history.py`/
   `test_funding_history_endpoint.py` 目标测试命令；补环境变量
   `APP_BACKGROUND_REFRESH_*`、`APP_FUNDING_HISTORY_CACHE_TTL_SECONDS` 及 launchd/
   `scripts/service-control.py` 运维路径；Status 日期推进。
6. `docs/architecture/ARCHITECTURE.md` — 仅推进 Status 日期行（内容已含 bookticker）。
7. bookticker stage living-docs 归一：`reports/agent-runs/
   2026-07-bookticker-open-columns-v1/{70-handoff.md,20-implementation.md,status.json}`
   中与 accepted 冲突的「Formal review has not started / pending」等中间态 token 清理
   为 accepted 最终态（以其 Recovery Header 为准），不改事实、只除矛盾残留。

绝对禁改（越界即 review 打回）：
`reports/agent-runs/STAGE_INDEX.md`、`docs/planning/ROADMAP.md`、`harness-manifest.yaml`、
`docs/harness-design.md`、`AGENTS.md`、`docs/planning/stage-branch-mode.md`、
`docs/README`、`docs/architecture/ADR/`，以及所有 `backend/`/`frontend/`/`schemas/`/
`scripts/` 代码与 schema。

完成后：
- 写 `reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md`（改了哪些
  文件、每处对照的真值来源、逐条自检结果）。
- 写 `reports/agent-runs/2026-07-docs-truth-sync-v1/60-test-output.txt`，跑并粘贴这 6 条
  机械断言的结果：
  1. `grep -c annualized docs/api/public-market-contract.md`（需 >0）
  2. `grep -nE "funding-history|symbol-snapshot" docs/api/public-market-contract.md`
     （需含各自独立端点小节标题）
  3. `grep -niE "current.*normative|delivered on .main" reports/follow-ups/README.md`
     （auto-review 处需已无此类现行合同措辞）
  4. `grep -niE "simulation only|simulation-only" docs/product/PRD.md`
     （不得再把它作为现存 UI 描述）
  5. `grep -niE "test_funding_history|APP_BACKGROUND_REFRESH|APP_FUNDING_HISTORY_CACHE"
     docs/development/DEVELOPMENT_GUIDE.md`（需命中）
  6. `git diff --name-only`（不得含任一 Forbidden 路径）
- 不要 commit（bookkeeper 负责 stage 提交）。报告用统一 footer，并给出 provider-native
  Session ID 或 unavailable+原因。

## END PROMPT BODY
