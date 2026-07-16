# Implementation Report — 内容回填（docs-truth-sync-v1）

实现者：`claude_glm`（backend/契约/data-semantics owner）。本 stage 只改仓内项目文档
文本，使人类文档追平已存在的 schema/代码/前端真值；**未改任何代码、schema、契约行为，
系统保持只读**。未 commit（bookkeeper 负责 stage 提交）。

## 改动总览（8 个文件，全部在 Allowed 集）

| # | 文件 | 改了什么 | 真值来源（对照物） |
|---|---|---|---|
| 1 | `docs/api/public-market-contract.md` | `## Backend API` 拆为三端点：保留 snapshot，新增 `### GET /api/public-market/funding-history`、`### GET /api/public-market/symbol-snapshot` 各一独立契约小节（method/path/入参/返回字段/schema 链接）；新增 `### Annualized funding fields (row-level, as-built)` 字段语义段（24h estimate / 7d·30d settled） | `schemas/api/public-market/{snapshot,funding-history,symbol-snapshot}.schema.json`、`backend/app/server.py` 路由 |
| 2 | `reports/follow-ups/README.md` | auto-review-pipeline 条目由「delivered on main / Normative contract (current)」改为「retired by DEC-2026-07-14-002；`docs/auto-review-pipeline.md` 与 `scripts/auto-review-runner.py` 已删除」；删死链、把「Former freeze pointer (still valid…)」改为「Design archaeology (historical only — not a live contract)」 | DEC-2026-07-14-002；两文件已不存在 |
| 3 | `docs/planning/DECISIONS.md` | DEC-2026-07-14-001 的 Source 列对两个已删文件 `docs/auto-review-pipeline.md`、`scripts/auto-review-runner.py` 加 `(deleted; retired by DEC-2026-07-14-002)` 历史注释；其它决策行与同行其它 Source 项未动 | DEC-2026-07-14-002 |
| 4 | `docs/product/PRD.md` | Product Summary「Current as-built status」补 `opening_quotes`/年化列/后台刷新 worker/launchd(`com.aoke.funding-hedging.server` + `scripts/service-control.py`)；UI Requirements 的「Manual open preview: simulation only」替换为 as-built 开仓价差展示（无任何执行动作）；验收准则同句改写去掉 simulation-only；Technology Direction 分层为 as-built(stdlib `http.server`+静态前端) vs future(asyncio/React/TS)；Status/Last updated 推进到 2026-07-16 | `docs/api/public-market-contract.md`(v0.7)、`docs/architecture/ARCHITECTURE.md`、`backend/config.py`、`scripts/service-control.py`、前端无交易按钮事实（`frontend/index.html` grep：无 simulation/preview/plan/rounds/notional/confirm，唯一「开仓」为 `<th>开仓价</th>` 开仓价差列） |
| 5 | `docs/development/DEVELOPMENT_GUIDE.md` | Commands 补 funding-history 目标测试命令（`test_funding_history.py` + `test_funding_history_endpoint.py`）；Environment 补 `APP_BACKGROUND_REFRESH_ENABLED`（含 `APP_BACKGROUND_TICK_SECONDS`/`APP_HISTORY_SWEEP_BATCH_SIZE`/`APP_SYMBOL_REFRESH_TIMEOUT_SECONDS` 同族）与 `APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`（默认 1800s）；Commands 补 launchd/`scripts/service-control.py` 运维路径（render/install/start/stop/restart/status/doctor，mutating 需 `--confirm`，install/restart 探 `/healthz`+`/readyz`）；Status 推进到 2026-07-16 | `backend/config.py`、`backend/tests/test_funding_history*.py`、`scripts/service-control.py` |
| 6 | `docs/architecture/ARCHITECTURE.md` | 仅推进 Status 日期行到 2026-07-16（正文已含 bookTicker/opening_quotes，无其它改动） | — |
| 7 | `reports/agent-runs/2026-07-bookticker-open-columns-v1/70-handoff.md` | 归一与 accepted 冲突的中间态 token：第 27 行「evidence is pending the final local Harness commit」→ 已提交；第 60-61 行「final counts are pending the addendum rerun」→ 终值 80 PASS / 375 passed；第 114 行「Formal review has not started」→ 改写为 pre-commit 快照且 reviews 已完成 ACCEPT；第 133 行「pending until…」→ completed ACCEPT；`## Blockers` 改为 `## Blockers (resolved)`（review-2 已捕获）；`## User Routing Amendment` 标记 `(superseded)` 并改为实际执行路由（Kimi Task C → 用户视觉验收 → 单次 fresh Codex `gpt-5.5` review-2 ACCEPT）。SHAs/Session IDs/指纹等事实全部保留 | 该 stage Recovery Header（accepted, merged `9abad62f`, pushed `a3d541d`）、`status.json`（review_2_routing_override / merge_result） |
| 8 | `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation.md` | 归一：Task C「display addendum is awaiting human execution」→ 两 pass 均完成；Task C Status「waiting for local evidence commit and the single fresh Codex final review」→ 全部完成、已合并并推送；footer 下一步由「codex_bookkeeper 创建证据提交」改为「human / stage 已完成」 | 同上 Recovery Header / `status.json` |

`reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json` 已是 accepted 终态
（`status: accepted`、`user_acceptance: accepted_merged_and_pushed`、`merge_result` 齐备、
review_2 verdict ACCEPT），grep 无任何矛盾中间态 token，**无需改动**。

## 契约对照（不得引入 schema 里不存在的字段）

- funding-history 小节字段严格 = `funding-history.schema.json` 的 7 个 required：
  `schema_version / symbol / data_time / history_status / funding_history /
  annualized_funding_7d / annualized_funding_30d`，并显式说明「无 24h」（schema 确无此字段）。
- symbol-snapshot 小节字段严格 = `symbol-snapshot.schema.json` 的 8 个 required：
  `schema_version / symbol / published_version / data_time / generated_at /
  refresh_status / warnings / row`；`refresh_status` 三态语义、`row` 单投影引用
  `snapshot.schema.json#/$defs/row`、永无 rows 数组，均照 schema description 原文。
- annualized 字段语义照搬 `snapshot.schema.json` row 的 description：24h = estimate
  (`daily_funding_rate × 365`)，7d/30d = settled 窗口求和 × (365/n)，含 null 语义与
  estimate/settled 不混入的红线。

## 逐条自检（对照 10-design.md Acceptance Criteria）

1. `grep -c annualized docs/api/public-market-contract.md` = **7** > 0；含 funding-history、
   symbol-snapshot 两个独立端点小节标题（`### GET …`，行 260 / 293）。✓
2. `reports/follow-ups/README.md` 不再出现「Normative contract (current) /
   delivered on `main`」；出现「retired by DEC-2026-07-14-002」「deleted」。✓
3. `docs/product/PRD.md` 不再把「simulation-only manual open」当现存 UI；含
   `opening_quotes`/年化/后台刷新/launchd 的 as-built 描述；Status 日期 2026-07-16。✓
4. `docs/development/DEVELOPMENT_GUIDE.md` 命中 `test_funding_history`、
   `APP_BACKGROUND_REFRESH_ENABLED`、`APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`。✓
5. bookticker `70-handoff.md` 全文不再有与 accepted 冲突的
   「Formal review has not started / pending / not yet captured / has executed /
   not yet prepared / awaiting / waiting for」等中间态 token；`20-implementation.md` 同。
   `status.json` 本就为 accepted 终态。✓
6. 禁改文件 0 改动：`git diff --name-only` 仅 8 个 Allowed 路径，Forbidden 列表
   （STAGE_INDEX / ROADMAP / harness-manifest / harness-design / AGENTS.md /
   stage-branch-mode / docs/README / docs/architecture/ADR/ / backend/ /
   frontend/ / schemas/ / scripts/）无一出现。✓

完整机械断言原始输出见 `60-test-output.txt`（6 条 + bookticker P1-9 额外自检）。

## 边界与遗留

- 本 stage 未触碰 Stage B 文件（STAGE_INDEX/ROADMAP/harness-manifest）与 Harness 轨文件
  （harness-design/AGENTS.md/stage-branch-mode/docs/README/ADR），按 10-design.md Non-Goals。
- `status.json.session_receipts` 回填不在实现者 Allowed 集（File Boundaries 未列入）；
  本报告 footer 已给出实现者 receipt（provider/model/Session/来源/原始输出路径），供
  bookkeeper 回填 `status.json.session_receipts`（与 bookticker stage 的「实现者写报告、
  bookkeeper 写 status.json」先例一致）。
- 无产品代码/schema 变更，无需跑 pytest/前端自检；验收 = 上述 6 条 grep/diff 断言 +
  review-1/review-2 对「文档所述 vs schema/server/前端真值」的抽样一致性核对。

当前 Session ID: unavailable (Claude Code 不向模型暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/20-implementation.md
本地北京时间: 2026-07-16 16:19:27 CST
下一步模型: review-1（Kimi，cross-review）
下一步任务: 逐条核对「文档所述 == schema/server/前端真值」+ 禁改文件 0 改动 + P1-9 归一无残留矛盾 token
