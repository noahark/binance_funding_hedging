# Stage Index

Status: as-built index, 2026-07-10

This human-readable index summarizes `reports/agent-runs/*/status.json`. The
stage `status.json` files remain authoritative. The bookkeeper should update
this index when a stage reaches `stage_accepted_waiting_user`, is merged, is
abandoned, or is found to be legacy/unindexed.

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

## Legacy Or Unindexed Directories

These directories currently have no `status.json`. They are retained as
evidence or direction material and should not be treated as active stages unless
a future cleanup adds explicit metadata.

- `2026-07-harness-quality-delivery`
- `2026-07-initial-direction`
- `2026-07-public-market-discovery`
- `harness-parallel-mode-v1`
- `phase2-direction-v1`
- `private-account-v1-direction`
