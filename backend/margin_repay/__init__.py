"""统一账户全仓杠杆还款的本地幂等存储包（阶段 2026-08-09-pm-margin-repay-v1，T1）。

本包只有存储层：请求校验与外发编排在 ``backend/app/server.py`` 的 handler 内，
还款本体复用既有的 ``services.hedge_open_live_client.HedgeOpenLiveClient.repay_margin_debt``
（one-shot 签名 POST ``/papi/v1/margin/repay-debt``，固定 ``specifyRepayAssets=USDT``）。
"""
