# Human Escalation — Real LaunchAgent Blocked By macOS Desktop TCC

Stage: `2026-07-local-service-launchd-v1`

## Authorization And Scope

At 2026-07-13 21:41 CST, the human operator explicitly requested that existing
local frontend/backend services be stopped and that the delivered stable
service controller be run for visible acceptance. This authorized the real
current-user `launchctl` mutation that the stage had previously deferred.

No existing listeners were present on `8787`, `3000`, `5173`, or `8000`, and
the service label was initially not loaded.

## Real Execution

The bookkeeper ran:

```text
python3 scripts/service-control.py install --confirm
```

The controller wrote the expected plist to:

```text
/Users/ark/Library/LaunchAgents/com.aoke.funding-hedging.server.plist
```

`launchctl` loaded the job and attempted it repeatedly, but the service never
listened on `127.0.0.1:8787`. The real service record showed:

```text
state = spawn scheduled
runs = 5
last exit code = 126
```

The controller's sanitized doctor bundle is:

```text
/Users/ark/Library/Logs/funding-hedging/diagnostics/20260713T134341Z
```

Its redacted stderr evidence is explicit:

```text
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
/bin/bash: /Users/ark/Desktop/ai code/funding_hedging/scripts/run-server.sh: Operation not permitted
```

## Finding

The development checkout is under macOS's protected `~/Desktop` tree. A
background LaunchAgent does not inherit the interactive terminal application's
Desktop-folder privacy grant. The service therefore cannot access its working
directory or launcher, regardless of the plist's correct quoting and XML
serialization.

This is real-environment evidence that was absent from the isolated tests. The
previous review-2 dispatch is suspended: it must not certify the stage while
the approved repository location cannot launch independently of a terminal.

## Safe Stop

To prevent `KeepAlive=true` from retrying every 10 seconds, the bookkeeper ran:

```text
python3 scripts/service-control.py stop --confirm
```

Final external state:

- service loaded: false
- listeners on the tested local ports: none
- installed plist: retained for a reversible retry
- logs and sanitized doctor bundle: retained
- no source file or `.env` content changed or printed

## Human Decision Required

Recommended: place the runtime checkout/deployment under a non-TCC-protected
directory such as `~/Developer/funding_hedging`, then regenerate the plist from
that location. This keeps launchd least-privileged and avoids granting
system-wide Full Disk Access to `/bin/bash` or Python.

Alternatives requiring explicit choice are:

1. Move the active repository to a non-protected development directory.
2. Add a separate deploy/sync flow that creates a runtime copy outside
   `Desktop` while keeping this checkout in place.
3. Grant a broad macOS privacy exception to the executable chain. This is not
   recommended because it expands filesystem authority.

本地北京时间: 2026-07-13 21:44:36 CST
下一步模型: Human
下一步任务: 选择非受保护运行目录方案或显式接受 macOS 隐私权限扩张；选择后修复并重新执行真实 launchd 验收
