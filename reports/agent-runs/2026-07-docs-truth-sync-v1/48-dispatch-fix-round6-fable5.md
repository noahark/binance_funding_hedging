# Dispatch Packet — fix round 6（semantic-convergence; user-authorized 3rd override）（executor → Fable5）

用户第三次授权超 rework 上限（本轮 rework 6），选 **(a) 语义收敛版**（Codex 建议）。
fix author = **Fable5**（anthropic/claude-fable-5）。opus4.8 继续 bookkeeper 并对账
（opus4.8 不 review 本 stage，无双帽）。正式 review-2 仍 **Codex/OpenAI**（与 anthropic
fix author 厂商隔离）。review-1 维持豁免。

只改 `docs/api/public-market-contract.md` 的 symbol-snapshot 段 + append-only
`40-fix-report.md`。**不 commit**。禁改 backend/frontend/schemas/scripts、Stage-B/
Harness-track、bookticker living-docs、active status/handoff/60-test/ACTIVE。**不改
schema、不改产品行为**。

`fable5 -p "$(cat reports/agent-runs/2026-07-docs-truth-sync-v1/48-dispatch-fix-round6-fable5.md)"`

---

## PROMPT BODY

Fix Review-2 Round-5 REWORK (F13/F14) for stage `2026-07-docs-truth-sync-v1` — user
has authorized a 6th over-limit bounded fix and chose the **semantic-convergence**
approach. Reviewed fingerprint:
`e214d6f819d76daa3b85865c1021b5aa2497ee95:d93ff6d4be65eda9882a6145e69a8dfcb346b854af38f40da79ff49f5cdf965e`.
Read `reports/agent-runs/2026-07-docs-truth-sync-v1/50-review-2.md` (round-5 raw, JSON
final block), `40-fix-report.md`, the fixed diff, and the cited source/tests; do not
work from a bookkeeper summary.

### 根因（为什么这次要"收敛"而不是"补 token"）
前 5 轮 review 全 REWORK，都集中在 symbol-snapshot 的失败矩阵 prose：它**过度枚举**了
每个 warning token / mode / timeout 成因，每补一个就暴露/引入一个相邻不准（F14 正是
上轮主动多加的 `base_raw_unavailable` 造成的回归——该 token 经 HTTP 不可达）。本轮**从
源头收敛过度承诺的表面积**，让后续 review 无 nit 可挑。

### 必做（一次性完成 F13 + F14 + 收敛）
仅改 `docs/api/public-market-contract.md` 的 symbol-snapshot 段：

1. **warnings 改为开放式保守描述**（不要把 vocabulary 权威指向 schema——
   `symbol-snapshot.schema.json` 只把 warnings 定义为 string[]、无 token 枚举，且其第
   5/39 行 prose 已确认陈旧；指向它会制造新的过度承诺）。目标措辞（可微调）：
   > `warnings`: diagnostic reason strings actually serialized for this response. The
   > vocabulary is open-ended and non-exhaustive; clients must not assume completeness
   > or branch on undocumented values. A `timeout` may carry no warning.
   > `refresh_status` remains authoritative.
2. **所有 row-source 表述统一为 mode-dependent（修 F13）**：
   live → latest `PublishedState`；offline → synchronously built / cached snapshot。
   删除所有"row always/unconditionally from published state"的无条件句（当前在
   ~306-309、~358-361、~392-395）。
3. **timeout 只保守描述**：本次请求没有产生新 publication，live row 使用 last-good
   published state。**不要枚举全部成因**。
4. **明确公开端点在首次 publication 前返回 503**（`snapshot_service.py:333-335`）；
   **删除 `base_raw_unavailable` 的公开 wire 描述（修 F14）**——它经 HTTP 不可达
   （冷启动先 503；`_base_raw` 在 publish 前必设置且无重置路径；分支 :1395-1402 仅单元
   测试直调可触发）。若要保留该事实，只能明标为"内部防御性 diagnostic、当前 HTTP 前置
   条件下不可达"，不得列为公开 outcome。
5. `refresh_command_expired` 可保留，但**最好仅作非规范示例**；最稳妥是完全不枚举 token。
6. 保留已正确的部分：live/offline `published_version`（live=真实修订号 / offline=0
   sentinel）、live-only same-PublishedState row 身份、无跨请求同版本保证；funding-history
   与 annualized 段不动。

### 禁改
backend/frontend/schemas/scripts、Stage-B/Harness-track、bookticker living-docs、
active status/handoff/60-test/ACTIVE（bookkeeper-owned）。不改 schema、端点、产品行为。
（`snapshot_service.py:320-322` docstring 仍写 same-version 属已披露 deferred，不在本轮修。）

### 跑
1. `rg -n 'published state|PublishedState|Offline|synchronously built|base_raw_unavailable|refresh_command_expired|snapshot_not_ready|non-exhaustive|open-ended' docs/api/public-market-contract.md`
2. `if rg -n 'base_raw_unavailable' docs/api/public-market-contract.md | rg -v 'internal|unreachable|not exposed'; then echo REVIEW-CONTEXT; fi`  # 若保留须带 internal/unreachable 限定
3. `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_funding_history.py backend/tests/test_funding_history_endpoint.py backend/tests/test_symbol_snapshot_endpoint.py -q -p no:cacheprovider`
4. `node frontend/self-check.js`
5. `git diff --check`
6. `git diff --name-only`  # 只应有 contract + append-only 40-fix-report.md

向 `40-fix-report.md` 追加 Round-5 段（F13/F14 → 精确 before/after + 命令输出，前序报告
逐字保留）。然后停下交 bookkeeper 对账。**不 commit。**

## END PROMPT BODY
