# Task Handoff: hyperliquid-funding-compare-design-recheck-codex

## Source Report (author-only; immutable after task end)

- task_id: `hyperliquid-funding-compare-design-recheck-codex`
- role: `Reviewer / Design Recheck`
- target_model: `codex`（OpenAI）
- stage_id: `2026-08-23-hyperliquid-funding-compare-v1`
- created_at: `2026-08-23 11:15:56 CST`
- base_sha: `25cc8fe4e31194261dd48415f085bc6f9fda062d`
- delivery_sha: `2645bb2211895323f72187ff6499af57310192c6`
- rev1_sha: `6ee75b0c1eb405fa2bf79a0a7aad4814142800d5`
- reviewed_file: `docs/planning/hyperliquid-funding-compare-v1.md`
- isolation: 设计作者 Opus 5 / Anthropic；本 Reviewer Codex / OpenAI。跨 provider 成立。已披露 F1–F5 由本 Reviewer 首轮提出，并对 rev2 §5/§6/§9 从头复核。

## Verdict

**REWORK**。rev2 已闭合大部分结构性问题：F3、F5、R2 确认闭合；F1/F2/F4 只剩同一个根因——失败/无效状态没有形成可唯一判断、可被首页消费的信号。另有一条现存离线路径未纳入设计。D7 不增加 xyz 休市价值判断提示的拒绝可接受。

本轮仍是实现前计划修订，`rework_count` 保持 `0`。

## Fixed-range verification

- `status.json.revision == 3`、task id、base/delivery SHA 与 dispatch 一致。
- `git rev-parse` 验证三个 SHA 均存在；当前分支为 `2026-08-23-hyperliquid-funding-compare-v1`。
- 只评审 delivery SHA 中的 `docs/planning/hyperliquid-funding-compare-v1.md`；控制文件、旧 handoff/dispatch 与 delivery 之后提交均未受审。
- `git diff --check 25cc8fe4e31194261dd48415f085bc6f9fda062d..2645bb2211895323f72187ff6499af57310192c6`：通过。

## F1–F5 / R2 recheck

| 项目 | 判定 | 独立复核 |
|---|---|---|
| F1 失败语义 | **部分闭合** | 独立 60s source_id、main+xyz 原子失败、失败后不投影 warm last-good、且不进入 `_compose_base_raw` 的 A+B 发布门，能同时做到 HL 变 `—` 与 Binance 继续发布；冷启动结构也相容。但“可见 warning”尚无唯一 token 和首页消费契约，见 N1。 |
| F2 验收可执行性 | **部分闭合** | 原不可执行的 HL-only 例子已正确换成 Binance-only fixture；A1–A6、A10–A12、A14–A16 均有明确 seam。A7–A9 的 warning oracle 不足，A13 的“全程两次”需按一次刷新明确，见 N1/N3。 |
| F3 漂移撞名 | **闭合（需收窄一句过度表述）** | `build_rows` 已持有 Binance `contractType`；main→`PERPETUAL`、xyz→`TRADIFI_PERPETUAL` 可拦住当前已证实的股票/加密跨类别撞名家族，A2 synthetic 可证明不依赖 BB/QNT 枚举。§8 的“新撞名均”应改成“新跨类别撞名”，因为同类别语义撞名不受该门保护；当前没有同类别实证，不另行扩 scope。 |
| F4 wire 契约 | **部分闭合** | block shape、dex、decimal string、DENY 顺序、`isDelisted` 与 per-row invalid fail-closed 均已定义。但 §5 先称 `null` 只有两种可区分成因，随后又引入非法 funding 的第三种 `null`，却没有对应信号，见 N1。 |
| F5 事实与文件边界 | **闭合** | 全文市场数字统一标为 2026-08-23 点时样本；258=171 main+87 xyz、122 4h+136 8h 与固定 JSON 复算一致。`self-check.js` 与 `public-market-contract.md` 已入清单；DI 分支明确要求追加 `server.py`。 |
| R2 成本 | **闭合** | 现有 `history_sweep_batch_size=10`；30 日 720 个小时点、单页 500，最坏每个币两页，因此 HL +20、总计 10→30 的口径正确。 |

## New findings

### N1 — `in-range`：失败、无匹配和非法单币值在现有产品链上仍不可可靠区分

**证据锚点**：

- rev2 §5 第 122–127 行：无匹配与源失败都为 `hyperliquid:null`，随后又规定非法 funding 也为 `null`，但非法值没有 warning/status。
- rev2 §6 第 142–146 行和 A7/A8：仅写“带 warning”，没有冻结 HL 专属信号或首页展示断言。
- base `backend/domain/snapshot.py:88-92,352-380`：每份快照无条件携带固定 `CONTRACT_WARNINGS`；所以断言“warnings 非空”在 HL 成功时也成立，不能证明 HL 失败信号存在。
- base `frontend/index.html:3221-3230`：首页只校验 `snapshot.warnings` 是数组，并不渲染内容；`3775-3786,3870-3885` 只在单 symbol drawer 的 `partial` 响应中显示该响应的 warnings，不会让首页 HL 全空时出现提示。

**实际影响**：实现完全可能让 A7/A8 以“快照本来就有 warning”假通过；页面上源失败、无匹配、单币非法都会只显示 `—`。这直接违反设计自己引用的“读不到不得假装知道没有”，并未闭合首轮 F1/F4。

**本轮必须最小修正**：

1. 在 §5/§6 冻结一个 HL 源失败专属、文档化的 warning token（例如 `hyperliquid_source_unavailable`），源成功时必须不存在；A7/A8 断言该 token，而不是只断言数组非空。
2. 对单币非法 funding 追加带完整 HL key 的专属 token（例如 `hyperliquid_funding_invalid:xyz:TSLA`）；A9 同时断言该 token，其他有效标的不受影响。无需新增 row 状态字段。
3. `frontend/index.html` 在首页/开关附近消费源失败 token，显示中性最小提示“HL 数据暂不可用”；A7/A8 增加该提示可见断言。它只描述真实源失败，不是 D7 拒绝的“休市读数退化”价值判断。
4. A6 增加反向 oracle：源成功且仅无匹配时，上述源失败 token 与提示均不存在。

### N2 — `in-range`：现存 offline 零网络路径没有 HL 投影契约或验收

**证据锚点**：base `backend/services/snapshot_service.py:324-340,489-508` 明确 offline 走同步 frozen-fixture build、零网络，不经过 `_refresh_due_sources`；base `backend/config.py:66-71` 明确 offline 不启动 worker。rev2 §6 只定义 worker source_id，A1–A16 没有 offline 用例，也没有 HL fixture。

**实际影响**：实现者仍需自行猜测 offline 是全 `null`、是否带源失败提示、是否错误访问公共网络；新增 required row block 后，这条现存路径可能破坏 schema 或零网络保证。

**本轮必须最小修正**：在 §6 增加一句并新增验收：`APP_OFFLINE=true` 时零次 HL 网络请求，每行 `hyperliquid:null`；明确复用 N1 的“HL 不可用”信号，或明确一个不同但同样可判定的 offline 信号。无需新增 fixture、状态或抽象。

### N3 — `in-range`：A13 的请求次数 oracle 需要限定“一次刷新”

rev2 A13 的“adapter 全程仅发出两次”可被理解为进程生命周期总计两次，与 60s 刷新矛盾，也没有说明首个 POST 失败时第二个是否仍必须发出。最小修正为：一次**成功**的 HL 刷新恰好发两次 `metaAndAssetCtxs`；任一次刷新最多两次；所有路径 `predictedFundings` 为零。若设计坚持失败时也必须尝试两 dex，则把“失败刷新也恰好两次”写明。只改 oracle，不新增机制。

## A1–A16 executable audit

- **pass**：A1–A6、A10–A12、A14–A16 均能分别落到 normalize/build_rows/schema/frontend self-check 或回归 fixture；A2 对新跨类别撞名有独立 synthetic oracle。
- **fail**：A7/A8 只要求“带 warning”，会被快照固定 warnings 假通过，也没有首页可见提示 oracle。
- **fail**：A9 没有区分非法 funding 与正常无匹配的可观察 oracle。
- **fail**：A13 未限定一次刷新与失败时调用次数，按原文不是唯一 oracle。
- **missing**：offline 零网络与 block 投影没有验收项。

## D7 decision

**接受不添加“非美股交易时段读数可能退化”的静态提示。** Human 已明确休市高费率正是产品要观察的现象；`HL·xyz` 中性来源标签足以说明来源。静态“退化”提示会把真实市场现象预判为低价值，不是数据正确性所必需。

N1 要求的“HL 数据暂不可用”只在请求/shape 真实失败时出现，属于中性事实状态，不评价 xyz 休市费率，也不推翻 D7。

## Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md`；`docs/planning/hyperliquid-funding-compare-v1.md`
- 执行：Bookkeeper 核验本 REWORK；派 Planner 只修 N1–N3，并收窄 §8“新撞名均”的表述后重新计划评审
- 关卡：专属失败信号、首页中性提示、offline 零网络投影及唯一请求次数 oracle 通过独立计划复评后，才可准备实现 dispatch
- 不能假设的事实：`warnings` 非空不证明 HL 失败；首页当前不展示 snapshot warnings；`null` 当前有无匹配、源失败、单币非法三种成因；D7 已接受，不应借本次修订加入 xyz 休市价值判断

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: hyperliquid-funding-compare-design-recheck-codex
执行结果: completed（完成）
结果摘要: rev2 已闭合类别门、成本、文件边界和多数验收，但 HL 失败信号仍会被固定 warnings 假通过，首页也不显示；非法单币值与无匹配仍同为无提示的空值，offline 路径未定义。结论 REWORK，D7 不加休市价值判断可接受。
产物: [reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md]
检查结果: [pass：固定 SHA、revision、范围与 provider 隔离成立；pass：F3 类别门闭合；pass：F5 时点/分母/文件边界闭合；pass：R2 最坏 +20、总量 10→30 闭合；pass：D7 拒绝休市价值判断可接受；fail：F1/F4 缺 HL 专属失败/非法值信号且首页不消费；fail：F2 的 A7–A9/A13 oracle 不唯一；fail：offline 零网络投影与验收缺失]
阻塞项: [按 handoff N1–N3 最小修订设计并重新计划评审；本次仍为实现前设计修订，不增加 rework_count]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md
修复要求: reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md
本地北京时间: 2026-08-23 11:15:56 CST
下一步模型: Opus 5 / Claude（当前 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck-codex.handoff.md、docs/planning/hyperliquid-funding-compare-v1.md；执行：核验 REWORK 并派 Planner 最小修订 N1–N3；关卡：修订设计重新通过独立计划评审后才可派实现
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)
