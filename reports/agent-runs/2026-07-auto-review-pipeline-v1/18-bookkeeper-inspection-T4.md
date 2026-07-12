# Bookkeeper inspection — T4 serial-v1 slimming

## Disposition

T4 is **not ready for evidence commit or review-1**. File boundaries and the
reported 163-test baseline are valid, but independent inspection found two
required runtime gaps and related live-contract residue.

## Verified

- Exactly 18 modified files: 16 implementation files plus append-only
  `20-implementation.md` and `60-test-output.txt`.
- No product path, `status.json`, `70-handoff.md`, history, seal, verdict, or
  review artifact was modified by GLM.
- Both evidence files are append-only.
- Independent full suite: 163 tests, PASS.
- `py_compile`, both JSON parses, checkpoint validator, and `git diff --check`:
  PASS.
- Slim authorization fields and registry values are otherwise aligned with the
  frozen design.

## Required corrections

### C1 — missing/invalid registry timeout does not fail closed

`AutoReviewRunner._resolve_timeout()` still returns
`DEFAULT_ADAPTER_TIMEOUT_SECONDS=1800` when the registered adapter timeout is
missing or invalid. The immutable T4 packet requires missing/invalid production
timeout configuration to fail during preflight, not silently install a shared
fallback. Independent probe returned:

```text
missing_timeout_resolves_to= 1800
```

Required: validate every auto-loop adapter's positive integer timeout and the
Grok command-specific override during preflight; reject missing, boolean,
non-positive, or malformed values without an adapter call or commit. An
explicit injected test override may remain.

### C2 — runner accepts non-task review units

The validator restricts `AUTO_UNIT_KINDS` to `task`, but runner
`_ordered_units()` returns every dictionary without checking `kind`. The runner
therefore lacks its own fail-closed task-only preflight. Independent probe
returned:

```text
non_task_units_returned= [{'id': 'legacy-tip', 'kind': 'tip'}]
```

Required: runner preflight must reject any review unit whose kind is not exactly
`task`, before model calls or commits, with a focused negative test.

### C3 — live parallel-tip event residue

`tip_once_grok_failure` remains a live terminal event in runner, workflow,
validator, docs, and tests. Serial v1 has no tip unit or tip-once branch. Rename
the event consistently to a serial semantic such as
`review_1_fallback_exhausted`; preserve the same fail-closed transition.

### C4 — normative documentation residue

- Authorization docs still say a change to `adapters` requires supersession,
  although adapter authority is no longer in authorization.
- Serial task steps contain a duplicated `2. implementer writes allowed paths`.

## Evidence correction

The implementation report's CMD6 used `git diff --name-only 54ce1c8..HEAD`,
which does not inspect uncommitted T4 files. The bookkeeper reran the correct
worktree command, `git diff --name-only`, and confirmed no forbidden product
path. Preserve the original output and append the corrected check.

These are pre-review implementation-completeness corrections under the same
operator-authorized amendment. They do not consume a new formal review rework.

本地北京时间: 2026-07-12 12:30:23 CST
下一步模型: Claude-GLM / GLM-5.2（现有实现会话）
下一步任务: 执行 task-T4-bookkeeper-correction-round1-claude-glm.prompt.md

---

## Correction round 1 reinspection

C1-C4 are independently verified complete:

- full suite: 168 tests, PASS;
- registry timeout missing/boolean/zero/negative values fail preflight;
- `_resolve_timeout` has no silent shared 1800-second production fallback;
- runner preflight independently rejects every non-`task` review unit;
- active `tip_once_grok_failure` residue is zero and the serial event is
  consistently `review_1_fallback_exhausted`;
- both documentation residues are removed;
- checkpoint validator and `git diff --check` pass.

The implementation is not yet committable because an unrelated concurrent
model-version update appeared in the same worktree. It changes GPT/Codex from
`gpt-5.5` to `gpt-5.6-sol` and Grok defaults from
`grok-build`/`grok-composer-2.5-fast` to `grok-4.5` across mixed T4 files and
the forbidden `docs/harness-design.md`. GLM states that it did not author these
version changes. They are outside the frozen T4 scope and cannot be silently
included, reverted, or moved by the bookkeeper without operator disposition.

本地北京时间: 2026-07-12 13:06:54 CST
下一步模型: Human operator
下一步任务: 决定并发模型版本升级是纳入当前 stage，还是隔离到后续 main Harness 维护
