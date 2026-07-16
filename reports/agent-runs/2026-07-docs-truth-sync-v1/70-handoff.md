# Handoff

This file is the stage's active handoff context. A new terminal session reads
it together with `status.json` and only the needed workflow section; it does
not read `history/` at startup.

## Recovery Header

- Active phase: `review_2`（round 5；用户裁定派 **Codex** 再审；opus4.8 转 bookkeeper）
- Next action: **操作者执行 `59-dispatch-review-2-codex-round5.md`（Codex 终审）**。
  ACCEPT→bookkeeper 跑 `--phase pre-accept`→`stage_accepted_waiting_user`→用户终审合并。
  REWORK→报用户（rework 已两次超限）。
- ✅ 路由约束已解：用户选 **Codex(openai)**（非 opus4.8），与所有 fix author
  （zhipu_glm、fable5/anthropic）跨厂商 → `validate-stage.py:717-718` 身份门通过；
  之前担心的 anthropic 身份红门因 opus4.8 不再是 reviewer 而消解。opus4.8 恢复 bookkeeper。
- 受审范围（新）：`127a600..e214d6f`，fingerprint
  `e214d6f819d76daa3b85865c1021b5aa2497ee95:d93ff6d4be65eda9882a6145e69a8dfcb346b854af38f40da79ff49f5cdf965e`。
- ⚠️ **路由约束（用户待决）**：用户曾表示 opus4.8 做下一轮 review，但
  `validate-stage.py:717-718` 硬规定 review_2 厂商身份必须 ≠ 所有 fix author 厂商身份、
  **无 override**。Fable5（anthropic）已是 round-4 fix author → opus4.8（anthropic）做
  正式 review_2 会永久红身份门。选项：(a) opus4.8 做用户侧非正式复核 + 正式 review_2
  仍由 codex（openai）对 e214d6f 执行；(b) 明知接受永久红门。记录于
  `status.user_authorizations[1].routing_constraint`。
- Round-4 结果（原文 `50-review-2.md`，Round-3 原文归档 `53-review-2-round3.md`）：
  Codex REWORK——**F9(P1)** offline `published_version: 0` 被误述为 PublishedState
  修订号（offline 不创建 PublishedState）；**F10(P1)** wire-visible warnings 清单漏
  `refresh_command_expired:<symbol>`；F11/F12(P2) 簿记同步缺口。
- Fix（rework 5，用户第二次超限授权 `status.user_authorizations[1]`，fix author 改派
  **Fable5**）：F9 合同改 mode-dependent（live=真实修订号 / offline=0 sentinel、
  row-from-same-PublishedState 限定 live）；F10 补 `refresh_command_expired:<symbol>`
  **并补 reviewer 漏列的 `base_raw_unavailable:<symbol>`**（`snapshot_service.py:1400-1404`
  同一序列化路径，独立复核发现）。6 命令全过（pytest 71 + 前端 80 + json.tool +
  diff-check + 边界）。fix commit `e214d6f`；详见 `40-fix-report.md` Round-4 段。
- F11/F12 已由 Fable5 以代理 bookkeeper 身份处理（opus4.8 拟转任 reviewer，不宜边记账
  边受审）：本 handoff 全文同步、status.json 补 Round-3/4 fix authors + 全部已完成模型
  session receipts + round-4 账目。
- ⚠️ RC4 假红门（已知，维持原样）：pre-accept 时 `review_1.diff_fingerprint(568fd41)` ≠
  `status.diff_fingerprint(e214d6f)` 会红——review-1 停在 round-3 ACCEPT，round-4 起
  review-1 被用户豁免（豁免不自动延伸，round-5 是否补 review-1 由用户随路由一并定）；
  如实记录、不伪造指纹。
- 历史：R1 REWORK(F1/F2/F3)→fix；R2 REWORK(F4/F5/F6)→fix；R3 REWORK(F7/F8)→fix（用户
  首次超限授权）；R4 REWORK(F9-F12)→fix（用户二次超限授权，fix author 改派 Fable5）。
  review-2 四轮原文存于 51-/52-/53-/50-。Codex 四轮都发现真实 doc-truth 缺陷。
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
- Status: `review_2`（round 5 待派发；rework 5，用户两次超限授权）
- Branch: `stage/2026-07-docs-truth-sync-v1`
- Base sha: `127a600281d60b7332be8aeb9552740a5e8c3254`
- Head sha（fix commit，受审）: `e214d6f819d76daa3b85865c1021b5aa2497ee95`
- Complexity: MEDIUM，lightweight route（用户批准，direction panel 跳过）
- Tests: pytest 71 passed + frontend self-check 80 PASS（round-4 fix 范围重跑）；
  纯文档 stage，产品无变更
- Review 历史：R1 Kimi ACCEPT→Codex REWORK(F1/F2/F3)；R2 Kimi ACCEPT→Codex REWORK
  (F4/F5/F6)；R3 Kimi ACCEPT→Codex REWORK(F7/F8)；R4 review-1 豁免→Codex REWORK
  (F9-F12)
- 待用户决策：round-5 评审路由（见 Recovery Header 路由约束）

## What Landed This Turn（Round-4 fix + 对账）

- `docs/api/public-market-contract.md`：F9 published_version live/offline 两分支 +
  F10 wire-visible warnings 补全（含 reviewer 漏列的 base_raw_unavailable）。
- `40-fix-report.md`：Round-4 段（发现→修复映射、独立复核证据、6 命令逐字输出、
  边界表、残余风险——含超范围披露：`snapshot_service.py:320-322` docstring 仍写
  same-version，backend Forbidden 不修，建议并入 deferred contract-amendment）。
- `50-review-2.md`：Round-4 codex 原文逐字落盘（自本地 codex rollout jsonl 恢复，RC9）；
  Round-3 原文先归档 `53-review-2-round3.md`。
- `status.json`：F12 补录（fix_authors R3/R4、session receipts 全员）、round-4 账目、
  新指纹、路由约束、rework 5。
- `70-handoff.md`（本文件）：F11 全文同步。
- `60-test-output.txt` / `62-validate-pre-review.txt`：Round-4 fix 验证与 pre-review
  validator 证据追加。

## Open Decisions（用户）

- **round-5 评审路由**：(a) opus4.8 非正式复核 + codex 正式 review_2（推荐，身份门可过）
  vs (b) opus4.8 正式 review_2 + 明知接受 validate-stage.py:717-718 永久红门。
  round-5 是否补 review-1（kimi）随路由一并定。
- D-A / D-B：已裁决（见 `status.linked_decisions`，Stage A/B 排期）。

## Next Steps

1. 用户裁决 round-5 评审路由并派发（对指纹 `e214d6f:d93ff6d4…`）。
2. Review ACCEPT → bookkeeper 跑 `--phase pre-accept`（已知 review_1 指纹落后 =
   授权豁免下的如实记录）→ `stage_accepted_waiting_user`。
3. 用户终审：批准 merge stage 分支回 main + push；ACTIVE 归位、STAGE_INDEX 待
   Stage B 生成化统一收口。

当前 Session ID: unavailable (Claude Code session id 未暴露)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-docs-truth-sync-v1/70-handoff.md
本地北京时间: 2026-07-16 23:20 CST
下一步模型: human（round-5 评审路由裁决）
下一步任务: 对新指纹派 round-5 review；其后 pre-accept → 用户终审
