"""Borrow scheduler — global decimal round-robin dispatch (breakdown §3.8).

The selection algorithm is a pure function (testable without a database). The
:class:`BorrowScheduler` thread wrapper drives :meth:`BorrowTaskService.tick` on
the monotonic cadence and is the only writer of the service's last-tick cursor.
It is decoupled from the snapshot worker: neither module imports the other.

No network imports.
"""
from __future__ import annotations

import threading


def select_next_task(eligible_tasks: list[dict], cursor_task_id: str | None) -> dict | None:
    """Pick the next eligible task strictly after the cursor, wrapping.

    ``eligible_tasks`` is ordered by ascending ``creation_seq``. The cursor is
    the task id dispatched last (or ``None``). With three eligible tasks the
    order is A -> B -> C -> A. ``None`` is returned only when no task is
    eligible.
    """
    if not eligible_tasks:
        return None
    if cursor_task_id is None:
        return eligible_tasks[0]
    cursor_seq = None
    for task in eligible_tasks:
        if task["id"] == cursor_task_id:
            cursor_seq = task["creation_seq"]
            break
    for task in eligible_tasks:
        if cursor_seq is None or task["creation_seq"] > cursor_seq:
            return task
    return eligible_tasks[0]  # wrap around


class BorrowScheduler:
    """Daemon thread that calls ``tick_callback`` on the monotonic cadence."""

    def __init__(self, tick_callback, get_interval_us, mono_us):
        self._tick = tick_callback
        self._get_interval_us = get_interval_us
        self._mono_us = mono_us
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="borrow-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            # Last-resort containment (Boundary C §5.2): a store/projection
            # exception inside tick() must not silently kill the scheduler
            # thread — that would stop reconciliation of unknown attempts. The
            # service's _dispatch_one/_reconcile_pass already contain their own
            # exceptions; this is the belt-and-braces outer net so an unexpected
            # raise from anywhere in the tick path cannot terminate dispatch.
            try:
                self._tick()
            except Exception:
                pass
            try:
                interval_us = self._get_interval_us() or 1
            except Exception:
                interval_us = 1
            # Poll at a fraction of the interval so sub-second cadences stay
            # responsive; the tick callback is the authority on what is due.
            slice_seconds = max(min(interval_us / 1_000_000 / 2.0, 0.25), 0.005)
            self._stop.wait(slice_seconds)
