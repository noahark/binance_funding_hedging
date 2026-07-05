# Review-1（stage-level 汇总）— 2026-07-phase2-borrow-sort-v1

> 本文件是 **stage-level review-1 汇总**（`validate-stage pre-accept` required file）。
> task-level 详评见 `30-review-1-backend.md`（round-1）/ `30-review-1-frontend.md`
> （round-1）/ `30-review-1-round2-backend.md`（round-2）。并行模式（ADOPTED-TRIAL
> 首试）保留 rounds 细粒度记录；本文件为扁平 stage-level verdict（gate 兼容）。

## 元信息

- gate：review_1
- stage-level verdict：**ACCEPT**（两 task 最终均 ACCEPT）
- status：`both_tasks_ACCEPT`
- role：`first_reviewer`（schema 合规——枚举无 second_reviewer，模板 T1/T2 笔误）
- 绑定 diff_fingerprint（final）：`2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9`
- json_schema_valid：true（三份 round verdict 均 schema 合规）

## Task A（backend）← fresh Kimi

- **round-1**（`session_bfdbafa6`）：**REWORK**，P1 = live `/fapi/v1/fundingInfo` 失败
  不降级（违反 design §2 E1「缺省全 8h + warning」）。绑定 round-1 head
  `cc25148:9dc905d5...`。详评 `30-review-1-backend.md`（含 fix_start_prompt）。
- **E1 fix** H_A2 `2a793a9`：`_fetch_live` fundingInfo try/except 降级 + 空 dict +
  warning；`assemble_snapshot` 加 `extra_warnings`（additive，schema 开放 array 未改）；
  `snapshot_service` 透传；新测试 `test_live_fundinginfo_failure_degrades_to_8h_with_warning`。
- **round-2**（fresh `session_bc79ad49` ≠ round-1）：**ACCEPT**。绑定 final head
  `2a793a9:9b92cc45...`（三方 MATCH：reviewer 重算 = bookkeeper 重算 = status.json）；
  reviewer **独立重跑** 96 passed + 20 PASS；fix 仅触 4 文件，零回归。详评
  `30-review-1-round2-backend.md`。

## Task B（frontend）← fresh Claude-GLM

- **round-1**（fresh plan-mode）：**ACCEPT**，2× P3 非阻塞（self-check 回归网收窄 F1 +
  role 模板 bug F2）。backend-only fix 不影响 frontend，**无需 round-2**。详评
  `30-review-1-frontend.md`。

## bookkeeper 独立核实

- 指纹演进清晰：round-1（cc25148:9dc905d5）→ E1 fix → round-2/final
  （2a793a9:9b92cc45）。stage-level 绑定 final 指纹。
- 两 reviewer 独立标记模板 `role=second_reviewer` bug（schema 枚举无此项），均采合规
  `first_reviewer`。
- A 的 P1 finding 经 bookkeeper 独立核实成立（design §2 E1 要求降级，原 live 分支漏降级）。

## stage-level verdict JSON（schema 合规）

```json
{
  "schema_version": 1,
  "stage_id": "2026-07-phase2-borrow-sort-v1",
  "role": "first_reviewer",
  "model": "kimi (Task A, round-1+round-2) + claude_glm (Task B, round-1)",
  "verdict": "ACCEPT",
  "diff_fingerprint": "2a793a9c35e8e5fe8cdebe8875cada9b85f335d0:9b92cc4595982f0e09ce33d179019fa54a370aa30aeeaa977772eca33fb433e9",
  "reviewer_prior_involvement": "none",
  "reviewer_prior_involvement_notes": "Task A reviewed by fresh Kimi sessions (round-1 bfdbafa6, round-2 bc79ad49); Task B by fresh Claude-GLM plan-mode session. None participated in direction synthesis, breakdown, design, or implementation. Stage-level verdict aggregates both tasks (both final ACCEPT).",
  "reviewed_artifacts": [
    "30-review-1-backend.md (Task A round-1 REWORK + fix_start_prompt)",
    "30-review-1-frontend.md (Task B round-1 ACCEPT)",
    "30-review-1-round2-backend.md (Task A round-2 ACCEPT after E1 fix)",
    "git diff 4d47ad2..2a793a9 (final, includes H_A2 E1 fix)"
  ],
  "findings": [
    {
      "severity": "P1",
      "title": "[Task A round-1, RESOLVED] live /fapi/v1/fundingInfo failure did not degrade to 8h+warning",
      "file": "backend/adapters/binance_public.py",
      "evidence": "round-1 _fetch_live had no try/except around fundingInfo GET; live failure propagated (503), violating design §2 E1. Fixed in H_A2 2a793a9; round-2 ACCEPT confirmed resolution.",
      "impact": "Resolved before acceptance.",
      "recommendation": "N/A (fixed + re-reviewed)"
    },
    {
      "severity": "P3",
      "title": "[Task B round-1, non-blocking] self-check regression net narrowed after design-fixture switch",
      "file": "frontend/self-check.js",
      "evidence": "Switch to inline designFixture dropped legacy BSTOCK/alias/PERP_ONLY assertions.",
      "impact": "Residual risk only; backend classify/normalize tests + unchanged index.html mapping backstop.",
      "recommendation": "Optional future: retain secondary real-fixture assertion path."
    }
  ],
  "required_fixes": [],
  "residual_risks": [
    "Frontend self-check coverage narrower for legacy BSTOCK/alias/PERP_ONLY cases (Task B P3).",
    "ADR-5 bounded-portfolio strategy may leave portfolio_account null under current market (design §3.4, not an implementation defect)."
  ],
  "next_action": "continue"
}
```

---

本地北京时间: 2026-07-05 08:45 CST
落档: bookkeeper (claude_glm)；stage-level 汇总，task-level 详评见上述三份 30-review-1-*.md
