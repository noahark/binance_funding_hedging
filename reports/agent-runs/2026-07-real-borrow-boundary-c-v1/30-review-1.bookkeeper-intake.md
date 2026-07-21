# Review-1 Bookkeeper Intake — REWORK Restored After Freshness Correction

## Disposition

The Kimi artifact at `30-review-1.md` contains a complete final JSON object
that independently passes `schemas/review-verdict.schema.json`: verdict
`REWORK`, five findings (three P1, two P3), a matching fixed fingerprint, and
a complete `fix_start_prompt`.

The human operator subsequently confirmed that `/clear` followed by `/new`
was executed in Kimi before the review prompt. This is the relevant freshness
evidence: the active prompt/tool context was reset before formal review. The
reported Session ID resolves to an older on-disk session directory, but neither
`AGENTS.md` nor the workflow requires a different provider-native Session ID,
and storage-container creation time alone cannot prove transcript reuse.

The earlier bookkeeper classification based only on `state.json.createdAt`
was over-strict and is withdrawn. Review-1 provider isolation also remains
valid: Kimi / `moonshot_kimi` is distinct from the Claude-GLM /
`zhipu_glm` implementation and fix author. The artifact is therefore restored
as formal **`REWORK`**, and formal `rework_count` is incremented to `1`.

One separate Harness defect remains: merged v0.5
`extract_last_json_object` scans opening braces backwards and returns the last
nested finding object. On this artifact, `_parse_review_artifact` therefore
reports missing top-level verdict fields even though robust end-of-file
top-level extraction validates the complete JSON. This is a validator defect,
not invalid reviewer JSON or a reason to rerun the same review for freshness.

The prepared dispatch packet also lacked the machine-readable
`DISPATCH RECEIPT` block required by the same v0.5 validator. The human-filled
narrative receipt is preserved unchanged; the bookkeeper added a mechanical
non-accepting block at its top and will use the correct block format for all
subsequent packets.

Formal `review_1.verdict` is `REWORK`, `rework_count` is `1`, and the already
human-dispatched fix-4 packet remains in progress without scope changes. A new
review is required after the fix because the committed fingerprint will
change, not because the current provider-native Session ID was reused.

## Finding Intake

The attempt is non-accepting, but its product findings are concrete audit
evidence. The bookkeeper independently inspected the fixed reviewed head
`61ce536dfba6ddd347586cf324209acdfdc6afd9` and confirmed:

- **F1 (P1): confirmed.** `frontend/index.html` lines 942, 953 and 2548
  statically claim that real borrowing is disabled while the same UI can show
  `live · 已启动`.
- **F2 (P1): confirmed.** The market-row create path renders only amount, count
  and Confirm, then posts immediately; it does not show asset, amount × count
  maximum target quantity and the current scheduler interval before submission.
- **F3 (P1): confirmed.** Startup recovery only restores
  `unresolved_attempt_id` for `outcome=pending`. Due reconciliation selects
  only `outcome=resolved AND result_category=unknown` with a non-null schedule,
  so a crash orphan remains permanently outside the bounded reconciliation
  sequence.
- **F4/F5 (P3): confirmed as non-blocking polish.** `raw_body` has no reader,
  and `.env.example` does not document the two dedicated borrow credential
  variable names.

Because the three P1s independently violate frozen AC #7/#12/#13 and
ADR-001/ADR-006, `task-C-bookkeeper-fix-4.prompt.md` is now tracked as the fix
for formal review-1 rework round 1. Its already dispatched prompt body is kept
immutable even though it contains the superseded `pre-formal` label; findings,
file boundaries, fake-only tests and safety constraints are unchanged.

## Harness Follow-Up

The JSON extractor defect must be repaired through a dedicated Harness change
that lands on `main`, with non-empty-findings regression coverage and no
historical-stage drift. It is not authorized inside the product fix packet.
Before the next formal review packet, the bookkeeper must require:

- fresh Kimi prompt/tool context, with operator reset evidence recorded; a new
  provider-native Session ID is recommended for clarity but not mandatory;
- a machine-readable dispatch receipt with exact command, ISO timestamps,
  human executor and verified Session ID;
- a Session ID footer whose ID token is separated from explanatory text so the
  current consistency check cannot absorb full-width punctuation.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/30-review-1.bookkeeper-intake.md
本地北京时间: 2026-07-21 12:21:18 CST
下一步模型: Claude-GLM / glm-5.2[1m] → bookkeeper
下一步任务: finish the already dispatched formal review-1 rework fix for F1/F2/F3, then stop for bookkeeper intake and fingerprint refresh
