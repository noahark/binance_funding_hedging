<!-- ============ RECEIPT（bookkeeper 回填；非任务内容） ============
status: pending            # pending | running | done
role: final_reviewer (review-2，stage 级)
target_model: codex (gpt-5.x)
adapter_cmd: codex exec -C <repo> -m gpt-5.5 -s read-only --output-schema schemas/review-verdict.schema.json - < <本文件>
invoked_by: bookkeeper（在 review-1 ACCEPT + 串行落盘后）
base_sha: 5bdfc4b3dc6843a8e52aeb86896c735500ed137a
head_sha: 11c3935ec859320b5dad50d31c0068993b4bd8f5
outputs: review-2-stage-by-codex.raw-output.json
======================================================================== -->

--- PROMPT BODY（不可变；只读评审） ---

你是 stage `2026-07-borrow-cost-coverage-v2` 的 **review-2（final_reviewer，stage 级独立复核）**。

## 执行纪律（硬）

- **只读**（adapter 已 `-s read-only`）。唯一产出 = 符合 `schemas/review-verdict.schema.json` 的单个 JSON 对象（adapter 用 `--output-schema` 约束）。
- review-2 是 stage 级最终技术复核：既查实现正确性，也查**流程/契约/独立性**，还要复核 bookkeeper 的关键设计决策。

## 评审对象

- 已落盘 diff：`git diff <base_sha>..<head_sha>`（head_sha 见 RECEIPT）。
- review-1 verdict：`embedded-review-H-round1.raw-output.md`（kimi）。
- 实现说明：`H.impl-note.md`。规格：`task-H-claude-glm.prompt.md` / `10-design.md` / `00-stage-plan.md`。
- 状态与披露：`status.json`（`model_routing` / `prior_involvement_disclosure` / `review_absorbed`）。
- Gate 证据：`gate-a-live.md`、`gate-b-endpoint-recon.md §9`。

## 必查清单

**A. 实现与契约闭合**
1. review-1 的 ACCEPT 是否成立；有无 kimi 漏判的 P0/P1。
2. 契约变更是否**全下游闭合**：backend `assemble_borrow_validation` ↔ schema `error` 枚举 ↔ `docs/api/public-market-contract.md` ↔ frontend 徽章 ↔ self-check ↔ 现有测试修改——任一处未同步即 REWORK（本 stage 反复强调"不拆层"）。
3. `borrowability_truncated=True` 保留利率、只清 portfolio；两态（`borrowability_not_probed` vs `borrow_rate_source=null`）可区分。

**B. bookkeeper 决策复核（务必给出结论）**
4. **未采纳 Opus 4.6 §3「整表缓存」建议**是否正确：确认逐片 `_cached_get` + 快照级 60s 缓存已足够，且整表缓存确会破坏"失败批 60s 自愈"。若你认为原建议其实更优，请以 P2+ finding 说明。
5. serial 模式**不跑** `validate-stage.py --phase dispatch-ready`、改 serial_handoff_checklist 是否可接受。

**C. 独立性与红线**
6. **prior-involvement 自评**：你（codex/GPT）撰写了**已被取代**的 DRAFT-1..3 fix-plan 草稿；本 stage 的活动设计（10-design=DRAFT-4、breakdown=stage-plan）由 Fable5 作，你非活动设计/breakdown/实现作者。请在 `reviewer_prior_involvement` 如实填写，并在 notes 说明；若你判断此历史参与已损害 review-2 独立性 → `verdict=BLOCKED` + `next_action=human_gate`，交用户改派。
7. 只读红线（零下单/借还/划转）、Decimal 无 float、key 零片段、bStock 仍禁用、单一写者（实现者未 commit/未碰 status.json）。

## verdict 字段填写约定

- `schema_version`:1；`stage_id`:`2026-07-borrow-cost-coverage-v2`；`role`:`final_reviewer`；`model`: 实际模型串。
- `verdict`: ACCEPT/REWORK/BLOCKED。
- `diff_fingerprint`: `<head_sha>:` + `sha256(git diff --binary <base_sha>..<head_sha> -- . ':(exclude)reports/agent-runs/2026-07-borrow-cost-coverage-v2/status.json')`。
- `reviewer_prior_involvement`: 如实（很可能为 `design`，因 DRAFT-1..3）；`reviewer_prior_involvement_notes`: 说明系"已被取代的 pre-stage fix-plan 草稿，非活动设计/breakdown/实现"，并给出独立性自评结论。
- `reviewed_artifacts` / `findings`(P0-P3) / `required_fixes` / `residual_risks`。
- REWORK → `fix_start_prompt` 必填（有界 fix 提示，保留证据路径与边界）。
- `next_action`: ACCEPT→`stage_accepted_waiting_user`；REWORK→`fix`；独立性受损或需人工→`human_gate`/`human_escalation_required`。

只输出该 JSON。

--- END PROMPT BODY ---
