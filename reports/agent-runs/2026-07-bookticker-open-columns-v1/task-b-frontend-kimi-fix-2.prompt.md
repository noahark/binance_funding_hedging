# Task B Frontend Pre-Commit Fix 2 — Resume Kimi

继续复用 Kimi Session
`session_727145b3-694a-4467-8277-60a65dd1b1c5`。Pre-Commit Fix 1 已关闭产品
语义 finding，独立 frontend/full-backend 回归均通过；现在只修正一条漏掉的
确定性断言和 implementation report 内部矛盾。不要扩大范围。

## Boundary

- Branch: `stage/2026-07-bookticker-open-columns-v1`
- HEAD: `dff8b4785f43cd9fb82b7fab6214bc8c7d98ac88`
- 保留当前未提交工作树，不 reset/checkout/clean。
- 本轮只允许修改：
  - `frontend/self-check.js`
  - `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-b.md`
- 不修改 `frontend/index.html`、preview fixture、backend/schema/Harness/
  status/handoff/ACTIVE/`60-test-output.txt`，不 commit、不 push、不 review。

## Required Corrections

### 1. BUSDT incomplete 必须显式断言 dash

当前 #33e 的注释/报告说“无效方向显示 `—`”，实际测试仍只断言
`busdtForward` 不含 `-0.04%`/`+0.04%`，任何其他错误文字也可能假通过。

对 BUSDT forward cell 增加明确断言：

- 仍显示有效 `合约买一` 价格 `64,925.00`；
- `现货卖一` 缺失腿显示 `—`；
- forward spread 本身显示 `—`。可通过对该 cell 的 em-dash 数量断言至少为 2，
  同时锁定有效腿价格和两个标签；
- 继续断言 reverse 的两个有效腿与 `+0.04%`。

保留“禁止出现样例错误百分比”的断言也可以，但它不能替代显式 dash 断言。

### 2. 清理同一 report/测试注释的残留矛盾

- `20-implementation-task-b.md` 的 Exact Changed Files 仍把 XAUUSDT 列在
  `fresh`；改成 `incomplete`，与 F2 和实际 fixture 一致。
- 测试结果写精确为：`77 [PASS] lines (1 syntax + 76 behavioral checks)`，不要
  模糊写 “all 76 checks”。
- `frontend/self-check.js` 借币三态旧注释仍说额度位于 `net-yield` 子行；改为
  合并列，不改测试行为。
- 在 report 追加 `Pre-Commit Fix 2` 小节，说明这只是测试/证据一致性修正；不要
  删除原 Session receipt 或 Fix 1 记录。

## Commands And Stop

运行：

```text
node frontend/self-check.js
node frontend/self-check.js | rg -c '^\[PASS\]'
git diff --check
git status --short
```

预期 PASS 行计数为 `77`。更新 report 的测试结果和 git status；不得 commit。
最终 footer 保留同一 provider-native Session ID、source、raw path，并将下一步任务
写为“bookkeeper 复核并创建 Task B evidence commit”。完成后停止。
