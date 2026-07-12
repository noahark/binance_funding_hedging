# Operator Decision — Withdraw Mandatory P8 Wall-Clock Budget

## Decision

On 2026-07-12, after review-2 round 3 and the explanatory follow-up, the human
operator explicitly directed:

> Fable5 quota has expired; Codex takes over the workflow. Formally withdraw
> frozen decision P8's mandatory wall-clock budget. Long tasks commonly work
> continuously for several hours, so the total wall-clock limit is unnecessary.

This decision supersedes only the wall-clock portion of P8 in
`reports/agent-runs/2026-07-auto-review-pipeline-design-review/40-operator-decision-table.md`.
The historical frozen table remains verbatim evidence and is not rewritten.

## Frozen Replacement

P8 is replaced with:

```text
P8 — Cost beyond round cap

Required per-stage controls:
- positive model-call cap;
- existing shared stage rework cap;
- aggregate automatic code-change cap;
- per-adapter invocation timeout from the registered adapter;
- operator stop and normal stage/review/merge gates.

Optional time control:
- expires_at remains required as a field and nullable as a value;
  null means no absolute authorization-expiry time.

Removed:
- no wall_clock_seconds authorization field;
- no run_started_at or run_deadline_at state;
- no total runner-session deadline or timeout escalation based solely on total
  elapsed stage time.
```

Long uninterrupted work is valid even when it lasts several hours. A hung
individual adapter is still bounded by its adapter timeout; repeated or runaway
model activity is bounded by model-call and rework budgets.

## Stage Disposition

- This resolves the human decision requested by
  `53-review-2-round3-panel-disposition.md` §6.
- The prior P1 remains a valid finding against the old contract. It is closed
  only after the amended contract and implementation remove the total-session
  clock consistently and pass new review; it is not silently downgraded.
- This is a human-authorized contract amendment, not rework 4/3.
  `rework_count` remains 3.
- The existing stage branch remains the only practical implementation base:
  the auto-review v1 delivery is not merged to `main`, so a new stage created
  from `main` would not contain the contract being amended.
- Auto mode stays disabled for this bootstrap stage.
- No merge to `main` is authorized by this decision.

## Bookkeeper Handover

The operator reports that Claude Fable 5 quota is exhausted. Codex/OpenAI is
explicitly assigned as replacement bookkeeper. This same Codex session authored
the round-3 REWORK report and now records the operator disposition; that
reviewer/bookkeeper/design dual-hat history must remain disclosed to the next
review-2. Codex is not eligible to implement or fix delivery code.

The configured Anthropic development-breakdown fallback is Opus 4.8. Per
`AGENTS.md`, Codex prepares but does not execute the Opus dispatch. The human
operator executes the prepared packet.

本地北京时间: 2026-07-12 10:26:57 CST
下一步模型: Claude Opus 4.8（development breakdown author；human dispatch）
下一步任务: 对 P8 wall-clock 撤销做有界开发细化，冻结文件边界、删除语义、测试矩阵与 review focus
