"""Dual-ledger flow-log package (borrow interest × UM income).

Submodules (import by dotted path; do NOT re-export here):

- :mod:`backend.ledger_flow.domain` — pure functions (normalize / dedup /
  sort / Decimal summarize / window validate / incremental grouping). Zero
  I/O, no network, no signing, no sqlite import.
- :mod:`backend.ledger_flow.store` — SQLite idempotent ledger (four tables
  per the design §14; amount columns TEXT, never SQL-aggregated).

The service (task B) and scheduler live in sibling modules created by later
tasks; this package init intentionally holds only this docstring.
"""
