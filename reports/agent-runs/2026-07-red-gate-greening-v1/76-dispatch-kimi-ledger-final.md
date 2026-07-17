# Dispatch — 纯账本收尾 commit（executor → Kimi）

依据: `74-review-fix-round-gpt5.6-sol.md`（REWORK，仅 2 P2 账本项）与
`75-review-fix-round-fable5.md`（Fable5 复核一致）。两路复审均确认实现实质零遗留——
本包**只做一个账本 commit**，不改任何实现代码、raw review、封印文件、产品文件，不 push。

## 修改项（单 commit 完成）

1. **第 0 步**：将 untracked 的 `74-review-fix-round-gpt5.6-sol.md`、
   `74-…verdict.json`、`75-review-fix-round-fable5.md`、本文件（76-）一并 add（与账本
   修正同一 commit 即可）。
2. **`status.json`（本 stage）**：
   - `known_state.fixture_final` 改为 `15 green + 1 green_with_exception + 8 registered
     known-red`，并明确本弧按用户 F3(a) **永久登记 known_red**（删除"补 receipts 后可
     转绿"一类表述）；
   - `session_receipts` 按 `docs/model-adapters.md` 契约归一：不可见 Session ID 用
     `null` + `session_id_source: "unavailable"` + 填 `unavailable_reason`；可见 ID
     保持原值且 `unavailable_reason: null`；全部补 `recorded_at`；Fable5 的 source 改用
     允许枚举值；新增 74（gpt5.6-sol，session 019f7065-f49c-75f1-999a-b40308b43bdd，
     source=runtime_env）与 75（fable5，id null，unavailable_reason=Claude Code 未暴露
     provider-native id）两条复审 receipt；
   - `current_phase`/`reviews_note`/`tests`/`updated_at` 同步到本检查点。
3. **`ACTIVE.json`**：phase 与两级 `updated_at` 同步。
4. **`70-handoff.md`（本 stage）**：checkpoint 更新到"双复审通过、待账本终检+用户终审"。
5. **`40-fix-report.md`**：追加 P2→修正映射段，并如实订正 diff-check 口径：
   `git diff --check 96f5b44..49529b3` 全范围 exit 2（命中全部为不可改写的 69 原文
   Markdown 尾随空格）；排除 69 后 exit 0；模板仓 exit 0。**不得改 69 原文。**

## 验证（命令+输出追加进 40 报告）

1. receipts 字段/枚举自检（对照 `docs/model-adapters.md`）；
2. `python3 scripts/validate-all-stages.py --repo-root . --compare
   reports/agent-runs/2026-07-red-gate-greening-v1/73-fixture-baseline-postfix-funding.json`
   → no drift、exit 0（模板仓同理对 73-…template.json）；
3. clean main 上 `python3 scripts/validate-stage.py 2026-07-bookticker-open-columns-v1
   --phase pre-accept` → PASS-with-exception；
4. `git diff --check 96f5b44..49529b3 -- . ':(exclude)reports/agent-runs/2026-07-red-gate-greening-v1/69-review-direct-fix-gpt5.6-sol.md'` → exit 0；
5. 两仓 `git status` clean、零 push。

完成即停。后续: fable5 + gpt5.6-sol 对该 commit 终检 → 用户终审 → 两仓 push、弧线闭合。

---
打包人: Fable 5（anthropic/claude-fable-5）
本地北京时间: 2026-07-18 02:15
下一步模型: kimi（单 commit 账本收尾）→ fable5 + gpt5.6-sol（终检）→ human（终审+push）
