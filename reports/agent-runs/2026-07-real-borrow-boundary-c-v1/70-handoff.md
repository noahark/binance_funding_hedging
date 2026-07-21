# Handoff — Boundary C Pre-Formal Correction 4 Prepared

## Recovery Header

- Active phase: `implementation`
  (`bookkeeper_preformal_fix_4_prepared_waiting_human_dispatch`).
- Next action: human operator executes
  `task-C-bookkeeper-fix-4.prompt.md` in the original registered
  Claude-GLM / GLM-5.2 implementation terminal, fills the machine receipt in
  `task-C-bookkeeper-fix-4.dispatch.md`, and stops for bookkeeper intake.
- Read-set: = `status.current_inputs`; the implementer additionally follows
  the exact read list and file boundaries in the fix-4 prompt.
- Do-not-read: credentials, `.env`, expanded alias environment,
  `reports/agent-runs/**/history/**`, and unrelated stages.

## Why The Reported Review Is Non-Accepting

- Raw artifact: `30-review-1.md`
- Bookkeeper intake: `30-review-1.bookkeeper-intake.md`
- Reported result: schema-valid `REWORK`, three P1 and two P3 findings, full
  `fix_start_prompt`, matching fixed fingerprint.
- Formal gate result: **unset / non-accepting**.
- Provider Session ID:
  `9bb7a540-1d7e-428f-9ab8-ebfb580cbb35`, verified at
  `~/.kimi-code/sessions/wd_funding_hedging_312b78e68b47/session_9bb7a540-1d7e-428f-9ab8-ebfb580cbb35/`.
- The matching `state.json` records
  `createdAt=2026-07-20T13:59:51.788Z`, before this review execution, while
  its last prompt matches this task. The session was therefore not fresh.
  Review-1 freshness has no override.
- Formal `rework_count` remains `0`; `review_1.verdict` remains null.

## Independently Confirmed Corrections

The bookkeeper re-inspected reviewed head
`61ce536dfba6ddd347586cf324209acdfdc6afd9` and confirmed:

1. **F1 / P1:** three stale frontend strings claim real borrowing is disabled
   while the same screen can show live execution started.
2. **F2 / P1:** the market-row create path posts after amount/count validation
   without showing asset, amount × count maximum target quantity and current
   global interval before submission.
3. **F3 / P1:** startup restores a pending orphan only as a blocker;
   `list_due_reconciliations` selects resolved unknown attempts with a
   non-null schedule, so the crash orphan never enters +5/+15/+60/+300/+900s
   reconciliation.
4. F4/F5 are confirmed P3 polish: unused transient `raw_body` and missing
   empty credential-name documentation in `.env.example`.

Because F1-F3 violate frozen AC #7/#12/#13 and ADR-001/ADR-006, they are routed
as a bookkeeper pre-formal correction rather than converted into a formal
review verdict.

## Fix-4 Packet

- Prompt: `task-C-bookkeeper-fix-4.prompt.md`
- Human receipt: `task-C-bookkeeper-fix-4.dispatch.md`
- Required output: `40-fix-report.md`
- Test evidence: append only to `60-test-output.txt`
- Author: original Claude-GLM / provider identity `zhipu_glm`
- Required findings: F1, F2, F3
- Optional findings: F4, F5
- Allowed files and exact fake-only commands are frozen in the prompt.
- Forbidden: real/authenticated/production-reachable Binance traffic,
  credential reads, second POST, hidden retry, force-clear/retry-anyway,
  Harness/state/design/raw-review edits, commit/push/merge or model relay.

After bookkeeper intake, the correction receives a new committed head and
fingerprint. Formal review-1 then restarts in a genuinely fresh Kimi provider
session; the current raw artifact is preserved and will not be overwritten.

## Harness Follow-Up

- Evidence: `harness-review-verdict-extractor.follow-up.md`
- Current v0.5 `extract_last_json_object` returns the last nested finding
  instead of the final top-level verdict when `findings` is non-empty.
- Robust end-of-file extraction independently validates the current JSON;
  therefore this is a Harness extractor defect, not invalid reviewer JSON.
- The main-only Harness repair is not authorized in the product fix packet.
  It needs dedicated tests and main promotion. If synced into this stage later,
  the stage must record the exception, rerun tests/validator, recompute the
  fingerprint and re-enter review.
- The earlier review dispatch packet also omitted the machine receipt block.
  The narrative receipt remains verbatim; a mechanical non-accepting block was
  added, and fix-4 uses the required machine format from the start.

## Git And Safety State

- Branch: `stage/2026-07-real-borrow-boundary-c-v1`
- Effective delivery base:
  `c9df14591ac4ca00977ce0e4d80c0950aae44c19`
- Previously reviewed head:
  `61ce536dfba6ddd347586cf324209acdfdc6afd9`
- Previously reviewed fingerprint:
  `61ce536dfba6ddd347586cf324209acdfdc6afd9:449b46378a324fa3c8bdd9ec9425b1e59b7509cb55e6c129d8991322dcb1a984`
- No live Binance write, push, merge, deployment or acceptance is authorized.
- `reports/agent-runs/_proposals/**` remains unrelated user-owned state and
  was not edited, staged, committed or cleaned.

当前 Session ID: unavailable (current runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/70-handoff.md
本地北京时间: 2026-07-21 12:02:59 CST
下一步模型: human operator → Claude-GLM / glm-5.2[1m]
下一步任务: execute task-C-bookkeeper-fix-4.prompt.md, fix F1/F2/F3 with fake-only evidence, fill the machine receipt, and stop for bookkeeper intake
