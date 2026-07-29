# Project State

This small file holds facts that remain relevant across stages. It is read at
startup, so keep it current and under roughly 2 KB. Stage Recorder is the normal
writer. Implementers and reviewers report facts through `TASK_RESULT`; they do
not edit this file.

## Live Risks

- `[OPEN][RUNTIME-UNVERIFIED]` Repository records dated 2026-07-28 say the
  durable Start gate was open and a real naked `SHORT 10000 NOMUSDT`
  (`orderId 888412130`) remained outstanding after the 2026-07-27 live
  acceptance run. The same records say the system had no close function.
  This branch has not queried the current exchange or runtime state, so this is
  last-known evidence, not a claim about the live state now. Before any further
  live action, an authorized runtime check must establish the current gate and
  position state. Evidence: historical
  `reports/agent-runs/ACTIVE.json` at commit
  `5c6ac65be1647dc171274bcc3d935420560faa90`,
  `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/18-live-acceptance-findings.md`.

## Open Follow-ups

- `[OPEN]` The next order-truth work must address F-1 through F-4 from the live
  run and persist raw order-placement responses plus full order-detail query
  responses. Source:
  `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/18-live-acceptance-findings.md`.
- `[OPEN]` Five non-blocking P3 follow-ups remain to be migrated into the next
  applicable stage. Their authoritative details remain in
  `reports/agent-runs/2026-07-hedge-open-live-hardening-v1/status.json`
  under `stage_followups`.

## Last Completed

- stage: `2026-07-hedge-open-live-hardening-v1`
- archive_ref: `c8b6bbe`
- recorded_completed_at: `2026-07-28T01:45:00+08:00`

## Update Rule

Record a newly verified live incident immediately; do not wait for stage
completion. Always distinguish repository-recorded history from a current
runtime check. Remove resolved risks and migrated follow-ups instead of growing
this file into a changelog.
