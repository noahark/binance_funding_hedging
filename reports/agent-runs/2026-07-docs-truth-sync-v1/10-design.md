# Stage Design — 内容回填（in-repo 项目文档 truth-sync）

## Scope（现在做）

把与新 Harness 门无依赖、且属于**仓内项目文档**的语义漂移一次性追平到真值。
实现者只改下列文件的文本，使人类文档与已存在的 schema/代码一致。系统只读，不改任何
产品/契约行为。

纳入项：
- **P0-2** `docs/api/public-market-contract.md`：补 `annualized_funding_24h/7d/30d`
  字段语义；为 `GET /api/public-market/funding-history`、`GET /api/public-market/
  symbol-snapshot` 各补一个独立端点契约小节（对齐 `schemas/api/public-market/*` 与
  `backend/app/server.py` 现状）。
- **P0-3** `reports/follow-ups/README.md`：auto-review-pipeline 条目从「delivered /
  current normative」改为「retired by DEC-2026-07-14-002，`docs/auto-review-pipeline.md`
  与 `scripts/auto-review-runner.py` 已删除」；去死链。
- **P0-4** `docs/planning/DECISIONS.md`：DEC-2026-07-14-001 Source 列对两个已删文件
  加历史注释（指向 DEC-2026-07-14-002 退役说明）。
- **P1-8** `docs/product/PRD.md`：as-built 补 `opening_quotes`/年化列/后台刷新/launchd；
  删除或改写「manual open preview: simulation only」等已不存在的 UI 描述（前端已无
  任何交易/开仓票据）；技术栈标注 as-built(stdlib+静态前端) vs future(React/TS) 分层；
  Status 日期推进。
- **P1-9** bookticker stage living-docs 归一：`reports/agent-runs/
  2026-07-bookticker-open-columns-v1/{70-handoff.md,20-implementation.md,status.json}`
  中残留的 pending/not-started 文字清理为 accepted 最终态（Recovery Header 为准）。
- **P1-10** 仓内项目文档 Status 日期推进到最近同步日：`PRD.md`、`ARCHITECTURE.md`、
  `DEVELOPMENT_GUIDE.md`（**不含 ROADMAP**，见 Non-Goals）。
- **P1-11** `docs/development/DEVELOPMENT_GUIDE.md`：补 `test_funding_history.py` /
  `test_funding_history_endpoint.py` 目标测试命令；补缺失环境变量
  （`APP_BACKGROUND_REFRESH_*`、`APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`、
  launchd / `scripts/service-control.py` 运维路径）。

## Non-Goals / 延后（不在本 stage 改）

- **STAGE_INDEX/ROADMAP（含 P0-5 单元格、P1-7 漏登、P1-13 manifest 分类）→ Stage B**：
  按 Fable5 Q3，STAGE_INDEX 从 `status.json` 生成、一次性回填；ROADMAP Done 半生成。
  手改即返工，禁止在本 stage 触碰这三个文件。
- **Harness 说明类文档 → 模板仓 first（Harness 轨，随 Stage A/B）**：`docs/harness-design.md`
  （P0-6 Deferred / P2-14 Current Scope）、`AGENTS.md`（P1-12 known-gaps）、
  `docs/planning/stage-branch-mode.md` 与 `docs/README`（P2-16）。理由：AGENTS.md 硬门
  「Harness/template sync 只落 main，不得混入 stage 分支」。
- **P2-15 ADR promotion → 由 RC1(a) promotion-debt 门驱动的后续**，本 stage 不批量补。
- **P2-17 记忆清理**：bookkeeper 直接处理（非派工项，非仓库文档）。
- 任何 `backend/` `frontend/` `schemas/` `scripts/` 代码与契约行为：禁止改。本 stage
  只让人类文档追平已存在的代码真值，不反向改代码。

## File Boundaries

- Allowed: `docs/api/public-market-contract.md`、`reports/follow-ups/README.md`、
  `docs/planning/DECISIONS.md`、`docs/product/PRD.md`、
  `docs/development/DEVELOPMENT_GUIDE.md`、`docs/architecture/ARCHITECTURE.md`
  （仅 Status 日期行）、bookticker stage 的三个 living-docs（P1-9）。
- Forbidden: `reports/agent-runs/STAGE_INDEX.md`、`docs/planning/ROADMAP.md`、
  `harness-manifest.yaml`、`docs/harness-design.md`、`AGENTS.md`、
  `docs/planning/stage-branch-mode.md`、`docs/README`、`docs/architecture/ADR/`、
  以及全部产品/契约代码与 schema。

## Acceptance Criteria（可机械复核，写入 60-test-output.txt）

1. `grep -c annualized docs/api/public-market-contract.md` > 0，且含
   `funding-history`、`symbol-snapshot` 两个独立端点小节标题。
2. `reports/follow-ups/README.md` 不再出现「Normative contract (current):
   docs/auto-review-pipeline.md」这类把已删文件当现行合同的措辞；出现「retired /
   DEC-2026-07-14-002」。
3. `docs/product/PRD.md` 不再把「simulation-only manual open」描述为现存 UI；含
   `opening_quotes`/年化/后台刷新/launchd 的 as-built 描述；Status 日期已更新。
4. `docs/development/DEVELOPMENT_GUIDE.md` 命中 `test_funding_history` 与新环境变量名。
5. bookticker `70-handoff.md` 全文不再有与 accepted 冲突的「Formal review has not
   started / pending」等中间态 token。
6. 禁改文件 0 改动（`git diff --name-only` 不含 Forbidden 列表任一路径）。

## Test Strategy

无产品代码变更，无需跑 pytest/前端自检。验收 = 上述 6 条 grep/diff 断言 +
review-1/review-2 对「文档所述 vs schema/server/前端真值」的抽样一致性核对。

## Routing

- Complexity: MEDIUM（lightweight route，已记）。
- Implementer: `claude_glm`（dominant workload = 契约/data-semantics/后端语义文档；
  前端无代码改动，PRD 的 UI 段为对既有前端的描述性文本，按 dominant 整单派 GLM）。
- Review-1: Kimi（cross-review，provider 隔离）。
- Review-2: Codex/GPT（final gate），不可得时 Claude（Fable5→Opus4.8）。
- Parallel mode: 否（单实现者）。

当前 Session ID: unavailable (Claude Code 未暴露)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/10-design.md
本地北京时间: 2026-07-16 16:19:27 CST
下一步模型: claude_glm（经操作者派发 dispatch 包）
下一步任务: 执行内容回填实现，写 20-implementation.md + 60-test-output.txt
