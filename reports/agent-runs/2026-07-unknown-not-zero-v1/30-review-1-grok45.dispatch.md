# Dispatch — review1-task1-grok45

```text
Identity:
  task_id:         review1-task1-grok45
  target_role:     Reviewer
  target_model:    grok-4.5
  provider:        xai
  status_revision: 6
  required_skill:  agents/skills/code-reviewer.md
```

Review-1 of the sealed delivery. You are **read-only**: no edit, no commit, no
branch, no write of any kind, no network, no credentials, no service control, no
read or write of `data/**`. Read-only `git` / `grep` / `rg` and running the test
suite are expected.

Provider isolation: the implementer is `claude_glm` (`zhipu_glm`); you are `xai`.
Kimi was the preferred review-1 model but its quota has not recovered, and Human
approved you as the registered fallback (`agents/roles.md:134`, decision D-2).

## Goal

Judge correctness, contracts, tests and integration seams of
`base_sha..delivery_sha`:

```text
base_sha     ac8d493a903051394fc9fda3ca467590a6e2f837
delivery_sha 851dd088183037564b0e0afb5ffe1347ce3665a0
```

The stage closes one defect family: **a figure the exchange did not return must
stay unknown (`None` / `NULL`), never become `0`; a real `"0"` from the exchange
must still be zero.** Seven deliverables, D1-D7, described in
`00-plan.md` §4 and the implementation packet.

The single most valuable thing you can do is **look for a money site the closed
list missed**. The list has already been extended twice — once by a plan review
that found `prepare_attempt`'s SQL seed (D7/S4), once by Bookkeeper verification
that found the guard blind to S2's shape. Neither was found by the sweep that
declared itself exhaustive. Run your own sweep of
`backend/hedge_open_tasks/**` and `backend/services/live_hedge_executor.py` and
report what you find with file and line, including a negative result stated as
such — 「查过且没有」 must stay distinguishable from 「没查」.

Second priority: **the guard itself** (`find_money_zero_defaults` in
`backend/tests/test_hedge_purity.py`). It is the stage's durable deliverable — the
thing that makes an eighth round of this defect impossible. Ask whether it can be
defeated by a plausible future edit, and whether its allow-list markers can drift
into blanket exemptions.

## Allowed Files

**None.** Read-only. Return findings in your terminal output; the Human operator
transfers them to the Bookkeeper. Do not write into the repository.

## Inputs

| Path | Range | Why |
|---|---|---|
| `reports/agent-runs/2026-07-unknown-not-zero-v1/00-plan.md` | whole | Goal, non-goals, the closed site list §4, acceptance criteria §8 |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/10-unknown-not-zero-glm.dispatch.md` | whole | What was ordered, D1-D7 |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/20-task1-glm-result.md` | whole | What the implementer says it did |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/21-bookkeeper-verification.md` | §2, §4 | The two P1 findings and the standing instructions below. **Note §2's V1 evidence was later corrected — see 24** |
| `reports/agent-runs/2026-07-unknown-not-zero-v1/24-bookkeeper-verification-task1b.md` | whole | The repair, the correction, and what is sealed |
| `backend/hedge_open_tasks/store.py` | `285-320`, `340-360`, `455-480`, `760-800`, `820-860`, `1230-1310`, `1345-1395`, `1955-2010` | Every changed region |
| `backend/tests/test_hedge_purity.py` | `160-400` | The guard and its meta-tests |
| `backend/tests/test_hedge_store.py` | search-only | The paired per-site regressions |
| `backend/hedge_open_tasks/domain.py` | `1017-1053` | `build_leg_exposure`, unchanged, now the single implementation |
| `git diff ac8d493..851dd08` | whole | The sealed range |

## Settled ground — do not re-litigate

Each of these is a recorded decision with a reason. Filing one as a finding costs
a round and will be declined:

1. **Quantity is out of scope** (Human decision D-5, `01-human-decisions.md`).
   `cumulative_base_qty` keeping its `'0'` default and `filled_qty` /
   `executed_qty` defaulting to `"0"` are correct. The reason is not merely
   precedent: that column is `TEXT NOT NULL DEFAULT '0'`, so honesty there costs a
   live-table schema rebuild, and a leg that was never sent genuinely has zero
   fill. The seven `or "0"` sites in `service.py` are all quantity.
2. **The guard cannot cover the r5 category** — a migration over-nulling a real
   `'0'`. No static pattern can distinguish a fabricated zero from a real one at
   rest. Paired per-site regressions (missing figure **and** real `'0'`) cover it
   instead. The implementer stated this limit rather than inflating coverage; that
   is correct behaviour, not a defect.
3. **D6 prevents semantic row rewriting on default construction, not all writes.**
   Additive DDL still writes the file. The `hedge_open_leg` rebuild is
   `PRAGMA`-guarded and no-ops on an already-migrated database. Both facts are
   stated deliberately; the strong claim is the one that would be wrong.
4. **M1 does not exist.** It was deleted at `95ac1a5` last stage. Its absence is
   correct; do not ask for it back.
5. **The review range contains bookkeeping commits and one unrelated `docs:`
   commit** (`c4ca4f4`, a Harness findings write-up). That is Harness finding G3 —
   a contract wording problem, not a delivery defect. Judge only the product and
   test changes.
6. **`backend/tests/test_hedge_api.py::test_oversized_body_is_body_too_large` is a
   known pre-existing flake** (`p3-flaky-oversized-body-test`) that fails
   intermittently with `ConnectionResetError` and passes on isolated re-run. It is
   untouched by this delivery. If it fails for you, re-run it alone and say so; it
   is not a finding.

## Acceptance Checks

Run and report raw output:

```text
python3 -m pytest backend/tests -q
```

Expected: 1090 passed (baseline 1071 + 19 new). Bookkeeper measured exactly that.

Your output must contain:

1. Your own sweep for missed money sites, with the commands and their raw output,
   and an explicit statement if the result is negative.
2. A judgement on the guard's defeatability, with a concrete example of an edit
   that would evade it if you find one.
3. A judgement on whether each of D1-D7 does what it claims, naming the file and
   line you checked rather than the report you read.
4. A judgement on the paired regressions: is every fixed site covered by both a
   missing-figure case and a real-`'0'` case, deterministically?
5. Findings ordered by severity, each with file, line, and a concrete failure
   scenario (inputs → wrong output). A finding without a failure scenario is an
   opinion; mark it as one.
6. What is load-bearing and must not be weakened by a later fix round. The
   previous stage lost work to fixes that collided.

## Stop

Stop after the verdict. Return exactly the `[TASK_RESULT v2]` block from
`AGENTS.md` §7, using **only** its nine mandated Chinese labels —
任务 ID / 执行结果 / 结果摘要 / 产物 / 检查结果 / 阻塞项 / 本地北京时间 /
下一步模型 / 下一步任务 — plus the three review-closure lines
评审结论 / 问题记录 / 修复要求, closing with `[/TASK_RESULT]`.

Do **not** invent fields (`model`, `provider`, `delivery_sha`, `branch`, `summary`,
`notes`, `verdict`, …), do not copy this Identity block into your result, and do
not write `[/TASK_RESULT v2]` as the closing marker. A previous delivery this
stage did all four and had to be redone. `结果摘要` is capped at 300 characters
and `检查结果` at eight grouped items; detailed findings go in your prose above the
block, and `问题记录: none（结论在终端输出）` is correct since you write no file.

`评审结论: ACCEPT` means the delivery closes the family as specified and you found
no defect requiring repair. `REWORK` requires findings plus executable repair
requirements.

`下一步模型: opus5（记账人，Human 转交结果）`.
