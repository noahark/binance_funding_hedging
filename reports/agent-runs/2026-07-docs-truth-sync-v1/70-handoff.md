# Handoff

This file is the stage's active handoff context. A new terminal session reads
it together with `status.json` and only the needed workflow section; it does
not read `history/` at startup.

## Recovery Header

- Active phase: `fixing`（review-2 Codex = REWORK；rework 1/3；等 fix）
- Next action: **操作者在 Claude-GLM 终端执行 `45-dispatch-fix-claude-glm.md` 的
  PROMPT BODY**（Codex fix_start_prompt 原文，修 F1/F2/F3，写 `40-fix-report.md`，
  不 commit）。fix 回来后 bookkeeper：R4 diff 对账 → 更新 `60-test-output.txt` →
  重算指纹 → `validate-stage.py --phase pre-review` → **重派 review-1(Kimi) 再
  review-2(Codex)** 于修复后的范围。
- review-1：Kimi ACCEPT（`30-review-1.md`）。review-2：Codex REWORK
  （`50-review-2.md`，schema-valid，指纹匹配）。
- **三个必修（P1）**：F1 contract funding-history empty 语义过度承诺；F2 symbol-snapshot
  ok/partial/timeout 语义比代码窄；F3 P1-9 归一不完整（含 bookticker status.json，
  **review-2 覆盖 review-1 的保留裁决**）。
- fix 允许文件：`docs/api/public-market-contract.md`、bookticker
  `70-handoff.md`/`20-implementation.md`/`status.json`、新建 `40-fix-report.md`。
  禁改本 active stage 的 status/handoff/60-test（bookkeeper-only）与全部代码/schema。
- 平行未决（不阻塞本 stage）：用户按 Fable5 裁决排期 **Stage A（模板仓 first）=
  RC4 分任务指纹 + authorized_exception**（D-A 由此解决）。
- Read-set: = `status.current_inputs`
- Open blockers: None
- Do-not-read: `reports/agent-runs/**/history/**`, other stages

## Scope 收敛（本 stage 现在做 vs 延后）

- 现在做（仓内项目文档）：P0-2 契约 annualized+两端点、P0-3 follow-ups 死链、
  P0-4 DECISIONS source、P1-8 PRD、P1-9 bookticker living-docs 归一、P1-10 日期
  (PRD/ARCHITECTURE/DEVELOPMENT_GUIDE)、P1-11 dev guide 环境变量+测试。
- 延后 Stage B（生成化）：P0-5、P1-7(STAGE_INDEX/ROADMAP)、P1-13(manifest)。
- 延后 Harness 轨（模板仓 first）：P0-6、P2-14、P1-12、P2-16。
- 由 RC1 门驱动：P2-15(ADR)。 bookkeeper 直接：P2-17(记忆)。

## Current State

- Stage: `2026-07-docs-truth-sync-v1`
- Status: `planned`（intake 已落档，未进入实现）
- Branch: `stage/2026-07-docs-truth-sync-v1`
- Current branch: `stage/2026-07-docs-truth-sync-v1`
- Base sha: `127a600281d60b7332be8aeb9552740a5e8c3254`
- Complexity: MEDIUM，lightweight route（用户批准，direction panel 跳过）
- Tests: not_applicable（纯文档 stage，验收用 grep/validator 断言）

## What Landed This Turn

- `00-intake.md`：分类与路由。
- `00-task.md`：17 项 P0/P1/P2 backlog（四模型审计 + 本地复核，去重排序），
  含 D-A/D-B 两个待用户拍板项与文件边界。
- `status.json`：intake 状态、stage branch、audit sources、linked_decisions。
- `80-harness-design-rootcause.md`：导致文档不同步的 Harness 设计根因分析
  （交付给用户路由 Fable5 review）。
- `ACTIVE.json`：active 指向本 stage。

## Open Decisions（用户）

- D-A：bookticker `pre-accept` 红门处置（a 补审 / b 编码豁免 / c 记例外）。
- D-B：是否采纳 Harness 流程改动（需模板仓 first + Fable5 强评审）。

## Next Steps

1. 用户审阅 backlog 与根因报告。
2. 用户选 D-A，并决定文档收口的实现派工（domain owner：Claude-GLM 后端/契约文档，
   Kimi 前端相关文档；纯 canonical 文本可整体派单）。
3. 实现 → review-1 → review-2 → `stage_accepted_waiting_user` → 用户批准 promote
   + merge。

当前 Session ID: unavailable (Claude Code session id 未暴露)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md
本地北京时间: 2026-07-16 14:33:56 CST
下一步模型: human
下一步任务: 审阅 backlog + Harness 设计根因报告；选 D-A；决定派工
