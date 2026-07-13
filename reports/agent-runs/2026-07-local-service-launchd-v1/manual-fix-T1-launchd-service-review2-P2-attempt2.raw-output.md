<!-- source_session: 5ee354f2-d410-4de2-aee7-fdd85e8f0d1b -->
<!-- source_timestamp: 2026-07-13T15:04:33.986Z -->
<!-- source_model: glm-5.2 -->
<!-- source_stop_reason: end_turn -->
<!-- attempt2_tool_counts: Read=2 Edit=4 -->

`_await_readiness` 最终状态确认正确。attempt2 极窄修复全部完成。

---

## Review-2 P2 Attempt 2 — Final-Sleep 边界修复报告

### 两文件均有修改
- `scripts/service-control.py` — 改 1 处(`_await_readiness` 循环)。
- `scripts/tests/test_service_control.py` — 改 2 处 ceiling 断言 + 新增 2 个测试。

### 最终 probe / sleep 上限
- `_await_readiness` 改为按 `attempt` 计数,仅在 `attempt + 1 < max_attempts` 时调用 `self.sleeper(interval)` —— 最后一次允许的 probe 失败后立即 `return False`,不再 sleep。
- **默认 `READY_WAIT_SECONDS=60` / `READY_POLL_INTERVAL_SECONDS=1.0`**:61 次 probe(每轮 healthz+readyz)、**60 次 sleep**(与声明的 60 秒窗口一致)。
- **`deadline=2, interval=1`**:3 次 probe、**2 次 sleep**。
- `READY_WAIT_SECONDS`、`READY_POLL_INTERVAL_SECONDS`、成功路径、`start/status/doctor`、失败文案均未改动。

### 增加 / 更新的测试
- **更新**:`test_install_fails_at_bounded_ceiling_when_health_always_unreachable`、`test_install_fails_at_bounded_ceiling_when_health_200_but_ready_503` —— sleep 上限断言由 `== _expected_attempts(mod)` 改为 `== max(0, _expected_attempts(mod) - 1)`;probe 调用数仍 `== _expected_attempts(mod)`。
- **新增**:`test_await_readiness_small_window_is_three_probes_two_sleeps_false` —— 直接断言 `deadline=2, interval=1` 下三轮 probe、两次 sleep、结果 `False`,每次 sleep 间隔为 1。
- **新增**:`test_restart_fails_at_bounded_ceiling_when_readiness_never_succeeds` —— `restart()` readiness 恒不成功:返回非零、stdout 不含 `restarted`、stderr 固定可操作且不含 dummy body/secret/URL、plist 保留、launchctl 非打印动词严格为 `["bootout", "bootstrap"]`(无额外清理)、sleep 上限为 `max(0, _expected_attempts(mod) - 1)`。

### Claude Session ID
`5ee354f2-d410-4de2-aee7-fdd85e8f0d1b`(同一 GLM 会话)

### 过程偏离
本轮严格仅用 `Read` / `Edit`,未调用 Bash/Python/pytest/py_compile/git/launchctl,未读取 `.env`、未启动服务、未写 stage evidence。未运行、亦未声称运行任何命令或测试 —— 冻结检查与 final-sleep 独立探针由 Codex bookkeeper 执行。
