# R4 Diff Reconciliation — Hedge Open Live Hardening v1

Performed by the bookkeeper after both implementation sessions stopped.
Parallel mode requires this before any evidence commit
(`docs/parallel-development-mode.md` R4; `AGENTS.md` Hard Gates).

## 1. File-boundary check — PASS

`git diff --stat HEAD` plus untracked files, mapped to each task's allowed list:

### Task A (backend, `claude_glm`) — 11 modified + 4 created, all in-boundary

| File | Allowed by |
| --- | --- |
| `backend/app/server.py` | allowed (route wiring only) |
| `backend/hedge_open_tasks/domain.py` | allowed (minimal error-code/copy additions) |
| `backend/hedge_open_tasks/executor.py` | allowed |
| `backend/hedge_open_tasks/service.py` | allowed |
| `backend/hedge_open_tasks/store.py` | allowed |
| `backend/hedge_open_tasks/wire_constraints.py` (new) | allowed, named in the list |
| `backend/services/hedge_preflight_provider.py` | allowed |
| `backend/tests/test_hedge_api.py` | `backend/tests/test_hedge_*.py` |
| `backend/tests/test_hedge_executor.py` | same |
| `backend/tests/test_hedge_service.py` | same |
| `backend/tests/test_hedge_store.py` | same |
| `backend/tests/test_hedge_preflight_provider.py` (new) | same |
| `backend/tests/test_hedge_wire_constraints.py` (new) | same |
| `backend/tests/test_live_hedge_executor.py` | allowed, named in the list |
| `reports/api-samples/2026-07-hedge-open-live-hardening-v1/` (new) | allowed, named in the list |

### Task B (frontend, `claude_glm`) — 2 modified, all in-boundary

| File | Allowed by |
| --- | --- |
| `frontend/index.html` | allowed |
| `frontend/self-check.js` | allowed |

### Forbidden files — zero changes, verified

`backend/services/live_hedge_executor.py`,
`backend/services/hedge_open_live_client.py`,
`backend/services/binance_signing.py`,
`backend/hedge_open_tasks/scheduler.py`, `backend/config.py`,
`backend/borrow_tasks/**`, `docs/**` — none appear in the diff. No R3
escalation was raised by either session, and none was needed.

Neither implementer committed, and neither touched `status.json` or
`70-handoff.md`. Single-writer discipline held.

## 2. Merged-state test rerun — PASS (authoritative)

Both sessions had stopped before this run, so it supersedes either
implementer's own observation. Raw output: `60-test-output.txt`.

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest backend/tests -q` | **979 passed** in 50.31s |
| `node frontend/self-check.js` | 全部自检通过, **122 PASS** |
| `.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q` | 72 passed |
| `git diff --check` | clean (exit 0) |

The frontend report cites 963 passed for the backend suite. That is not a
discrepancy: it ran while Task A was still writing, exactly the transient the
dispatch predicted. The merged-state number is 979.

## 3. Cross-seam contract check — PASS

The direct lesson from the previous stage's three cross-seam drifts. Each face
the frontend consumes, checked against the backend's actual wire shape:

| Contract face | Backend | Frontend | Verdict |
| --- | --- | --- | --- |
| settings doc `version` | `settings_to_doc` returns `"version": int(settings["version"])` (`service.py:174-183`) | reads `state.hedgeSettings.version` (`index.html:3520`) | match |
| start-gate POST body | `_START_GATE_BODY_KEYS = ("enabled", "confirm", "version")` with `reject_unknown_keys` (`service.py:49`) | posts `{ enabled, confirm: true, version }` (`index.html:3522-3524`) | match, field for field |
| `missing_leg` error | `400 "missing_leg"`, Chinese detail, `extra={"missing": [...]}` (`service.py:483-485`) | consumed through the generic `hedgeApi` → `setErr(err.message)` path, no bespoke parsing | match; B-4 deliberately added no new error logic |

## 4. Spot-check of the implementations' factual claims

Claims verified against the code rather than taken from the reports:

- **A-1**: `_client_order_ids` returns `hg{attempt_id}s|p`, documented as 2+32+1
  = 35 (`executor.py:159-163`). Single derivation point; the live executor picks
  it up by import, and `live_hedge_executor.py` is unmodified.
- **A-5**: confirmed and repaired — `build_*_order_params` now use
  `D.fmt_decimal(quantity)` instead of `str(quantity)`
  (`executor.py:131,152`). The design's §8 unverified point turned out to be
  real (`str(Decimal)` can emit `1E-7`), and the fix is the minimal one the
  design pre-authorised inside S5.
- **A-3**: `body.get("confirm") is not True` — a truthy `1` or `"true"` is
  rejected, which is what the breakdown's review focus demanded
  (`service.py:911`). `version` excludes `bool` before the int check
  (`service.py:915-917`). CAS and its audit row share one transaction under
  `with self._lock, self._conn` (`store.py:1735-1741`).
- **A-4**: the probe is genuinely tri-state — `status >= 500` or transport
  failure → `None`; HTTP 400 with body `code == -1121` → `False`; 2xx with the
  symbol present → `True` (`hedge_preflight_provider.py:121-132`). A separate
  status-surfacing reader was added because the pre-existing one swallowed
  `HTTPError` bodies.
- **M-1**: pinned on both sides — backend asserts the audit payload's key set is
  disjoint from the attempt-shape keys (`test_hedge_store.py:349-360`); frontend
  asserts `extractHedgeAttempts` ignores a `start_gate_changed` row
  (self-check `[PASS] M-1 …`).
- **B-1**: strict `task.worker_active === false` (`index.html:3796`), so
  `null`/`undefined` fall on the disabled side and dry-run is unchanged.
- **M-2**: the frontend chose not to touch the 14 `hgo-` fixtures, stating the
  reason (arbitrary display arguments; changing them would require syncing four
  assertions for no benefit). Permitted by the dispatch, and consistent — none
  were changed.

## 5. Open items carried into review (not blockers)

From the two reports, for the reviewers' attention rather than for repair here:

1. UM-side `newClientOrderId` charset regex is still not independently measured;
   the 36-char cap is measured. Documented in the api-samples page as an
   unverified boundary.
2. The 409 dialog **title** was not frozen by the design (only the body text
   was); the frontend used a neutral structural title and flagged it.
3. Live `create_task` now issues two extra public unsigned GETs. Dry-run is
   unaffected (`DisabledPreflightProvider` has no probe).
4. `set_start_gate_cas` has never run against the durable production DB — by
   design, since the implementers were barred from starting the service. Its
   correctness rests on `tmp_path` tests until an operator exercises it.
5. ADR-H5's known tradeoff stands: a leg that is genuinely absent *while* the
   read also fails is not caught.

## 6. Verdict

**R4 reconciliation PASS.** Boundaries held, no forbidden file touched, no
cross-seam drift, merged-state suites green. Proceeding to the evidence commit,
the fingerprint, and the pre-review gate.

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/16-r4-diff-reconciliation.md
本地北京时间: 2026-07-27 20:52:00 CST
下一步模型: bookkeeper
下一步任务: 证据 commit + 指纹 + pre-review 门，然后出两个 grok-4.5 review-1 packet
