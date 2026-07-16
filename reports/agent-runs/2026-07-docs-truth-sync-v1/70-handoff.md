# Handoff

This file is the stage's active handoff context. A new terminal session reads
it together with `status.json` and only the needed workflow section; it does
not read `history/` at startup.

## Recovery Header

- Active phase: `review-1`（实现已提交、指纹已算、pre-review 门 PASSED，等 review-1）
- Next action: **操作者在 Kimi 终端执行 `35-dispatch-review-1-kimi.md` 的 PROMPT BODY**；
  Kimi 产出 `30-review-1.md`（含 schema-valid JSON verdict）后，bookkeeper 记录 verdict：
  ACCEPT→路由 review-2(Codex)；REWORK→用 fix_start_prompt 派 fix。
- 受审范围：`127a600..c72987d`，fingerprint `c72987d:bfd3106…`（pre-review PASSED）。
- 待 review-1 裁决的开放点：P1-9 bookticker `status.json` 是否需归一
  （见 `status.review_1_open_observations`）。
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
