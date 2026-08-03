Identity:
- task_id: fix-review-1-test-stubs
- target_role: Implementer（Backend repair / HIGH_RISK）
- target_model: claude_glm
- provider: zhipu_glm
- status_revision: 11
- required_skill: agents/skills/minimal-change-engineer.md

Goal

修复 review-1 的唯一 `in-range` 根因 `test_stub_signature_drift`，不改变任何生产逻辑、公共契约、
schema 或前端。交付 `0ef8053` 已将 `get_snapshot` 调整为 `(coin, direction)`，将 `query_leg` 调整为
`(leg, symbol, client_order_id, endpoint)`；下列两个既有回归测试中的 fake / 子类 override 仍使用旧
参数签名，导致 77 项回归 TypeError。

将两个测试文件中**全部**相关 fake / override 同步为新签名：`get_snapshot` 显式接受
`direction`，`query_leg` 显式接受 `endpoint`；子类调用父类时也须原样转发新增参数。保持原有测试
语义、并发同步与 fake-transport 行为。不要将生产接口改回兼容旧签名，也不要用吞掉参数的通配写法
掩盖接口漂移。

Allowed Files

- `backend/tests/test_hedge_task_local.py`
- `backend/tests/test_hedge_review2_regressions.py`

Inputs

- `AGENTS.md`
- `agents/developer-discipline.md`
- `agents/skills/minimal-change-engineer.md`
- `PROJECT_STATE.md`
- `reports/agent-runs/ACTIVE.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/status.json`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/evidence/review-1-code.deepseek.raw.md`
- `reports/agent-runs/2026-08-02-spot-order-routing-cap-display-v1/bookkeeper-review-1-rework-verification.md`
- `backend/hedge_open_tasks/service.py`（只读，当前调用方）
- `backend/services/live_hedge_executor.py`（只读，当前接口）
- 两份 Allowed Files（仅它们可修改）

Acceptance Checks

- `rg` 核对两份测试文件中所有 `get_snapshot` / `query_leg` fake 和 override 均接受新增的
  `direction` / `endpoint`，且子类 `super()` 调用完整转发。
- 运行并通过：

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_hedge_preflight_provider.py backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_api.py backend/tests/test_snapshot.py \
  backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py \
  backend/tests/test_negative_schema.py backend/tests/test_service_health.py \
  backend/tests/test_hedge_task_local.py backend/tests/test_hedge_review2_regressions.py -q
```

- `git diff --check` 通过；仅 Allowed Files 有交付改动；将改动做成一个新的本地提交。
- 回执报告提交 SHA、完整测试命令结果和实际变更文件。修复提交将在 Bookkeeper 核验后替换
  `delivery_sha`，随后必须由 DeepSeek 重跑 review-1。

Stop

- 不得修改 `backend/**` 的任何其他文件、`frontend/**`、`docs/**`、`schemas/**`、fixtures、配置、阶段记录或 `PROJECT_STATE.md`。
- 不得调用 Binance 或任何外域、读取/输出凭证、发单、转账、启动服务、改变 Start gate、推送、合并、部署。
- 不得改写生产接口以迁就旧 fake，不得新增兼容层、环境变量或测试跳过。
- 完成单次本地提交和 `[TASK_RESULT v2]` 后停止；Human 将原始回执交回 Bookkeeper，未经 review-1
  明确 ACCEPT 不得启动 review-2。
