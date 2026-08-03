"""Review-2 REWORK backend regressions (breakdown 16 §3.3, items 1–9).

Deterministic, offline, fake-transport only: no network, no Binance, no real
signing. A fake live executor (duck-typed ``dispatch``/``query_leg``) and a fake
preflight provider script every exchange observation. Each test first encodes
the Review-2 defect's invariant, then asserts the rework honors it.

Amendment 21 (task-local runtime): the live scheduler ``tick`` no longer
dispatches inline — it launches a bounded task-local worker. These tests drive
that worker deterministically via the ``_step`` seam (a synchronous
``_pump_worker`` round with no background thread and no sleep race) instead of
the old synchronous live ``tick``.

1. ``target_n=1`` yields at most one attempt row + one POST pair across
   success / confirmed-failed / single-leg, and via concurrent
   fill-once+scheduler (A-1 / I-1).
2. Fresh filters that change the common grid -> the persisted attempt AND the
   executor's would-send quantity both use the fresh ``q_common`` (A-2).
3. Any missing preflight fact -> zero attempt / zero POST / zero failure count /
   zero simulated call (I-7); a fatal preflight fact stops the task with a
   ``stop_reason`` + a log entry (A-3 / rows 1–2).
4. executor->client signed bodies carry EXACTLY the approved keys; no
   ``endpoint`` or other internal field (A-4).
5. Reconciliation keeps polling with Start off / task done / none eligible,
   never blocks another task; a 400 auth-ambiguity stays UNKNOWN; an explicit
   absent code confirms failure; ``CANCELED`` with a partial fill is terminal
   and retains the fill (A-5 / I-6).
6. Cumulative quote / partial fill / fee / residual reach the projections;
   position aggregation includes any positive-fill non-``FILLED`` leg (A-6).
7. Error matrix: fatal -> ``stopped``+``stop_reason``; non-fatal -> counter;
   threshold reached -> ``paused``; both-accepted resets consecutive failures;
   a confirmed 429 pauses THIS task only (rate_limited) without consuming the
   failure counter (A-7 / I-4 / I-5 / I-2 / amendment 21).
8. The §5 ``entries`` projection: additive key, §5 field names, newest-first,
   pagination, ``—``-able nullable fields, pre-``orderId`` error entries, and
   task-event entries (A-8).
9. Two running tasks proceed independently (each dispatched in the same tick)
   yet each task never starts its pair N+1 until pair N is terminal (A-9).
"""
from __future__ import annotations

from collections import deque
from decimal import Decimal

import pytest

from backend.hedge_open_tasks import domain as D
from backend.hedge_open_tasks.service import HedgeOpenTaskService
from backend.services.live_hedge_executor import (
    LEG_ACCEPTED,
    LEG_REJECTED,
    LEG_UNKNOWN_QUERYING,
    LegDispatch,
    LiveAttemptDispatch,
    LiveHedgeExecutor,
)
from backend.services.hedge_open_live_client import HedgeHttpResponse


# ---------------------------------------------------------------------------
# Clocks + fakes (no network, no signing)
# ---------------------------------------------------------------------------


class _Clock:
    """Monotonic + wall clock advanced explicitly between steps."""

    def __init__(self, t0: int = 0):
        self.t = t0

    def mono_us(self) -> int:
        return self.t

    def wall_us(self) -> int:
        return self.t


def _step(svc, task_id, clock, rounds=1):
    """Deterministic offline replacement for the old synchronous live ``tick``:
    advance the clock then synchronously pump the task-local worker for ``rounds``
    rounds via the ``_pump_worker`` test seam (no background thread, no pacing
    wait, no sleep race). Amendment 21: live dispatch runs on the worker."""
    clock.t += 1_000_000
    svc._pump_worker(task_id, max_rounds=rounds)


def _filters(step: str = "0.1", *, min_qty: str = "0.0001", max_qty: str = "9000",
             min_notional: str = "5") -> dict:
    """A symmetric lot/market filter set so the effective step is unambiguous."""
    return {
        "lot_size": {"min_qty": min_qty, "max_qty": max_qty, "step_size": step},
        "market_lot_size": {"min_qty": min_qty, "max_qty": max_qty, "step_size": step},
        "notional": {"min_notional": min_notional, "apply_min_to_market": True},
    }


def _ok_snapshot(*, usdt="1000000", step="0.1", est_price="50000", tradable=True,
                 position_mode=D.POS_MODE_BOTH, spot=None, perp=None) -> D.PreflightSnapshot:
    return D.PreflightSnapshot(
        spot_filters=spot or _filters(step),
        perp_filters=perp or _filters(step),
        balances={"USDT": Decimal(usdt), "BTC": Decimal("100")},
        position_mode=position_mode,
        est_price=Decimal(est_price),
        rate_limit_order=50,
        symbol_tradable=tradable,
    )


class _FakeProvider:
    """Returns a mutable snapshot (or None) per call."""

    def __init__(self, snapshot=None):
        self.snapshot = snapshot

    def get_snapshot(self, coin, direction):
        return self.snapshot


class _FakeExecutor:
    """Duck-typed live executor scripting per-task dispatch + query results.

    ``dispatch`` consults ``self.scripts[task_id]`` (a deque of
    :class:`LiveAttemptDispatch`); a missing/empty script defaults to a balanced
    accepted pair. ``query_leg`` consults ``self.queries`` (a flat deque of
    verdicts / None) so reconcile polling is deterministic.
    """

    def __init__(self):
        self.scripts: dict[str, deque] = {}
        self.queries: deque = deque()
        self.dispatch_calls = 0
        self.query_calls = 0
        self.last_ctx = None

    def set_script(self, task_id, dispatches):
        self.scripts[task_id] = deque(dispatches)

    def dispatch(self, ctx):
        self.dispatch_calls += 1
        self.last_ctx = ctx
        q = self.scripts.get(ctx.task_id)
        if q:
            return q.popleft()
        return _accepted_pair(ctx.task_id)

    def query_leg(self, leg, symbol, client_order_id, endpoint):
        self.query_calls += 1
        if self.queries:
            return self.queries.popleft()
        return None


def _leg(state, *, name="spot", order_id=None, status=None, executed="0",
         quote="0", avg=None, rate_limited=False, error_code=None,
         error_category=None, retry=None) -> LegDispatch:
    return LegDispatch(
        leg=name, dispatch_state=state, order_id=order_id, exchange_status=status,
        executed_qty=executed, cumulative_quote=quote, avg_price=avg,
        rate_limited=rate_limited, error_code=error_code,
        error_category=error_category, retry_after_seconds=retry,
    )


def _accepted_pair(task_id="t", *, executed="0.5", status=D.LEG_FILLED) -> LiveAttemptDispatch:
    return LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_ACCEPTED, name="spot", order_id="s1", status=status,
                  executed=executed, quote="25000", avg="50000"),
        perp=_leg(LEG_ACCEPTED, name="perp", order_id="p1", status=status,
                  executed=executed, quote="25000", avg="50000"),
        record_payload={"transport": "live", "posted": True},
        rate_limited=False,
        retry_after_seconds=None,
    )


def _live_svc(tmp_path, executor, provider, *, creds=True, clock=None):
    clock = clock or _Clock()
    svc = HedgeOpenTaskService(
        str(tmp_path / "ho.sqlite3"),
        executor=executor,
        preflight_provider=provider,
        mode="live",
        credentials_present=creds,
        mono_us=clock.mono_us,
        wall_us=clock.wall_us,
    )
    svc.set_start_gate(True)
    return svc, clock


def _create(svc, *, direction=D.DIR_FORWARD, single_amount="0.5", target_n=2):
    _, doc = svc.create_task({
        "coin": "BTCUSDT", "direction": direction, "mode": "immediate",
        "single_amount": single_amount, "target_n": target_n,
    })
    return doc


# ---------------------------------------------------------------------------
# 1. target_n=1 -> at most one attempt row + one POST pair
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dispatch_factory", [
    lambda: _accepted_pair(),  # success
    lambda: LiveAttemptDispatch(  # confirmed-failed (both rejected, non-fatal)
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot"),
        perp=_leg(LEG_REJECTED, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    ),
    lambda: LiveAttemptDispatch(  # single-leg (one accepted)
        attempt_id="x",
        spot=_leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
                  executed="0.5", quote="25000", avg="50000"),
        perp=_leg(LEG_REJECTED, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    ),
])
def test_1_target_n_one_yields_at_most_one_attempt_and_one_post(tmp_path, dispatch_factory):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=1)
    exe.set_script(doc["id"], [dispatch_factory()])
    _step(svc, doc["id"], clock)  # first pair
    _step(svc, doc["id"], clock)  # must NOT start a 2nd pair
    # An explicit fill-once must NOT add a 2nd pair either (a done task raises
    # 409 here; a still-running one is blocked by the scheduled>=target guard).
    try:
        svc.post_fill_once(doc["id"])
    except D.HedgeError:
        pass
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 1
    assert exe.dispatch_calls == 1  # exactly one POST pair across worker + fill-once


# ---------------------------------------------------------------------------
# 2. Fresh filters changing the common grid -> fresh q_common everywhere
# ---------------------------------------------------------------------------


def test_2_fresh_filters_persist_and_send_fresh_q_common(tmp_path):
    exe = _FakeExecutor()
    # Create-time grid step 0.1 -> floor(0.555, 0.1) = 0.5 stored on the task.
    provider = _FakeProvider(_ok_snapshot(step="0.1"))
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, single_amount="0.555", target_n=2)
    assert doc["q_common"] == "0.5"  # create-time grid
    # Fresh grid step 0.01 before the live send -> floor(0.555, 0.01) = 0.55.
    provider.snapshot = _ok_snapshot(step="0.01")
    _step(svc, doc["id"], clock)
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert len(attempts) == 1
    # Persisted attempt AND the executor's would-send quantity use the FRESH grid.
    assert attempts[0]["q_common"] == "0.55"
    assert exe.last_ctx.q_common == Decimal("0.55")


# ---------------------------------------------------------------------------
# 3. Missing preflight fact -> fail-closed; fatal fact -> stop + reason + log
# ---------------------------------------------------------------------------


def test_3a_missing_preflight_fact_is_fail_closed(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    # Unreadable market step (both lot + market disabled) -> INCOMPLETE, not fatal.
    provider.snapshot = _ok_snapshot(step="0")
    _step(svc, doc["id"], clock)
    # Zero attempt, zero POST, zero failure count, zero simulated dispatch.
    assert svc.store.list_attempts_for_task(doc["id"]) == []
    assert exe.dispatch_calls == 0
    task = svc.store.get_task(doc["id"])
    assert task["fail_count"] == 0
    assert task["status"] == D.STATUS_RUNNING  # still running, retries later
    # A fail-closed preflight_incomplete task event was recorded.
    _, page = svc.get_logs(None, None)
    assert any(e["entry_type"] == "task_event" and e["overall_result"] is None
               and e["next_action"] == "waiting_query" for e in page["entries"])


def test_3b_fatal_preflight_fact_stops_task_with_reason_and_log(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    # Insufficient USDT for forward (need q*N*price) -> fatal stop at preflight.
    provider.snapshot = _ok_snapshot(usdt="1")
    _step(svc, doc["id"], clock)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_STOPPED
    assert task["stop_reason"] == D.STOP_REASON_INSUFFICIENT_BALANCE
    # No attempt / POST on a fatal stop.
    assert svc.store.list_attempts_for_task(doc["id"]) == []
    assert exe.dispatch_calls == 0
    # A task_stopped entry surfaces the reason.
    _, page = svc.get_logs(None, None)
    stopped = [e for e in page["entries"] if e["entry_type"] == "task_event"
               and e["overall_result"] == "task_stopped"]
    assert stopped and stopped[0]["error_category"] == "fatal"


# ---------------------------------------------------------------------------
# 4. executor->client signed bodies: exactly the approved keys, no endpoint
# ---------------------------------------------------------------------------


class _CapturingClient:
    """Records the params handed to each POST; returns a FILLED acceptance."""

    def __init__(self):
        self.captured = []
        self.credentials_present = True

    def post_margin_order(self, params, *, timestamp_ms, recv_window_ms=None):
        self.captured.append(("spot", params))
        return HedgeHttpResponse(200, {"orderId": 1, "status": "FILLED",
                                       "executedQty": "0.5", "cummulativeQuoteQty": "25000"},
                                 "", None, None)

    def post_um_order(self, params, *, timestamp_ms, recv_window_ms=None):
        self.captured.append(("perp", params))
        return HedgeHttpResponse(200, {"orderId": 2, "status": "FILLED",
                                       "executedQty": "0.5", "cumQuote": "25000"},
                                 "", None, None)

    def query_margin_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        return HedgeHttpResponse(404, None, "", None, None)

    def query_um_order(self, symbol, cid, *, timestamp_ms, recv_window_ms=None):
        return HedgeHttpResponse(404, None, "", None, None)


def test_4_executor_to_client_signed_body_exact_keys_no_endpoint(tmp_path):
    client = _CapturingClient()
    exe = LiveHedgeExecutor(client, now_ms=lambda: 1000)
    from backend.hedge_open_tasks.executor import AttemptContext
    ctx = AttemptContext(
        attempt_id="att1", task_id="t1", coin="BTCUSDT", direction=D.DIR_FORWARD,
        single_amount=Decimal("0.5"), q_common=Decimal("0.5"),
        position_side_mode=D.POS_MODE_BOTH, preflight_snapshot={"est_price": "50000"},
        filter_versions={}, target_n=3, ts_us=1000,
    )
    exe.dispatch(ctx)
    bodies = dict(client.captured)
    spot, perp = bodies["spot"], bodies["perp"]
    assert "endpoint" not in spot and "endpoint" not in perp
    assert set(spot.keys()) == {
        "symbol", "side", "type", "quantity", "sideEffectType",
        "newClientOrderId", "newOrderRespType",
    }
    assert set(perp.keys()) == {
        "symbol", "side", "type", "quantity", "positionSide",
        "newClientOrderId", "newOrderRespType",
    }
    # No secret/credential field ever enters the order body.
    for key in ("apiKey", "apikey", "signature", "timestamp", "recvWindow"):
        assert key not in spot and key not in perp


# ---------------------------------------------------------------------------
# 5. Reconciliation: Start-off/done/none-eligible polling, no cross-task block,
#    auth-ambiguity unknown, explicit-absent confirmed, CANCELED retains fill
# ---------------------------------------------------------------------------


def test_5_reconciliation_invariants(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    # Dispatch leaves both legs UNKNOWN_QUERYING (an ambiguous live write).
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock)
    # Reconcile polls even with Start OFF (I-6): turn the gate off, then poll.
    svc.set_start_gate(False)
    exe.queries.extend([
        _leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000"),
        _leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_FILLED,
             executed="0.5", quote="25000", avg="50000"),
    ])
    _step(svc, doc["id"], clock)
    assert exe.query_calls > 0  # reconciled while Start was off
    task = svc.store.get_task(doc["id"])
    assert task["accepted_pair_count"] == 1  # resolved despite gate off


def test_5b_auth_ambiguity_stays_unknown_then_absent_confirms_failure(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock)
    # First poll: auth-ambiguity stays UNKNOWN (query_leg None) -> keep querying.
    exe.queries.extend([None, None])
    _step(svc, doc["id"], clock)
    attempts = svc.store.list_attempts_for_task(doc["id"])
    assert attempts[0]["pair_outcome"] is None  # still unresolved, never resent
    # Next poll: explicit absent (confirmed never accepted) -> confirmed failure.
    # fix-review1-retry-counter (Human-approved minimal adaptation): a 404 / -2013
    # below the LEG_QUERY_MAX_RETRIES cap is eventual-consistency noise, not a
    # confirmed-absent terminal, so the legs would keep querying and the failure
    # would NOT count. Fill the cap with inconclusive (None) polls so the LAST
    # (10th) query is the absent poll. Only the mechanism adaptation changes; the
    # core assertion (absent confirmed -> fail_count == 1) is unchanged.
    exe.queries.extend([None] * (2 * (D.LEG_QUERY_MAX_RETRIES - 2)))
    exe.queries.extend([
        _leg(LEG_REJECTED, name="spot", error_code="http_404", error_category="absent"),
        _leg(LEG_REJECTED, name="perp", error_code="http_404", error_category="absent"),
    ])
    _step(svc, doc["id"], clock, rounds=D.LEG_QUERY_MAX_RETRIES - 1)
    task = svc.store.get_task(doc["id"])
    assert task["fail_count"] == 1


def test_5c_canceled_with_partial_fill_is_terminal_and_retains_fill(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_FILLED,
                  executed="0.5", quote="25000", avg="50000"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock)
    # Spot poll: accepted + CANCELED but with a partial fill -> terminal, fill kept.
    exe.queries.append(_leg(LEG_ACCEPTED, name="spot", order_id="s1",
                            status=D.LEG_CANCELED, executed="0.2", quote="10000", avg="50000"))
    _step(svc, doc["id"], clock)
    legs = {l["leg"]: l for l in svc.store.list_legs_for_attempt(
        svc.store.list_attempts_for_task(doc["id"])[0]["id"])}
    assert legs["spot"]["terminal"] == 1
    assert Decimal(legs["spot"]["cumulative_base_qty"]) == Decimal("0.2")  # partial retained


# ---------------------------------------------------------------------------
# 6. Cumulative quote / partial / fee / residual + aggregation of non-FILLED legs
# ---------------------------------------------------------------------------


def test_6_partial_fill_fee_residual_and_aggregation(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    # Spot partially fills (NEW, executed 0.3); perp fills fully -> single-leg.
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_ACCEPTED, name="spot", order_id="s1", status=D.LEG_NEW,
                  executed="0.3", quote="15000", avg="50000"),
        perp=_leg(LEG_ACCEPTED, name="perp", order_id="p1", status=D.LEG_FILLED,
                  executed="0.5", quote="25000", avg="50000"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock)
    _, page = svc.get_logs(None, None)
    a = page["attempts"][0]
    assert Decimal(a["spot"]["cumulative_quote_amt"]) == Decimal("15000")  # real quote
    assert Decimal(a["spot"]["cumulative_base_qty"]) == Decimal("0.3")  # partial fill
    assert a["residual"] != "0"  # 0.3 - 0.5 residual surfaced
    # Aggregation includes the spot leg's positive fill even though it is NEW
    # (not literally FILLED).
    positions = {p["coin"]: p for p in svc.get_positions()[1]["positions"]}
    assert "BTCUSDT" in positions


# ---------------------------------------------------------------------------
# 7. Error matrix: fatal stop / non-fatal counter / threshold pause / reset / 429
# ---------------------------------------------------------------------------


def test_7a_fatal_leg_stops_non_fatal_counts_threshold_and_reset(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=5)

    def _failed():
        return LiveAttemptDispatch(
            attempt_id="x",
            spot=_leg(LEG_REJECTED, name="spot"),
            perp=_leg(LEG_REJECTED, name="perp"),
            record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
        )

    # 3 non-fatal failures (default threshold 3) -> paused, not stopped.
    exe.set_script(doc["id"], [_failed(), _failed(), _failed()])
    for _ in range(3):
        _step(svc, doc["id"], clock)
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["fail_count"] == 3
    assert task["stop_reason"] is None


def test_7b_fatal_exchange_code_stops_task(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=5)
    # An UNCONFIRMED -2010 (no balance proof in the message) stays a fatal stop
    # (amendment 21 / user constraint: never mistake an unrecoverable fact for a
    # recoverable pause).
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_REJECTED, name="spot", error_code="-2010", error_category="fatal"),
        perp=_leg(LEG_REJECTED, name="perp", error_code="-2010", error_category="fatal"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock)
    _step(svc, doc["id"], clock)  # worker drains the stopped pair then exits
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_STOPPED
    assert task["stop_reason"] == D.STOP_REASON_EXCHANGE_FATAL


def test_7c_both_accepted_resets_consecutive_failures(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=5)

    def _failed():
        return LiveAttemptDispatch(
            attempt_id="x", spot=_leg(LEG_REJECTED, name="spot"),
            perp=_leg(LEG_REJECTED, name="perp"),
            record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
        )

    exe.set_script(doc["id"], [_failed(), _accepted_pair()])
    _step(svc, doc["id"], clock)  # failure -> consecutive 1
    assert svc.store.get_task(doc["id"])["consecutive_submission_failures"] == 1
    _step(svc, doc["id"], clock)  # success -> consecutive reset
    assert svc.store.get_task(doc["id"])["consecutive_submission_failures"] == 0


def test_7d_rate_limit_pauses_this_task_without_counter(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=5)
    # A 429 surfaces on both legs: rate_limited + a stated retry-after wait.
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True, retry=2),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True, retry=2),
        record_payload={"transport": "live"}, rate_limited=True, retry_after_seconds=2,
    )])
    _step(svc, doc["id"], clock)  # 429 -> pause THIS task + mark the pair for drain
    # Amendment 21 / user constraint 1: the worker drains the in-flight 429 pair
    # (confirmed never accepted -> absent) BEFORE it exits, without resending.
    exe.queries.extend([
        _leg(LEG_REJECTED, name="spot", error_code="http_404", error_category="absent"),
        _leg(LEG_REJECTED, name="perp", error_code="http_404", error_category="absent"),
    ])
    _step(svc, doc["id"], clock)  # drain to terminal -> settle without the counter
    _step(svc, doc["id"], clock)  # own empty + paused -> worker exits
    task = svc.store.get_task(doc["id"])
    # 429 pauses THIS task only and never consumes the failure counter (I-5 / 21).
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    assert task["fail_count"] == 0


def test_7e_query_phase_rate_limit_pauses_keeps_pending_no_resend(tmp_path):
    # R2-F2 (user authorization 28 §2.2): a 429 surfaced during the QUERY phase
    # (reconcile), NOT the POST. The pair was dispatched with ambiguous legs
    # (transport error -> UNKNOWN_QUERYING, NOT rate-limited); the worker's drain
    # then queries them and BOTH come back rate-limited. The worker pauses THIS
    # task, KEEPS the pending legs non-terminal (the write POST is NEVER resent),
    # exits, and consumes no failure counter — distinct from test_7d where the
    # 429 is observed at the POST and the pair later drains to absent.
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    exe.set_script(doc["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    _step(svc, doc["id"], clock)  # dispatch ambiguous pair -> mark for drain
    # The drain queries come back rate-limited (a typed 429 signal, not None).
    exe.queries.extend([
        _leg(LEG_UNKNOWN_QUERYING, name="spot", rate_limited=True),
        _leg(LEG_UNKNOWN_QUERYING, name="perp", rate_limited=True),
    ])
    _step(svc, doc["id"], clock)  # query-phase 429 -> pause + keep pending + exit
    task = svc.store.get_task(doc["id"])
    assert task["status"] == D.STATUS_PAUSED
    assert task["pause_reason"] == D.PAUSE_REASON_RATE_LIMITED
    assert task["fail_count"] == 0  # rate-limited pair consumes no counter
    # the pending legs are KEPT non-terminal (no resend of the write POST).
    assert svc.store.list_non_terminal_legs_for_task(doc["id"]) != []
    # exactly one POST pair was dispatched — the query 429 triggered no resend.
    assert exe.dispatch_calls == 1


# ---------------------------------------------------------------------------
# 8. §5 entries projection
# ---------------------------------------------------------------------------

_ENTRY_KEYS = {
    "entry_id", "entry_type", "task_id", "coin", "direction", "attempt_seq",
    "created_ts", "submitted_ts", "final_ts", "q_common", "planned_quote_amount",
    "spot", "perp", "residual", "overall_result", "error_category",
    "error_code", "error_reason_zh", "next_action",
}


def test_8_entries_projection_shape_pagination_and_events(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=5)

    def _failed():
        return LiveAttemptDispatch(
            attempt_id="x", spot=_leg(LEG_REJECTED, name="spot"),
            perp=_leg(LEG_REJECTED, name="perp"),
            record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
        )

    # A pre-orderId error (both rejected) entry, then a balanced accepted entry.
    exe.set_script(doc["id"], [_failed(), _accepted_pair()])
    _step(svc, doc["id"], clock)
    _step(svc, doc["id"], clock)

    # Additive key present; legacy keys untouched; entries_next_cursor additive.
    _, page = svc.get_logs(None, None)
    assert set(page.keys()) == {
        "logs", "attempts", "entries", "next_cursor", "entries_next_cursor",
    }

    entries = page["entries"]
    assert entries  # non-empty
    # Every entry carries EXACTLY the frozen §5 field names.
    for e in entries:
        assert set(e.keys()) == _ENTRY_KEYS
    # Newest-first by ts.
    ts_seq = [e["created_ts"] for e in entries]
    assert ts_seq == sorted(ts_seq, reverse=True)
    # A pre-orderId error attempt entry (confirmed_failed) is present.
    assert any(e["entry_type"] == "attempt" and e["overall_result"] == "confirmed_failed"
               for e in entries)
    # Amendment 17: entries paginates on its OWN entries_limit/entries_cursor,
    # NOT the legacy limit — the legacy limit no longer caps the entries window.
    # The legacy next_cursor still comes from the logs stream (independent).
    _, paged = svc.get_logs(None, 1)  # legacy limit=1
    assert len(paged["entries"]) == len(page["entries"])  # entries unaffected
    assert paged["next_cursor"] is not None  # legacy logs has-more (2 logs > 1)


def test_8b_entries_task_event_rows_null_leg_fields(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    provider.snapshot = _ok_snapshot(usdt="1")  # fatal preflight at send time
    _step(svc, doc["id"], clock)  # fatal stop -> task_stopped event
    _, page = svc.get_logs(None, None)
    events = [e for e in page["entries"] if e["entry_type"] == "task_event"]
    assert events
    ev = events[0]
    # task_event rows carry null attempt/leg fields (UI renders —).
    assert ev["attempt_seq"] is None
    assert ev["q_common"] is None
    assert ev["spot"]["order_id"] is None and ev["perp"]["order_id"] is None
    assert ev["overall_result"] == "task_stopped"


def test_8c_entries_unified_stream_paginates_no_dup_no_gap(tmp_path):
    """Amendment 17 (opening-log-pagination-compatibility): the additive
    ``entries`` stream paginates a unified attempt+task-event flow on its OWN
    ``entries_cursor``. Loading more never re-surfaces a task event — the R4
    defect was that events had no cursor and re-appeared on every page. Across
    pages every ``entry_id`` appears exactly once, order is globally newest-
    first, the same-ts tie-break is deterministic, has-more comes from the
    unified ``limit+1`` read, and the legacy logs cursor still works on its own.
    """
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=6)
    exe.set_script(doc["id"], [_accepted_pair() for _ in range(6)])
    # Interleave 6 accepted attempts with 3 task events. Events land at the SAME
    # ts as attempts 1/3/5 to exercise the (ts, rank, id) tie-break — at equal ts
    # an event (rank 1) precedes an attempt (rank 0) in DESC order.
    event_ts: list[int] = []
    for i in range(6):
        _step(svc, doc["id"], clock)  # one accepted pair per step (per-task serial)
        if i % 2 == 0:
            svc.store.record_task_event(
                doc["id"], "rate_limited",
                {"reason": "rate_limited", "i": i}, clock.t,
            )
            event_ts.append(clock.t)
    # 6 attempts + 3 events = 9 unified entries. Page through with entries_limit=3.
    seen_ids: list[str] = []
    seen_ts: list[str] = []
    pages: list[list[dict]] = []
    cursor = None
    while True:
        _, page = svc.get_logs(None, None, entries_cursor_str=cursor, entries_limit_raw=3)
        entries = page["entries"]
        pages.append(entries)
        seen_ids.extend(e["entry_id"] for e in entries)
        seen_ts.extend(e["created_ts"] for e in entries)
        cursor = page["entries_next_cursor"]
        if cursor is None:
            break
    # Every entry_id exactly once across all pages (no duplicate, no gap).
    assert len(seen_ids) == 9
    assert len(set(seen_ids)) == 9
    # Globally newest-first across the concatenated pages.
    assert seen_ts == sorted(seen_ts, reverse=True)
    # No entry_id repeats between consecutive pages (the R4 defect would
    # re-surface events here).
    for a, b in zip(pages, pages[1:]):
        assert not ({e["entry_id"] for e in a} & {e["entry_id"] for e in b})
    # All 3 task events survived exactly once.
    event_entries = [e for p in pages for e in p if e["entry_type"] == "task_event"]
    assert len(event_entries) == 3
    # has-more from the unified limit+1 read: 9/3 -> exactly 3 full pages, the
    # last with entries_next_cursor=None (no spurious empty 4th page).
    assert len(pages) == 3
    assert all(len(p) == 3 for p in pages)
    # Deterministic same-ts tie-break: at a shared ts the event (rank 1) is
    # immediately followed by the attempt (rank 0) sharing that ts.
    flat = [e for p in pages for e in p]
    for ts in event_ts:
        idx = next(
            i for i, e in enumerate(flat)
            if e["entry_type"] == "task_event" and e["created_ts"] == D.us_to_iso(ts)
        )
        assert flat[idx + 1]["entry_type"] == "attempt"
        assert flat[idx + 1]["created_ts"] == D.us_to_iso(ts)
    # The 3 task events all land at distinct interleaved ts (1e6/3e6/5e6), so
    # they must be spread across the 3 pages — not all crammed into page 1.
    assert all(any(e["entry_type"] == "task_event" for e in p) for p in pages)
    # Legacy cursor/limit still drive logs/next_cursor INDEPENDENTLY: a small
    # legacy limit yields a legacy next_cursor, re-requesting with it works, and
    # it does NOT touch the entries cursor (entries home page still returns all 9).
    _, legacy = svc.get_logs(None, 2)  # legacy limit=2
    assert legacy["next_cursor"] is not None  # 9 log rows > 2
    _, legacy2 = svc.get_logs(legacy["next_cursor"], 2)
    assert len(legacy2["logs"]) > 0
    assert len(legacy2["entries"]) == 9  # entries home page, independent cursor


# ---------------------------------------------------------------------------
# 9. A-9 two-task independence + per-task sequentiality
# ---------------------------------------------------------------------------


def test_9_two_task_independence_and_per_task_sequentiality(tmp_path):
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc_a = _create(svc, target_n=2)
    doc_b = _create(svc, target_n=2)
    # Task A's pair stays querying (unresolved); task B's pair resolves accepted.
    exe.set_script(doc_a["id"], [LiveAttemptDispatch(
        attempt_id="x",
        spot=_leg(LEG_UNKNOWN_QUERYING, name="spot"),
        perp=_leg(LEG_UNKNOWN_QUERYING, name="perp"),
        record_payload={"transport": "live"}, rate_limited=False, retry_after_seconds=None,
    )])
    exe.set_script(doc_b["id"], [_accepted_pair(), _accepted_pair()])
    _step(svc, doc_a["id"], clock)  # both dispatched (independence)
    _step(svc, doc_b["id"], clock)
    a_after_1 = len(svc.store.list_attempts_for_task(doc_a["id"]))
    b_after_1 = len(svc.store.list_attempts_for_task(doc_b["id"]))
    assert a_after_1 == 1 and b_after_1 == 1  # each got its first pair this tick
    # A's unresolved pair keeps polling as unknown; B (resolved) is free to advance.
    exe.queries.extend([None, None])
    _step(svc, doc_a["id"], clock)  # tick 2
    _step(svc, doc_b["id"], clock)
    a_after_2 = len(svc.store.list_attempts_for_task(doc_a["id"]))
    b_after_2 = len(svc.store.list_attempts_for_task(doc_b["id"]))
    # Per-task serial rule (A-9): A never starts pair 2 while pair 1 is in flight;
    # B is NOT blocked by A and starts pair 2.
    assert a_after_2 == 1
    assert b_after_2 == 2


# ---------------------------------------------------------------------------
# 10. R2-F4 crash-gap recovery: terminal legs + NULL pair_outcome
# ---------------------------------------------------------------------------


def _seed_crash_gap(store, task_id, *, attempt_uuid="gap-1", spot_oid="os1",
                    perp_oid="op1", spot_status=D.LEG_FILLED, perp_status=D.LEG_FILLED,
                    now_us=1_100) -> int:
    """Construct the R2-F4 crash gap directly (user authorization 28 §2.3):
    prepare an attempt, then close BOTH legs to terminal WITHOUT settling the
    pair — simulating a crash between leg-terminalization and pair settlement.
    Returns the attempt id (pair_outcome stays NULL, no non-terminal leg)."""
    attempt = store.prepare_attempt(
        task_id, attempt_uuid, D.DIR_FORWARD, "0.5", D.POS_MODE_BOTH,
        {"est_price": "50000"}, f"cid-{attempt_uuid}-s", {"side": "BUY"},
        D.SPOT_ORDER_PATH,
        f"cid-{attempt_uuid}-p", {"side": "SELL"}, now_us,
    )
    assert attempt is not None
    legs = {l["leg"]: l for l in store.list_legs_for_attempt(attempt["id"])}
    store.resolve_leg_from_query(
        legs["spot"]["id"], exchange_status=spot_status, order_id=spot_oid,
        base_qty="0.5", quote_amt="25000", fee_amount=None, fee_asset=None,
        now_us=now_us, terminal=True,
    )
    store.resolve_leg_from_query(
        legs["perp"]["id"], exchange_status=perp_status, order_id=perp_oid,
        base_qty="0.5", quote_amt="25000", fee_amount=None, fee_asset=None,
        now_us=now_us, terminal=True,
    )
    return attempt["id"]


def test_10a_crash_gap_terminal_legs_null_outcome_recovered(tmp_path):
    # R2-F4 (user authorization 28 §2.3): a crash between leg-terminalization and
    # pair settlement leaves an attempt with BOTH legs terminal but pair_outcome
    # still NULL. It has no non-terminal leg to drain, yet prepare_attempt's
    # in-flight guard (pair_outcome IS NULL) blocks the next group — and the
    # real fill would stay off the counters. A worker round must idempotently
    # finalize it (never resend, never recount).
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=1)
    store = svc.store
    attempt_id = _seed_crash_gap(store, doc["id"])
    # Defect proof: the gap pair is terminal-but-unsettled.
    assert store.list_non_terminal_legs_for_task(doc["id"]) == []
    assert store.get_attempt(attempt_id)["pair_outcome"] is None
    _step(svc, doc["id"], clock)  # worker round recovers the gap
    closed = store.get_attempt(attempt_id)
    assert closed["pair_outcome"] == D.PAIR_ACCEPTED  # both orderId -> accepted
    task = store.get_task(doc["id"])
    assert task["accepted_pair_count"] == 1
    assert task["status"] == D.STATUS_DONE  # last planned group completed


def test_10b_crash_gap_finalize_is_idempotent_no_recount(tmp_path):
    # R2-F4: finalizing the gap is idempotent — a second worker round does NOT
    # re-count (finalize is a no-op once pair_outcome is set).
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=1)
    store = svc.store
    _seed_crash_gap(store, doc["id"])
    _step(svc, doc["id"], clock)
    after1 = store.get_task(doc["id"])
    assert after1["accepted_pair_count"] == 1
    _step(svc, doc["id"], clock)  # second round — must not re-count the gap
    after2 = store.get_task(doc["id"])
    assert after2["accepted_pair_count"] == 1


@pytest.mark.parametrize("status", [D.STATUS_PAUSED, D.STATUS_STOPPED, D.STATUS_DELETED])
def test_10c_crash_gap_recovered_preserves_terminal_task_status(tmp_path, status):
    # R2-F4: the gap is recovered for a task in ANY terminal-ish status the
    # worker may find it in after a restart (paused / stopped / deleted). The
    # pair is finalized (in-flight guard cleared, real fill booked) WITHOUT
    # reviving the task to running and WITHOUT opening a new group.
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    store = svc.store
    _seed_crash_gap(store, doc["id"])
    store.set_task_status(doc["id"], status, 1_200)
    _step(svc, doc["id"], clock)  # worker recovers the gap, then exits
    task = store.get_task(doc["id"])
    assert task["status"] == status  # not revived
    assert task["accepted_pair_count"] == 1  # real fill booked
    # no second group opened (the in-flight guard cleared only via finalize).
    assert len(store.list_attempts_for_task(doc["id"])) == 1


def test_10d_crash_gap_rate_limited_settles_without_counter(tmp_path):
    # R2-F4 + amendment 21: a gap left by a rate-limited pair (attempt.rate_limited
    # stamped at the 429 dispatch) is recovered via settle_attempt_no_counters —
    # the pair_outcome is set (in-flight guard clears) but the failure counter is
    # NOT consumed, exactly like a 429 pair drained the normal way.
    exe = _FakeExecutor()
    provider = _FakeProvider(_ok_snapshot())
    svc, clock = _live_svc(tmp_path, exe, provider)
    doc = _create(svc, target_n=2)
    store = svc.store
    attempt_id = _seed_crash_gap(store, doc["id"])
    store.mark_attempt_rate_limited(attempt_id)
    store.set_task_status(doc["id"], D.STATUS_PAUSED, 1_200)
    _step(svc, doc["id"], clock)
    closed = store.get_attempt(attempt_id)
    assert closed["pair_outcome"] is not None  # in-flight guard cleared
    task = store.get_task(doc["id"])
    assert task["fail_count"] == 0  # rate-limited pair consumes no counter
    assert task["consecutive_submission_failures"] == 0
