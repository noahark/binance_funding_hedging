# Task A Backend Implementation Prompt — Claude-GLM

你是本 stage 的 Task A 实现者，负责 backend/API/schema/domain/tests 与人读
contract 同步。请在严格文件边界内完成实现、运行测试并写 implementation
report。不要启动其他模型。

## Identity And Mode

- Adapter: `claude_glm`
- Provider identity: `zhipu_glm`（不是 Anthropic）
- Model: `glm-5.2`
- Skill: `senior_developer`
- Mode: write code inside allowed files only
- Stage role: Task A implementer；因此不得担任本 Task A 的 review-1，也不得
  担任本 stage 的 review-2。

## Repository And Git Boundary

- Repository: `/Users/ark/Desktop/ai code/funding_hedging`
- Required branch: `stage/2026-07-bookticker-open-columns-v1`
- Base SHA: `fea9fdc3ecce7675b34b01fe0a4b9de08811f939`

开始前确认 branch。若不匹配，停止并报告 blocker；不得自行切 branch、merge、
rebase、commit、push 或修改 git history。工作区已有 stage 设计/Harness/API
sample 改动，均属于用户/bookkeeper；不要清理、覆盖或重写无关改动。

## Required Read Set

必须亲自读取：

1. `AGENTS.md`
2. `agents/developer-discipline.md`
3. `docs/model-adapters.md`，特别是
   `Session ID Capture And Execution Receipts`
4. `reports/agent-runs/2026-07-bookticker-open-columns-v1/00-task.md`
5. `reports/agent-runs/2026-07-bookticker-open-columns-v1/10-design.md`
6. `reports/agent-runs/2026-07-bookticker-open-columns-v1/11-adr.md`
7. `reports/agent-runs/2026-07-bookticker-open-columns-v1/12-development-breakdown.md`
8. `reports/agent-runs/2026-07-bookticker-open-columns-v1/14-design-review-reconciliation.md`
9. `reports/agent-runs/2026-07-bookticker-open-columns-v1/status.json`
10. `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/evidence-index.md`
11. evidence index 点名的 raw/normalized bookTicker evidence
12. 下面所有 allowed source/test/doc files 的当前内容

若 `12-development-breakdown.md` 与后来的 reconciliation 存在差异，以
用户批准语义、`00-task.md`、修订后的 `10-design.md`/`11-adr.md` 和
`14-design-review-reconciliation.md` 为准。

## Allowed Writes

只允许修改或创建：

- `backend/adapters/binance_public.py`
- `backend/domain/snapshot.py`
- `backend/services/snapshot_service.py`
- `schemas/api/public-market/snapshot.schema.json`
- `backend/tests/test_book_ticker.py`
- `backend/tests/test_background_worker.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_negative_schema.py`
- `backend/tests/test_symbol_snapshot_endpoint.py`
- `docs/architecture/ARCHITECTURE.md`
- `docs/development/DEVELOPMENT_GUIDE.md`
- `docs/api/public-market-contract.md`
- `reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md`

Docs 只同步本次实际实现的 endpoint、cache、wire contract 和验证方式，不扩写
未来功能。

## Forbidden Writes And Semantics

- 不修改 frontend、其他 schema、`backend/tests/fixtures/**`、config、server、
  private client、PRD/ROADMAP/DECISIONS、Harness/templates、status/handoff/ACTIVE、
  API raw samples 或 `60-test-output.txt`。
- 不改 history 1500s refresh-ahead、history cursor、每 tick ≤10 symbol、
  `-0.00030000` 门槛、coverage ledger、borrow/max cadence、private transport
  TTL、签名 GET、白名单或现有 price-map gating。
- 不新增 config/env、scheduler abstraction、per-symbol HTTP、WebSocket、交易
  或借贷副作用。
- 不升级 wire version，不改 `/api/public-market/snapshot` route，不删除
  `ui_flags`/`asset_tag`/`negative_funding_status`。

## Required Implementation

### Adapter and pair cache

- 每次 due 顺序全量请求且无参数：spot
  `/api/v3/ticker/bookTicker`，futures
  `/fapi/v1/ticker/bookTicker`；request log 分开计数。
- 顶层均须非空 list；归一化后双 map 均非空；任一失败都不部分提交、不推进
  pair timestamp。
- 原始 `bidPrice`/`askPrice` 只有 JSON string 才能进入 map；禁止
  `str(number)`，全程禁止 `float`。
- 用独立 `book_ticker_pair` source，复用 `cache_ttl_seconds`（默认 60s）；
  completion-time 后一次性写 paired cache。
- 新 seam 用 capability check，不打断没有该方法的 legacy stubs；无 pair 不
  阻塞 premium/Group B 快照。
- source 始终公开启用，不受 private channel/classic reference gating。

### Assembly, status and formulas

- futures 按 `row.futures.symbol`；spot 按 resolved `row.spot.symbol`；锁定
  `TSLAUSDT -> TSLABUSDT`，不猜经济替代资产。
- 每次 assembly 用 monotonic age 重算：`age < 2*ttl` usable，
  `age >= 2*ttl` stale；跨 120s 不依赖额外 failure fetch。
- never succeeded -> `unavailable`、全 null、`updated_at=null`；stale ->
  全 price/spread null，但保留 last-success `updated_at`；fresh/incomplete 均
  保留 `updated_at`。
- 每个方向独立：forward 仅 F_bid+S_ask；reverse 仅 S_bid+F_ask。四价未全
  有效时 row 为 incomplete，但另一方向仍可计算。
- 仅 `Decimal`，严格 `(bid-ask)/ask*100` 顺序，最后一步才以
  `ROUND_HALF_UP` quantize `0.01`；`-0.00 -> 0.00`。

### Contract

- row 新增 optional `opening_quotes`；当前 producer 每行总是输出完整对象。
- 对象内部字段全 required 且 `additionalProperties=false`；旧 row 可整体缺失。
- `*_spread_pct` 是已经乘 100 的 percentage-point decimal string，不含 `%`。
- 不改 `symbol-snapshot.schema.json`；它通过 shared row `$ref` 自动继承。
- selected-symbol click 不新增 bookTicker HTTP，复用 canonical row 报价。

## Deterministic Tests

除 `12-development-breakdown.md` 清单外，必须明确覆盖：

- raw JSON number price 被拒绝，不能经 `str()` 进入可计算 map；
- 一次 success 后 monotonic `119.9` usable、`120.0` stale，不额外制造 fetch
  failure；
- forward-only / reverse-only / all-four / zero or missing leg / never-success
  真值表；
- non-list、empty list、normalized empty map、second endpoint failure 都不推进
  timestamp；
- legacy no-seam stub、private disabled、bStock alias、click no-extra-I/O；
- schema legacy compatibility、nested unknown/number rejection。

运行：

```text
pytest backend/tests/test_book_ticker.py backend/tests/test_snapshot.py backend/tests/test_background_worker.py backend/tests/test_symbol_snapshot_endpoint.py backend/tests/test_negative_schema.py -q
pytest backend/tests -q
python3 -m py_compile backend/adapters/binance_public.py backend/domain/snapshot.py backend/services/snapshot_service.py
git diff --check
```

不要修改 `60-test-output.txt`。在 implementation report 中逐条列出 command、
exit code 和简要结果；bookkeeper 会独立重跑并保存正式 test evidence。

## Required Report

写入 `20-implementation-task-a.md`，包含：

- implementer/provider/model/skill；
- exact changed files；
- 关键实现决策；
- 每条测试命令与结果；
- task boundary/ADR deviations（没有写 None）；
- remaining work/findings；
- git status（不得 commit）；
- 以下 footer。Session ID 优先读取 `CLAUDE_CODE_SESSION_ID`，并用当前
  transcript path 交叉验证；拿不到就写 unavailable reason，不得猜测。

最终响应也必须以同一 footer 结束：

```text
当前 Session ID: <provider-native id | unavailable (reason)>
Session ID 来源: <runtime_env | hook_payload | transcript_path | unavailable>
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/20-implementation-task-a.md
本地北京时间: YYYY-MM-DD HH:MM:SS CST
下一步模型: codex_bookkeeper
下一步任务: 核对 Task A diff/file boundary，独立重跑测试并创建 Task A evidence commit
```

时间必须来自本地 `date`。不得输出 token、cookie、credential、expanded env。
完成后停止，交回 codex_bookkeeper；不要开始 Task B 或任何 review。
