# Dispatch — review2-task1-codex

```text
Identity:
  task_id:         review2-task1-codex
  target_role:     Reviewer
  target_model:    codex (GPT-5 class)
  provider:        openai
  status_revision: 8
  required_skill:  agents/skills/reality-checker.md
```

Final review of the sealed delivery. Read-only: no edit, no commit, no branch, no
network, no credentials, no service control, no read or write of `data/**`.
Read-only `git` / `grep` / `rg` and running the test suite are expected.

## Mandatory disclosure — read before anything else

**You already reviewed this stage's plan.** You ran `task0-plan-review` on
2026-07-30 and returned `REWORK` with four substantive findings. You therefore have
prior design involvement in what you are now finally reviewing
(`agents/roles.md:125-127`). Human was told and selected you anyway (decision D-6).

Consequences you must act on:

1. **Treat your own earlier verdict as unproven.** Re-derive from the code. Do not
   confirm a finding because you remember making it, and do not assume a finding
   was fixed because a document says so.
2. Provider isolation still holds and is not waived: the implementer is
   `claude_glm` (`zhipu_glm`); you are `openai`.
3. What is lost is independence at the final gate. Compensate by being harder on
   the things you did **not** raise before — your earlier list is the part of this
   delivery most likely to have been over-fitted.

## Goal

Review-1 (Grok 4.5, `xai`) returned `ACCEPT`. You are the release-readiness gate.
`agents/skills/reality-checker.md` is your method: requirement vs actual effect,
evidence quality, operational risk, readiness. Not a second code review.

Range:

```text
base_sha     ac8d493a903051394fc9fda3ca467590a6e2f837
delivery_sha 851dd088183037564b0e0afb5ffe1347ce3665a0
```

Judge these, each with evidence or an explicit "cannot determine":

**J1 — Were your own four findings actually resolved, or absorbed?** You raised:
S4 (`prepare_attempt` seeding a money zero), D5 under-specification, the M1
factual error, and the quantity scope question. Check each against the code and
the record, not against the claim that it was fixed. An absorbed finding — one
answered in prose while the behaviour is unchanged — is the failure mode to hunt.

**J2 — Does the delivery actually close the family, or does it close a list?**
The plan's own §4 admits the site list was extended twice by outside review and
describes itself as "exhaustive as far as two independent sweeps reach". Review-1
swept independently and found nothing new. You are the third sweep. If you find a
money site nobody has named, that is the finding of this review.

**J3 — Is the guard worth what the stage claims for it?** Bookkeeper verification
confirmed five ways past it: `or Decimal(0)`, `or 0`, a ternary, laundering a
coercion through an intermediate variable, and `fee_amount` being outside the
money-name set entirely (`31-review-1-grok45-result.md`). Given that, judge whether
the stage's central promise — that this defect family cannot silently return — is
honestly stated in the delivery documents, or whether some document overstates it.
**Flag any overstatement as a finding.** This stage exists to remove
plausible-but-false claims; one about its own guard would be the same defect at the
level of the report.

**J4 — Is the evidence real?** The paired per-site regressions (missing figure
**and** real exchange `'0'`, per site) are the only coverage for the r5 category
the static guard cannot reach. Are they deterministic, do they actually assert what
they claim, and would they fail if the fix were reverted? Pick at least one and
revert-test it mentally or by reading, not by trusting its name.

**J5 — Operational risk of releasing this.** Specifically: `D4` moved the
reconcile path onto `domain.build_leg_exposure`, which **raises** on `ts_us <= 0`
where the old copy silently emitted a 1970 timestamp. That is a new exception path
in a live settlement route. Is it safe, is it tested, and what happens
operationally if it fires? Second: `D6` moved M2's row repair behind a default-off
flag — confirm no production caller passes it and that its absence cannot leave a
database in a state the code cannot read.

**J6 — Is the record honest?** Two corrections were made mid-stage: the plan
asserted an M1 that had been deleted a stage earlier, and the Bookkeeper's own V1
evidence mislabelled seven quantity sites as money sites and demanded acceptance
evidence obtainable only by damaging the guard (corrected in
`24-bookkeeper-verification-task1b.md` §2). Both are disclosed. Judge whether the
disclosures are adequate or whether something else was quietly adjusted. You have
the whole ledger; use it.

## Allowed Files

**None.** Read-only. Return findings in your terminal output; the Human operator
transfers them to the Bookkeeper. Do not write into the repository.

## Inputs

`00-plan.md` is top authority for what was required. All paths under
`reports/agent-runs/2026-07-unknown-not-zero-v1/` unless stated.

| Path | Range | Why |
|---|---|---|
| `00-plan.md` | whole | **Top authority.** §2 goal, §3 non-goals, §4 site list, §8 acceptance |
| `01-human-decisions.md` | whole | D-1..D-6, including your own disclosure |
| `10-unknown-not-zero-glm.dispatch.md` | whole | What was ordered |
| `20-task1-glm-result.md`, `23-task1b-glm-result.md` | whole | What the implementer claims |
| `21-bookkeeper-verification.md` | whole | The two P1 findings and the corrected V1 evidence |
| `24-bookkeeper-verification-task1b.md` | whole | The repair, the correction, what is sealed |
| `31-review-1-grok45-result.md` | whole | Review-1's verdict and the confirmed residual risks |
| `backend/hedge_open_tasks/store.py` | `285-320`, `340-360`, `455-480`, `760-800`, `820-860`, `1230-1310`, `1345-1395`, `1955-2010` | Every changed region |
| `backend/tests/test_hedge_purity.py` | `160-400` | The guard |
| `backend/tests/test_hedge_store.py` | search-only | The paired regressions — J4 |
| `backend/hedge_open_tasks/domain.py` | `1017-1053` | `build_leg_exposure`, the single remaining implementation, unchanged |
| `git diff ac8d493..851dd08` | whole | The sealed range |

Do **not** read `07-plan-review-verdict-raw.md` (your own earlier output) before
forming your own view on J1. Read it afterwards if you want to compare.

## Settled ground — do not re-litigate

Each carries a recorded reason. Filing one as a finding costs a round and will be
declined:

1. **Quantity is out of scope** (Human decision D-5). `cumulative_base_qty` is
   `TEXT NOT NULL DEFAULT '0'`, so honesty there costs a live-table schema rebuild;
   a leg never sent genuinely has zero fill. The seven `or "0"` sites in
   `service.py` are all quantity — this was the subject of the Bookkeeper's
   corrected error, so it is doubly settled.
2. **The guard cannot cover the r5 category** and the delivery says so rather than
   inflating it. That is correct behaviour. J3 asks whether the *rest* of the
   documents are equally honest, not whether this limit should be hidden.
3. **D6 prevents semantic row rewriting, not all writes.** Additive DDL still
   writes. The `hedge_open_leg` rebuild is `PRAGMA`-guarded and no-ops on a
   migrated database.
4. **M1 does not exist** (deleted at `95ac1a5`). Its absence is correct.
5. **The review range contains bookkeeping commits and one unrelated `docs:`
   commit** (`c4ca4f4`). Harness finding G3, not a delivery defect.
6. **`test_hedge_api.py::test_oversized_body_is_body_too_large` is a known
   pre-existing flake** (`p3-flaky-oversized-body-test`), untouched by this
   delivery. If it fails, re-run it alone and say so.
7. **`task2-same-family-rework-rule` is still pending** and is outside this range.
   The stage is not closed by your verdict; task1 is. Do not file the stage as
   incomplete.

## Acceptance Checks

```text
python3 -m pytest backend/tests -q
```

Expected 1090 passed. Bookkeeper measured exactly that; review-1 confirmed.

Your output must contain:

1. A verdict per judgement J1-J6, evidence-backed or explicitly undeterminable.
2. Your own sweep for J2 with raw command output, and a negative result stated as
   a negative — 「查过且没有」 must stay distinguishable from 「没查」.
3. For J3, a direct answer: is any delivery document overstating the guard? Quote
   the sentence if so.
4. Findings by severity, each with file, line, and a concrete failure scenario
   (inputs → wrong output). A finding without one is an opinion; label it.
5. A release recommendation: is this fit to merge to `main` on Human's
   authorisation, and what risk remains after merge?
6. What is load-bearing and must not be weakened by a later round.

## Stop

Stop after the verdict. Return exactly the `[TASK_RESULT v2]` block from
`AGENTS.md` §7 — the nine mandated Chinese labels 任务 ID / 执行结果 / 结果摘要 /
产物 / 检查结果 / 阻塞项 / 本地北京时间 / 下一步模型 / 下一步任务, plus the three
closure lines 评审结论 / 问题记录 / 修复要求, closing with `[/TASK_RESULT]`.

No invented fields (`model`, `provider`, `delivery_sha`, `branch`, `verdict`,
`summary`, `notes`, …), do not copy this Identity block into the result, and the
closing marker is not `[/TASK_RESULT v2]`. An earlier delivery this stage violated
all four and was redone. `结果摘要` ≤ 300 characters, `检查结果` ≤ eight grouped
items; detailed findings go in prose above the block.
`问题记录: none（结论在终端输出）` is correct since you write no file.

`评审结论: ACCEPT` means fit for Human's merge decision. `REWORK` requires findings
plus executable repair requirements.

`下一步模型: opus5（记账人，Human 转交结果）`.
