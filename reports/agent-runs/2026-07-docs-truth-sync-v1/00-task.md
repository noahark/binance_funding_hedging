# Stage Task

## Stage ID

`2026-07-docs-truth-sync-v1`

## Goal

把四模型审计（codex/grok/claude-glm/kimi）+ 本地 bookkeeper 复核发现的文档 / 状态
账本不同步项收口到 canonical 文档与 stage 账本，使「机器真值（代码 / schema /
`status.json` / `ACTIVE.json`）」与「人类导航文档（PRD / ROADMAP / STAGE_INDEX /
follow-ups / harness 说明）」重新一致。系统保持只读，不改任何产品运行行为。

## Evidence Base（方向输入，等价 synthesis）

- 四模型只读审计会话：codex `019f698c-fe76-7a93-8b0f-4a2a980f0bf0`、
  grok `019f698d-3684-7840-8404-dacc837f1b23`、
  claude-glm `66ecab0d-8ab7-4830-9c30-bb89c7bf33be`、
  kimi `session_7dd224db-3b22-4383-a85f-e0b7db9b2cbe`（kimi 定稿由用户回传）。
- 本地 bookkeeper 复核：对 P0/P1 关键项逐条复跑（validator、grep、git ancestor）。

## Backlog（按严重程度，已本地复核）

### P0 — 事实矛盾 / 会误导执行 / 证据门未收口

- **P0-1（Linked-Decision，非文档编辑）** `2026-07-bookticker-open-columns-v1`
  的 `pre-accept` validator 仍红：`review_1.diff_fingerprint must match
  status.diff_fingerprint`。根因：Task C 在 review-1 之后加入，review-1 指纹未覆盖，
  仅 review-2 覆盖全量；用户 fast-route 授权合并/推送，但 Harness 未编码该豁免。
  见 §Linked-Decisions。
- **P0-2** `docs/api/public-market-contract.md` 缺 `annualized_funding_24h/7d/30d`
  字段语义（schema 已定义，合同 0 处 `annualized`），且 `GET /api/public-market/
  funding-history`、`GET /api/public-market/symbol-snapshot` 已在 `server.py` 暴露
  但合同无一等契约。**同时违反 `DEVELOPMENT_GUIDE.md` 自订规则**「Contract changes
  must update both human documentation and JSON schema」。
- **P0-3** `reports/follow-ups/README.md` 仍把 auto-review-pipeline 写成
  "delivered on `main` / Normative contract (current): `docs/auto-review-pipeline.md`"，
  而该文件已被 DEC-2026-07-14-002 退役并从磁盘删除（死链）。
- **P0-4** `docs/planning/DECISIONS.md` DEC-2026-07-14-001 的 Source 列引用已删除的
  `scripts/auto-review-runner.py`、`docs/auto-review-pipeline.md`。
- **P0-5** `reports/agent-runs/STAGE_INDEX.md` 中 `harness-flow-optimization-v1`
  行「Merged to main」列写 `false`，但 `status=accepted_and_merged_to_main` 且
  `693a7b6` 已在 main 祖先链上 → 应为 `true`。
- **P0-6** `docs/harness-design.md` §Deferred Work（约第 496–504 行）仍把 PRD、
  Manual first stage delivery execution、Git commits for bootstrap 列为未实现，
  三者均已存在 → 需重写为真实未实现项。

### P1 — 文档过时应更新

- **P1-7** `STAGE_INDEX.md` + `ROADMAP.md` Done 漏登 5 个已 accepted+merged stage：
  `bookticker-open-columns-v1`、`history-background-refresh-v1`、
  `local-service-launchd-v1`、`history-refresh-ahead-v1`、
  `cache-refresh-scheduler-v2`；并修正 cache 的双向不符（索引记了磁盘已无的
  abandoned `v1`、漏了实际存在的 accepted `v2`）。
- **P1-8** `docs/product/PRD.md`（07-10）过时且描述已删的 UI：466/537 行仍写
  "manual open preview: simulation only"，前端已无任何交易/开仓票据；补 as-built
  （opening_quotes / 年化 / 后台刷新 / launchd 常驻），技术栈做 as-built vs future
  分层。
- **P1-9** bookticker stage 的 living-docs 自相矛盾：`70-handoff.md`（114 行
  "Formal review has not started"、133 行 pending）、`20-implementation.md`、
  `status.json` 中部残留 pending 文字，机械清理为最终事实。
- **P1-10** canonical 头部日期统一推进到最近同步日：`PRD.md:5`、
  `ARCHITECTURE.md:3`、`DEVELOPMENT_GUIDE.md:4`、`ROADMAP.md:4`。
- **P1-11** `DEVELOPMENT_GUIDE.md` 补 `test_funding_history.py` /
  `test_funding_history_endpoint.py` 目标测试命令，并补缺失环境变量
  （`APP_BACKGROUND_REFRESH_*`、`APP_FUNDING_HISTORY_CACHE_TTL_SECONDS`、
  launchd / `scripts/service-control.py` 运维路径）。
- **P1-12** `AGENTS.md` Known open gaps 增补契约层 gap（symbol-snapshot /
  funding-history / annualized 未入人类可读契约），或在 P0-2 修完后确认无需增补。
- **P1-13** `harness-manifest.yaml` `generated_or_runtime` 归类 `ACTIVE.json` 与
  `reports/agent-runs/STAGE_INDEX.md`。

### P2 — 措辞 / 引用 / 历史残留

- **P2-14** `docs/harness-design.md` §Current Scope（第 16 行）"only the
  document-level Harness contract" 与第 27 行 "Multiple bounded delivery stages
  have completed" 冲突，改为 "document-level contract plus multiple completed
  manual delivery stages"。
- **P2-15** 已接受的架构决策未 promote 进 canonical：`docs/architecture/ADR/`
  仅模板；配对原子缓存 / `Decimal` 价差 / opening_quotes 等只在阶段 `11-adr.md`；
  评估是否补 ADR 与 DECISIONS 产品决策条目。
- **P2-16** 历史状态词 / 草稿残留：`harness-friction-fixes-v1`（waiting 却 merged）、
  `docs/planning/stage-branch-mode.md` 仍标"待执行"（实际已强制）、`docs/README`
  声称只放 approved 却含 DRAFT、Phase 2 方向文档 FROZEN 与"待批准"并存。
- **P2-17** 两条 auto-memory 过期（属 bookkeeper 记忆层，非仓库文档，附带清理）：
  `followup-auto-review-pipeline`、`context-recovery-declaration-v1`。

## Linked-Decisions（需用户拍板，非本 stage 文档编辑）

- **D-A（P0-1 处置）** 三选一：
  (a) 补一次 Task C review-1 交叉评审，重算 review-1 指纹使 `pre-accept` 转绿
      （勿手改旧指纹）；
  (b) 在 Harness 中正式编码 user-authorized fast-route 豁免记录，让 validator 承认；
  (c) 知情接受红门为一次性历史例外并落档，不改 validator。
- **D-B** 是否采纳 `80-harness-design-rootcause.md` 提出的 Harness 流程改动。此属
  Harness 契约变更，需模板仓 first + 强评审（Fable5 review 由用户路由）。

## File Boundaries（拟）

- Allowed（canonical 文档收口，需用户批准 promote）：`docs/product/PRD.md`、
  `docs/planning/ROADMAP.md`、`docs/planning/DECISIONS.md`、
  `docs/api/public-market-contract.md`、`docs/development/DEVELOPMENT_GUIDE.md`、
  `docs/harness-design.md`、`AGENTS.md`（仅 Known open gaps 段）、
  `harness-manifest.yaml`、`reports/agent-runs/STAGE_INDEX.md`、
  `reports/follow-ups/README.md`、bookticker stage 的 living-docs（P1-9）。
- Forbidden：任何 `backend/`、`frontend/`、`schemas/`、`scripts/` 产品/契约代码
  （本 stage 只让人类文档追平已存在的代码真值，不反向改代码）；validator/workflow
  行为（Harness 改动走 D-B 单独流程）。

## Non-Goals

- 不做任何产品功能变更、不改 API 行为、不改 schema。
- 不在本 stage 内实施 Harness 流程改动（只产出根因分析供 review）。

## Acceptance Criteria

- 上述 P0/P1/P2 文档项经用户批准后 promote，且每项可指回 backlog 条目。
- 收口后重跑：`grep annualized docs/api/public-market-contract.md` 命中；
  `STAGE_INDEX.md` 含 5 个补登 stage 且 harness-flow 行 Merged=true；
  follow-ups/README 无 auto-review 死链。
- D-A 由用户选定并落档；`80-harness-design-rootcause.md` 交付且用户确认路由 Fable5。

当前 Session ID: unavailable (Claude Code session id 未暴露)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/00-task.md
本地北京时间: 2026-07-16 14:33:56 CST
下一步模型: human
下一步任务: 审阅 backlog + 根因报告；选 D-A 处置；决定实现派工
