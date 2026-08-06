"""Durable hedge-open task core (round 1: immediate mode, dry-run record transport).

Isolated modular-monolith package mirroring ``borrow_tasks``: domain/store/
service/executor + durable SQLite + one scheduler thread + a disabled/gated
executor. Independent of snapshot assembly and any Binance adapter: no
``backend.services`` or ``backend.domain`` module imports this package, and this
package imports none of them. No network or signing primitives are used anywhere
under this package (the dry-run record transport's zero-network proof).

Round 1 (ADR-5/ADR-6): immediate open only (1 fill/sec, polling-based); default
dry-run record transport; a real POST is reachable only under
``APP_HEDGE_EXECUTOR=live`` AND the durable global Start gate AND a passing
preflight, and the live executor is NOT wired this round.
"""
from __future__ import annotations

from .domain import HedgeError
from .executor import (
    AttemptContext,
    AttemptOutcome,
    DisabledHedgeExecutor,
    HedgeExecutor,
)
from .scheduler import HedgeOpenScheduler
from .service import (
    DisabledPreflightProvider,
    HedgeOpenTaskService,
    PreflightProvider,
)
from .store import HedgeOpenStore

__all__ = [
    "AttemptContext",
    "AttemptOutcome",
    "DisabledHedgeExecutor",
    "DisabledPreflightProvider",
    "HedgeError",
    "HedgeExecutor",
    "HedgeOpenScheduler",
    "HedgeOpenStore",
    "HedgeOpenTaskService",
    "PreflightProvider",
]
