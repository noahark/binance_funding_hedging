# Manual Review-2 P2 Repair Attempt 2 — Final-Sleep Boundary

继续使用同一 `claude_glm` / `zhipu_glm` 修复身份，并显式使用
`senior_developer` skill（高级开发者执行规范）。这是对刚才 P2 实现的一次极窄边界修复，
不是重新设计。

只允许编辑：

```text
scripts/service-control.py
scripts/tests/test_service_control.py
```

继续遵守
`manual-fix-T1-launchd-service-review2-P2.tool-policy.json`：只使用 `Read`、`Glob`、
`Grep`、`Edit`、`Write`；禁止 Bash、Python、pytest、py_compile、git、launchctl、网络访问、
服务启动、`.env` 读取和 stage evidence 写入。全部命令检查由 Codex bookkeeper 执行。

## 已通过的部分

Bookkeeper 已运行全部冻结检查：目标测试 `86 passed`，后端 `301 passed`，前端自检、
`bash -n scripts/run-server.sh`、`git diff --check` 均通过。当前两文件边界、成功路径、固定
脱敏失败提示和 probe/sleeper 注入设计均保留。

## 唯一阻断边界

当前 `_await_readiness(deadline=2, interval=1)` 会在 t=0、t=1、t=2 做三次 probe，
这是合理的；但第三次最终失败后仍调用一次 sleeper，导致三次 sleep。默认 60 秒/1 秒配置
因此可能实际等待 61 秒，与声明的 60 秒窗口不符。

请只做以下修复：

1. 最后一次允许的 probe 失败后立即返回 `False`，不得再 sleep。默认应是 61 次 probe、
   60 次 sleep；`deadline=2, interval=1` 应是 3 次 probe、2 次 sleep。
2. 更新现有 ceiling 测试：probe 调用数仍等于 `_expected_attempts(mod)`，sleep 调用数应为
   `max(0, _expected_attempts(mod) - 1)`。
3. 增加一个直接的小窗口回归测试，明确断言 `deadline=2, interval=1` 时 probe 三轮、sleep
   两次、结果为 `False`。
4. 增加 `restart()` readiness 永不成功的失败测试：确认返回非零、不打印 `restarted`、
   stderr 保持固定可操作且不泄露 dummy body/secret/URL、plist 保留、launchctl 仍严格只有
   `bootout -> bootstrap`，没有额外清理调用。
5. 不改 `READY_WAIT_SECONDS=60`、`READY_POLL_INTERVAL_SECONDS=1.0`，不改成功路径、
   `start/status/doctor`、失败文案或任何其他行为。

完成后只返回：两文件是否均有修改、最终 probe/sleep 上限、增加/更新的测试名称，以及
Claude Session ID。不要运行或声称运行任何命令。

本地北京时间: 2026-07-13 22:58:19 CST
下一步模型: Codex bookkeeper
下一步任务: 重新执行冻结检查与 final-sleep 独立探针；全绿后封存修复提交
