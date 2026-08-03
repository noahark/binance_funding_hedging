# fix-review-1-test-stubs — Bookkeeper 核验

核验时间：2026-08-03 08:57 CST

## 结论

修复提交 `3a07f4a87e863d9b2b5b74b92abd09e74dc411b9` 承接前端提交 `0ef8053`，仅修复
review-1 指出的同根因测试接口漂移。完整交付区间更新为
`1a55781a5f80ee5b3e15d7124003af2dda73f0d5..3a07f4a87e863d9b2b5b74b92abd09e74dc411b9`。

## 范围核验

- `0ef8053..3a07f4a` 仅改 `backend/tests/test_hedge_task_local.py` 与
  `backend/tests/test_hedge_review2_regressions.py`，计 10 增 / 9 删；均在 repair Allowed Files 内。
- 所有相关 fake / override 明确接受新增 `direction` / `endpoint`；子类 `super()` 完整转发。
  原通配 `*a, **k` stub 已改为显式签名。
- `_seed_crash_gap` 的 `prepare_attempt` 调用同步本交付新增的 `spot_endpoint` 参数，属于同一
  测试桩签名根因；未改生产接口、契约、schema、前端、配置或 Start gate。
- `git diff --check base..3a07f4a` 通过。

## 独立测试核验

以 repair 任务卡指定的 14 文件 pytest 命令，在允许测试临时本机回环端口的隔离外环境运行，退出码为
0。该命令覆盖原 12 文件与两个此前失败的测试文件；未访问外网、未使用凭证、未发单。

## 下一闸门

`rework_count` 保持 1，`delivery_sha` 替换为 `3a07f4a`。必须由**全新、只读**的 DeepSeek session
重跑 review-1；未有明确 `ACCEPT` 前，Opus5 review-2 仍不得启动。
