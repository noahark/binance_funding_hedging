"""Durable borrow-task core (A+B slice).

Isolated modular-monolith package for backend-owned borrow tasks. It is
independent of snapshot assembly and the future Binance adapter: no
``backend/services`` or ``backend/domain`` module imports this package, and
this package imports none of them. No network or signing primitives are used
anywhere under this package.
"""
from __future__ import annotations

from .domain import BorrowError
from .executor import BorrowExecutor, DisabledBorrowExecutor, ExecutorResult
from .scheduler import BorrowScheduler, select_next_task
from .service import BorrowTaskService
from .store import BorrowTaskStore

__all__ = [
    "BorrowError",
    "BorrowExecutor",
    "BorrowTaskService",
    "BorrowTaskStore",
    "BorrowScheduler",
    "DisabledBorrowExecutor",
    "ExecutorResult",
    "select_next_task",
]
