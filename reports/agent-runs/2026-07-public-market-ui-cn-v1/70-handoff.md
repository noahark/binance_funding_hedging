# Handoff — 2026-07-public-market-ui-cn-v1

## Stage status

`implementing` → 即将 `review_1`（Task A/B/C 全部实现并验证完毕；本提交 H_C 收尾）。
Controller **不**声明最终验收（`can_accept_final=false`）；终态目标 `stage_accepted_waiting_user`。

## Prerequisite (satisfied)

`2026-07-public-market-impl-v1` + `2026-07-public-market-bstock-alias-v1` 均已获用户最终验收
（commit `6d8c0c4`）。本阶段 base 锚定 H_intake = `b84a342`（intake/task/design/status +
live funding-semantics evidence）+ `d3d6e7c`（Fable5 预写 Task B 派工 prompt，intake/design 范畴）。

## Delivered tasks

| Task | Owner | Head | Scope | Key result |
|---|---|---|---|---|
| A — lastFundingRate warning semantic amendment | `claude_glm` | `dba4c12` | `snapshot.py` (CONTRACT_WARNINGS[1] string only) + contract doc + tests | 新实证文案；snapshot.py diff 仅 -1/+1；54 passed |
| B — frontend CN-first + column merge + flags de-noise | `kimi` | `0fd0d17` | `frontend/**` | 字符串移位格式化；列合并；数据说明区；self-check 14/14 |
| C — integration verification | `claude_glm` (controller, no product code) | H_C（本提交） | `20-implementation.md`/`60-test-output.txt`/`11-adr.md`/`70-handoff.md` | rows 与 548ae0d 逐字段一致；schema VALID；not BLOCKED |

## Evidence (intake, read-only during stage)

`reports/api-samples/2026-07-public-market-ui-cn-v1/20260704T044945Z/` — `evidence-index.md`
（sha256 of raw）+ `verify-funding-semantics.py`（offline replay, exit 0 = PASS）证明
`premiumIndex.lastFundingRate` 是本周期实时预估值（周期中段 ETHUSDT/SOLUSDT 预估值 ≠ 已结算记录；
15 分钟内漂移）。

## Hard constraints honored

- 无 live HTTP（intake 证据已抓齐；A/B/C 全程 offline）；无 key/签名/私有端点/order/borrow/
  repay/transfer/websocket。
- rows 结构与数值零变化（Task C 逐字段对比 548ae0d PASS）；API 载荷唯一变化是 `warnings[1]` 文本。
- `classify.py` / `normalize.py` / `snapshot_service.py` / `schemas/**` 零改动。
- 前端费率百分比格式化为纯字符串移位（`parseFloat`/`Number×100` 禁用；`formatFundingRate` 验证）。
- UI 中文优先（主表无英文枚举直出；USDT/bStock/API/symbol 等技术词保留）。
- `reports/api-samples/**` 全部只读。

## Review routing (per AGENTS.md + status.json)

- **review-1**（cross-review）：
  - Task A → **Kimi**（实现者 `claude_glm`，cross-review 选 Kimi）。
  - Task B → **全新只读 Claude-GLM 会话**（实现者 `kimi`；fresh session，禁止复用 controller/Task A transcript）。
- **review-2**（final gate）：**Codex/GPT `gpt-5.5`**（`codex exec -s read-only`），
  `reviewer_prior_involvement = direction_synthesis`（strong-reviewer disclosure override）。
  Anthropic/Fable5 本阶段为 designer/breakdown author（design involvement）→ 排除出 review-2 池；
  两实现方（`claude_glm`/`kimi`）hard-ban。Codex 无本阶段设计/拆分/代码参与（唯一先前参与是覆盖契约阶段的
  user-approved direction synthesis）。与前两阶段同径。

## Fingerprint protocol (single, unchanged)

`diff_fingerprint = head_sha + ":" + sha256(git diff --binary <base_sha>..<head_sha> -- . ":(exclude)reports/agent-runs/<stage-id>/status.json")`

- base_sha = `b84a342`（全程不变）。
- stage-level top-level fingerprint 在 H_C 后绑定（status.json.head_sha / diff_fingerprint）。
- status.json 排除在 hash 外。

## Known notes (transparent, non-blocking)

- H_intake 物理上是 `b84a342` + `d3d6e7c` 两个提交（`d3d6e7c` = Fable5 预写 Task B 派工 prompt，
  intake/design 范畴，无产品代码）。base_sha 按用户指令锚定 `b84a342`，故 `d3d6e7c` 的 intake 产物
  随 stage diff 携带（合法 intake/design 范畴，非产品代码；详见 `status.json.diff_fingerprint_note`）。
- 11-adr.md：`00-task.md` 称本阶段不设 ADR，但 `validate-stage.py` gate 要求该文件存在，故创建
  minimal ADR 记录「无新架构决策」+ 几条过程决策（见 `11-adr.md`）。

## Next step

`validate-stage.py --phase pre-review`（需 clean tree）→ status `review_1` → 派 review-1（A→Kimi，
B→fresh read-only Claude-GLM）→ review-2（Codex）→ `--phase pre-accept` → `stage_accepted_waiting_user`。
Controller 不声明最终验收，等用户外部 review。

本地北京时间: 2026-07-04 13:36 CST
下一步模型: review-1（cross-review）
