# Manual Pre-Review Repair Attempt 2 — Narrow Delta

Use the `senior_developer` skill explicitly. Continue as the same
`claude_glm` / `zhipu_glm` implementation/fix author. Edit only:

```text
scripts/service-control.py
scripts/tests/test_service_control.py
```

Do not touch the other delivery files, `scripts/run-server.sh`, stage evidence,
`.env`, schemas, or git state. Use only `Read`, `Glob`, `Grep`, `Edit`, and
`Write`. Do not invoke Bash, Python, pytest, py_compile, git, launchctl, or any
other command; the Codex bookkeeper owns every check.

The first repair materially improved coverage, but the independent frozen run
still exits 1 with `64 passed, 6 failed`. Fix all four remaining points in one
pass:

1. In `doctor()`, the final success message references undefined `loaded` after
   the state refactor. Use the actual boolean (`is_loaded`) and add/retain a
   regression assertion that `doctor()` returns 0 and prints the success line.

2. Tighten not-loaded classification. The generic marker `"not found"` still
   makes an unrelated error such as `configuration file not found` authorize
   the not-loaded/uninstall path. Remove generic matching and recognize only
   service-specific not-loaded results required by A4. Add negative coverage
   proving `configuration file not found` cannot authorize mutation or plist
   deletion while `Could not find service` remains tolerated.

3. Complete base-URL syntactic validation. These currently pass but must be
   rejected without echoing the value: non-numeric port, port outside 1..65535,
   and whitespace/control characters in the authority/host. Access and validate
   the parsed port safely (the parser may itself raise `ValueError`). Add both
   direct validator and `main()` non-echo tests with dummy values.

4. Diagnostic redaction must also remove userinfo credentials embedded in URLs
   found in captured logs/launchctl text, e.g.
   `http://user:DUMMY_SECRET@127.0.0.1:8787/path`. Add a doctor-bundle test that
   searches every written bundle file and proves the dummy username/password
   bytes do not survive. Preserve only a safe redaction marker/non-secret URL
   structure.

Return only a concise completion report with the two files actually changed
and the Claude session ID if available. Do not claim any command or test ran.

本地北京时间: 2026-07-13 20:40:27 CST
下一步模型: Codex bookkeeper
下一步任务: 重新执行六项冻结检查与四个负向探针；全绿后创建证据提交
