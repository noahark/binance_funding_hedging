# fix-review-1-test-stubs — Claude-GLM 原始回执

由 Human 于 2026-08-03 交回 Bookkeeper；原文保留如下。

```text
[TASK_RESULT v2]
任务 ID: fix-review-1-test-stubs
执行结果: completed（完成）
结果摘要: 同步两份回归测试 fake 至新签名：get_snapshot 加 direction、query_leg 加 endpoint（含 super() 完整转发，并把一处 *a/**k 通配 stub 改为显式签名，不掩盖漂移）；同根因的 _seed_crash_gap 内 prepare_attempt 调用补 spot_endpoint。仅 2 个 Allowed Files，569 测试通过，提交 3a07f4a。
产物: [backend/tests/test_hedge_task_local.py, backend/tests/test_hedge_review2_regressions.py]
检查结果:
1. [pass] get_snapshot 全部 fake 同步 direction（test_hedge_task_local ×2：line 95/1544；test_hedge_review2_regressions ×1：line 116）。
2. [pass] query_leg 全部 fake/override 同步 endpoint 并完整转发：task_local line 118/238/1412（def）+ 1419（super().query_leg 转发 endpoint）；review2 line 147。原 line 305 的 *a, **k 通配已改为显式 (leg_name, coin, cid, endpoint)，不再吞参数掩盖接口漂移。
3. [pass] 同根因补充：review2 的 _seed_crash_gap 调 store.prepare_attempt 补 spot_endpoint（后端交付新增参数）；否则修完 get_snapshot/query_leg 后 6 个 crash-gap 用例仍 TypeError。该调用在 Allowed File 内、属同一 test_stub_signature_drift 根因、为满足 Acceptance 命令所必需。
4. [pass] 完整测试命令（dispatch 指定 14 文件）569 passed，无失败；此前 77 项 TypeError 已清零。
5. [pass] git diff --check 通过；交付改动仅限 2 个 Allowed Files（10 增/9 删）；未触及 backend/** 其他文件、frontend、docs、schemas、fixtures、配置、阶段记录或 PROJECT_STATE.md。
6. [pass] 未改写生产接口迁就旧 fake；无兼容层、无环境变量、无测试跳过；保持原有测试语义、并发同步与 fake-transport 行为。
阻塞项: [none]
本地北京时间: 2026-08-03 08:57:51 CST
下一步模型: Bookkeeper（codex）
下一步任务: Human 将本回执交回 Bookkeeper（codex）；Bookkeeper 核验 569 测试与仅 2 个 Allowed Files 改动后，以修复提交 SHA 3a07f4a87e863d9b2b5b74b92abd09e74dc411b9 替换 delivery_sha；随后必须由 DeepSeek 在新 SHA 上重跑 review-1（rework_count 已为 1，根因 test_stub_signature_drift）；未经 review-1 明确 ACCEPT 不得启动 review-2，本任务不授权实盘/开闸/部署。
[/TASK_RESULT]
```
