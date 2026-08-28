"""Dual-ledger flow-log service — fetch orchestration + response assembly
(design §13.1–§13.5, §15).

Owns one fetch ``run`` (paginated pull of both sources → idempotent store
write → run record + per-source coverage), the pure-read ``GET flow-log``
response (§13.2), and the manual ``POST refresh`` entrypoint (§13.4). The
cadence thread lives in :mod:`backend.ledger_flow.scheduler`; this module
holds no threading of its own except a single-flight lock.

Hard rules carried over from task A (design §13.2): IDs are strings, amounts
pass through verbatim, no SQL aggregation on amount columns (summaries are
:mod:`backend.ledger_flow.domain` Decimal sums), and an unparseable amount in
a group nulls that group's total. The service is the authority for "success
run" classification (§15.4 / F3) and ``consecutive_failure_count`` (§13.2
rule 10 / F2) — the store only returns raw run rows.
"""
from __future__ import annotations

import threading
from decimal import Decimal, localcontext
from typing import Any, Callable, Dict, List, Optional

from ..services.private_client import PrivateEndpointError
from . import domain
from .store import LedgerStore

# ---- window / pagination constants (design §13.5 / §15.2) ----
_3H_MS = 3 * 60 * 60 * 1000
_30D_MS = 30 * 24 * 60 * 60 * 1000
_1D_MS = 24 * 60 * 60 * 1000
_1H_MS = 60 * 60 * 1000
_5M_MS = 5 * 60 * 1000

_INTEREST_PAGE_SIZE = 100
_INTEREST_MAX_PAGES = 40
_INCOME_PAGE_LIMIT = 1000
_INCOME_MAX_PAGES = 10
# Cross-margin capital-flow (stage 2026-08-10): SINGLE page, no fromId paging.
_CAPITAL_PAGE_LIMIT = 1000

_ROW_LIMIT = 500  # §13.2 rule 8: detail cap per pane

# Stable short error codes (§13.2 rule 9). Never carry Binance bodies/URLs.
_ERR_INTEREST = "interest_history_failed"
_ERR_INCOME = "um_income_failed"
_ERR_CAPITAL = "capital_flow_failed"
_ERR_RATE_LIMITED = "rate_limited"
_ERR_DISABLED = "private_channel_disabled"

# "Success run" kinds (§15.4 / F3). manual NEVER participates in the baseline.
_SUCCESS_KINDS = frozenset({"scheduled", "startup_catchup", "backfill"})
# Kinds that count toward the hourly retry budget (manual is user-triggered).
_ATTEMPT_KINDS = frozenset({"scheduled", "startup_catchup", "backfill"})

# How many recent runs to inspect for baseline / failure-count / hour logic.
_RUN_LOOKBACK = 64

_INTEREST_PUBLIC_KEYS = (
    "tx_id", "accrued_at_ms", "asset", "raw_asset", "principal",
    "interest", "interest_rate", "type", "isolated_symbol",
)
_INCOME_PUBLIC_KEYS = (
    "tran_id", "income_type", "time_ms", "symbol", "income",
    "asset", "info", "trade_id",
)
_CAPITAL_PUBLIC_KEYS = (
    "id", "tran_id", "time_ms", "asset", "flow_type", "amount",
)


def _beijing_day_start_ms(now_ms: int) -> int:
    """Beijing (UTC+8) local midnight of ``now_ms``, as a UTC ms epoch.

    ``today`` (§15.4) attributes rows by occurred time within the Beijing
    calendar day; the day boundary is Beijing 00:00, not UTC 00:00.
    """
    day_ms = 24 * 60 * 60 * 1000
    offset = 8 * 60 * 60 * 1000
    beijing = now_ms + offset
    day_index = beijing // day_ms
    return day_index * day_ms - offset


class _FetchResult:
    """Outcome of paginating one source for one run."""

    __slots__ = ("status", "error", "rows", "fetched", "truncated", "boundary_ms")

    def __init__(self, status, error, rows, fetched, truncated, boundary_ms):
        self.status = status            # "ok" | "error"
        self.error = error              # stable short code or None
        self.rows = rows                # normalized, deduped
        self.fetched = fetched          # len(rows)
        self.truncated = truncated      # hit page cap
        self.boundary_ms = boundary_ms  # interest: oldest; income: newest


class LedgerFlowService:
    """Fetch orchestrator + response builder for the dual-ledger flow-log.

    ``store`` is the task-A :class:`LedgerStore`; ``private_client`` is the
    shared :class:`PrivateClient` (same credential read / gates as the
    snapshot); ``now_ms`` is an injectable millisecond clock (tests drive it
    without sleeping).
    """

    def __init__(
        self,
        store: LedgerStore,
        private_client,
        *,
        now_ms: Callable[[], int],
    ):
        self._store = store
        self._client = private_client
        self._now_ms = now_ms
        self._flight_lock = threading.Lock()
        self._scheduler_enabled = False

    # ------------------------------------------------------------------ #
    # usability / scheduler flag
    # ------------------------------------------------------------------ #
    def is_usable(self) -> bool:
        """True when the private read-only channel can actually fetch."""
        return self._client is not None and bool(getattr(self._client, "enabled", False))

    def mark_scheduler_enabled(self) -> None:
        """Called by the composition root once the cadence thread has started."""
        self._scheduler_enabled = True

    @property
    def scheduler_enabled(self) -> bool:
        return self._scheduler_enabled

    # ------------------------------------------------------------------ #
    # one fetch run (single-flight)
    # ------------------------------------------------------------------ #
    def run_once(self, kind: str) -> Optional[Dict[str, Any]]:
        """Run one fetch of both sources. Returns an outcome dict or ``None``
        if another run is in flight (single-flight, non-blocking)."""
        if not self._flight_lock.acquire(blocking=False):
            return None
        try:
            return self._do_run(kind)
        finally:
            self._flight_lock.release()

    def _do_run(self, kind: str) -> Dict[str, Any]:
        now = self._now_ms()
        started_at = now
        cov = self._store.get_coverage()

        i_ws, i_we, i_gap = self._compute_window("interest", cov["interest_end_ms"], now)
        u_ws, u_we, u_gap = self._compute_window("income", cov["income_end_ms"], now)

        i_res = self._fetch_interest(i_ws, i_we)
        u_res = self._fetch_income(u_ws, u_we)

        first_seen = self._now_ms()
        # run record is its own transaction (F1): written from the FETCH outcome
        # so it persists regardless of any later commit issue; it is written
        # before the per-source commits because commit_* need its id as
        # first_seen_run_id. new_row_count defaults to 0 in storage (see
        # handoff: the task-A store exposes no update_run; the authoritative
        # new counts come from commit_* and are returned in the run outcome).
        run_id = self._store.insert_run({
            "kind": kind,
            "started_at_ms": started_at,
            "finished_at_ms": first_seen,
            "window_start_ms": min(i_ws, u_ws),
            "window_end_ms": now,
            "interest_status": i_res.status,
            "interest_error": i_res.error,
            "interest_fetched_row_count": i_res.fetched,
            "income_status": u_res.status,
            "income_error": u_res.error,
            "income_fetched_row_count": u_res.fetched,
            "truncated": i_res.truncated or u_res.truncated,
        })

        i_new = self._commit_interest(run_id, first_seen, i_res, cov, i_ws, i_we, i_gap)
        u_new = self._commit_income(run_id, first_seen, u_res, cov, u_ws, u_we, u_gap)

        # Capital pull is fully isolated (plan §4.2.6): it runs after the
        # two-source run record + commits, never touches flow_refresh_runs, and
        # any failure is recorded only in capital's own meta — it cannot change
        # the interest/income outcome above.
        cap_outcome = self._run_capital_flow(now)

        run = self._store.recent_runs(1)
        run_record = run[0] if run else None
        return {"run": run_record, "interest_new": i_new, "income_new": u_new,
                "capital": cap_outcome}

    # ---- per-source window (§15.2) ----
    def _compute_window(self, src, cov_end_ms, now):
        """Return (window_start, window_end, downtime_gap_or_None).

        ``window_end = now``; ``window_start = max(cov_end - 3h, now - 30d)``;
        first-ever (cov_end None) → 1-day backfill window. A downtime gap is
        recorded when the 30-day floor cuts off before the old coverage end
        (downtime > 30d)."""
        floor = now - _30D_MS
        if cov_end_ms is None:
            return now - _1D_MS, now, None
        window_start = max(cov_end_ms - _3H_MS, floor)
        gap = None if cov_end_ms >= floor else {
            "source": src, "start_ms": cov_end_ms, "end_ms": floor,
        }
        return window_start, now, gap

    # ---- paginated fetch (§13.5) ----
    def _fetch_interest(self, ws, we) -> _FetchResult:
        rows: List[dict] = []
        page = 1
        done = False
        while page <= _INTEREST_MAX_PAGES and not done:
            try:
                data = self._client.fetch_interest_history_page(
                    start_time=ws, end_time=we, current=page, size=_INTEREST_PAGE_SIZE)
            except PrivateEndpointError as exc:
                return _FetchResult("error", self._classify(exc, _ERR_INTEREST),
                                    [], 0, False, None)
            page_rows = data.get("rows", []) if isinstance(data, dict) else []
            if not page_rows:
                done = True
                break
            rows.extend(domain.normalize_interest_rows(page_rows))
            total = data.get("total") if isinstance(data, dict) else None
            if (isinstance(total, int) and len(rows) >= total) or len(page_rows) < _INTEREST_PAGE_SIZE:
                done = True
            else:
                page += 1
        truncated = not done
        rows = domain.dedup_interest_rows(rows)
        oldest = min((r["accrued_at_ms"] for r in rows), default=None)
        return _FetchResult("ok", None, rows, len(rows), truncated, oldest)

    def _fetch_income(self, ws, we) -> _FetchResult:
        rows: List[dict] = []
        page = 1
        done = False
        while page <= _INCOME_MAX_PAGES and not done:
            try:
                data = self._client.fetch_um_income_page(
                    start_time=ws, end_time=we, page=page, limit=_INCOME_PAGE_LIMIT)
            except PrivateEndpointError as exc:
                return _FetchResult("error", self._classify(exc, _ERR_INCOME),
                                    [], 0, False, None)
            page_rows = data if isinstance(data, list) else []
            if not page_rows:
                done = True
                break
            rows.extend(domain.normalize_income_rows(page_rows))
            if len(page_rows) < _INCOME_PAGE_LIMIT:
                done = True
            else:
                page += 1
        truncated = not done
        rows = domain.dedup_income_rows(rows)
        newest = max((r["time_ms"] for r in rows), default=None)
        return _FetchResult("ok", None, rows, len(rows), truncated, newest)

    @staticmethod
    def _classify(exc, default):
        status = getattr(exc, "status", None)
        code = getattr(exc, "code", None)
        if status == 429 or code == -1003:
            return _ERR_RATE_LIMITED
        return default

    # ---- per-source commit + coverage advance (§15.2 / F6(b)) ----
    def _commit_interest(self, run_id, first_seen, res, cov, ws, we, downtime_gap):
        if res.status != "ok":
            return 0  # failed source: zero rows, coverage unchanged
        old_start = cov["interest_start_ms"]
        new_gaps = []
        if downtime_gap is not None:
            new_gaps.append(downtime_gap)
        if res.truncated:
            # Left pane is DESC: rows continuously cover [oldest, window_end];
            # coverage_end advances to window_end, start must NOT move to
            # window_start, and a gap [window_start, oldest] is recorded.
            cov_start = old_start if old_start is not None else res.boundary_ms
            cov_end = we
            if res.boundary_ms is not None:
                new_gaps.append({"source": "interest", "start_ms": ws, "end_ms": res.boundary_ms})
        else:
            cov_start = min(old_start if old_start is not None else ws, ws)
            cov_end = we
        result = self._store.commit_interest(
            rows=res.rows, run_id=run_id, first_seen_at_ms=first_seen,
            coverage_start_ms=cov_start, coverage_end_ms=cov_end,
            new_gaps=new_gaps or None)
        return result["new_row_count"]

    def _commit_income(self, run_id, first_seen, res, cov, ws, we, downtime_gap):
        if res.status != "ok":
            return 0
        old_start = cov["income_start_ms"]
        new_gaps = [downtime_gap] if downtime_gap is not None else []
        if res.truncated:
            # Right pane is ASC: rows cover [window_start, newest]; coverage_end
            # advances only to newest_fetched (NOT window_end); no gap — the
            # next run resumes from newest-3h and self-heals.
            cov_start = min(old_start if old_start is not None else ws, ws)
            cov_end = res.boundary_ms if res.boundary_ms is not None else we
        else:
            cov_start = min(old_start if old_start is not None else ws, ws)
            cov_end = we
        result = self._store.commit_income(
            rows=res.rows, run_id=run_id, first_seen_at_ms=first_seen,
            coverage_start_ms=cov_start, coverage_end_ms=cov_end,
            new_gaps=new_gaps or None)
        return result["new_row_count"]

    # ------------------------------------------------------------------ #
    # cross-margin capital-flow (stage 2026-08-10) — isolated third source
    # ------------------------------------------------------------------ #
    def _compute_capital_window(self, cap_end_ms, now):
        """Capital pull window (plan §4.1.2): first-ever → ``[now-1d, now]``;
        otherwise ``[cap_end-3h, now]``. No 30d floor and no gap — capital
        coverage is fully separate from the two-source coverage aggregate
        (plan §4.2), so a downtime gap is never recorded for it."""
        if cap_end_ms is None:
            return now - _1D_MS, now
        return cap_end_ms - _3H_MS, now

    def _fetch_capital(self, ws, we) -> _FetchResult:
        """Single-page capital-flow pull. A FULL page (== limit) is flagged
        ``truncated`` (= "possibly incomplete"); no ``fromId`` paging is done
        (plan §4.1.2 / non-goal §4.3)."""
        try:
            data = self._client.fetch_capital_flow_page(
                start_time=ws, end_time=we, limit=_CAPITAL_PAGE_LIMIT)
        except PrivateEndpointError as exc:
            return _FetchResult("error", self._classify(exc, _ERR_CAPITAL),
                                [], 0, False, None)
        page_rows = data if isinstance(data, list) else []
        rows = domain.dedup_capital_rows(domain.normalize_capital_rows(page_rows))
        possibly_incomplete = len(page_rows) >= _CAPITAL_PAGE_LIMIT
        newest = max((r["time_ms"] for r in rows), default=None)
        return _FetchResult("ok", None, rows, len(rows), possibly_incomplete, newest)

    def _run_capital_flow(self, now) -> Dict[str, Any]:
        """One capital pull + commit, fully isolated from the interest/income
        run (plan §4.2.6). Any failure is recorded in capital's own
        ``last_run`` meta only; it never raises into the caller and never
        touches the two-source run record / coverage aggregate.

        On a successful single page, coverage_end advances to ``now``
        regardless of ``possibly_incomplete`` — a full page is a success, not a
        failure (plan §5.4 frozen: only failure blocks the advance); the flag
        is carried in ``last_run`` for display."""
        try:
            state = self._store.get_capital_flow_state()
            ws, we = self._compute_capital_window(state["end_ms"], now)
            res = self._fetch_capital(ws, we)
            first_seen = self._now_ms()
            last_run = self._capital_last_run(first_seen, res, ws, we)
            if res.status != "ok":
                # Failed pull: record last_run, advance NOTHING.
                self._store.commit_capital_flow(
                    rows=[], first_seen_at_ms=first_seen,
                    coverage_start_ms=None, coverage_end_ms=None,
                    last_run=last_run)
                return {"status": "error", "error": res.error,
                        "fetched_row_count": 0, "new_row_count": 0,
                        "possibly_incomplete": False}
            cov_start = min(state["start_ms"] if state["start_ms"] is not None else ws, ws)
            result = self._store.commit_capital_flow(
                rows=res.rows, first_seen_at_ms=first_seen,
                coverage_start_ms=cov_start, coverage_end_ms=we,
                last_run=last_run)
            return {"status": "ok", "error": None,
                    "fetched_row_count": result["fetched_row_count"],
                    "new_row_count": result["new_row_count"],
                    "possibly_incomplete": bool(res.truncated)}
        except Exception:  # isolation guard: capital must never break the run
            try:
                self._store.commit_capital_flow(
                    rows=[], first_seen_at_ms=self._now_ms(),
                    coverage_start_ms=None, coverage_end_ms=None,
                    last_run={"finished_at_ms": self._now_ms(), "status": "error",
                              "error": "capital_internal_error",
                              "possibly_incomplete": False,
                              "window_start_ms": None, "window_end_ms": None})
            except Exception:
                pass
            return {"status": "error", "error": "capital_internal_error",
                    "fetched_row_count": 0, "new_row_count": 0,
                    "possibly_incomplete": False}

    @staticmethod
    def _capital_last_run(finished_at, res, ws, we):
        """Build the capital ``last_run`` JSON (fetched/new counts are stamped
        by the store, which is the authority for them)."""
        return {
            "finished_at_ms": finished_at,
            "status": res.status,
            "error": res.error,
            "possibly_incomplete": bool(res.truncated),
            "window_start_ms": ws,
            "window_end_ms": we,
        }

    # ------------------------------------------------------------------ #
    # run classification (§15.4 / F3) — service authority, not store
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_success_run(run) -> bool:
        return (
            run["kind"] in _SUCCESS_KINDS
            and run["interest_status"] == "ok"
            and run["income_status"] == "ok"
        )

    def _recent_finished_runs(self) -> List[dict]:
        return self._store.recent_runs(_RUN_LOOKBACK)

    def _successful_runs(self) -> List[dict]:
        return [r for r in self._recent_finished_runs() if self._is_success_run(r)]

    # ---- scheduler helpers (called by scheduler.py) ----
    def had_successful_run_since(self, since_ms: int) -> bool:
        return any(
            r["finished_at_ms"] is not None and r["finished_at_ms"] >= since_ms
            for r in self._successful_runs()
        )

    def count_attempts_since(self, since_ms: int) -> int:
        return sum(
            1 for r in self._recent_finished_runs()
            if r["kind"] in _ATTEMPT_KINDS
            and r["finished_at_ms"] is not None
            and r["finished_at_ms"] >= since_ms
        )

    def last_attempt_finished_since(self, since_ms: int) -> Optional[int]:
        times = [
            r["finished_at_ms"] for r in self._recent_finished_runs()
            if r["kind"] in _ATTEMPT_KINDS
            and r["finished_at_ms"] is not None
            and r["finished_at_ms"] >= since_ms
        ]
        return max(times) if times else None

    def last_successful_finished(self) -> Optional[int]:
        succ = self._successful_runs()
        return succ[0]["finished_at_ms"] if succ else None

    def coverage_exists(self) -> bool:
        cov = self._store.get_coverage()
        return any(v is not None for k, v in cov.items() if k.endswith("_end_ms"))

    # ------------------------------------------------------------------ #
    # 持仓周期费率/利息汇总（功能二，stage3 §3.1/§3.3）— 纯读，不触发拉取
    # ------------------------------------------------------------------ #
    def sum_funding_by_symbol(
        self, symbol: str, start_ms: int, end_ms: int,
    ) -> Optional[str]:
        """``um_income_rows`` 中 ``income_type='FUNDING_FEE' AND symbol=? AND
        time_ms ∈ [start_ms, end_ms]`` 的 ``income`` Decimal 合计。

        窗口内无行 → ``"0"``（真零）；任一行不可解析 → ``None``（沿用
        ``domain._sum_amounts`` 规则，绝不部分相加）。只读，不触发拉取。
        """
        rows = self._store.query_income_rows(start_ms, end_ms, limit=None)
        amounts = [
            r["income"] for r in rows
            if r.get("income_type") == "FUNDING_FEE" and r.get("symbol") == symbol
        ]
        total, unparsed = domain._sum_amounts(amounts)
        return total if unparsed == 0 else None

    def sum_interest_by_asset(
        self, asset: str, start_ms: int, end_ms: int,
    ) -> Optional[str]:
        """``interest_rows`` 中 ``asset=? AND accrued_at_ms ∈ [start_ms, end_ms]``
        的 ``interest`` Decimal 合计。规则同上（无行 → ``"0"``；不可解析 → None）。"""
        rows = self._store.query_interest_rows(start_ms, end_ms, limit=None)
        amounts = [
            r["interest"] for r in rows if r.get("asset") == asset
        ]
        total, unparsed = domain._sum_amounts(amounts)
        return total if unparsed == 0 else None

    def sum_interest_usdt_by_asset(
        self, asset: str, start_ms: int, end_ms: int, price_map, repay_records=None,
    ) -> Optional[str]:
        """窗口内该资产利息逐行折算 USDT 合计（阶段 2026-08-28，与曲线同一权威）。

        每行走 ``domain.interest_usdt_value``：开放桶按当前价动态暂估、匹配到
        Human 约定终态（``amount=="0"`` + 严格 ``succeeded``）的行按该次还款
        捕获的存储价固定折算。窗口无行 → ``"0"``（真零）；任一行缺适用价格或
        不可解析 → 整体 ``None``（绝不部分相加）。币本位合计仍走
        :meth:`sum_interest_by_asset`，两者并存。
        """
        rows = [
            r for r in self._store.query_interest_rows(start_ms, end_ms, limit=None)
            if r.get("asset") == asset
        ]
        index = domain.build_repay_match_index(repay_records)
        with localcontext() as ctx:
            ctx.prec = domain._SUM_PREC
            total = Decimal(0)
            for row in rows:
                value = domain.interest_usdt_value(
                    row.get("interest"), asset,
                    domain.match_interest_repay(asset, row.get("accrued_at_ms"), index),
                    price_map)
                if value is None:
                    return None
                total += value
            return format(total, "f")

    def coverage_for_window(self, start_ms: int, end_ms: int) -> Dict[str, Any]:
        """按窗口调用的公开覆盖率包装（gap-aware 判定权威在 ``_build_coverage``）。

        供组合根（server）逐行统计前调用；``complete == False`` 时该窗口统计
        不得呈现为真值（端点覆盖但中间有洞同样算不完整）。
        """
        return self._build_coverage(start_ms, end_ms, self._store.get_coverage())

    # ------------------------------------------------------------------ #
    # GET flow-log response (§13.2) — pure read, zero upstream I/O
    # ------------------------------------------------------------------ #
    def get_flow_log(self, start_ms: int, end_ms: int) -> Dict[str, Any]:
        domain.validate_window(start_ms, end_ms)  # raises WindowValidationError
        now = self._now_ms()
        store_cov = self._store.get_coverage()

        i_full = self._store.query_interest_rows(start_ms, end_ms)
        u_full = self._store.query_income_rows(start_ms, end_ms)
        cap_full = self._store.query_capital_flow_rows(start_ms, end_ms)

        coverage = self._build_coverage(start_ms, end_ms, store_cov)
        # capital coverage is DISPLAY-ONLY (plan §4.1.5): merged into by_source
        # AFTER _build_coverage returns, so the aggregate start_ms/end_ms/
        # complete/pending_tail_ms — and therefore coverage_for_window, the
        # P0-1 protection point consumed by server.py — are provably unchanged
        # by the capital source (whether it never succeeded or is failing).
        cap_state = self._store.get_capital_flow_state()
        coverage["by_source"]["capital_flow"] = (
            None if (cap_state["start_ms"] is None and cap_state["end_ms"] is None)
            else {"start_ms": cap_state["start_ms"], "end_ms": cap_state["end_ms"]}
        )

        return {
            "schema_version": "private-ledger/v2",
            "served_at_ms": now,
            "scheduler_enabled": self._scheduler_enabled,
            "window": {"start_ms": start_ms, "end_ms": end_ms},
            "coverage": coverage,
            "last_run": self._format_last_run(),
            "delta": self._compute_delta(),
            "today": self._build_today(now),
            "interest": self._interest_block(i_full),
            "um_income": self._income_block(u_full),
            "capital_flow": self._capital_block(cap_full, cap_state),
        }

    def _build_coverage(self, window_start, window_end, store_cov):
        i_start, i_end = store_cov["interest_start_ms"], store_cov["interest_end_ms"]
        u_start, u_end = store_cov["income_start_ms"], store_cov["income_end_ms"]
        # aggregate: start = later of the two; end = earlier of the two.
        cov_start = max(i_start, u_start) if (i_start is not None and u_start is not None) else None
        cov_end = min(i_end, u_end) if (i_end is not None and u_end is not None) else None
        # gaps intersecting the window, ≤20, start_ms ascending.
        gaps = [
            g for g in store_cov["gaps"]
            if g.get("start_ms", 0) <= window_end and g.get("end_ms", 0) >= window_start
        ]
        gaps = sorted(gaps, key=lambda g: g.get("start_ms", 0))[:20]
        complete = (
            cov_start is not None
            and window_start >= cov_start
            and len(gaps) == 0
        )
        pending_tail = max(0, window_end - cov_end) if cov_end is not None else None
        by_source = {
            "interest": (None if (i_start is None and i_end is None)
                         else {"start_ms": i_start, "end_ms": i_end}),
            "income": (None if (u_start is None and u_end is None)
                       else {"start_ms": u_start, "end_ms": u_end}),
        }
        return {
            "start_ms": cov_start, "end_ms": cov_end, "complete": complete,
            "pending_tail_ms": pending_tail, "by_source": by_source, "gaps": gaps,
        }

    def _format_last_run(self):
        runs = self._store.recent_runs(1)
        if not runs:
            return None
        r = runs[0]
        return {
            "run_id": r["id"],
            "kind": r["kind"],
            "finished_at_ms": r["finished_at_ms"],
            "interest_status": r["interest_status"],
            "interest_error": r["interest_error"],
            "income_status": r["income_status"],
            "income_error": r["income_error"],
            "truncated": bool(r["truncated"]),
            "consecutive_failure_count": self._consecutive_failure_count(),
        }

    def _consecutive_failure_count(self) -> int:
        count = 0
        for r in self._recent_finished_runs():  # finished_at DESC
            if r["interest_status"] == "error" or r["income_status"] == "error":
                count += 1
            else:
                break  # first run with neither pane in error stops the run
        return count

    def _compute_delta(self):
        succ = self._successful_runs()  # finished_at DESC
        if len(succ) < 2:
            return {
                "baseline_ms": None, "complete": False,
                "interest_by_asset": [], "income_by_type_asset": [],
                "funding_by_symbol": [],
                "interest_new_row_count": 0, "income_new_row_count": 0,
            }
        baseline = succ[1]["finished_at_ms"]
        i_rows = self._store.query_interest_since(baseline)
        u_rows = self._store.query_income_since(baseline)
        return {
            "baseline_ms": baseline, "complete": True,
            "interest_by_asset": domain.summarize_interest_by_asset(i_rows),
            "income_by_type_asset": domain.summarize_income_by_type_asset(u_rows),
            "funding_by_symbol": domain.summarize_funding_by_symbol(u_rows),
            "interest_new_row_count": len(i_rows),
            "income_new_row_count": len(u_rows),
        }

    def _build_today(self, now):
        day_start = _beijing_day_start_ms(now)
        i_rows = self._store.query_interest_rows(day_start, now)
        u_rows = self._store.query_income_rows(day_start, now)
        return {
            "day_start_ms": day_start,
            "interest_by_asset": domain.summarize_interest_by_asset(i_rows),
            "income_by_type_asset": domain.summarize_income_by_type_asset(u_rows),
        }

    @staticmethod
    def _interest_block(full_rows):
        count = len(full_rows)
        return {
            "rows": [{k: r.get(k) for k in _INTEREST_PUBLIC_KEYS} for r in full_rows[:_ROW_LIMIT]],
            "summary_by_asset": domain.summarize_interest_by_asset(full_rows),
            "row_count": count,
            "row_limit_applied": count > _ROW_LIMIT,
        }

    @staticmethod
    def _income_block(full_rows):
        count = len(full_rows)
        return {
            "rows": [{k: r.get(k) for k in _INCOME_PUBLIC_KEYS} for r in full_rows[:_ROW_LIMIT]],
            "summary_by_type_asset": domain.summarize_income_by_type_asset(full_rows),
            "row_count": count,
            "row_limit_applied": count > _ROW_LIMIT,
        }

    @staticmethod
    def _capital_block(full_rows, cap_state):
        """The cross-margin capital-flow pane. Unlike interest/um_income it
        carries no Decimal amount summary: summing capital ``amount`` across
        flow_type values (a BORROW and a REPAY, a buy and a sell) has no clear
        product meaning, so a per-type row COUNT is the frontend's job (plan
        §4.1.5 — "可选 status 摘要"). ``last_run`` is capital's own run state,
        separate from the two-source ``last_run``."""
        count = len(full_rows)
        return {
            "rows": [{k: r.get(k) for k in _CAPITAL_PUBLIC_KEYS} for r in full_rows[:_ROW_LIMIT]],
            "row_count": count,
            "row_limit_applied": count > _ROW_LIMIT,
            "last_run": cap_state["last_run"],
        }

    # ------------------------------------------------------------------ #
    # POST refresh (§13.4)
    # ------------------------------------------------------------------ #
    def trigger_refresh(self):
        if not self.is_usable():
            return 409, {"error": "private_channel_disabled", "detail": "私有只读通道未启用"}
        outcome = self.run_once("manual")
        if outcome is None:
            return 429, {"error": "flow_log_busy", "detail": "另一次流水拉取正在进行"}
        run = outcome["run"]
        return 200, {
            "run_id": run["id"],
            "kind": run["kind"],
            "finished_at_ms": run["finished_at_ms"],
            "interest_status": run["interest_status"],
            "interest_error": run["interest_error"],
            "interest_new_row_count": outcome["interest_new"],
            "income_status": run["income_status"],
            "income_error": run["income_error"],
            "income_new_row_count": outcome["income_new"],
            "truncated": bool(run["truncated"]),
            "capital_flow": outcome["capital"],
        }
