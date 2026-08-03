Identity:
- task_id: fix-review-2-allowlist-guard-scan
- target_role: Implementer（Backend repair / HIGH_RISK）
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 14
- required_skill: agents/skills/minimal-change-engineer.md

Goal

修复 review-2 的两个 `in-range` 发现，同时执行同根因刹车要求的穷举扫描。根因必须原样采用：
**「改共享常量/签名后 dispatch 清单外既有守卫测试失效」**。这是连续第二次同根因返工，禁止只为
两条失败断言点补丁。

1. 在 `backend/tests/test_hedge_purity.py` 更新冻结守卫，精确锁定 Human 已授权的 12 条 endpoint：
   原 7 条 PAPI endpoint（全为 `https://papi.binance.com`）加本轮 5 条普通 Spot / 名单 endpoint
   （全为 `https://api.binance.com`）。保留**精确相等**和长度为 12 的反扩张断言；host 断言按两组
   endpoint 分别验证硬编码 host。禁止删断言、改成子集/包含判断、或回退生产 allowlist。
2. 只更新 `backend/services/hedge_open_live_client.py` 的模块级 docstring：如实说明下单执行路径仍是
   default-off（仅 `APP_HEDGE_EXECUTOR=live` 才会注入 executor），但行情展示可由组合根独立构造
   deny-by-default client，且展示侧只能调用名单 GET；端点清单补齐本轮 5 条。不得改变任何运行时代码。
3. 对 `backend/tests/**` 做**穷举静态扫描**，覆盖共享常量/签名
   `ALLOWLIST`、`get_snapshot`、`query_leg`、`prepare_attempt`、`_persist_leg_raw`、`build_rows`。
   在最终 `[TASK_RESULT v2]` 的 `检查结果` 中用紧凑表或逐项列表列出每个命中测试文件/站点、它对哪一
   共享项做冻结或 fake 实现、以及“已修”或“无需修”的具体理由。扫描若发现需要修改的站点不在
   Allowed Files 内，立即停止并报告，不得扩大范围。

Allowed Files

- `backend/tests/test_hedge_purity.py`
- `backend/services/hedge_open_live_client.py`（仅模块 docstring，不得改任何可执行代码）

Inputs

- `AGENTS.md`
- `agents/developer-discipline.md`
- `agents/skills/minimal-change-engineer.md`
- `PROJECT_STATE.md`
- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-2-reality.opus5.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-2-rework-verification.md`
- `backend/tests/test_hedge_purity.py`
- `backend/services/hedge_open_live_client.py`
- 仅为穷举扫描读取 `backend/tests/**` 与上述共享项的现有调用方；不得修改扫描范围外文件。

Acceptance Checks

- `test_hedge_purity.py` 精确断言 12 条 `(method, path) -> hardcoded host`，其中 7 条 PAPI 与 5 条
  api.binance.com 分组正确；未知 path 仍在签名前 fail-closed。不得弱化任何反扩张断言。
- 用 `git diff --word-diff` 或等价检查证明 `hedge_open_live_client.py` 除模块 docstring 外无任何
  可执行行改动。
- 提供第 3 条穷举扫描的完整站点清单与每站结论；清单遗漏、仅搜失败文件、或没有不适用理由均不通过。
- 运行并通过全量命令，回执附**原始末尾汇总行**：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
```

- `git diff --check` 通过；仅两个 Allowed Files 有交付改动；一个新的本地提交；回执报告 SHA、实际
  改动文件和完整测试结果。

Stop

- 不得修改任何生产逻辑、契约语义、schema、前端、config、fixtures、阶段记录或 `PROJECT_STATE.md`。
- docstring 之外不得改 `hedge_open_live_client.py` 的可执行行；不得新增兼容层、环境变量或测试跳过。
- 不得调用 Binance 或任何外域、读取/输出凭证、发单、转账、启动服务、改变 Start gate、推送、合并或部署。
- 若穷举扫描发现需要修复的范围外站点，停止并报告；完成单次本地提交与 `[TASK_RESULT v2]` 后停止。
  Bookkeeper 核验新 SHA 后，必须由 DeepSeek 重跑 review-1，再回 Opus5 review-2。
