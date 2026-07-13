# Manual Pre-Review Repair — T1 launchd service

Use the `senior_developer` skill explicitly. Continue as the same
`claude_glm` / `zhipu_glm` delivery author and repair the current uncommitted
implementation. This is a pre-review correction, not a new design and not a
review verdict.

You may create/edit only these five delivery files:

```text
deploy/launchd/com.aoke.funding-hedging.server.plist.template
scripts/service-control.py
scripts/tests/test_service_control.py
backend/app/server.py
backend/tests/test_service_health.py
```

Do not edit `scripts/run-server.sh`, any Harness/stage evidence, `.env`, or any
other file. Do not use Bash, do not run `launchctl`, do not start the service,
and do not inspect secrets. The Codex bookkeeper will run all deterministic
commands after you finish.

## Blocking repair findings

1. Make `scripts/tests/test_service_control.py` import the hyphenated controller
   correctly on the repository's Python 3.9. Register the module in
   `sys.modules` before `exec_module`; the current fixture raises from
   `dataclasses` and causes 31 setup errors. Correct the XML-metacharacter test:
   validate `plistlib` round-trip/escaping rather than requiring a raw literal
   path containing `<`, `>`, and `&` to appear unescaped in XML.

2. Enforce amendment A2 for the health base URL. Accept only a syntactically
   valid HTTP(S) base containing host/optional port and no userinfo credentials,
   query, fragment, or non-root path. Reject invalid input non-zero without
   echoing the supplied value. Ensure neither `status` nor `doctor` can emit a
   credential-bearing or signed URL. Add negative tests for userinfo and query
   data from both CLI and `FUNDING_HEDGING_SERVICE_URL` sources.

3. Strengthen diagnostic privacy. `_redact` and doctor bundle tests must cover
   dummy signed-query values, `Cookie`/`Set-Cookie`, `X-MBX-APIKEY`, bearer
   tokens, and secret-like key/value data. No dummy secret bytes may survive in
   any written bundle file. Preserve the fixed, non-secret host/port summary.

4. Make doctor tail collection memory-bounded to the most recent 200 lines; do
   not call `readlines()` on the whole unbounded log. Use a streaming bounded
   structure such as `collections.deque(maxlen=200)` and retain deterministic
   UTF-8 replacement behavior.

5. Before `bootstrap`, create the configured logs directory so both
   `StandardOutPath` and `StandardErrorPath` have an existing parent. `render`
   must remain side-effect free. Add fake-executor/tmp-path coverage proving the
   logs directory exists for install/restart and that no real home path or real
   `launchctl` is touched.

6. Do not collapse every non-zero `launchctl print` into "not loaded". Only the
   documented specific service-not-found/not-loaded result may take that path;
   permission, malformed-command, or other tool errors must be surfaced and
   must stop `install`, `start`, `stop`, and `restart` before mutation. Tighten
   uninstall tolerance so broad text such as `unrecognized` or unrelated
   `no such` errors cannot authorize plist deletion. Add negative tests for
   `Operation not permitted`, `unrecognized command`, and unrelated
   `No such file or directory` results.

7. Put worker startup inside the lifecycle failure boundary in
   `backend/app/server.py`. If `start_worker()` or `serve_forever()` raises an
   unexpected exception, emit `server_fatal_error` with exception class only,
   emit `server_stop`, stop the worker safely, close the server, and exit
   non-zero. Never emit exception text. Add deterministic injected lifecycle
   tests for startup failure and main-loop failure, plus the normal/keyboard
   cleanup path.

## Frozen verification owned by the bookkeeper

```text
python3 -m py_compile backend/app/server.py scripts/service-control.py
python3 -m pytest scripts/tests/test_service_control.py backend/tests/test_service_health.py -q -p no:cacheprovider
python3 -m pytest backend/tests -q -p no:cacheprovider
node frontend/self-check.js
bash -n scripts/run-server.sh
git diff --check
```

When finished, return a concise report containing the exact files changed and
how each numbered finding was addressed. Include the Claude session ID if the
terminal exposes it. Do not claim that tests ran.

本地北京时间: 2026-07-13 19:47:13 CST
下一步模型: Codex bookkeeper
下一步任务: 检查五文件修复 diff，执行六项冻结检查，并在全绿后创建实现证据提交
