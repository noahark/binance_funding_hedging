"""资产互转（统一账户 ⇄ 普通现货账户）的幂等存储包。

阶段 `2026-08-06-asset-transfer-live-v1` 任务 T1。本包只有存储层：请求校验与
外发编排在 `backend/app/server.py` 的 handler 内，划转本体复用既有的
`services.hedge_open_live_client.HedgeOpenLiveClient.universal_transfer`。
"""
