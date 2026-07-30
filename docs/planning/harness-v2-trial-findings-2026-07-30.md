# Harness v2 Trial Findings — First Live Stage

Author: Opus 5, as Bookkeeper of `2026-07-unknown-not-zero-v1` (the first stage
run entirely under v2). Recorded 2026-07-30 at Human's request, to be verified and
turned into fixes by an independent model later. **Nothing here is actioned.**

Baseline: v2 merged to `main` at `ac8d493`; v1 baseline for comparison is
`7180f61`. The v2 merge removed 9,269 lines and added 2,382 — including
`scripts/validate-stage.py` (2,414 lines) and
`workflows/templates/stage-delivery.yaml` (825 lines).

Every finding below carries a verification command or a file:line so a reviewer
can confirm or reject it without trusting this document.

---

## Part 1 — Gaps worth fixing

### G1. Review closure lost both its schema and its validator, while the contract still demands well-formedness

`AGENTS.md:118` — "Missing or ambiguous review-closure data is non-accepting."
Nothing enforces it any more. The v2 merge deleted **both**
`schemas/review-verdict.schema.json` and `scripts/validate-stage.py`, so review
closure is now three prose lines (`评审结论` / `问题记录` / `修复要求`) with no
machine check of any kind.

Why this is not academic: in the previous stage the bookkeeper twice received a
verdict whose JSON had been mangled in transit — once by shell expansion
(`865ca33`), once by terminal line-wrapping in the operator's paste (round 7).
Both times the repair could be *validated* against the schema afterwards. That
safety net is gone. This session's Codex verdict was well-formed, but that was a
competent model's habit, not enforcement.

```text
git show 7180f61:schemas/review-verdict.schema.json | head -5   # existed
test -e schemas/review-verdict.schema.json                       # now absent
grep -n "非accepting\|non-accepting" AGENTS.md
```

Candidate fix: either restore a minimal verdict schema plus a ~50-line checker, or
delete the "ambiguous is non-accepting" clause and admit the closure is
advisory. The current state — a rule with no mechanism — is the worst of the
three.

### G2. No plan or design review step exists

`AGENTS.md` §6 goes from step 1 (Human + Planner decide the goal) straight to
step 3 (implementer implements). §8 classifies **task changes** and routes
review-1/review-2 at the delivery boundary only. Nothing independent reads the
plan that decides what the implementer will and will not touch.

Evidence that this costs real money, from this stage: Human asked for an ad-hoc
Codex read of the plan before implementation. It returned `REWORK` and found
(a) a missed defect site at the *source* of the family the stage exists to close
(`store.py:748/765`), and (b) a factual error where the plan asserted a migration
still existed that had been deleted a stage earlier at `95ac1a5`. Under the
previous stage's observed rate, both would have surfaced as review rounds after
implementation. The previous stage's own `design_staleness` record is the second
case study.

Full write-up with three options and a recommendation:
`reports/agent-runs/2026-07-unknown-not-zero-v1/06-v2-gap-plan-review.md`.
Recommended: one sentence in §8, `HIGH_RISK` only, verdict routes to the Planner
and does not touch `rework_count`.

### G3. `base_sha`'s definition puts bookkeeping commits inside the review range

`agents/roles.md:223-225` defines `base_sha` as "the committed HEAD immediately
before preparing the task packet", justified as non-self-referential. That
reasoning is sound but it is not review-range purity: the plan, the dispatch and
every status revision land between `base_sha` and `delivery_sha`, so reviewers
receive them inside the diff they are told to inspect.

Candidate fix: define `base_sha` as the commit the implementer starts from, and
keep the anti-self-reference property by requiring it to exist before the packet
is prepared (both hold simultaneously — they are not in tension).

### G4. Nobody is made responsible for putting the worktree on the work branch

`AGENTS.md` §9 says Human selects the branch or worktree. No role is told to
*put the worktree there*. In this stage the Bookkeeper committed on `main`,
force-pointed the stage branch at the same commit, and delegated the checkout to
the implementer through packet prose — a soft guarantee that depends on the
implementer obeying. Human caught the worktree still on `main` after the packet
had been handed over. No damage (both refs were the same commit, tree clean), but
the packet is the wrong place for this.

Candidate fix: one line in the Bookkeeper section — the worktree must be on the
selected branch before the packet is handed to Human, and the Bookkeeper reports
the branch name with the handover.

### G5. `status.json`'s field set is closed, with no home for routing decisions

`roles.md:178-203` specifies "exactly these top-level fields". Correct instinct —
v1's `status.json` had grown past 1,200 lines with 60+ ad-hoc keys. But real
decisions still need a home: which model does review-1 and why, which branch
Human chose, what deviation was disclosed, what scope question Human resolved.
This stage invented `01-human-decisions.md` for them. The next stage will invent
a different filename.

Candidate fix: name the file in the contract (one row in the §4 table), or add a
single `decisions` pointer field to `status.json`. Do **not** reopen the field
set.

### G6. `PROJECT_STATE.md` has a hard 2 KB budget and no eviction rule

The file was already at 2,125 bytes when this stage began. Recording one new fact
(a live risk Human had resolved) required trimming two unrelated entries to fit.
The budget is right; the absence of a rule means the trimming choice is the
Bookkeeper's taste, and the trimmed content is only recoverable from git.

Candidate fix: state the eviction order — resolved items first, then oldest
`[LEGACY-*]`, and require a git reference for anything evicted while still open.

### G7. The reading budget is arithmetically unreachable for this codebase, and nothing requires ranged reading

`AGENTS.md:61` targets ~8K tokens for startup and ~15K for a loaded task.
`backend/hedge_open_tasks/store.py` alone is 98 KB (~25K tokens);
`service.py` is another 1,933 lines. A packet that names whole files cannot meet
the target, and nothing in v2 requires line ranges — that is a convention this
stage applied by hand after the previous stage measured an implementation session
reaching ~65% of a 1M context *before implementing anything*.

```text
wc -c backend/hedge_open_tasks/store.py backend/hedge_open_tasks/service.py
```

Candidate fix: require ranged inputs in the dispatch shape whenever a named file
exceeds some threshold, and say what the Implementer should do when the ranges
prove insufficient (report a blocker, not read the whole file silently).

### G8. The named Planner skill is inapplicable vendored boilerplate

`AGENTS.md:69` routes planning to "`Planner` + one named planning skill", and
`roles.md:48-49` names `agents/skills/task-planner.md` first. That file is a
vendored web-agency PM role: its concrete guidance is Laravel/Livewire/FluxUI,
`ai/memory-bank/site-setup.md` paths, Playwright screenshot capture, and 30-60
minute task sizing. None of it applies to this repository.
`agents/skills/software-architect.md` genuinely does apply.

The practical effect is that "load one planning skill" reads as a compliance
ritual, which is how it came to be skipped in this stage. Note the honest part:
the plan review found no plan defect traceable to the missing skill — its
findings were evidence errors, not methodology errors. So this is a contract
hygiene issue, not a proven quality loss.

Candidate fix: map stage type to skill (backend defect stage →
`software-architect.md`), or drop `task-planner.md` from the Planner menu until
it is adapted.

### G9. How to launch each model terminal is now undocumented

v1 required dispatch preparation to use `docs/model-adapters.md`, and
`agents/registry.yaml` held adapter commands plus `observed_available_models`.
The v2 merge deleted both. `roles.md` carries model *names* and provider identity
but no invocation, so the knowledge now lives only with the Human operator.

```text
git show 7180f61:docs/model-adapters.md | head -20
git diff --name-only --diff-filter=D 7180f61..main | grep -vE "^reports/"
```

Related: the registry also carried the review-1 candidate pool. Its deletion
silently resolved a v1 follow-up (`registry-grok-drift`) by removing the file
that was wrong, which is fine, but the Kimi-unavailable / GLM-is-the-implementer
squeeze it documented is still real — this stage needed a Human waiver to route
review-1 to Grok 4.5, the third stage running to need one.

### G10. No harness version marker

`.harness-version` was deleted. There is now no in-repo statement of which
harness contract version is in force, which makes "was this stage run under v1 or
v2" a git-archaeology question.

### G11. 39 completed stage directories still sit in the normal worktree

Against `AGENTS.md` §9.5, which requires removing a completed stage directory at
close. Already filed in `PROJECT_STATE.md` as `[OPEN][HARNESS-HYGIENE]`. Listed
here only so it is not raised twice.

### G14. An implementer invented its own result schema, and nothing objected

The first `[TASK_RESULT v2]` returned for `task1-unknown-not-zero` (`claude_glm`)
replaced §7's nine mandated Chinese labels with eleven invented English fields —
`model`, `provider`, `status_revision`, `result: DONE`, `delivery_sha`, `branch`,
`blockers`, `summary`, `notes`, `handoff_model` — copied the dispatch's `Identity`
block into the result, and closed with `[/TASK_RESULT v2]` instead of
`[/TASK_RESULT]`. Human caught it by eye and had the implementer redo it; the
corrected block is compliant.

Two separate problems:

1. **No mechanism.** This is G1 seen from the other side. §7 specifies the label
   set, `AGENTS.md:162` specifies the closing marker, and nothing checks either.
   A ~30-line checker over the result block would have caught all four violations
   deterministically. Notably the invented fields were *plausible* — `delivery_sha`
   and `branch` are things a Bookkeeper wants — which is exactly why prose
   conformance fails: a helpful-looking deviation reads as an improvement.
2. **The invented fields carried authority they should not have.** `result: DONE`
   is not one of §7's three values, and `delivery_sha: 6c250f4` is a field only the
   Bookkeeper may set (`roles.md:170-171`). A downstream reader could have taken a
   self-declared delivery SHA as sealed state.

Candidate fix: a small result-block validator, shared with G1's verdict checker —
the same routine can check both, since a review result is a task result plus three
closure lines. Alternatively state in §7 that unrecognised fields are ignored and
an unrecognised closing marker is non-accepting, so at least the contract says
what happens.

### G15. No route exists for "Bookkeeper verification found a defect before review-1"

Verification of `task1-unknown-not-zero` failed on D5: the delivered static guard
implemented a different rule than the dispatch specified, missing two of the four
defect categories it claimed (`21-bookkeeper-verification.md` §2). The findings are
objective and reproduced, so sending them to review-1 would waste a round.

But v2 has no vocabulary for this. `current_task.state` has exactly three values —
`dispatched`, `reported`, `verified` (`roles.md:207-216`) — and no way to say
"reported, verified, and rejected". `rework_count` counts "formal `REWORK` repair
rounds" (`AGENTS.md:182`), which a Bookkeeper rejection is not. §6 step 6 gives
repair authority only after a review finding.

The Bookkeeper's chosen handling: keep `rework_count` at 0 and carry the repair as
a distinct task `task1b-d5-repair`. **That reading is favourable to the implementer
and gameable** — the same reasoning would let a Bookkeeper route unlimited repair
rounds around the three-round cap by renaming the task each time. It was disclosed
rather than quietly used.

Candidate fix: say explicitly whether a pre-review Bookkeeper rejection consumes
rework budget, and give it a state or a counter so it cannot be hidden by task
renaming. This is closely related to G12's same-root-cause brake — both are about
what counts as a round.

### G16. No channel exists for an implementer to contest an acceptance check

The `task1b-d5-repair` packet required, as acceptance evidence, a non-empty
detector hit list over a pre-fix file. That check was **wrong** — the Bookkeeper
had mislabelled seven quantity sites as money sites, and the defect category it
cited had been repaired a stage earlier, so the evidence was obtainable only by
mis-flagging quantity, i.e. by damaging the guard to satisfy a Bookkeeper
(corrected in `24-bookkeeper-verification-task1b.md` §2).

The implementer handled it correctly: it fixed the real code defect, stated the
disagreement objectively, supplied alternative proof, and refused to comply
silently. But v2 gave it nowhere to put that. §7's fields are 执行结果 / 结果摘要 /
产物 / 检查结果 / 阻塞项 — none of which is "I met the intent and dispute this
criterion". It ended up as prose inside `检查结果` and a qualified `阻塞项: none`,
which worked only because the model was careful and the reader was paying
attention. A less careful implementer's cheapest path is to widen a definition
until the check goes green.

Candidate fix: one sentence in §7 or the Implementer section — an implementer may
return `completed` while marking a named acceptance check as contested, with its
reason and substitute evidence, and the Bookkeeper must rule on it explicitly
before sealing. Cheap, and it makes the honest path the documented one.

### G13. The proposals directory is not versioned, and the workflow depends on it

`reports/agent-runs/_proposals/` is excluded by `.git/info/exclude:8` — a
machine-local exclusion, not the shared `.gitignore`. Nothing in it has ever been
committed:

```text
git check-ignore -v reports/agent-runs/_proposals/<any file>
git log --oneline -1 -- reports/agent-runs/_proposals/   # empty
```

This matters because the workflow cites those files as authority. The previous
stage's `70-handoff.md` describes three of its four defects as coming "from the
standing proposal" — a source that exists on exactly one machine, in no history,
recoverable from no archive. This document was originally written there and moved
to `docs/planning/` for that reason.

Candidate fix: decide whether proposals are durable inputs (then track them) or
scratch (then stop citing them as a defect source in stage documents). Either is
fine; the current state means a stage's stated evidence can vanish with a
`git clean`.

### G12. Same-root-cause brake — already scheduled, do not re-raise

v2 closed half of the v1 problem: `AGENTS.md:182` caps `rework_count` at three and
routes past it to a Human choice, which removes the "amended criteria" bypass the
previous stage used to reach round 7 on a cap of 3. What is still missing is a
brake on repeated point fixes to one root cause. That is `task2` of the current
stage, already planned. Listed for completeness.

---

## Part 2 — What worked, and must not be "improved" away

A reviewer given a list of gaps tends to fix everything nearby. These earned
their place:

**W1. The startup path.** `AGENTS.md` → `ACTIVE.json` → `PROJECT_STATE.md` was
enough to resume cold with no active stage, well under the 8K target. This is a
large improvement over v1's workflow-YAML-first startup.

**W2. SHA discipline.** `roles.md:220-221` requires every SHA in `status.json` to
come from `git rev-parse` output and be validated before commit. It caught a real
defect **this session**: the Bookkeeper wrote a `ledger_sha` whose first 7
characters were right and whose remaining 33 were invented. The mandated check
failed it and it was replaced with the true value. Keep this rule; consider
extending it to a commit-time check rather than a habit.

**W3. The closed `status.json` field set.** G5 asks where the overflow lives, not
for the field set to be reopened. v1's 1,200-line status file is the thing being
escaped.

**W4. `rework_count` excluding pre-dispatch packet correction** (`AGENTS.md:182`).
This stage's plan review returned `REWORK` before any code existed; because of
this clause the implementer's three-round budget stayed intact. Under v1's
reading that correction could plausibly have consumed a third of the budget
before implementation began.

**W5. The six-section dispatch shape** (`roles.md:233-243`). Small enough to
write, complete enough to bound a task. Two packets written to it this stage;
neither needed a field it did not have.

**W6. The v1→v2 deletion was clean.** Mechanically checked: no active contract
file references any deleted path.

```text
for f in AGENTS.md PROJECT_STATE.md agents/roles.md agents/developer-discipline.md; do
  grep -oE '`[a-zA-Z0-9_./-]+\.(md|py|json|yaml|sh)`' "$f" | tr -d '`' | sort -u |
  while read -r p; do case "$p" in */*|*.py|*.sh|*.yaml) [ -e "$p" ] || echo "[$f] $p"; esac; done
done
```

Returned empty on 2026-07-30 at `6471873`. G1 and G9 are about capability lost
with the deleted files, not about broken references.

---

## Part 3 — Suggested handling

These are not equal. If only some get done:

| Priority | Findings | Why |
|---|---|---|
| Do first | G1, G14, G2 | G1 and G14 are the same hole from two sides — the contract specifies a result/verdict shape and nothing checks it; both were exercised for real this stage, and one shared ~30-line checker closes them. G2 has measured value from this stage |
| Do first, needs a decision not just wording | G15 | Whether a pre-review Bookkeeper rejection consumes rework budget. Left open, the cap is evadable by renaming a task; the current handling is disclosed but is the Bookkeeper's judgement, not a rule |
| Cheap and clearly right | G3, G4, G5, G6, G10, G13 | Each is one to three lines in an authority that already exists, or one `git add` |
| Needs judgement | G7, G8 | G7 needs a threshold nobody has picked; G8 needs someone to decide whether to adapt or drop a vendored skill |
| Already owned | G11, G12 | Filed elsewhere; do not duplicate |
| Leave alone | W1-W6 | |

**Pattern across G1, G14, G15 and G12.** Four of the five highest-priority findings
are the same species: v2 kept v1's rules and deleted v1's mechanisms. The contract
still says what a verdict must contain, what a result must contain, what counts as
a rework round — and there is now no code that checks any of it. v2's minimalism
was right about the 2,414-line validator being too much; the lesson is not that
zero was the correct replacement.

Constraint any fix must respect: `AGENTS.md` §2 forbids a second detailed active
authority for any rule, field shape, state vocabulary, routing map, or numeric
limit. Several candidate fixes above are deliberately phrased as edits to the
authority that already owns the rule, not as new files. A reviewer proposing a new
document should be asked which existing authority cannot hold it.

Also note that a Harness contract change is `HIGH_RISK` under §8 and needs
review-1 plus review-2 — so batching these into one edit is cheaper than
trickling them, but a batch spanning §6, §8, §9, roles.md and PROJECT_STATE.md is
harder to review. Two batches (mechanism gaps, then hygiene) is probably the
right shape.
