"""Hedge-open scheduler — durable 1s tick driver (10-design §6 / ADR-1).

Mirrors ``borrow_tasks.scheduler``: the :class:`HedgeOpenScheduler` thread calls
:meth:`HedgeOpenTaskService.tick` on the monotonic cadence and is the only writer
of the service's last-tick cursor. Round 1 fixes the interval at 1s (immediate
mode, ADR-6); it is not environment-configurable this round.

No network imports.
"""
from __future__ import annotations

import threading


class HedgeOpenScheduler:
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
            target=self._loop, name="hedge-open-scheduler", daemon=True
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
            # Last-resort containment: an exception inside tick() must not kill
            # the scheduler thread. The service's dispatch path contains its own
            # exceptions; this is the belt-and-braces outer net.
            try:
                self._tick()
            except Exception:
                pass
            try:
                interval_us = self._get_interval_us() or 1
            except Exception:
                interval_us = 1
            # Poll at a fraction of the interval so the 1s cadence stays
            # responsive; the tick callback is the authority on what is due.
            slice_seconds = max(min(interval_us / 1_000_000 / 2.0, 0.25), 0.005)
            self._stop.wait(slice_seconds)
