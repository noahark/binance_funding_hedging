"""Single execution-owner advisory lock for one borrow-task SQLite DB (§4.3).

Non-blocking ``fcntl.flock(LOCK_EX | LOCK_NB)`` on the sidecar file
``<borrow_db_path>.lock`` (NEVER the DB file itself — SQLite owns its own
DB-file locking). Held for process lifetime once acquired; released only on
``close()`` / process exit, never while the scheduler runs.

Owner: the scheduler runs normally. Non-owner: serves read/task-mutation APIs,
starts no scheduler, dispatches nothing even on a forced tick. Crash recovery
is automatic — the kernel releases the lock on process death, so the next
process acquires it.

``flock`` is per open file description: two ``open()`` calls on the same sidecar
path in one process reproduce the two-owner case without subprocesses (§9-1).
No network or signing imports (the borrow-package AST purity guard is preserved).
"""
from __future__ import annotations

import errno
import fcntl
import os
import threading


class BorrowDbOwnership:
    """Non-blocking exclusive sidecar lock for one borrow DB."""

    def __init__(self, db_path: str):
        self._lock_path = os.path.abspath(db_path + ".lock")
        self._fd: int | None = None
        self._owned = False
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Acquire the exclusive lock without blocking. ``True`` iff this is the owner."""
        with self._lock:
            if self._owned:
                return True
            parent = os.path.dirname(self._lock_path)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            fd = os.open(self._lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                # EAGAIN/EACCES: another open file description already holds it.
                os.close(fd)
                if exc.errno in (errno.EACCES, errno.EAGAIN):
                    return False
                raise
            self._fd = fd
            self._owned = True
            return True

    @property
    def is_owner(self) -> bool:
        return self._owned

    def close(self) -> None:
        """Release the lock. Safe to call repeatedly and on never-acquired instances."""
        with self._lock:
            if self._fd is None:
                return
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
            self._owned = False
