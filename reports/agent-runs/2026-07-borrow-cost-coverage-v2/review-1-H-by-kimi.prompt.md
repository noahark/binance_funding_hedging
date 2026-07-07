<!-- ============ RECEIPT（bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done
role: first_reviewer (review-1，亦作 R10 嵌入预审输入)
target_model: kimi (kimi-code/kimi-for-coding)
adapter_cmd: kimi --model kimi-code/kimi-for-coding -p "$(cat <本文件>)" | tee embedded-review-H-round1.raw-output.md
invoked_by: claude_glm 实现会话 R10 步骤 4（嵌入预审）；bookkeeper 在 fingerprint 对账后 promote 为正式 review-1
base_sha: 5bdfc4b3dc6843a8e52aeb86896c735500ed137a
outputs: embedded-review-H-round1.raw-output.md
======================================================================== -->

--- PROMPT BODY（不可变；只读评审，禁止修改任何文件） ---

你是 stage `2026-07-borrow-cost-coverage-v2` 的 **review-1（first_reviewer）**。

## 执行纪律（硬）

- **只读**。禁止修改、创建、删除任何源码/测试/文档文件（本次唯一产出 = stdout 的一段 JSON verdict；调用方会 tee 落档，你不要自己写文件）。
- 禁止运行会改工作树的命令。可运行只读命令核对（`git diff`、`cat`、`pytest` 只读跑一遍验证）。
- **输出：严格符合 `schemas/review-verdict.schema.json` 的单个 JSON 对象，不要包裹 markdown 代码块、前后不加任何解释文字。** 非法/缺失 JSON 按不通过处理。

## 评审对象

- 实现 diff：`reports/agent-runs/2026-07-borrow-cost-coverage-v2/H.diff.patch`（工作树 vs base_sha）。
- 实现说明：`reports/agent-runs/2026-07-borrow-cost-coverage-v2/H.impl-note.md`。
- 权威规格：`task-H-claude-glm.prompt.md`（§3 逐文件边界 + §4 测试）、`10-design.md`、`00-stage-plan.md §5`。
- Gate 证据（只读）：`gate-a-live.md`、`gate-b-endpoint-recon.md §9`。

## 必查清单（每条给出通过/不通过 + 证据行）

1. **主修有效**：next-hourly 改为 batch_size=15 分批，合并在 `_select_chain_tier` 之前；实盘/测试 `chain_hit_source` 能达到 `next_hourly`（不再永远 rate_history）。
2. **缓存纪律**：逐片 `_cached_get` 保留；**没有**把 `merged_next_hourly` 整表另存为单一缓存项（若有 → P0/P1，破坏 60s 自愈）。
3. **静默异常已修**：批失败被记录（`next_hourly_batch_failed:...`），非静默 `pass`。
4. **部分批失败语义**：某批失败仅跳过该批、不整体降级 tier②、不清空已合并；失败批资产 rate=None（不伪造）。
5. **预算解耦**：`select_borrow_candidates` 拆 `rate_probe_assets`（全量）/`borrowability_probe_assets`（受 cap）/`borrowability_unprobed_assets`；利率解析只依赖 rate set，不再受 `truncated`。
6. **契约不清空利率（核心）**：`assemble_borrow_validation` 的 `borrowability_truncated=True` 分支**保留** `daily_interest_account`、只清 `portfolio_account`、`error="borrowability_not_probed"`、`verified=False`、`checked_at` 保留。
7. **下游收口全**：前端第六态徽章（在 `not_probed_this_round` 之前）；`self-check.js` 六文案 + 旧态回归；`docs/api/public-market-contract.md` coverage/warnings 语义更新；coverage/warning 文案改。
8. **测试**：§4 的 4 个新增（含子集缺失不伪造、部分批失败）+ 3 个修改（尤其 `test_borrow_validation_truncated_state` 改为断言保留利率）全部到位且真实断言；`pytest backend/tests -q` 与 `node frontend/self-check.js` 全绿。
9. **边界纪律**：改动文件严格在 task-H §3 允许集内；无越界改动；Decimal 无 float；key 零片段；bStock 仍禁用；未 commit、未碰 status.json。

## verdict 字段填写约定

- `schema_version`: 1；`stage_id`: `2026-07-borrow-cost-coverage-v2`；`role`: `first_reviewer`；`model`: `kimi-code/kimi-for-coding`。
- `verdict`: `ACCEPT` / `REWORK` / `BLOCKED`。任一 P0/P1 未解决 → 不得 ACCEPT。
- `diff_fingerprint`: 预审阶段按工作树计算：`worktree:` + `sha256(git diff --binary <base_sha> -- . ':(exclude)reports/agent-runs/2026-07-borrow-cost-coverage-v2/status.json')` 的十六进制；base_sha 见 RECEIPT。（bookkeeper 落盘后会以 head_sha 重算对账。）
- `reviewer_prior_involvement`: `none`；`reviewer_prior_involvement_notes`: "kimi 执行 Gate B 端点摸排（证据采集），非本 stage 的 design/breakdown/implementation。"
- `reviewed_artifacts`: 列出实际读过的文件路径（至少 H.diff.patch + task-H + 10-design）。
- `findings`: 每项 severity(P0-P3)/title/file/line/evidence/impact/recommendation。
- `required_fixes`: REWORK 时列出必须修项（对应 §3 边界内的具体改动）。
- `fix_start_prompt`: REWORK 时必填——可直接发给 claude_glm 的有界 fix 提示，保留 findings/文件边界/测试命令/成功标准，不得只给摘要。
- `next_action`: ACCEPT→`continue`；REWORK→`fix`；无法判定/需人工→`human_gate`。

只输出该 JSON。

--- END PROMPT BODY ---
