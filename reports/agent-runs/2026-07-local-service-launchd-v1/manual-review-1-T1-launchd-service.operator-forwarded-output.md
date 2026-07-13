# Operator-Forwarded Kimi Formal Review-1 Output

Source: the human operator forwarded the complete Kimi review response in chat
on 2026-07-13. The terminal/chat presentation inserted hard wraps inside long
paths and the fingerprint. The reviewer prose below preserves the forwarded
content; the strict JSON mechanically de-wrapped from the final fenced block is
stored separately in `manual-review-1-T1-launchd-service.verdict.json`.

---

# Formal Review-1 结论 — T1 launchd service

## 总体评价

本阶段交付代码满足设计冻结的边界与安全约束，六项冻结检查全部通过：

- `python3 -m py_compile backend/app/server.py scripts/service-control.py` — PASS
- `python3 -m pytest scripts/tests/test_service_control.py backend/tests/test_service_health.py -q -p no:cacheprovider` — 82 passed
- `python3 -m pytest backend/tests -q -p no:cacheprovider` — 301 passed
- `node frontend/self-check.js` — PASS
- `bash -n scripts/run-server.sh` — PASS
- `git diff --check` — PASS
- `python3 scripts/validate-stage.py 2026-07-local-service-launchd-v1 --phase pre-review` — PASS

审查范围严格使用
`base_sha=3bb253a489bf2854d8b9d81060a45ca056e1cea2..head_sha=85ab5011e4b99fe464d9e1996ad455fdbc389206`，
`diff_fingerprint` 与 `status.json` 记录一致。

## 逐项审查

### 交付文件边界

仅五个授权交付路径发生变更：

- `backend/app/server.py`
- `backend/tests/test_service_health.py`
- `deploy/launchd/com.aoke.funding-hedging.server.plist.template`
- `scripts/service-control.py`
- `scripts/tests/test_service_control.py`

`scripts/run-server.sh` 未被修改，`.env` 加载与私有通道门保持原样。

### 正确性

- `backend/app/server.py:41-46` 在静态服务前正确分发 `/healthz` 与 `/readyz`。
- `_handle_healthz()` 返回固定 `{"status":"ok","service":"com.aoke.funding-hedging.server"}`，不触碰业务状态。
- `_handle_readyz()` 通过 `get_snapshot()` 做纯本地发布状态读取，任何异常均返回 503 `{"status":"not_ready"}`，异常文本不泄露。
- `run()` 将 `start_worker()` 纳入生命周期异常边界，`server_fatal_error` 仅记录异常类名，`server_stop` 后 `SystemExit(1)`，符合 `KeepAlive=true` 重启语义。
- `scripts/service-control.py` 使用 `plistlib` 序列化 Python dict，路径含空格/XML 元字符可正确回读。
- `KeepAlive=True` 与 `RunAtLoad=True`、`ThrottleInterval=10` 符合架构修正案 A1。
- 各 mutating 子命令 `--confirm` 门、install 已加载拒绝、restart `bootout→bootstrap`、uninstall 仅删除已知 plist 等逻辑符合修正案 A4。

### 安全/隐私

- 控制器不读取 `.env`，plist 不嵌入任何秘密。
- `_validate_base_url()` 拒绝 userinfo、query、fragment、非根路径、非 http(s) scheme、空白/控制字符、非法端口（0、负数、>65535）。
- `_redact()` 覆盖签名查询、Cookie/Set-Cookie、X-MBX-APIKEY、Bearer、URL userinfo；测试验证 userinfo 凭据不会出现在 doctor bundle 任何文件中。
- doctor 使用 `collections.deque(maxlen=200)` 做有界尾读，避免读取无界日志。

### 外部副作用隔离

- 测试通过注入 `FakeExecutor` 拦截所有 `launchctl` 调用，断言 argv 构造正确；真实 `~/Library/LaunchAgents/com.aoke.funding-hedging.server.plist` 的 mtime 在测试前后不变。
- 所有 mutating 命令在缺少 `--confirm` 时直接拒绝且零子进程调用。
- 测试从未向真实 `launchctl` 传递 `bootstrap/bootout/kickstart/enable/disable`。

### 测试

- `scripts/tests/test_service_control.py` 覆盖 plist 精确键、空格/XML 路径、`--confirm` 门、argv 构造、错误分类、port/host 校验、userinfo 脱敏、200 行尾读 cap、真实 plist 不被触碰。
- `backend/tests/test_service_health.py` 覆盖 healthz 固定 200、readyz ready/503、异常不泄露、零上游 I/O、生命周期 cleanup 与 `SystemExit`。
- 独立负向探针通过：非数字/越界/零端口、空白主机、URL userinfo 脱敏、`configuration file not found` 不被归类为 not-loaded。

## P0 / P1 发现

无。

## P2 / P3 发现

P3 `scripts/service-control.py:73-85`：脱敏正则为基础的最佳努力（best-effort）集合，未声明覆盖所有凭证形态；但设计已明确此属性，且 base URL 校验阻止凭证从主 URL 来源进入，当前阶段可接受。

## 过程说明

实施/修复作者（zhipu_glm）在 attempt 1 自报使用了只读 py_compile，attempt 2 自报使用了只读 Bash/grep。两次偏差均为只读、未触碰交付文件边界、未读取 `.env` 或执行真实 `launchctl`。Bookkeeper 已在 `20-implementation.md`、`40-fix-report.md`、`60-test-output.txt` 中披露。这两处属于过程合规性记录，不构成代码缺陷，不影响本次 review-1 结论。

## 结论

ACCEPT。无开放 P0/P1，冻结检查与负向探针均通过，证据完整。阶段可进入 review-2。

本地北京时间: 2026-07-13 21:21:28 CST
下一步模型: Codex bookkeeper / review-2 路由
下一步任务: 校验本 verdict JSON 与指纹，更新 status.json 并停在人工启动 review-2 前

The forwarded response ended with a fenced JSON object. Long tokens were hard
wrapped by the terminal/chat presentation; the de-wrapped object is preserved
without semantic edits in the adjacent verdict file.
