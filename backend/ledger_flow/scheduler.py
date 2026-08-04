"""Ledger flow-log cadence — hourly scheduled refresh (design §15.1 / §15.3).

A daemon thread that wakes every 20 seconds and asks ``decide(now)`` whether a
``scheduled`` run is due. The decision is idempotent by construction: it runs
at most one successful scheduled run per natural hour, and never sleeps to a
precise wall-clock instant (clock jumps and sleep/wake would break a precise
schedule, while "has this hour already succeeded?" is naturally idempotent and
also covers missed-tick catch-up).

On start it performs one ``startup_catchup`` / ``backfill`` if the last
successful run is older than an hour (or the ledger is empty). On failure the
hourly budget is 3 attempts (a first try plus two 5-minute-spaced retries);
beyond that it waits for the next hour. Every attempt writes its own run
record (the service owns that).

Thread model mirrors :mod:`backend.borrow_tasks.scheduler`: a daemon thread
plus a :class:`threading.Event` stop signal, with an injected clock so tests
drive ``decide`` / ``_startup_catchup`` without sleeping. The scheduler is
only started by the composition root when the private channel is usable
(§15.3); it performs no network of its own.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional, Tuple

from .service import LedgerFlowService

_POLL_SECONDS = 20.0
_HOUR_MS = 60 * 60 * 1000
_MIN_MS = 60 * 1000
_5MIN_MS = 5 * _MIN_MS
_MAX_ATTEMPTS_PER_HOUR = 3
_MINUTE_OF_HOUR_THRESHOLD = 1  # run from :01 onward within the hour


class LedgerScheduler:
    """Daemon thread driving :meth:`LedgerFlowService.run_once` on the cadence."""

    def __init__(self, service: LedgerFlowService, *, now_ms: Callable[[], int],
                 poll_seconds: float = _POLL_SECONDS):
        self._service = service
        self._now_ms = now_ms
        self._poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="ledger-flow-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)

    def _loop(self) -> None:
        # Startup catch-up (§15.3): catch up immediately if the last successful
        # run is older than an hour or the ledger is empty. Contained so an
        # unexpected raise cannot kill the cadence thread.
        try:
            self._startup_catchup()
        except Exception:
            pass
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop.wait(self._poll_seconds)

    def _tick(self) -> None:
        now = self._now_ms()
        due, kind = self.decide(now)
        if due:
            self._service.run_once(kind)

    def decide(self, now: int) -> Tuple[bool, Optional[str]]:
        """Pure decision: should a ``scheduled`` run start at ``now``?

        Returns ``(due, kind)``. A run is due when all hold: the minute-of-hour
        is at least :1, this natural hour has no successful run yet, the hourly
        attempt budget (3) is not exhausted, and either no attempt has happened
        this hour or at least 5 minutes have passed since the last one.
        """
        minute_of_hour = (now // _MIN_MS) % 60
        if minute_of_hour < _MINUTE_OF_HOUR_THRESHOLD:
            return False, None
        hour_start = self._hour_start(now)
        if self._service.had_successful_run_since(hour_start):
            return False, None
        if self._service.count_attempts_since(hour_start) >= _MAX_ATTEMPTS_PER_HOUR:
            return False, None
        last = self._service.last_attempt_finished_since(hour_start)
        if last is not None and now - last < _5MIN_MS:
            return False, None
        return True, "scheduled"

    def _startup_catchup(self) -> None:
        now = self._now_ms()
        last = self._service.last_successful_finished()
        if last is None or now - last > _HOUR_MS:
            kind = "backfill" if not self._service.coverage_exists() else "startup_catchup"
            self._service.run_once(kind)

    @staticmethod
    def _hour_start(now: int) -> int:
        return (now // _HOUR_MS) * _HOUR_MS
