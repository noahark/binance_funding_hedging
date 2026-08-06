"""资产互转的 SQLite 幂等存储（阶段 2026-08-06-asset-transfer-live-v1，T1）。

**为什么必须有这张表**：币安 `POST /sapi/v1/asset/transfer` 没有 `clientOrderId`
之类的幂等键——这是它与下单接口的关键差异，重复提交会真的转两次钱。本表的
`client_request_id` 唯一索引就是那个缺失的幂等键：请求先落 `pending`，唯一约束
冲突即返回已有记录而**不重发**币安。

并发模型沿用既有 store（`borrow_tasks/store.py`）：单连接 + 单把 `RLock`，每个
公开方法各自取锁。**外发调用永远不在持锁期间发生**——handler 先 `begin()`（短事务、
释放锁），再调币安，最后 `resolve()`（第二个短事务）。

金额一律 `TEXT` 原样存取，本模块不做任何金额算术，也不提供金额聚合查询。
时间为整数微秒（对齐既有 store）。

无网络导入：只用 :mod:`sqlite3`、:mod:`threading`、:mod:`os`。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional

# 状态四态。unknown 是显式态而非失败：超时/5xx 时钱可能已经转了，
# 前端必须提示人工核对而不是诱导重试（00-intake.md §4.4 / §4.6）。
STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS asset_transfer (
    client_request_id TEXT PRIMARY KEY,
    from_account      TEXT NOT NULL,
    to_account        TEXT NOT NULL,
    asset             TEXT NOT NULL,
    amount            TEXT NOT NULL,
    status            TEXT NOT NULL,
    tran_id           TEXT,
    error_code        TEXT,
    error_message     TEXT,
    created_at_us     INTEGER NOT NULL,
    updated_at_us     INTEGER NOT NULL
);
"""


def _row_to_doc(row: sqlite3.Row) -> dict:
    return {
        "client_request_id": row["client_request_id"],
        "from_account": row["from_account"],
        "to_account": row["to_account"],
        "asset": row["asset"],
        "amount": row["amount"],
        "status": row["status"],
        "tran_id": row["tran_id"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
    }


class AssetTransferStore:
    def __init__(self, db_path: str):
        self._lock = threading.RLock()
        # 生产库在 gitignore 的 data/ 下，checkout 时该目录可能不存在。
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def begin(
        self,
        *,
        client_request_id: str,
        from_account: str,
        to_account: str,
        asset: str,
        amount: str,
        now_us: int,
    ) -> tuple[dict, bool]:
        """登记一笔划转意图，返回 ``(记录, 是否新建)``。

        ``是否新建`` 为 ``False`` 时调用方**不得**再发往币安：该
        `client_request_id` 已经处理过（或正在处理），直接返回已有记录的当前状态。
        唯一约束由数据库保证，并发重复请求同样只有一个能拿到 ``True``。
        """
        with self._lock:
            try:
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO asset_transfer"
                        " (client_request_id, from_account, to_account, asset, amount,"
                        "  status, tran_id, error_code, error_message,"
                        "  created_at_us, updated_at_us)"
                        " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)",
                        (
                            client_request_id, from_account, to_account, asset, amount,
                            STATUS_PENDING, now_us, now_us,
                        ),
                    )
            except sqlite3.IntegrityError:
                existing = self._get_locked(client_request_id)
                # 唯一约束命中但记录读不回来只能是并发删除，本表无删除路径。
                if existing is None:  # pragma: no cover - 无删除路径，不可达
                    raise
                return existing, False
            return self._get_locked(client_request_id), True

    def resolve(
        self,
        client_request_id: str,
        *,
        status: str,
        now_us: int,
        tran_id: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> dict:
        """写入终态（`succeeded` / `failed` / `unknown`）并返回记录。"""
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE asset_transfer"
                " SET status = ?, tran_id = ?, error_code = ?, error_message = ?,"
                "     updated_at_us = ?"
                " WHERE client_request_id = ?",
                (status, tran_id, error_code, error_message, now_us, client_request_id),
            )
        with self._lock:
            return self._get_locked(client_request_id)

    def get(self, client_request_id: str) -> Optional[dict]:
        with self._lock:
            return self._get_locked(client_request_id)

    def _get_locked(self, client_request_id: str) -> Optional[dict]:
        cur = self._conn.execute(
            "SELECT * FROM asset_transfer WHERE client_request_id = ?",
            (client_request_id,),
        )
        row = cur.fetchone()
        return _row_to_doc(row) if row is not None else None
