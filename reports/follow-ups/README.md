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

Status: **delivered on `main`** via stage
`2026-07-auto-review-pipeline-v1` (`accepted`, fast-forward merge).

Normative contract (current): `docs/auto-review-pipeline.md` (with
`AGENTS.md`, `workflows/templates/stage-delivery.yaml`, `agents/registry.yaml`).

| Artifact | Role |
|---|---|
| `2026-07-auto-review-pipeline-design-note.md` | **Historical** original design note (pre-delivery) |
| `2026-07-auto-review-pipeline-review-fable5.md` | **Historical** Fable5 review of design note (stale model/wall-clock claims may remain in body) |
| `reports/agent-runs/2026-07-auto-review-pipeline-design-review/` | **Historical** decision freeze evidence (`40-operator-decision-table.md`) |
| `reports/agent-runs/2026-07-auto-review-pipeline-v1/` | **Delivery stage** (accepted + merged); process evidence under `history/` |

Former freeze pointer (still valid as design archaeology):

`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`

## 2026-07-post-main-docs-hygiene-and-semantic-conflicts

Status: **proposed plan** under cross-model review (not yet an approved fix
stage). Treat the unamended S1–S9 list as **superseded for execution** by the
cross-review synthesis until the operator decides otherwise.

Source: `2026-07-post-main-docs-hygiene-and-semantic-conflicts.md`.

Contains: post-accept history archive record, scatter inventory, semantic
conflict table (C1–C7 + leave-alones), and original priority fix plan S1–S9.

### Cross-model review set (2026-07-12)

| Artifact | Role |
|---|---|
| `2026-07-post-main-docs-hygiene-codex-semantic-sync-plan.md` | Codex: layering, A1/A2 commit split, Batch B nav scope |
| `2026-07-docs-sync-method-opus4.8.md` | Opus 4.8: single-home SoT, accept ritual, A1/A2 vs original plan |
| `2026-07-post-main-docs-hygiene-and-semantic-conflicts-glm52-counterproposal.md` | GLM-5.2: authority-order fidelity, C4 split, P0/P1/P2 + lint stage |
| `2026-07-post-main-docs-hygiene-grok-cross-review.md` | **Grok cross-review synthesis** — verdicts, amendments, Batch 0→A→B→C→D |

**Execution authority:** operator only. Cross-review files do not authorize
commit, push, or model dispatch.
