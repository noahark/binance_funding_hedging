"""Funding-hedging backend service.

Public-market snapshot plus human-gated live execution: hedge open/close
orders, portfolio-margin borrow, and asset transfer behind deny-by-default
endpoint whitelists and executor switches. Repay and user-data-stream paths
still do not exist. The service binds 127.0.0.1.
"""
