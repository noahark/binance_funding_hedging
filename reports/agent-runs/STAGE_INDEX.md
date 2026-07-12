# Stage Index

Status: as-built index, 2026-07-12

This human-readable index summarizes `reports/agent-runs/*/status.json`. The
stage `status.json` files remain authoritative. The bookkeeper should update
this index when a stage reaches `stage_accepted_waiting_user`, is merged, is
abandoned, or when a retained pre-status or historical-reference directory is
identified.

## Indexed Stages

| Stage | Status | Stage branch | Merged to main | Note |
|---|---|---|---|---|
| `2026-07-public-market-contract-v2` | `stage_accepted_waiting_user` | none recorded | false | Historical public contract stage; later additive amendments are recorded in the API contract. |
| `2026-07-public-market-impl-v1` | `accepted` | none recorded | false | Public snapshot backend implementation accepted in the early manual run. |
| `2026-07-public-market-ui-cn-v1` | `accepted` | none recorded | false | Chinese workstation UI accepted; open items deferred to position-opening planning. |
| `2026-07-public-market-bstock-alias-v1` | `accepted` | none recorded | false | bStock alias route amendment accepted with the early public-market stages. |
| `2026-07-phase2-borrow-sort-v1` | `accepted` | none recorded | false | Borrow-aware sorting accepted; notes say delivered to main through commit chain. |
| `2026-07-private-account-v1` | `accepted` | `stage/2026-07-private-account-v1` | true | Optional private read-only account and borrow-validation channel accepted and merged. |
| `2026-07-private-account-ui-polish-v1` | `accepted` | `stage/2026-07-private-account-ui-polish-v1` | true | Private-account UI polish accepted and merged. |
| `2026-07-ui-filter-balance-metal-v1` | `accepted` | `stage/2026-07-ui-filter-balance-metal-v1` | true | Metal tagging and UI balance updates accepted and merged. |
| `2026-07-borrow-cost-coverage-v2` | `accepted` | `stage/2026-07-borrow-cost-coverage-v2` | true | Borrow-cost coverage accepted and merged. |
| `2026-07-borrowability-error-zero-mapping-v1` | `accepted` | `stage/2026-07-borrowability-error-zero-mapping-v1` | true | Borrowability `51061` zero mapping accepted and merged. |
| `2026-07-env-startup-v1` | `accepted` | `stage/2026-07-env-startup-v1` | true | Environment/startup stage closed. |
| `2026-07-harness-flow-optimization-v1` | `accepted_and_merged_to_main` | none recorded | false | Legacy status value recorded before the current status vocabulary tightened. |
| `2026-07-harness-manifest-itbm-sync-v1` | `accepted` | `stage/2026-07-harness-manifest-itbm-sync-v1` | true | Harness manifest / ITBM sync accepted and merged. |
| `2026-07-harness-friction-fixes-v1` | `stage_accepted_waiting_user` | `stage/2026-07-harness-friction-fixes-v1` | true | Source status says merged to main while still using the waiting status; leave for a future Harness cleanup. |
| `2026-07-harness-hardening-followups-v1` | `accepted` | `stage/2026-07-harness-hardening-followups-v1` | true | Harness hardening follow-ups accepted and merged. |
| `2026-07-harness-promotion-gate-upsync-v1` | `abandoned` | `stage/2026-07-harness-promotion-gate-upsync-v1` | false | Superseded by DEC-2026-07-10-002 before dispatch; evidence lives only on the unmerged stage branch. |
| `2026-07-funding-annualized-history-v1` | `accepted` | `stage/2026-07-funding-annualized-history-v1` | true | Funding annualized history accepted and merged to main (no-ff `4b29c69`). |
| `2026-07-auto-review-pipeline-v1` | `accepted` | `stage/2026-07-auto-review-pipeline-v1` | true | Auto review pipeline v1 accepted and merged to main (fast-forward `ef1a593`). Normative contract: `docs/auto-review-pipeline.md`. Design shells `10-design.md`/`11-adr.md` are superseded intra-stage by `16-serial-v1-slimming-design.md` + `19-model-routing-convergence-operator-decision.md` + `docs/auto-review-pipeline.md`; post-accept process evidence is under `history/`. |

Note: DEC-2026-07-10-002 (main `540513d`, 2026-07-10) rolled the canonical
Harness files back to the DRAFT-2 decision baseline (`41c6ba5`). The Harness
stages above remain historically accepted and merged, but the file-level
effects of `2026-07-harness-flow-optimization-v1` (§14 ITBM enablement),
`2026-07-harness-friction-fixes-v1`, `2026-07-harness-hardening-followups-v1`,
and the paste-first dispatch semantics were reverted on top of main. The
pre-rollback state is preserved at branch
`archive/harness-pre-rollback-2026-07-10`.

## Retained Pre-Status And Historical-Reference Directories

These directories have no `status.json` and are not active stages. They remain
at their existing paths for navigation and historical reference; `migrate: no`
does not imply that a directory is disposable.

- `2026-07-public-market-discovery` - index-only historical marker. `main`
  has no tracked stage files or `status.json`; local raw transcripts are
  gitignored. The abandoned Grok implementation package is preserved under
  `reports/archives/2026-07-03-grok-public-market-discovery/`. `migrate: no`.
- `2026-07-harness-quality-delivery` - early Draft proposal for quality-driven
  stage delivery and a conceptual predecessor to later stage-delivery framing;
  it is not a frozen acceptance record. `migrate: no`.
- `harness-parallel-mode-v1` - process-trial review evidence cited by
  `docs/parallel-development-mode.md` (`ADOPTED-TRIAL`). `migrate: no`.
- `2026-07-initial-direction` - frozen direction evidence, including the
  registered panel output referenced by `agents/registry.yaml`. `migrate: no`.
- `phase2-direction-v1` - frozen Phase 2 direction evidence. `migrate: no`.
- `private-account-v1-direction` - frozen private-account direction evidence.
  `migrate: no`.
- `2026-07-auto-review-pipeline-design-review` - frozen pre-delivery decision
  evidence (`40-operator-decision-table.md`) for the auto review pipeline. Not a
  standard stage (no `status.json`); the delivery stage is
  `2026-07-auto-review-pipeline-v1`. `migrate: no`.
