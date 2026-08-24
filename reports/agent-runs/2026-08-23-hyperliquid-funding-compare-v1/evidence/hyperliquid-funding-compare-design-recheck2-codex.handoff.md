# Task Handoff: hyperliquid-funding-compare-design-recheck2-codex

## Source Report (author-only; immutable after task end)

- task_id: `hyperliquid-funding-compare-design-recheck2-codex`
- role: `Reviewer / Design Recheck`
- target_model: `codex`（OpenAI）
- stage_id: `2026-08-23-hyperliquid-funding-compare-v1`
- created_at: `2026-08-23 11:29:12 CST`
- base_sha: `25cc8fe4e31194261dd48415f085bc6f9fda062d`
- delivery_sha: `fe91abb69e236e9ef110ca354b8773dfcb042773`
- rev2_sha: `2645bb2211895323f72187ff6499af57310192c6`
- reviewed_file: `docs/planning/hyperliquid-funding-compare-v1.md`
- isolation: 设计作者 Opus 5 / Anthropic；本 Reviewer Codex / OpenAI。跨 provider 成立。已披露前两轮 finding 均由本 Reviewer 提出，并按 rev3 方案本身复核，未要求沿用 token 方案。

## Verdict

**ACCEPT**。N1（含替代方案）、N1-2、N2、N3 与 §8 表述收窄均已闭合；设计可以进入实现 dispatch 准备。本轮为实现前计划复评，`rework_count` 保持 `0`。

## Fixed-range verification

- `status.json.revision == 4`，task id、base/delivery SHA 与 dispatch 一致。
- 三个 SHA 均可由 `git rev-parse` 解析；当前分支为 `2026-08-23-hyperliquid-funding-compare-v1`。
- rev2→rev3 产品修订为 `docs/planning/hyperliquid-funding-compare-v1.md` 的 `106 insertions / 25 deletions`；仅该文件受审，控制文件和 delivery 之后提交均排除。
- `git diff --check 25cc8fe4e31194261dd48415f085bc6f9fda062d..fe91abb69e236e9ef110ca354b8773dfcb042773`：通过。

## N1 — 时间戳替代 warning token

**判定：等效且在新鲜度维度更优。**

rev3 的单一 `hyperliquid_data_time` 能覆盖 token 所需的核心状态，并额外覆盖 token 不表达的陈旧状态：

| 后端/页面状态 | 可观察结果 | 判定 |
|---|---|---|
| HL 成功且某行无匹配 | 行内 `—`，时间有值且不红 | “知道没有” |
| 本轮整源失败 / 从未成功 / offline | 全行 `—`，时间 `null`，页面 `—` 且红 | “当前取不到” |
| worker/发布停滞但页面仍持有旧批次 | 旧值仍在，时间超过 90 秒后标红 | “数据陈旧” |

这消除了 rev2 的假绿：A7/A8 不再断言本来就永远非空的 `warnings`，而是断言字段从有值变 `null`、旧值与旧时间均不得保留，并检查页面 `.stale-time`；A9b 又守住成功但无匹配时不能误报失败。

相较 token，时间戳没有覆盖“具体失败原因”，但本产品要求是让使用者区分可用/陈旧/不可用，不要求在首页诊断 transport、shape 或 Decimal 的细分原因。当前没有必须把失败原因写进 wire 的证据，因此这不是缺口。

## N1-2 — 非法单币值简化为整源失败

**判定：可接受。** main+xyz 已被定义为一个原子批次；任一响应 shape 或任一 funding 无法转 Decimal 时整批作废，是一致的 fail-closed 规则。代价是单个坏值会降低整表 HL 可用性，但不会展示可能错误的费率，也不引入 per-row 状态或第二套 token。A9 给出了与其他整源失败相同且唯一的 oracle。

## N2 — offline

**判定：闭合。** §6.3 明确 offline 不进入 `_refresh_due_sources`、零 HL 网络、每行 `hyperliquid:null`、顶层时间为 `null`；A9c 同时检查零调用、row 投影、页面红色空时间与 schema。

一个必须带入实现 dispatch/代码评审的兼容检查：base `snapshot.schema.json` 顶层 `additionalProperties:false`，历史快照夹具也不含新时间字段。因此 schema 必须注册 `hyperliquid_data_time` 属性，但不能把它加入顶层 `required`；当前 producer 则由 A7–A9c 保证始终显式发出 string 或 null。rev3 已明确 row block 非 required，顶层字段的 optional 细节属于实现级 schema 落点，现有兼容测试会机械发现，不需要再改一轮 307 行设计稿。

另一个实现检查：现有 `isStaleTime(NaN)` 返回 false，因此 `null`/非法 ISO 的红色状态不能只调用该函数，必须显式把 unavailable 纳入 `.stale-time` 条件；A7/A8/A9c 已足以拦截。建议只给“HL 数据时间”片段加红色类，避免把同一 meta 行里仍新鲜的 Binance 时间一起染红；这是渲染范围检查，不是新产品契约。

## N3 — A13 请求次数

**判定：闭合且 oracle 唯一。** 一次成功刷新恰好 main/xyz 各一 POST；任一次刷新最多两 POST；所有路径 predictedFundings 为零；首个 POST 失败后短路、不发第二个。成功、第一请求失败、第二请求失败三个 adapter fixture 即可机械覆盖。

## §8 scope statement

**判定：准确。** 类别门只承诺拦截已有证据支持的跨类别撞名家族；同类别同名不受保护，仍由人工 DENY。该表述不再宣称所有未来撞名均自动消失，也没有为无证据假设扩 scope。

## 是否还需要继续修设计

**不需要。** 本轮没有剩余 design-stage finding。上述两个注意点（顶层时间字段 schema optional；null/非法时间显式标红并尽量只作用于 HL 片段）都已有明确验收或现有兼容测试，是实现后的 Review-1 应检查的具体落点。继续扩写设计的边际收益低于直接实现并让测试、代码 diff 暴露实际问题。

## Required Reading for the Next Task

- 读取路径及顺序：`reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck2-codex.handoff.md`；`docs/planning/hyperliquid-funding-compare-v1.md`
- 执行：Bookkeeper 核验 ACCEPT 并准备最小实现 dispatch；把“顶层 `hyperliquid_data_time` schema optional、producer 恒显式输出”和“null/非法时间显式标红且不误染 Binance 时间”列为实现/Review-1 检查
- 关卡：实现者按固定文件边界交付并自测后，依 HIGH_RISK 路由完成 Review-1 与 Review-2；本 ACCEPT 不授权合并、部署或实盘
- 不能假设的事实：时间戳方案已接受，不需要补 warning token；任一非法 funding 使 main+xyz 整批失败；offline 零 HL 网络；同类别同名仍不受类别门保护

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: hyperliquid-funding-compare-design-recheck2-codex
执行结果: completed（完成）
结果摘要: rev3 ACCEPT。时间戳方案等效且更强，可区分正常、陈旧、不可用；非法 funding 整源失败、offline 零网络、A13 次数 oracle 与撞名边界均闭合。仅保留两项实现审查点，无需继续扩写设计。
产物: [reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck2-codex.handoff.md]
检查结果: [pass：固定 SHA、revision、范围与 provider 隔离成立；pass：N1 时间戳三态消除 warning 假绿；pass：N1-2 非法值整源失败可接受；pass：N2 offline 零网络与投影闭合；pass：N3 请求次数 oracle 唯一；pass：§8 跨类别边界表述准确；pass：剩余 schema/CSS 落点可在实现与 Review-1 机械验证]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck2-codex.handoff.md
修复要求: none
本地北京时间: 2026-08-23 11:29:12 CST
下一步模型: Opus 5 / Claude（当前 Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-23-hyperliquid-funding-compare-v1/evidence/hyperliquid-funding-compare-design-recheck2-codex.handoff.md、docs/planning/hyperliquid-funding-compare-v1.md；执行：核验 ACCEPT 并准备最小实现 dispatch，纳入两项实现审查点；关卡：实现交付后按 HIGH_RISK 路由通过 Review-1 与 Review-2，方可交 Human 决策
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

## Errata (append-only)
