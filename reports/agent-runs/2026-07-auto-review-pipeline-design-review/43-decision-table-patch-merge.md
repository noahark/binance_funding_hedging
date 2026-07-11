# Patch Merge: Decision Table Dual Review → Frozen Table

Date: 2026-07-11  
Branch: `docs/2026-07-auto-review-pipeline`  
Author: Grok (mechanical merge for operator)

## Inputs

| Source | Verdict | Patches |
|---|---|---|
| `42-decision-table-review-gpt.md` | ACCEPT-with-edits | G1–G6 + P8 config note |
| `41-decision-table-review-fable5.md` | ACCEPT-with-edits | F1–F3 |

## Merge matrix

| Patch | Origin | Applied to frozen `40-…` |
|---|---|---|
| Seen-diff = patch byte equality; no status/verdict hash field | GPT G1 | Vocabulary **seen-diff bind** + D1 + P1 |
| Capture at cross-check, assert at seal; skip → N/A | Fable F2 | Vocabulary + D1 + D3 + §D flow |
| Review unit + author set + all serial units ACCEPT before R2 | GPT G2 | D2 |
| Tip-once Grok fail → human_escalation; serial cross-pool only if eligible | GPT G2 + Fable F1 | D7 |
| P7 auto-fix charges same auto ≤2 ledger | GPT G3 | D4 + P7 + §C |
| invalid_json_max_attempts_per_model = 2 unchanged | Fable F3 | §C |
| Multi-owner serial fix or isolated worktrees; unified re-seal | GPT G4 | P6 |
| Last-and-only schema-valid JSON block | GPT G5 | P3 |
| P13 untrusted inputs + RECEIPT secrets | GPT G6 | P13 |
| P8 as required per-stage config, no global numbers | GPT note | P8 + §F deferred |

## Conflicts between reviewers

**None.** All patches are complementary. No operator arbitration remaining on
this table.

## Result

`40-operator-decision-table.md` status set to  
**FROZEN — POST DUAL REVIEW (GPT + Fable5 ACCEPT-with-edits merged)**.

Suitable as sole requirements source for `2026-07-auto-review-pipeline-v1`
`00-intake.md`.

```text
本地北京时间: 2026-07-11 11:21:54 CST
下一步模型: human 或 GPT bookkeeper
下一步任务: 开 2026-07-auto-review-pipeline-v1 intake
```
