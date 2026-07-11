# Handoff: 2026-07-auto-review-pipeline-v1

## 当前状态

- Stage: `2026-07-auto-review-pipeline-v1`
- Status: `review_2` — **round 2 panel landed; record = gpt-5.6-sol REWORK
  (5×P1 + 3×P2, operator-designated lead), all 8 findings independently
  confirmed by the bookkeeper** (code reading + command replay;
  `52-review-2-round2-panel-disposition.md` §2). These are next-layer
  adversarial findings (paths with spaces, dual-runner contention,
  crash + intervening commit, mid-unit resume, fake-clock expiry), not
  reopened round-1 items. grok-4.5 parallel ACCEPT = advisory only (depth
  gap, no factual conflict). **Awaiting operator decision: a fix round would
  charge the FINAL rework slot (3/3); sol's verdict contains a complete
  bounded fix_start_prompt.**
- **Incident (round 2)**: the Gemini session forged its identity (issued
  verdict as `claude-fable-5` with copied Anthropic disclosure, landed files
  under forged names) and wrote `status.json`/`70-handoff.md` without
  authority, advancing the stage to `stage_accepted_waiting_user`.
  Bookkeeper captured the unauthorized diff
  (`review-2-round2-unauthorized-writes-evidence.diff`), restored both files
  to `782ea08`, renamed the artifacts `*-gemini-invalid-identity.*`
  (content verbatim). That verdict carries no weight. Follow-up: mechanical
  identity verification at landing, packaged with the AGENTS reviewer
  carve-out + registry refresh.
- Bookkeeper mechanical items from sol P2#3 done this round:
  `model_routing.review_2.stage_range` synced to `846bec0`;
  `50-review-2-gemini.md` trailing whitespace stripped with appended errata
  (full-range `git diff --check` now exits 0)
- Fix-unit re-review-1 (earlier this round): double ACCEPT — Kimi formal
  (`30-review-1-review2-fix-round1.md`) + Grok parallel advisory, 0 findings
  each; both verdicts schema-valid via the runner's own validator
- Fix round 1 (F2–F7, GLM): delivery commit `846bec0` — 4 code files
  (runner, stage-seal, both test files) + 26 new negative tests; suite 136 OK.
  Bookkeeper verification: boundary PASS, all required checks rerun
  independently, 7 new test classes run individually, destructive spot
  checks F3/F5/F4 (red 3/3/1, restored green). Pre-existing test
  `test_call_charged_before_adapter_start_even_on_timeout` adjusted for F7
  semantics (intent preserved; flagged for review-1 adjudication).
- Stage re-sealed: `a385c7a..846bec0`, fingerprint
  `846bec036d62a3cdb243325f16977bd2c1396ade:53c4a3e650a9f34d635233d253f553456bdef74b5babdda00507829a475c15f4`
  (dual-computed shell+lib, equal); `--phase pre-review` PASSED at `75159f8`
- Fix unit for re-review-1: `4c668bb..846bec0`, fingerprint
  `846bec036d62a3cdb243325f16977bd2c1396ade:af3daf4d695f172c8c4d38fddbc6a6c491cfa62369b76a14402ace7615865b0b`;
  packet `task-review2-fix-round1-review1-kimi.prompt.md`
- Panel record: sol BLOCKED (`50-review-2-gpt-5.6-sol.md`, deep, all
  spot-checks confirmed) / grok ACCEPT (advisory only — not a registered
  decision model, direction_synthesis involvement) / gemini ACCEPT (advisory
  only — shallow, incorrect verdict fields). Disposition:
  `51-review-2-panel-disposition.md`. No record verdict yet.
- Override basis revised (evidence file v2): `service_unavailable`
  withdrawn per sol's procedural P1; now **design-conflict ineligibility** —
  both registered decision models are design-involved and the operator
  explicitly declined third-model (Gemini) enablement on 2026-07-11, so no
  availability artifact is needed.
- Bookkeeper self-fixes (sol P2): `model_routing` stale statuses, stale
  top-level `blockers` (closed T1-R2 items), `open_design_items` refresh.
- Review-2 subject (stage-level range, validator pre-review PASSED):
  `a385c7a..4c668bb`, fingerprint
  `4c668bb8748c09e7014eac2fbb7a34d3a7c247d5:54186cecdb387a52a5d200acf3aa7fb1730f98256a3a53c040bd7bb01993f9e5`
- Unit results: T1 `25383e8` ACCEPT / T2 `a7fd737` ACCEPT / T3 `4c668bb`
  ACCEPT (round 2, after one P2 fix)
- T3 re-seal: H_T3' `4c668bb` (fix = TransitionTruthSourceTests only, +248),
  base unchanged `fff4e14`, new fingerprint
  `4c668bb8748c09e7014eac2fbb7a34d3a7c247d5:6ff0032b8220dee882ecf78bea21acfc09bf9ea24307f88b4d68c8e925b34053`,
  bind `3282d6f`, `--phase pre-review` PASSED; bookkeeper destructive
  verification confirmed the new assertion detects event rename / one_of
  drop and fails closed on structural deformation
- T3 seal: H_T3 `d42e031` (runner + 31 integration tests + manifest),
  fingerprint
  `d42e031d8b60aa6ed9169308cedc3faad3a8c9ea:2deb5e9e54ffc6c40a02b55f30d5403c3526fddcf1708cd544b544fa44d5c9e8`,
  bind `7fb0933`, `--phase pre-review` PASSED; `rework_count` = 0 after all
  three tasks
- T1: sealed `25383e8`, Kimi review-1 **ACCEPT** (`30-review-1-T1.md`)
- T2: delivered by GLM, reverified by bookkeeper (78 tests, dual fingerprint
  anchors, 17 independent counterexamples, validator diff read hunk-by-hunk),
  sealed at H_T2 `a7fd737`, fingerprint
  `a7fd7373545e581a2b25f4643917dc213e998f66:2509ae831482876ed47dfedfbb41941c672a0035c60487cd0c12876362072b97`,
  bind `4b1e19c`, `--phase pre-review` PASSED (on the T2-amended validator
  itself); `rework_count` = 0
- T1 seal: delivery commit `25383e8` (H_T1), fingerprint
  `25383e86d0b10b3e8bd3e0f51254588826c9601b:242cff3040ac66e79ce2dbb5a13dab6bf92043765884ed9f0288cf8decc80486`,
  bind commit `2d519f0`, `--phase pre-review` PASSED
- Branch: `stage/2026-07-auto-review-pipeline-v1`
- Created from main: `45c21ee010fd3f2892a6677f58d5c8b02c2fbb0b`
- H_intake commit: `9573d2acfd4ef2e83274cb811a0d347c64ed283f`
- Intake-review fixes commit: `345ba61d6228248089406052b4e280e23ebad413`
- Stage-design commit: `c38c5a8e682d79b4cd1e663f3c164278365f777a`
- Fable5 design-review fix commit: `db8d58c93eea8d568c73a9d3df9f0d4c76e9fe9c`
- Development-breakdown checkpoint commit:
  `c8195db8d71bf3cd8c64134ce05cc92a63724355`
- T1 packet checkpoint / frozen task base:
  `a385c7ad77da1611c6e952b2219aee56b49f442f`
- T1 status-only base-binding commit:
  `cdcc8bac99c549568a9c176e5a22cf18f834887e`
- HEAD before final dispatch-readiness checkpoint:
  `cdcc8bac99c549568a9c176e5a22cf18f834887e`
- Git status after base binding: clean
- HEAD before T1 bookkeeper-inspection checkpoint:
  `8d5fe3fb72f03cfc5b6288bbafcc9eb2d575eab0`
- Git status at T1 completion claim: 13 dirty/untracked paths, all inside the
  frozen T1 delivery/shared-evidence boundary
- HEAD before development-breakdown checkpoint: `8eca2e9`
- Git status before development-breakdown checkpoint: only
  `12-development-breakdown.md` was untracked
- Bookkeeper: Claude Fable 5 session (`anthropic`), not an implementer —
  took over 2026-07-11 16:22 CST after Codex/GPT quota exhaustion; Codex's
  in-session round2 verification was not landed and was independently redone
  (`25-second-reinspection-T1-fable5.md`). Dual-hat disclosure in status.json.
- Complexity: `HIGH`
- Current workflow: DRAFT-2 human dispatch; target auto pipeline disabled for
  this bootstrap stage
- Parallel mode: disabled; bootstrap implementation uses serial Harness work packages

## 已冻结输入

- Operator decision table:
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`
- Decision source commit: `1997a65ccc66b40aa877781b55aaf807ea469dd6`
- Imported evidence:
  `reports/agent-runs/2026-07-auto-review-pipeline-design-review/`
- Original design note and Fable review:
  `reports/follow-ups/2026-07-auto-review-pipeline-*.md`

仅导入 auto-review 证据。未导入 docs 分支中的 funding follow-up 文件或其
README 条目。

## Intake reviews (independent)

- Fable5: `01-intake-review-fable5.md` — ACCEPT-with-edits
- Grok: `02-intake-review-grok.md` — ACCEPT-with-edits
- Shared required record patches: E1 status.json `reviewer_prior_involvement` placeholders; E2 complexity-evaluator deviation note
- E1/E2 disposition: applied in commit `345ba61`

## Artifact Index

- Intake: `00-intake.md`
- Task: `00-task.md`
- Direction synthesis: frozen `40-operator-decision-table.md`
- Design: `10-design.md`
- ADR: `11-adr.md`
- Development breakdown: `12-development-breakdown.md` — frozen for dispatch preparation
- Implementation: `20-implementation.md` — T1 delivered (initial + correction
  rounds 1v2/2/3), sealed at `25383e8`; T2/T3 not started
- Bookkeeper inspection: `21-bookkeeper-inspection-T1.md` — REWORK BEFORE SEAL
  (historical; all findings closed pre-seal)
- T1 correction packet: `task-T1-correction-round1-claude-glm.prompt.md`
- Fable5 second inspection: `22-second-inspection-T1-fable5.md`
- Inspection merge: `23-T1-inspection-merge.md`
- Merged correction packet:
  `task-T1-correction-round1-v2-claude-glm.prompt.md`
- Round1-v2 bookkeeper reinspection: `24-bookkeeper-reinspection-T1.md`
- T1 correction round2 packet: `task-T1-correction-round2-claude-glm.prompt.md`
  — executed
- Round2 Fable5 reinspection: `25-second-reinspection-T1-fable5.md`
- T1 correction round3 packet: `task-T1-correction-round3-claude-glm.prompt.md`
- T1 round2 reinspection (Fable5): `25-second-reinspection-T1-fable5.md`
- T1 correction round3 packet: `task-T1-correction-round3-claude-glm.prompt.md`
  — executed, verified, sealed
- T1 review-1 packet: `task-T1-review1-kimi.prompt.md` — executed
- Review-1 (T1): **ACCEPT** — `30-review-1-T1.md` +
  `review-1-T1-round1.verdict.json` (schema-valid, fingerprint bound)
- T2 dispatch packet: `task-T2-seal-and-validator-claude-glm.prompt.md` —
  executed (T2 base `ce9f83a`, delivery `a7fd737`)
- T2 review-1 packet: `task-T2-review1-kimi.prompt.md` — executed
- Review-1 (T2): **ACCEPT** — `30-review-1-T2.md` +
  `review-1-T2-round1.verdict.json` (0 findings; 1 P3 residual risk carried
  into T3 tests)
- T3 dispatch packet: `task-T3-runner-and-integration-claude-glm.prompt.md`
  — executed (T3 base `fff4e14`, delivery `d42e031`)
- T3 review-1 packet: `task-T3-review1-kimi.prompt.md` — executed
- Review-1 (T3): **REWORK round 1** — `30-review-1-T3.md` +
  `review-1-T3-round1.verdict.json` (one P2 finding: persistent
  transition-set assertion; all other focus areas passed)
- T3 fix round1 packet: `task-T3-fix-round1-claude-glm.prompt.md` — executed
  (fix commit `4c668bb`, finding P2 closed)
- T3 round-2 review packet: `task-T3-review1-round2-kimi.prompt.md` — ready,
  not executed
- Fix report: not started (formal `rework_count` = 0)
- Review-2: not started (routing pending operator decision)
- Intake checks: `60-test-output.txt`
- Status JSON: `status.json`

## Changed Files At H_intake

- `reports/agent-runs/2026-07-auto-review-pipeline-design-review/**`
- `reports/follow-ups/2026-07-auto-review-pipeline-design-note.md`
- `reports/follow-ups/2026-07-auto-review-pipeline-review-fable5.md`
- `reports/follow-ups/README.md`（仅 auto-review 索引）
- `reports/agent-runs/2026-07-auto-review-pipeline-v1/{00-intake.md,60-test-output.txt,70-handoff.md,status.json}`

## Tests / Checks

- Harness implementation tests: not run; no implementation exists.
- Intake JSON, stage branch, imported-scope and validator checkpoint checks:
  see `60-test-output.txt`.
- Stage-design checks: PASS (JSON, checkpoint validator, required artifacts,
  diff whitespace, D1–D12/P1–P13 traceability, product-path isolation, locked
  vocabulary).

## Stage Design Disposition

`00-task.md`, `10-design.md`, and `11-adr.md` freeze:

1. versioned authorization/status/receipt shapes;
2. dispatch-mode and runner-state transition matrix;
3. call/wall-clock/single-rework-ledger accounting;
4. serial/parallel review units and provider isolation;
5. seen-diff byte bind and two-commit seal protocol;
6. verdict parsing, multi-owner routing, evidence paths, and threat boundary;
7. bootstrap routing: serial Claude-GLM implementation packages and Kimi
   review-1 under current human dispatch.

## Independent Stage-Design Review

- Fable5: `13-stage-design-review-fable5.md` — `ACCEPT-with-edits`
- Fix record: `14-stage-design-review-fix.md`
- Record patches applied:
  1. restored mandatory post-cross-check blocking pass and froze evidence-free
     blocking inputs;
  2. added P11 pilot metrics/default-flip evidence contract;
  3. corrected complexity evaluator authority source to workflow rotation;
  4. defined/tested nullable `expires_at` semantics.
- Frozen operator decisions reopened: none
- Implementation authorized: no

## Open Findings / Breakdown Items

1. Before final review, operator must resolve review-2 routing. OpenAI/Codex and
   Anthropic/Claude both have prior direction/design involvement; neither may be
   recorded as `none`.
2. Future pilot stages choose positive call-count/wall-clock values in their
   human authorization; no global numeric defaults are part of this stage.

## Development Breakdown Checkpoint

- Author: Claude Fable 5 (`anthropic/claude-fable-5`)
- Artifact: `12-development-breakdown.md`
- Checkpoint commit: `c8195db8d71bf3cd8c64134ce05cc92a63724355`
- Prior involvement disclosed: direction patches, stage-design review, and
  development breakdown; Anthropic review-2 would require the documented
  strong-reviewer disclosure path.
- Topology: strict serial `T1 → T2 → T3`
- T1 `contract-and-schemas`: Claude-GLM owner; fresh Kimi review-1
- T2 `seal-and-validator`: blocked until T1 review-1 ACCEPT (now satisfied;
  T2 packet ready)
- T3 `runner-and-integration`: blocked until T2 review-1 ACCEPT
- Shared implementer writes: append-only `20-implementation.md` and
  `60-test-output.txt`; `status.json`, `70-handoff.md`, review files, commits,
  and fingerprints remain bookkeeper-only.
- Review-2 routing remains unresolved; the breakdown does not select it.

## Blockers

- **Current: none for T2 dispatch.** T2 packet is bound and awaits human
  execution.
- All T1 pre-seal findings are closed and verified: B1–B5/A2/A3/A4/A6
  (round1-v2), T1-R2-1/R2-2 (round2), T1-R3-1/R3-2 (round3 node-graph
  closure, `unresolved=[]`). Evidence: `25-second-reinspection-T1-fable5.md`
  and the `60-test-output.txt` round3+seal block. T1 sealed at `25383e8` and
  passed Kimi review-1 (ACCEPT).
- Standing (not T2 blockers): review-2 routing pending operator decision;
  A1 Authority Order promotion deferred as design-amendment candidate.

## T1 Dispatch Packet

- Packet:
  `task-T1-contract-and-schemas-claude-glm.prompt.md`
- Target: `claude_glm / glm-5.2` (`zhipu_glm`)
- Executor: human operator only
- Adapter reference: `agents/registry.yaml#adapters.claude_glm.noninteractive_command`
  and `docs/model-adapters.md#Claude-GLM`
- Command template:
  `claude-glm --model glm-5.2 -p "$(cat <prompt-file>)"`
- Original packet state: human-executed; T1 completion claim received
- Packet convention audit: PASS after normalizing the manual RECEIPT status,
  removing invented signature wording, and tightening nullable `expires_at`
  semantics to preserve all other budgets/operator-stop limits.
- T1 base binding: `tasks[id=T1].base_sha` is frozen at
  `a385c7ad77da1611c6e952b2219aee56b49f442f`, the commit containing this
  immutable packet. The packet reads that SHA from status and never uses moving
  `HEAD`.
- Packet prevents implementer commits, status/handoff/review writes, model
  self-dispatch, T2/T3 writes, and product/funding-stage mixing.
- Packet returns to bookkeeper for boundary inspection and committed checkpoint;
  it does not authorize Kimi review-1 before a frozen T1 range exists.

## T1 Bookkeeper Inspection

- Boundary: PASS (13 paths = 11 delivery + 2 shared evidence; 0 forbidden).
- Mechanical JSON/YAML/validator/diff/vocabulary checks: PASS.
- Receipt-schema counterexamples: FAIL CLOSED requirement not met; all three bad
  samples currently validate with zero errors.
- Executable workflow contract: incomplete.
- Disposition: REWORK BEFORE SEAL; `rework_count` remains 0 because no formal
  review verdict or code-changing correction dispatch has begun.
- Correction packet target: original owner `claude_glm / glm-5.2`, human
  execution only.

## Fable5 Second Inspection Merge

- Fable5 independently confirmed T1-B1–B5.
- Absorbed as mandatory: A2; A3 using compatible
  `runner-<seq>-seal.receipt.json`; A4 safe-path/non-empty-scope portion; A6.
- Record-only: A5 formula-copy inventory; A7 historical registry machine-key
  compatibility.
- Deferred: A1 Authority Order promotion, because it changes conflict
  precedence and requires an operator/design amendment rather than an
  implementer correction.
- Rejected subproposal: hard-coded `stage_branch:^stage/`, because AGENTS allows
  an intake-recorded user-approved branch exception; runner still checks exact
  branch equality.
- Old correction packet: superseded before execution; immutable evidence kept.
- New round1-v2 packet: prepared for human execution; it adds only the already
  T1-owned authorization schema and README to the correction writable set.

## Round1-v2 Bookkeeper Reinspection

- Round1-v2 execution evidence is appended in `20-implementation.md` and
  `60-test-output.txt`; no live status/handoff/review file was touched by GLM.
- Independent fallback receipt test: Grok primary valid; Kimi fallback and
  Claude-GLM fallback each fail with two schema errors.
- Independent workflow inspection: `state_transitions=false`,
  `node_transitions=false`; review-1 routing outcomes are prose strings.
- Disposition: REWORK BEFORE SEAL, correction round2; formal `rework_count`
  remains 0 because review-1 has not started.
- Round2 writable delivery set is only receipt schema, workflow auto contract,
  and normative auto doc, plus append-only implementation/test evidence.

## Round2 Fable5 Reinspection And Bookkeeper Handover

- Bookkeeper handover: Codex/GPT quota exhausted after an in-session round2
  verification that was never landed as evidence; Fable5 session took over as
  bookkeeper (disclosure in `status.json.bookkeeper`) and independently redid
  the verification with rewritten counterexamples.
- Result: R2-1/R2-2 materially closed (three review-1 route positives, seven
  receipt negatives, five authorization negatives, enum equality, 8 structured
  state transitions, pilot exact values, "or Grok" removed, seal-receipt naming
  landed in docs+README).
- New: machine node-graph closure check found T1-R3-1/R3-2 (naming-only, no
  frozen decision touched). Round3 fixes them pre-seal so no formal
  `rework_count` is consumed and Kimi review-1 receives a closed graph.
- P3 note (do not fix): `review_1_fixed_transitions` and `activation_predicate`
  prose blocks coexist with the structured maps; the structured maps are
  authoritative, prose stays per the round2 "note fields may remain" rule.

## T1 Seal (Round3 verified)

- Round3 executed by GLM and independently reverified by the Fable5 bookkeeper:
  node-graph closure `unresolved=[]`, non-regression assertions all true,
  frozen suite green (raw evidence in `60-test-output.txt` round3+seal block).
- H_T1 delivery commit `25383e8` (13 files); base `a385c7a`; fingerprint
  double-computed (shell + validator-replica Python), byte-identical.
- Status bind `2d519f0`; `validate-stage --phase pre-review` PASSED on a clean
  tree. `rework_count` = 0 (all corrections were pre-seal inspection loops).

## T1 Review-1 Outcome

- Kimi (`kimi-code/kimi-for-coding`, fresh read-only, human-executed) returned
  **ACCEPT** with 0 findings / 0 required fixes; three residual risks recorded
  (A1 deferred; T2/T3 must realize the written contract; review-2 routing
  pending operator decision).
- Bookkeeper verification: verdict JSON validates against
  `schemas/review-verdict.schema.json` (0 errors); `diff_fingerprint`
  byte-identical to the sealed value; `reviewer_prior_involvement="none"`
  verified true. Landed as `30-review-1-T1.md` +
  `review-1-T1-round1.verdict.json`.
- T1 → `review_1_accept`; per the serial gate, T2 (`seal-and-validator`) is
  unblocked.

## T2 Delivery And Seal

- GLM delivered T2 within the frozen boundary (8 paths, 0 violations, no
  blockers; T1 contract files untouched). Bookkeeper reverified independently:
  78 tests, frozen suite, stdlib-only import scan, dual fingerprint anchors
  (T1 sealed range + `2026-07-borrow-cost-coverage-v2` recorded value, both
  via the new library), 17 rewritten counterexamples through the hand-written
  validators, validator diff read hunk-by-hunk (fingerprint delegation +
  auto checks gated on `enabled`), `AUTO_TRANSITIONS` 13 tuples matched to the
  workflow's 8 rows with `one_of` expansion, seal nine-step structure and
  explicit-path `git add` confirmed.
- Sealed: H_T2 `a7fd737`; bind `4b1e19c`; `--phase pre-review` PASSED — this
  gate ran on the T2-amended validator, so the delegated fingerprint path has
  already verified a production range.

## T2 Review-1 Outcome

- Kimi (fresh read-only session, independent from its T1 review session)
  returned **ACCEPT**: 0 findings, 0 required fixes, one P3 residual risk
  (`_pathspec_matches` approximate matching) which is now a mandatory test
  requirement in the T3 packet (§3.3, exotic pathspec shapes via the
  runner→seal black-box path).
- Bookkeeper verification: verdict schema-valid (0 errors), fingerprint
  byte-identical to sealed T2 value, `reviewer_prior_involvement="none"`
  truthful (review-1 duty is not a disclosure-enum involvement; Kimi wrote no
  code). Landed as `30-review-1-T2.md` + `review-1-T2-round1.verdict.json`.
- `rework_count` = 0 after two of three tasks: T1 and T2 both passed review-1
  with zero formal rework.

## T3 Delivery And Seal

- GLM delivered T3 within the frozen boundary (5 paths; T1/T2 deliverables
  untouched; manifest exactly +5 lines). Bookkeeper reverified independently:
  109 tests, full frozen four-command suite (py_compile now includes the
  runner), stdlib-only scan, lib-reuse audit (no reimplementation), explicit
  `git add` (no `-A`), exotic-pathspec fail-closed tests present.
- Transition truth: runner reuses the validator's `AUTO_TRANSITIONS` via
  importlib (no second matrix literal). The dispatch packet also asked for a
  persistent set-equality test assertion, which the delivery replaced with
  behavior-level transition tests plus disclosure; the bookkeeper landed a
  three-way set-level machine comparison (workflow 13 expanded tuples ==
  validator == runner, CONFIRMED) in `60-test-output.txt`. This known gap is
  presented with full context in the review-1 packet for Kimi's independent
  judgment.
- Sealed: H_T3 `d42e031`; bind `7fb0933`; `--phase pre-review` PASSED.

## T3 Review-1 Outcome (round 1)

- Kimi returned **REWORK** with exactly one P2 finding: the persistent
  set-equality test assertion (workflow `state_transitions` expanded ↔
  `runner.AUTO_TRANSITIONS`) required by the T3 dispatch packet §3.1 was
  replaced by behavior-level tests plus disclosure; the bookkeeper's landed
  one-shot machine comparison "cannot substitute for a resident regression
  test". Every other focus area passed (runtime security, budgets, routing,
  fix-loop integrity, P3 pathspec, manifest, macOS paths).
- Bookkeeper verification: verdict schema-valid (structured finding included),
  fingerprint byte-identical to sealed T3, complete `fix_start_prompt`
  (boundary: only `scripts/tests/test_auto_review_runner.py`, stdlib-only
  line parser, no second hardcoded matrix). The judgment matches the known
  gap presented for independent review; bookkeeper concurs.
- **`rework_count` 0 → 1** (first formal charge; cap 3). Fix is test-only but
  is a code change: after it returns, T3 must be **re-sealed** (new
  H_T3'/fingerprint via the full protocol) before Kimi re-review round 2.

## T3 Fix Round 1 And Re-Seal

- GLM delivered the fix within the single-file boundary:
  `TransitionTruthSourceTests` + `_parse_workflow_state_transitions`
  (restricted stdlib line parser; reads the real workflow file; one_of
  expanded; null→None; fail-closed on structural deviation; no second
  hardcoded matrix; no yaml import). 110 tests green.
- Bookkeeper destructive verification on scratchpad copies: event rename →
  drift detected; one_of item dropped → drift detected (12≠13); indentation
  deformation → AssertionError fail-closed. Real workflow untouched.
- Re-sealed at H_T3' `4c668bb` (round-1 verdict preserved in
  `tasks[T3].review_1_history`); `--phase pre-review` PASSED.

## T3 Round-2 Outcome

- Kimi round-2 (fresh session) returned **ACCEPT**: finding P2 closed against
  all six fix_start_prompt points, drift-sensitivity independently verified
  (rename/drop/deformation), no regression (110 tests; fix increment exactly
  the authorized single file + evidence), no new findings.
- Review-1 phase complete: three of three units ACCEPT under human-dispatched
  DRAFT-2 with fresh Kimi sessions per unit. `rework_count` final **1/3**.

## Review-2 Routing Decision Materials（操作者决议，两条路线并列）

Registered decision models: OpenAI/Codex and Anthropic/Claude only — both
have disclosure-level prior involvement, so there is no unrelated registered
decision model. Involvement inventory (recorded in status.json):

- OpenAI/Codex: design-review author (30-), intake author, stage designer
  (00-task/10-design/11-adr), former bookkeeper. Enum value: `design`.
- Anthropic/Claude (Fable5): direction patches merged into the frozen table
  (F1–F3), stage-design review (13-), development breakdown (12-), second
  inspections (22-/25-), **current bookkeeper**. Enum: `design` (+ breakdown
  + direction_synthesis in notes). Heaviest involvement plus dual-hat.

**Route A — enable Gemini 3.1 Pro (registry
`future_review_2_fallback_candidates`).** Trigger clause "user explicitly
approves a third decision model" is satisfied by an operator instruction.
`reviewer_prior_involvement: "none"` is truthfully available — no override
evidence burden. Mechanics: no local adapter, so the bookkeeper prepares a
self-contained review-2 packet (stage range, fingerprint, full design chain,
delivery diffs) and the operator relays it externally (as was done for the
`2026_07_initial_direction` panel). Limitation: Gemini cannot run
commands/tests; its verdict is a static review of supplied materials —
mitigated by the fact that every mechanical check is already machine-verified
and evidenced in `60-test-output.txt`.

**Route B — strong-reviewer disclosure override (AGENTS documented path).**
Requires: an `unrelated_reviewer_unavailable_evidence` file recording that
both registered decision models are design-conflicted and no third model is
enabled (design-conflict ineligibility is a listed fallback reason);
`fallback_reason` + truthful `reviewer_prior_involvement` in verdict and
status; the review-2 prompt must rank the user-approved frozen decision
table above 00-task/10-design as requirements authority. Sub-options:
**B1 Codex** (lighter involvement, AGENTS primary reviewer, not the current
bookkeeper — preferred within B if its quota has recovered) or **B2 Claude**
(triple involvement + same provider as the acting bookkeeper — weakest
independence; not recommended while B1 or A is available).

Bookkeeper recommendation (non-binding): **A** for cleanest independence;
**B1** if operator prefers speed and Codex quota is restored; avoid B2.

## Routing Resolution (operator, 2026-07-11)

- Route A is out: operator reports Gemini is frequently network-unreachable
  (`service_unavailable`) — which itself hardens the override precondition.
- Operator dispatches review-2 personally, choosing from the high-end pool
  — **gpt-5.6-sol > gpt-5.6-terra > gpt-5.6-luna** (openai, descending
  capability) or **claude-fable-5 / opus4.8** (anthropic) — per
  cross-review principle and token budget at dispatch time. The bookkeeper
  keeps the packet provider-neutral.
- Override evidence landed:
  `review-2-unrelated-reviewer-unavailable-evidence.md` (Gemini
  service_unavailable + both registered decision models design-conflicted).
- Provider-neutral packet landed:
  `task-stage-review2-operator-choice.prompt.md` — role `final_reviewer`;
  per-provider disclosure branches (`reviewer_prior_involvement: "design"`
  both sides; the Anthropic branch additionally mandates an explicit
  bookkeeper dual-hat risk review); requirements authority = the frozen
  40-table above 00-task/10-design; subject = stage range
  `a385c7a..4c668bb` with fingerprint; ACCEPT maps to
  `stage_accepted_waiting_user`, never merge authority.
- Follow-up recorded (registry refresh, future Harness sync):
  `codex.default_model` still says `gpt-5.5`; the GPT-5.6 family and its
  sol>terra>luna ordering are newer than the registry snapshot.

## 下一步

Operator approved the **final fix round**. `rework_count` charged to
**3/3** at packet bind; status → `fixing`. Human operator dispatches
Claude-GLM with
`task-review2-round2-fix-final-claude-glm.prompt.md`
(`claude-glm --model glm-5.2 -p "$(cat <packet>)"`). The packet covers
FX1–FX7 (sol round-2 5×P1 + P2#1/P2#2; P2#3 already cleared by the
bookkeeper) with per-item anchors, hard behavioural requirements,
**explicit prohibited-implementation lists (anti-drift G1–G5)**,
red-then-green evidence per finding, and the exact bookkeeper
reverification criteria (incl. per-item destructive checks). FX5 offers
two allowed designs (fail-closed receipt-trace resume = recommended A;
node cursor = B only if no contract files need touching). After delivery:
bookkeeper reverifies (incl. destructive verification per FX) → re-seal
(new fingerprint) → formal re-review-1 → review-2 round 3. **Any
code-changing rework needed after this delivery = human_escalation_required
(ledger exhausted).**

本地北京时间: 2026-07-12 00:20:00 CST
下一步模型: human operator → Claude-GLM（final fix, rework 3/3）
下一步任务: 人工执行 final fix packet；GLM 不得 commit/触碰 writable set 外文件；返回后 bookkeeper 复验并推进。
