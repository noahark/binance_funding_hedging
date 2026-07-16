# Development Breakdown — 内容回填

## Owner Split

单实现者 `claude_glm`（无并行、无前端代码改动）。Breakdown 作者：bookkeeper
（Claude Opus 4.8）——作为 review-2 的 design-involvement 披露项记录。

## 逐文件规格

| # | 文件 | 改什么 | 真值来源（对照物） |
|---|---|---|---|
| P0-2 | `docs/api/public-market-contract.md` | 补 `annualized_funding_24h/7d/30d` 字段语义段；`funding-history`、`symbol-snapshot` 各一独立端点小节（method/path/入参/返回/schema 链接） | `schemas/api/public-market/snapshot.schema.json`（annualized 3 处）、`funding-history.schema.json`、`symbol-snapshot.schema.json`、`backend/app/server.py` 路由 |
| P0-3 | `reports/follow-ups/README.md` | auto-review 条目改「retired by DEC-2026-07-14-002；文件已删」，删死链 | DEC-2026-07-14-002；`docs/auto-review-pipeline.md`/`scripts/auto-review-runner.py` 已不存在 |
| P0-4 | `docs/planning/DECISIONS.md` | DEC-2026-07-14-001 Source 列对两个已删文件加历史注释 | 同上 |
| P1-8 | `docs/product/PRD.md` | as-built 补 opening_quotes/年化/后台刷新/launchd；删/改「simulation-only manual open」现存描述；技术栈 as-built vs future 分层；Status 日期 | `public-market-contract.md`(v0.7)、`ARCHITECTURE.md`、前端无交易按钮事实（前端测试） |
| P1-9 | bookticker `70-handoff.md`/`20-implementation.md`/`status.json` | 中间态 pending/not-started 文字归一为 accepted 终态 | 该 stage Recovery Header（accepted, merged, pushed） |
| P1-10 | `PRD.md`/`ARCHITECTURE.md`/`DEVELOPMENT_GUIDE.md` | Status 日期行推进到最近同步日 | — |
| P1-11 | `docs/development/DEVELOPMENT_GUIDE.md` | 补 `test_funding_history*.py` 目标测试；补 `APP_BACKGROUND_REFRESH_*`、`APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`、launchd/`service-control.py` | `backend/config.py`、`backend/tests/`、`scripts/service-control.py` |

## 禁改（硬边界）

`STAGE_INDEX.md`、`ROADMAP.md`、`harness-manifest.yaml`、`harness-design.md`、
`AGENTS.md`、`stage-branch-mode.md`、`docs/README`、`docs/architecture/ADR/`、
全部 `backend/`/`frontend/`/`schemas/`/`scripts/` 代码与 schema。理由见 10-design.md
Non-Goals。

## Review Focus

- review-1（Kimi）：逐条核对「文档所述 == schema/server/前端真值」；确认禁改文件
  0 改动；确认 P1-9 归一后无残留矛盾 token。
- review-2（Codex/GPT）：契约小节是否与 schema 字段/端点一一对应；PRD 是否还残留
  已删 UI 的现存表述；范围是否越界到 Stage B/Harness 轨文件。

## 风险点

- **越界风险**：实现者可能顺手改 STAGE_INDEX/ROADMAP/harness-design——review 必须挡。
- **契约过度承诺**：补端点契约时不得引入 schema 里不存在的字段（只描述现状，不新增
  契约面）。

当前 Session ID: unavailable
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/12-development-breakdown.md
本地北京时间: 2026-07-16 16:19:27 CST
下一步模型: claude_glm
下一步任务: 执行实现，产出 20-implementation.md + 60-test-output.txt
