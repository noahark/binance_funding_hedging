# Follow-Up Index

The source follow-up files remain authoritative. This index records whether an
item is resolved or remains open without rewriting the original follow-up
evidence.

## 2026-07-borrowability-51061-zero-mapping

Status: resolved.

Resolved by stage `2026-07-borrowability-error-zero-mapping-v1`, merged in
commit `c880a554721321c083136e6899027435a1bf4552`.

Source: `2026-07-borrowability-51061-zero-mapping.md`.

## 2026-07-ui-filter-balance-metal-v1-residuals

- R1: resolved by `2026-07-borrowability-error-zero-mapping-v1`; the
  `snapshot_service.py` comments now use `{CRYPTO, METAL}`.
- R2: open product fact. A METAL spot-leg live sample is required before the
  candidate path can re-enter review.
- R3: ignored by the original disposition. The report-artifact trailing
  whitespace requires no action.

Source: `2026-07-ui-filter-balance-metal-v1-residuals.md`.

## 2026-07-auto-review-pipeline

Status: **design decisions frozen** (not yet a Harness contract delivery stage).

| Artifact | Role |
|---|---|
| `2026-07-auto-review-pipeline-design-note.md` | Original design note |
| `2026-07-auto-review-pipeline-review-fable5.md` | Fable5 review of design note |
| `reports/agent-runs/2026-07-auto-review-pipeline-design-review/` | Codex design review, Fable divergence response, decision table, dual table reviews, patch merge |

**Authoritative freeze for intake:**

`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`

(Status: FROZEN — POST DUAL REVIEW. Next: open `2026-07-auto-review-pipeline-v1`
Harness stage from that table. Lives on branch `docs/2026-07-auto-review-pipeline`.)
