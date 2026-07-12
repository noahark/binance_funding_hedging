# Handoff — 2026-07-auto-review-pipeline-v1

## Current State

- Status: **`accepted`** — user acceptance recorded; stage branch
  **fast-forwarded to `main`**.
- Current branch: `main`.
- Stage branch merge point: `ef1a593844af65436fda2b355bb4b47650d630f6`.
- Merge strategy: `fast_forward`.
- T4 review base: `039358012174af949c9f17a94c96bd3ac085a35f`.
- T4 delivery head: `433980d8384304a528ab5633591aa8dc4018b6ed`.
- Recorded fingerprint:
  `433980d8384304a528ab5633591aa8dc4018b6ed:5316c5dee336354eacc762af913f1cb6cadcb73f13b1dadfc5536e8686b3ca97`.
- Auto mode was **not** self-hosted on this bootstrap stage
  (`enabled_for_this_stage=false`).
- Historical `rework_count` remains 3/3; serial-v1 slimming was a separate
  operator-authorized amendment, not rework 4.

## What Landed On Main

Serial-only auto-review pipeline v1:

- remove unimplemented auto parallel worktrees / tip / integration units;
- remove redundant authorization fields;
- remove total runner-session wall clock (per-adapter registry timeouts only);
- cold-history + startup read budget;
- model routing convergence: Codex `gpt-5.6-sol`, Grok `grok-4.5` (dev+review),
  Claude remains `claude-fable-5` + fallback `opus4.8`.

Normative contracts: `docs/auto-review-pipeline.md`,
`workflows/templates/stage-delivery.yaml`, `agents/registry.yaml`, `AGENTS.md`.

## Startup Read Budget

1. `AGENTS.md`
2. `workflows/templates/stage-delivery.yaml`
3. this stage root `status.json` and this handoff
4. only `status.json.current_inputs` (design authority paths)

Do **not** recursively read `history/` at startup. Compatibility symlinks at
former root paths still resolve; open raw files only for named audit/review.

## Active Root Design Authority

- `54-p8-wall-clock-withdrawal-operator-decision.md`
- `16-serial-v1-slimming-design.md`
- `12-serial-v1-slimming-development-breakdown-codex.md`
- `19-model-routing-convergence-operator-decision.md`
- `15-p8-wall-clock-withdrawal-design-amendment.md`
- `00-task.md`
- lineage shells: `10-design.md`, `11-adr.md` (see serial-v1 amendment first)

## History Archive (two passes)

1. Pre-slimming: 67 artifacts → `history/raw/` + symlinks.
2. Post-accept process pass (2026-07-12): **20** additional closed process
   artifacts (T4 prompts/verdicts, `20-implementation.md`, gate logs `61–65`,
   intermediate inspections, short `30-review-1`/`50-review-2` stubs) →
   `history/raw/` + symlinks. Snapshots under `history/snapshots/`.

Provenance: pass-2 archive content is committed as `6212c5a` (A1) and bound in
`status.json.history_archive.post_accept_archive.content_commit`. The T4 delivery
checkpoint stays `433980d` (`combined_serial_v1_delivery_evidence`,
`post_merge_pre_accept`, `passed`).

Root real files now: design authority + `status.json` + handoff +
`60-test-output.txt` (~11 files). Process evidence remains path-compatible via
symlinks.

## Roles (historical for this stage)

- Bookkeeper/designer/breakdown: Codex (dual-hat disclosed; not final accept).
- Implementer: Claude-GLM; model-routing convergence also via Grok Fast.
- Review-1 T4: Kimi ACCEPT.
- Review-2 T4: Opus 4.8 ACCEPT (unrelated reviewer).

## Next Action

Stage delivery is complete on `main`. Optional follow-ups (docs nav cleanup,
first docs-only / small-real auto pilot) are **new work**, not open T4 fixes.

本地北京时间: 2026-07-12 15:11:00 CST
下一步模型: human
下一步任务: 可选：修 STAGE_INDEX / follow-ups README 等导航语义；或开首个 auto pilot stage
