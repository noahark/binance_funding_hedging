# Harness Roles

Read only the section named by the active dispatch packet. `AGENTS.md` has
higher authority than this file. A role describes responsibility; it does not
give a model permission to launch another model or expand task scope.

## Shared Rules

- The human-delivered dispatch packet follows the exact shape in the Bookkeeper
  section below.
- A model's self-check against `target_model` is only a warning tripwire. The
  operator's launch record and Bookkeeper verification establish the actual
  model identity.
- No model may start, call, relay to, or impersonate another model session.
- Stay inside the dispatch file boundary. Stop and report if the boundary is
  insufficient or overlaps another terminal's work.
- Preserve raw evidence. Do not replace test output, findings, or model output
  with a narrative summary.
- 勘误（Errata）。自己的已交付文档可就地更正，但须附日期说明改了什么、为什么；他人的已交付产物只可追加显著标记的勘误，不得编辑其散文；原始模型输出、测试输出与 verdict 永不编辑，只以追加勘误更正。勘误判据（权威原文）：产物勘误仅限不改变交付效果的编辑性更正——只修正文字、格式、引用路径或证据标注，且更正后交付物的代码行为、契约语义、验收标准、各项检查的通过状态与评审结论均须与更正前一致；其计数后果（越此线即修复）见 `AGENTS.md` §8。
- Never record credentials, tokens, cookies, private keys, or expanded secret
  environments.
- Skill cardinality: a generic dispatch names zero or one `required_skill`; an
  Implementer dispatch names exactly one, chosen from its implementation or
  bounded-repair skill. Planner and Reviewer follow zero or one as their own
  section states. The Implementer rule is a stricter role-specific limit, not a
  conflict with the generic maximum.

## Task Handoff Evidence Contract

This is the single detailed active authority for task handoff files. `AGENTS.md`
§7 states only that a new approved stage lists its handoff path in the receipt
`产物` and writes `下一步任务` in the `读取／执行／关卡` form; the detail lives
here, and no other active file restates it. Every dispatched implement, fix,
review-1 and review-2 task in a stage approved after this contract takes effect
ends by creating exactly one handoff at the deterministic path:

```text
reports/agent-runs/<stage-id>/evidence/<task-id>.handoff.md
```

Bookkeeper verifies the task from the same file and does not build a parallel
record. Archived stages keep their existing files; this contract applies only to
stages approved after it takes effect.

### Structure

The file is the author's immutable source report plus a Human Brief, followed by
a Bookkeeper append region:

```markdown
# Task Handoff: <task-id>

## Source Report (author-only; immutable after task end)
- task_id / role / target model
- stage_id / created_at
- base_sha / delivery_sha（不适用时明确写 none）

完整任务背景、实际修改范围或只读评审范围、结论、未完成事项、命令与结果、仓库内
证据路径，以及下一任务必须读取的材料和不能假设的事实。大体积测试原件只引用路径，
不复制进本文件。

### Required Reading for the Next Task
- 读取路径及顺序：<一个或多个仓库相对路径，或 none>
- 执行：<立即动作>
- 关卡：<下一验证或 Human 决策>
- 不能假设的事实：<具体约束>

## Human Brief / Console Receipt Source (author-only; immutable after task end)
既有 `TASK_RESULT v2` 字段与闭合标记的 Human 可读简报，也是控制台回执的唯一内容
来源。作者须先完成本交接件，再以本节内容生成控制台回执，不得另行创作与本节不一致
的控制台叙事。本节 `下一步任务` 必须写为：
读取：<一个或多个仓库相对路径，或 none>；执行：<立即动作>；关卡：<下一验证或 Human 决策>

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)
由 Bookkeeper 核验后追加：源区块 SHA-256、核验时间、核对的 status revision、通过或
拒收依据、可复现命令与后续状态。

## Errata (append-only)
任何更正均追加，说明日期、作者、改动原因与不改变的事实；不得改写 Source Report 或
Human Brief。
```

`Required Reading for the Next Task` is a `Source Report` sub-section, so it sits
inside the immutable source payload before the `BOOKKEEPER_APPEND_ONLY` marker;
that marker's preceding bytes define the SHA-256 source boundary.

### Author Authority And Failure Handoffs

- The author creates the file within its dispatch scope, then emits the console
  receipt from the Human Brief.
- The author block is immutable after task end. `Source Report` and `Human Brief`
  are never rewritten; corrections are append-only `## Errata`.
- `blocked`, `failed`, review `REWORK` and Bookkeeper rejection also produce a
  handoff stating the blocker or basis and the cited evidence paths.
- A later dispatch lists only the input handoffs it needs, read in written order.

### Reviewer Create-Only Exception

Beyond this exception a reviewer is fully read-only: it must not touch delivery
code, existing evidence, `status.json`, `PROJECT_STATE.md`, commits, or model
routing. Its sole write is creating, after review, the exact dispatch-specified
handoff path that Bookkeeper's preflight `test ! -e <path>` recorded as absent in
Allowed Files; an existing path fails the task. The reviewer handoff holds only
its own conclusion, evidence paths and formal receipt; it does not copy or
rewrite the reviewed code, prior reviews, or `status.json`.

### Bookkeeper Same-File Verification

Bookkeeper is the only normal `status.json` writer. Before dispatch it preflights
`test ! -e <path>` for the planned handoff and records the result, command,
deterministic path and create-only authority in the dispatch Allowed Files, and
names this Task Handoff Evidence Contract in the dispatch `Inputs` so every
contract-bound task is routed to the detailed rules before execution. After the
raw result returns it
confirms the path exists and was newly created by this task, and that task_id,
role, stage_id and the declared SHAs match `status.json` and `git rev-parse`. It
verifies the Human Brief's `TASK_RESULT v2` structure, review-closure fields when
present, cited evidence paths and commands, and that `下一步任务` carries explicit
read paths, immediate action and next gate consistent with `Required Reading for
the Next Task`; multiple paths are read in written order and, for `REWORK`, cover
the paths cited by `修复要求`. When the `BOOKKEEPER_APPEND_ONLY` marker is
present it computes SHA-256 over the bytes before that marker and appends only
the `## Bookkeeper Verification` block to the same file. If the file exists but
the marker is missing or the source payload is malformed, Bookkeeper edits no
author byte: it appends only a marked rejection `Bookkeeper Verification` block
at EOF with `source_sha256: unavailable`, the malformed precondition, a
reproducible check, and the `reported`/blocker state. A normal source SHA-256 is
calculated only when the marker exists; a fully missing file remains the only
`SOURCE_REPORT_MISSING` case. This append is Bookkeeper's sole verification
record; it creates no parallel record, edits no author block, and never alters
`delivery_sha`.

### Errata And Archive

Errata appended before verification are judged with the original block. An
erratum after verification that crosses the edit-vs-repair line of the Shared
Rules 勘误判据 and `AGENTS.md` §8 is repair (it increments `rework_count`);
otherwise Bookkeeper appends one erratum confirmation and re-verifies, or returns
the task to `reported`. After a stage is archived, no erratum is appended in
place within the archive or the normal worktree; new findings open a follow-on
task that cites the archive SHA.

### SOURCE_REPORT_MISSING Fallback

If a task cannot create its handoff due to permission, disk, or path conflict,
the task returns `blocked` and does not advance. Bookkeeper may then create only
a marked `SOURCE_REPORT_MISSING` record at the path stating the missing fact and
the Human-transferred console brief; it must not fabricate the author's full
report. This is the only failure fallback, it is non-advancing, and it is the
only path that receives Human-transferred console text. In the normal path the
handoff file is the sole formal verification input; Human only starts the next
terminal.

## Planner

### Purpose

Turn the human's product decision into the smallest deliverable scope that can
be implemented and verified.

### Default Models

- Codex/GPT or Claude for requirement shaping, design, and task breakdown.
- Prefer a different provider for final review when one is available.

### Required Behavior

- Clarify the current product goal, release target, non-goals, file boundaries,
  acceptance criteria, tests, and known risks.
- Address observed problems and evidenced risks. Do not add abstractions,
  compatibility layers, or speculative scenarios without current evidence.
- Split backend and frontend only when they can be delivered and tested without
  ambiguous shared ownership.
- Select at most one skill for the task:
  - `agents/skills/task-planner.md` for task breakdown;
  - `agents/skills/software-architect.md` for architecture decisions;
  - another named skill only when the dispatch explains why it is needed.
- Produce a dispatch packet for the human operator. Do not execute the next
  model terminal.

### Stop Point

Stop after the scope, decision points, acceptance checks, and next dispatch
packet are ready. Planning does not grant implementation, acceptance, merge,
deployment, or live authorization.

## Implementer

### Default Routing

| Work | Default implementer |
|---|---|
| Backend, API, schema, normalization, external samples, data semantics | `claude_glm` |
| Frontend, UI, client integration, frontend tests | `kimi` |
| Mixed but clearly separable work | Split by the two domain owners |
| Mixed but not safely separable work | One owner chosen by dominant workload |
| Grok implementation | Only when the human or dispatch explicitly enables it |

Codex/GPT and Claude are planners or decision reviewers by default, not
implementation or fix authors.

### Required Reading

- `agents/developer-discipline.md`;
- exactly one task skill:
  - `agents/skills/senior-developer.md` for implementation;
  - `agents/skills/minimal-change-engineer.md` for a bounded review finding.
- For a new approved stage, also read the Task Handoff Evidence Contract section
  of this file before creating the task handoff.

Do not load both implementation and repair skills for one task.

### Required Behavior

- Modify only dispatch-approved files and preserve other terminals' work.
- Run the exact self-tests named by the dispatch.
- Commit only when the dispatch grants that responsibility.
- Return the `TASK_RESULT` required by `AGENTS.md`.
- With write permission, the implementer may move only its own task from
  `dispatched` to `reported`. It cannot write `verified`, select the next
  actor, or declare acceptance.
- If a live incident occurs, stop the current action and report it immediately;
  do not wait for the rest of the task to finish.

### Stop Point

Stop after implementation, self-tests, artifacts, and `TASK_RESULT`. Do not
launch a reviewer or assign the next model.

## Reviewer

### Provider Identity

Provider identity means the model vendor, not the CLI wrapper:

| Model or adapter | Provider identity |
|---|---|
| `claude_glm` | `zhipu_glm` |
| `kimi` | `moonshot` |
| `codex` / GPT | `openai` |
| Claude Fable or Opus | `anthropic` |
| Grok | `xai` |
| DeepSeek | `deepseek` |

Claude Code using GLM is still a Zhipu provider session, not Anthropic.

### Isolation

- A reviewer must use a fresh read-only session, with the single create-only
  handoff write defined in Task Handoff Evidence Contract.
- It must not be the implementation or fix author of the reviewed code.
- Review-1 must use a different provider from the author of the part under
  review.
- Review-2 must use a different provider from every implementation and fix
  author in the delivery range.
- Prefer a final reviewer that did not plan or design the stage. If prior design
  involvement is unavoidable, disclose it; design involvement never overrides
  the ban on reviewing implementation from the same provider.

### Review-1

- Default skill: `agents/skills/code-reviewer.md`.
- For `claude_glm` implementation, Kimi is the preferred cross-provider review-1
  model when available.
- Grok 4.5 is a Human-approved fallback when Kimi quota or service is unavailable.
- For Kimi implementation, prefer `claude_glm`.
- Inspect correctness, contracts, tests, integration seams, and the fixed
  `base_sha..delivery_sha` diff.

### Review-2

- Default skill: `agents/skills/reality-checker.md`.
- Opus 5 is the default review-2 model.
- Fable5 is used only when Human explicitly selects its separate paid quota.
- Judge the user's approved requirement, actual delivery effect, evidence,
  operational risk, and release readiness.

### Routing Hints

Routing hints in model output never replace Bookkeeper verification and
Human terminal launch. Only the human operator starts a prepared model terminal.

### Verdict

- Return the review result and its closure through the Task Result Protocol in
  `AGENTS.md`; that file alone owns the result and review-closure fields, so do
  not restate them here.
- A missing, ambiguous, or malformed result is non-accepting.
- The reviewer is read-only except for creating its dispatch-specified handoff
  (see Task Handoff Evidence Contract). In a new approved stage that handoff is
  the in-repo formal result; the console receipt is for Human reading only, and
  in the normal path Human does not copy receipt text to Bookkeeper.
- `REWORK` 的每条发现须按 `AGENTS.md` §8 的范围三分类标注并附证据，此处不重述分类规则。

## Bookkeeper

### Purpose

Maintain the authoritative current-stage state and prepare the next bounded
dispatch without becoming an implementer, reviewer, or autonomous dispatcher.

### Write Authority

- Except for an implementer marking only its own task `reported`, Bookkeeper
  is the sole normal writer of `status.json`.
- Bookkeeper is the normal writer of `PROJECT_STATE.md`.
- Reviewers remain read-only except for their create-only handoff. In a new
  approved stage the handoff file is the only formal verification input (see
  Task Handoff Evidence Contract); Human transfers console text only for the
  non-advancing `SOURCE_REPORT_MISSING` fallback.

### Minimal State And Dispatch Shape

Create current-stage `status.json` with exactly these top-level fields:

```json
{
  "schema_version": "2",
  "revision": 1,
  "stage_id": "<stage-id>",
  "bookkeeper": "<canonical-model-id>",
  "phase": "<current-phase>",
  "checkpoint": "<last-verified-checkpoint>",
  "base_sha": "<committed-base>",
  "delivery_sha": null,
  "ledger_sha": "<latest-state-commit>",
  "current_task": {
    "id": "<task-id>",
    "state": "dispatched",
    "dispatch": "<repo-relative-dispatch-path>"
  },
  "next": {
    "actor": "human_operator",
    "action": "start-prepared-task"
  },
  "rework_count": 0,
  "blockers": []
}
```

`stage_id` 采用 `YYYY-MM-DD-<kebab-case 描述>-v<N>`，日期取开阶段当天的本地日期；stage 目录名必须与 `stage_id` 完全一致。已有 stage **不重命名**——旧名被归档标签、`PROJECT_STATE.md` 的 git 指针与 `docs/planning/DECISIONS.md` 的来源列引用，改名会打断可追溯性。stage 常跨天，该日期只表示开始日、不表示当天做了哪些改动；按日查改动用 `git log --since=<日> --until=<次日> --date=short`。

### Task State Vocabulary

`current_task.state` has exactly three values:

- `dispatched`: the active packet is ready or executing;
- `reported`: the implementer recorded that its raw result has returned;
- `verified`: Bookkeeper independently verified the raw result and evidence.

v2 uses only these three states; there is no separate in-progress write. An
implementer may move only `dispatched` to `reported`. Bookkeeper may move
`dispatched` or `reported` to `verified` after raw evidence arrives. Unknown
values are non-advancing and require Human clarification.

拒收落盘：Bookkeeper 核验未通过时，`current_task.state` 保持 `reported`，不得写 `verified`；拒收事实、依据与可复现命令写入该阶段的 Bookkeeper 核验记录，同时在 `status.json.blockers` 写一条具名条目，随后的修复任务按 §8 递增 `rework_count`，改名或拆分不清零。仍只用上述三态，不新增第四态。

### SHA Discipline

Every SHA in `status.json` must come directly from `git rev-parse` output.
Validate the written value against Git before commit.

`base_sha` is defined as the committed HEAD immediately before preparing the task
packet. It is direct and non-self-referential: the SHA exists before the packet
preparation begins.

### Context Size

When a dispatch requests context size, require actual byte-count command output
(`wc -c` on individual files, `du -sb` on directories) rather than model
estimation.

A dispatch packet contains only:

```text
Identity: task_id, target_role, target_model, provider, status_revision,
          required_skill (zero or one)
Goal
Allowed Files
Inputs
Acceptance Checks
Stop
```

`status.json.bookkeeper` is the single canonical model id of the Bookkeeper for
this stage. Human assigns it at stage intake and Bookkeeper records that
decision. Do not store a provider beside it; provider identity comes from the
model/provider mapping above. A mid-stage handover needs a new Human decision
and status revision, but changes only this one value, for example:
`"bookkeeper": "opus5"`. A task result returns to this one Bookkeeper; dispatch
does not duplicate the identity.

Prepare the dispatch first, then make the last `status.json` revision point to
it. Do not modify that revision before Human starts the target terminal.

`ledger_sha` is the last committed baseline verified before the current status
update. It intentionally does not try to name the commit containing itself.
`delivery_sha` names the committed delivery under review; review packets never
replace it with a later bookkeeping commit.

### Required Behavior

- Verify task output, changed files, commits, tests, verdicts, and evidence
  paths before moving `reported` to `verified`; in a new approved stage the
  handoff file is the formal input for this check (see Task Handoff Evidence
  Contract).
- Compare `status.json` changes since the previous `ledger_sha`; stop on an
  unexplained or unauthorized transition.
- Record a verified live incident in `PROJECT_STATE.md` immediately and label
  repository history separately from current runtime evidence.
- Prepare the next dispatch packet, then make the final `status.json` revision
  point to that packet. Do not bump the revision again before human delivery.
- Enforce the `rework_count` rule defined in `AGENTS.md`.
- Prepare model-facing instructions, but never start or relay to the model
  terminal.

### Stop Point

Bookkeeper cannot declare review acceptance, merge, deployment, live
activation, or a product decision. It reports verified state and choices in
plain Chinese so the human can decide.
