# AGENTS.md - Minimal Project Harness

This is the single startup guide. Read it before acting, then load only files required by the current task.

## 1. Project Development Principle

Ship a usable version quickly and learn from real feedback. Solve problems that exist, have evidence, and have clear acceptance criteria. Do not add abstractions, compatibility layers, or defensive machinery for hypothetical scenarios. Fix a concrete problem with the smallest sufficient change.

Known live exposure, money risk, open gates, missing close capability, observed model mismatch, proven review gaps, cheap validation, and fail-closed safety still require action.

## 2. Harness Design Principle

Use minimal changes and progressive disclosure. Startup holds only universal rules; role, skill, task, and evidence details are read on demand. Prefer changing an existing authority file. Add a file only for an independent lifecycle, owner, or startup duty.

Before adding structure, identify its maintainer, reader, unique duty, and why an existing authority cannot hold it. If unclear, do not add it.

During a Harness change, each rule, field shape, state vocabulary, routing mapping, or numeric limit has a single detailed active authority. Other active files may point to it or give a scoped one-line reminder, but must not copy a field list, enum set, numeric limit, or full workflow. When a Harness modification encounters another independently executable definition, consolidate it within the authorized scope or report it. This requirement applies when modifying Harness contracts, not to ordinary product tasks.

## 3. Safety Kernel

These are Human-authorization gates: the actions below require explicit Human authorization before a model performs them. They are a different classification from the review-topology risk in §8 Review Rules.

1. Money, orders, live gates, credentials, destructive data actions, risk-limit changes, deployment, and external side effects require explicit human authorization.
2. No model may start, call, relay to, assign, or impersonate another model session. The human operator starts the next terminal from a prepared packet.
3. An implementer may modify only dispatch-approved files. It must not overwrite the human's or another terminal's work; insufficient scope is a blocker.
4. An implementation or fix author cannot review its own delivery. Formal review uses a fresh read-only session.
5. Review isolation follows the model vendor, not the CLI wrapper.
6. Formal review uses the committed `base_sha..delivery_sha` recorded in `status.json`, never moving `HEAD` or an uncommitted worktree.
7. A review without an explicit, well-formed `ACCEPT` is non-accepting.

## 4. Startup

When the human delivers a task packet, read in this order:

1. `AGENTS.md`;
2. the delivered `<task>.dispatch.md`;
3. `reports/agent-runs/ACTIVE.json`;
4. `PROJECT_STATE.md`;
5. the active stage's `status.json`;
6. the matching section of `agents/roles.md`;
7. `agents/developer-discipline.md` for implementation or fix work;
8. at most one skill named by the dispatch;
9. only source files and evidence explicitly required for the task.

The packet is the session entry; `status.json` verifies it. Stop if stage, task, target model, or revision differs.

Without a packet, read `ACTIVE.json`, `PROJECT_STATE.md`, and active `status.json` when present, then wait. Do not scan `reports/agent-runs/`, completed stages, or `history/`.

| File | Sole responsibility |
|---|---|
| `AGENTS.md` | Startup, hard rules, navigation, and default flow |
| `PROJECT_STATE.md` | Cross-stage live risks, follow-ups, last archive |
| `ACTIVE.json` | Active stage pointer only |
| `<stage>/status.json` | Current stage progress and routing |
| `<task>.dispatch.md` | Current task scope; the exact packet shape lives in the Bookkeeper section of `agents/roles.md` |
| `agents/roles.md` | Role duties, model routing, provider identity |
| `agents/developer-discipline.md` | Shared implementation and fix discipline |
| `agents/skills/*.md` | One task-specific capability, read on demand |
| `<stage>/evidence/*` | Raw tests, reports, verdicts, and samples |

Target at most about 8K tokens for startup and 15K for a loaded task. Required high-risk evidence may exceed the target with a recorded reason; never skip necessary evidence.

## 5. Role Routing

Read only the target role section in `agents/roles.md`.

| Task | Role and additional reading |
|---|---|
| Requirements, design, breakdown | `Planner` + one named planning skill |
| Backend, API, schema, data | `Implementer` + discipline + implementation skill |
| Frontend, UI, client integration | `Implementer` + discipline + implementation skill |
| Bounded finding repair | `Implementer` + discipline + repair skill |
| Review-1 | `Reviewer` + `agents/skills/code-reviewer.md` |
| Review-2 | `Reviewer` + `agents/skills/reality-checker.md` |
| State verification and next packet | `Bookkeeper` |

Detailed model routing and provider identity live only in `agents/roles.md`; this file does not restate them.

## 6. Default Delivery Flow

1. Human and a senior Planner decide the product goal, release boundary, non-goals, and acceptance criteria.
2. Planner creates bounded backend/frontend tasks only when safely separable.
3. The dispatched implementer implements, self-tests, reports, and stops.
4. Bookkeeper verifies results and seals a committed delivery range.
5. Review routing follows §8 Review Rules.
6. The original implementer fixes an explicit finding with the smallest change.
7. A model explains effect, problems, and choices in plain Chinese; Human may make a business pre-decision.
8. An unrelated senior model performs review-2.
9. After review-2 `ACCEPT`, a model explains the verdict and remaining risk; Human makes the final decision.
10. Merge, deployment, or live activation requires explicit human authorization.

Models prepare dispatch packets; only the human operator starts the selected
model terminal.

## 7. Task Result Protocol

Every task ends with:

```text
[TASK_RESULT v2]
任务 ID: <id>
执行结果: completed（完成） | blocked（阻塞） | failed（失败）
结果摘要: <不超过 300 个总字符>
产物: [<paths>]
检查结果: [<最多八项，合并重复检查>]
阻塞项: [<none or concrete blockers>]
[/TASK_RESULT]
```

A review task also returns:

```text
评审结论: ACCEPT（接受） | REWORK（返工）
问题记录: <path | none>
修复要求: <path | none>
```

`执行结果: completed` means the review ran; only `评审结论: ACCEPT` passes. `REWORK` requires findings and executable repair requirements. Missing or ambiguous review-closure data is non-accepting.

### Compact Output Rules

For every low-risk task with `执行结果: completed`:
- `结果摘要` is a hard maximum of 300 total characters (Chinese, English,
  numbers, spaces, and punctuation), not a soft target and not a Han-character
  count.
- `检查结果` is a hard maximum of eight grouped, non-duplicative items.

Required high-risk or `REWORK` evidence may exceed the summary target when
necessary; put detailed findings and repair requirements in the review evidence
referenced by `问题记录` and `修复要求`.

### Chinese Handoff Labels (Inside Result Block)

Every formal `[TASK_RESULT v2]` must contain these three Chinese handoff lines:

```text
本地北京时间: <YYYY-MM-DD HH:MM:SS CST from local date>
下一步模型: <readable role/model name with transfer note>
下一步任务: <concrete evidence path, state transition, next gate, target model when known>
```

- `本地北京时间` uses exact format `YYYY-MM-DD HH:MM:SS CST`, produced by:
  `date '+%Y-%m-%d %H:%M:%S CST'`.
- `下一步模型` names the immediate next workflow actor in readable form, not an
  internal enum:
  - after an Implementer or Reviewer returns a task result, show the current
    `status.json.bookkeeper`, because Bookkeeper is the immediate recipient;
  - after Bookkeeper prepares a dispatch, show that dispatch's `target_model` in
    readable form and state that Human starts it;
  - while waiting for a Human decision, show `Human（决策者）`.
  A later planned reviewer must not appear here; it may appear in `下一步任务`
  only as part of the concrete follow-on sequence.
- `下一步任务` describes the action of that same immediate actor: the concrete
  evidence path, state transition, next gate, and any later reviewer only when
  it is part of the follow-on sequence. Do not use vague text.

These fields are informational only and never authorize dispatch. The current
model cannot start, call, relay to, or assign the next model.

### Final Output Marker

The closing line `[/TASK_RESULT]` must be the final non-whitespace output. No session ID footer, next-model instruction, or any other text may follow it.

The complete `status.json` field shape lives only in the Bookkeeper section of `agents/roles.md`; do not restate it here.

An implementer may move only its own task from `dispatched` to `reported`. Bookkeeper is the only other normal `status.json` writer and alone may verify results, set `next`, or record a gate result. Reviewers are read-only; Human transfers their raw result to Bookkeeper.

Write a verified live incident to `PROJECT_STATE.md` immediately. Never present repository history as a current runtime check.

## 8. Review Rules

This section defines review-topology risk: which task changes require review-1 plus review-2. It alone defines the `LOW_RISK` and `HIGH_RISK` review routes, which are a different classification from the Human-authorization gates in §3 Safety Kernel.

- `HIGH_RISK`: orders, positions, borrowing, repayment, transfer, money/PnL meaning, accounting, live gates, risk limits, credentials, controlling contracts, Harness safety or workflow contract changes, or an unclear acceptance oracle — require review-1 plus review-2.
- `LOW_RISK`: a documentation or mechanical change with none of the above may use one independent final review only when its dispatch records why.
- Review-1 checks code, contracts, tests, and seams. Review-2 checks the requirement, actual effect, evidence, operational risk, and release readiness.
- Reviewers inspect raw artifacts and fixed `base_sha..delivery_sha`, not only a summary.
- Provider isolation and model selection follow `agents/roles.md`.
- Review-1 `REWORK` returns to review-1 after repair and retest.
- A narrow review-2 finding returns directly to review-2 after repair, retest, and a new commit.
- A review-2 repair that expands files, changes a contract, or adds risk must pass review-1 again.
- `rework_count` counts only formal `REWORK` repair rounds for the current task. It resets to zero for a new task and does not count Human requirement refinement or pre-dispatch packet correction. The maximum is three; beyond it Human chooses to narrow, redesign, accept a limitation, or stop.

## 9. Stage Completion

Harness v2 branch, SHA, and merge policy: v2 does not require automatic `stage/<stage-id>` branch creation or a mandatory branch name; Human selects the branch or worktree for the bounded work; formal review stays anchored only to the committed `base_sha..delivery_sha`; and merge to `main` stays forbidden without explicit Human authorization.

Before closing a stage, Bookkeeper:

1. promotes durable product or architecture decisions to canonical documents;
2. moves unresolved live risks and follow-ups to `PROJECT_STATE.md`;
3. records the last completed stage and Git archive reference;
4. preserves full evidence under a tag or archive branch;
5. removes the completed stage directory from the normal worktree;
6. sets `ACTIVE.json` to `{"active": null}`.

Audit a completed stage only in a separate worktree from its exact archive. Review `ACCEPT` does not merge, deploy, activate live behavior, or replace final human acceptance.

## 10. Human Boundary And Communication

Human does not review code or technical documents and does not manually edit code, documents, stage evidence, or state. Models perform implementation, modification, testing, technical review, and progress recording. Human reads model-terminal output and decides requirements, priority, risk authorization, business acceptance, merge, deployment, and live operation.

When Human input is required, use plain Chinese and state: what happened, practical effect, recommended choice, and alternatives. Translate English terms, abbreviations, and statuses on first use. Do not hand raw diffs, JSON, code, or technical-review work to Human.

Starting a prepared model terminal executes an already-made dispatch decision. It does not make Human the technical reviewer, repository editor, or autonomous model router.
