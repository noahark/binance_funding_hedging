# Follow-up: ui-filter-balance-metal-v1 终审 residual risks（并入下个 stage）

- 来源 stage: `2026-07-ui-filter-balance-metal-v1`（review-2 终审记录，用户验收时指示归入下个 stage）
- 落档人: claude / anthropic（review-2 终审 + 验收 bookkeeper）
- 落档时间: 2026-07-08 13:42:10 CST（用户验收: 2026-07-08）
- 归属: 与 [`2026-07-borrowability-51061-zero-mapping.md`](./2026-07-borrowability-51061-zero-mapping.md) 一起由 bookkeeper 在下个 stage 收口。

三项均为 **non-blocking**，已随 `2026-07-ui-filter-balance-metal-v1` ACCEPT 交付；不得回改该已冻结 diff（指纹 `2e966904…:83956ebe…`）。

## R1 — `snapshot_service.py` 陈旧注释（最实在，建议修）

`backend/services/snapshot_service.py:132`、`:182` 两处注释仍写 "CRYPTO-only"，但 `select_borrow_candidates` 已扩展为 `{CRYPTO, METAL}`。

- `:132` — `# §1.5 borrow probe sets (neg funding + MARGIN_SPOT_CANDIDATE + CRYPTO, ...)`
- `:182` — `# bStock rows are excluded upstream (asset_tag != CRYPTO)`

纯注释漂移、无功能影响；该文件在原 stage 实现边界外故 GLM 未动（符合外科式纪律）。行为由已更新且有测试覆盖的 `select_borrow_candidates` 驱动。**建议下个 stage 顺手机械补正为 `{CRYPTO, METAL}` 语义。** 注：51061 follow-up 的「影响范围」已列出可顺带补正本项。

## R2 — METAL 借币候选路径仅合成 fixture 覆盖（等外部接口，非我方可补）

当前币安公开金属样本中，XAU/XAG/COPPER/XPT/XPD 均只有 `TRADIFI_PERPETUAL` 期货腿，**无 exact/B-suffix 现货腿**。故「METAL + 负费率 + `MARGIN_SPOT_CANDIDATE` 进入借币候选」路径目前只被合成 fixture 覆盖，缺 live sample。契约与实现报告已记录。**待公开接口出现金属现货腿时，补 `reports/api-samples/<stage>/` live sample 并重进 review。** 产品事实局限，无代码可改。

## R3 — 报告产物行尾空格（最轻，可顺手清或忽略）

冻结区间 `git diff --check <base>..<head>` 对 `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/task-serial-claude-glm.prompt.md:5-7` 报 trailing whitespace，实为 `。` 后的 markdown 硬换行双空格，位于 bookkeeper 派发 prompt 报告产物、**非产品代码**。工作区形式 `git diff --check`（验收实际执行形式）clean。证据卫生小项。

---

本地北京时间: 2026-07-08 13:42:10 CST
下一步模型: bookkeeper（下个 stage）
下一步任务: 与 51061 follow-up 一起在下个 stage intake 收口；R1 建议随 51061 修复顺带补正，R2 挂等 live sample，R3 可忽略。
