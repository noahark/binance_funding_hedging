# Review 2

## Reviewer

- Model: `claude-opus-4-8`（interactive Claude Code 会话）
- Provider identity: `anthropic`
- Skill: `code_reviewer`（final gate）
- Adapter deviation disclosure: registry 默认 Claude 评审模型为 `claude-fable-5`；本次终审由用户在当前 Opus 4.8 会话内直接执行。Provider 身份仍为 `anthropic`，review-2 的 provider-level 隔离（≠ zhipu_glm/openai/moonshot）不受影响；如实记录实际模型而非冒充 fable5。
- Role: `final_reviewer`
- reviewer_prior_involvement: `none`

### 隔离与路由说明

- implementer = `claude_glm`/`zhipu_glm`；designer/breakdown/bookkeeper = `codex`/`openai`；review-1 = `kimi`/`moonshot_kimi`。
- 终审者 `anthropic` 对以上全部 provider 隔离，且无本 stage 任何 direction/design/breakdown/implementation/fix 参与，`reviewer_prior_involvement = none`，无需 strong-reviewer override。
- status.json 原 `model_routing.review_2 = "codex"` 因 Codex 兼 designer+breakdown，若由其终审需触发 strong-reviewer 免责（仅在无关决策模型不可用时允许）。无关决策模型 Claude/anthropic 可用，故按 AGENTS.md「review-2 prefers provider-level isolation from the designer/breakdown author」将终审路由至 anthropic。与先例 `2026-07-private-account-ui-polish-v1`（designer=Codex → 终审改由独立 Fable5）同构。

## Reviewed Artifacts

- `AGENTS.md`、`workflows/templates/stage-delivery.yaml`
- `00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`、`15-requirements-review.md`、`16-design-review.md`
- `20-implementation.md`、`60-test-output.txt`、`status.json`、`70-handoff.md`
- `30-review-1.md`、`review-1-kimi.raw-output.md`（review-1 原始输出）
- 冻结区间真实 diff：`git diff --binary 3d3c66e6..2e966904 -- . ':(exclude)…/status.json'`
- 产品源文件：`backend/domain/normalize.py`、`backend/domain/snapshot.py`、`backend/services/snapshot_service.py`（边界外，仅核对 residual）、`backend/tests/test_normalize.py`、`backend/tests/test_snapshot.py`、`docs/api/public-market-contract.md`、`frontend/index.html`、`frontend/self-check.js`、`frontend/fixture/public-market-snapshot.json`、`schemas/api/public-market/snapshot.schema.json`
- 金属公开样本：`reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/…`

## 独立复核（不复用 bookkeeper/Kimi 叙述）

冻结指纹独立重算 = `…:83956ebe0146…2222a1`，与 status 记录一致，diff 未漂移。逐条验收：

1. **低费率默认隐藏**：`filteredRows()`（index.html:1049）对 `hideLowDailyRate` 应用 `absDailyRateAtOrBelowThreshold`；默认 `checked` + `state.filters.hideLowDailyRate=true`。null/''/非法 → `false`（不被此过滤隐藏）。PASS。
2. **阈值无 float**：`absDailyRateAtOrBelowThreshold`（index.html:1022-1040）纯 regex + BigInt 定标比较。手工验算边界：`0.00030000`→隐藏、`0.00030001`→显示、`-0.0003`→取绝对值隐藏、高精度 `0.000300001`→显示，均正确，无浮点漂移。PASS。
3. **checkbox 位置/组合/可恢复**：位于 `显示 PERP_ONLY_EXCLUDED` 之后，change 监听 re-render，与既有过滤复合。PASS。
4. **余额三行 + 隐私遮罩**：`formatBalanceAmount`（隐私→`****`）+ `approximateUsdtLine`（隐私→`≈ **** USDT`）分别遮罩数量与估值两行。PASS。
5. **仅整数部分千分位**：`formatPrice` 以字符串 `split('.')`，仅对 `intPart` 走 `toLocaleString`，`fracPart` 原样拼接（保留前导零，如 `123,456.07890000`）。PASS。
6. **value_usdt null/零**：null/''/非法 → `≈ — USDT`；`formatUsdt2("0")→"0.00"` → `≈ 0.00 USDT`。PASS。
7. **METAL 优先级**：`REAL_METAL_BASE_ASSETS={XAU,XAG,COPPER,XPT,XPD}` 的 base_asset 检查置于 `TRADIFI_PERPETUAL→BSTOCK` 之前，返回 `(METAL, base_asset_metal_symbol, HIGH)`，大小写不敏感。测试 `test_asset_tag_metal_*`、`test_metal_base_asset_tagged_metal_over_tradifi` 覆盖。PASS。
8. **跨层同步**：schema enum、docs 契约（frozen 2026-07-08）、前端下拉+徽章（中性样式）、fixture `XAUUSDT` METAL 行、后端 + 8 项测试均含 METAL。PASS。
9. **无 DISABLED_METAL / 非结构性禁借**：全仓无 `DISABLED_METAL`；徽章走中性样式；契约明确 METAL 非借币禁止。PASS。
10. **METAL 入只读借币候选、bStock 仍排除**：`select_borrow_candidates` 过滤 `asset_tag in ("CRYPTO","METAL")`；`test_metal_margin_spot_candidate_enters_borrow_candidates`、`test_bstock_remains_excluded_from_borrow_candidates`、`test_metal_and_crypto_compose_in_borrow_candidates` 覆盖。PASS。
11. **未改私有签名/下单/借还/划转/密钥**：diff 仅触及 normalize/snapshot/UI/schema/docs/tests/fixture；`backend/services/private_client.py` 等执行路径未改。PASS。
12. **证据测试**：本会话复跑 `python3 -m pytest backend/tests -q` → `173 passed`；`node frontend/self-check.js` → `全部自检通过`；工作区 `git diff --check` → clean。PASS。

## Findings

无 P0/P1/P2/P3 阻塞发现。终审确认 Kimi review-1 的 ACCEPT 结论成立，无新增阻塞项。

## Residual Risks（non-blocking，转 follow-up）

1. `backend/services/snapshot_service.py:132`、`:182` 两处 CRYPTO-only 注释在候选集扩展为 `{CRYPTO, METAL}` 后陈旧。已确认为纯注释、该文件在本 stage 实现边界外（GLM 未改动符合外科式纪律），行为由已更新且有测试覆盖的 `select_borrow_candidates` 驱动。非功能缺陷，建议后续单独机械补正。
2. 公开金属样本无 exact/B-suffix 现货腿，METAL 借币候选路径仅合成 fixture 覆盖；契约与实现报告已记录为待补 live sample 的 follow-up。
3. 证据卫生小项：冻结区间 `git diff --check <base>..<head>` 对 `task-serial-claude-glm.prompt.md:5-7` 报行尾空格，实为 markdown 硬换行的行末双空格，位于 bookkeeper 撰写的报告产物、非产品代码；工作区形式 `git diff --check`（验收实际执行形式）clean。不影响交付。

## Verdict

ACCEPT。stage 进入 `stage_accepted_waiting_user`，等待用户显式验收后方可 no-ff 合回 `main`；review-2 ACCEPT 本身不授权合并。

## Operational Footer

本地北京时间: 2026-07-08 13:42:10 CST
下一步模型: human（用户显式验收）
下一步任务: 用户确认后由 bookkeeper 执行 `stage/2026-07-ui-filter-balance-metal-v1` → `main` 的 no-ff 合并；否则保持 waiting。

## Strict JSON Verdict

{"schema_version":1,"stage_id":"2026-07-ui-filter-balance-metal-v1","role":"final_reviewer","model":"claude-opus-4-8","verdict":"ACCEPT","diff_fingerprint":"2e966904a6adb576adee8f979738ef664f80058c:83956ebe014a34fc8ee85cfb04bb701fac76e488e106fac746a1a542762222a1","reviewer_prior_involvement":"none","reviewer_prior_involvement_notes":"anthropic 终审者对 implementer(zhipu_glm)、designer/breakdown(openai)、review-1(moonshot_kimi) 全部 provider 隔离，无本 stage 任何 direction/design/breakdown/implementation/fix 参与；无需 strong-reviewer override。实际模型为 claude-opus-4-8（用户当前会话），非 registry 默认 fable5，已如实披露。","reviewed_artifacts":["AGENTS.md","workflows/templates/stage-delivery.yaml","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-task.md","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/10-design.md","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/11-adr.md","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/12-development-breakdown.md","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/20-implementation.md","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/60-test-output.txt","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/30-review-1.md","reports/agent-runs/2026-07-ui-filter-balance-metal-v1/review-1-kimi.raw-output.md","backend/domain/normalize.py","backend/domain/snapshot.py","backend/services/snapshot_service.py","backend/tests/test_normalize.py","backend/tests/test_snapshot.py","docs/api/public-market-contract.md","frontend/index.html","frontend/self-check.js","frontend/fixture/public-market-snapshot.json","schemas/api/public-market/snapshot.schema.json"],"findings":[],"required_fixes":[],"residual_risks":["backend/services/snapshot_service.py:132/:182 CRYPTO-only 注释在候选集扩展为 {CRYPTO, METAL} 后陈旧，纯注释、边界外、有测试覆盖，建议机械补正。","公开金属样本无 exact/B-suffix 现货腿，METAL 借币候选路径仅合成 fixture 覆盖，待补 live sample follow-up。","冻结区间 git diff --check 对 task-serial-claude-glm.prompt.md:5-7 报行尾空格，实为报告产物的 markdown 硬换行双空格，非产品代码；工作区形式 diff-check clean。"],"next_action":"stage_accepted_waiting_user"}
