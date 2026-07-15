# Stage Intake And Complexity

## User Discussion Summary

用户批准创建本 stage，目标是在现有只读资金费率工作台中完成以下有界改动：

1. 表头“净收益”改为“日净收益”，排序提示同步为“日净收益优先”。
2. 删除前端默认表的“提示标记”展示列，但保留后端 `ui_flags` 契约字段以维持兼容性。
3. 将“资产标签”和“负费率状态”合并为一个前端展示单元格：借贷/可借状态在上，资产标签在下；底层字段继续独立。
4. 每 60 秒全量请求公开、无 key 的现货 `GET /api/v3/ticker/bookTicker` 与合约 `GET /fapi/v1/ticker/bookTicker`，缓存匹配交易腿的买一/卖一字符串价格；不得逐行请求，也不得受私有通道开关控制。
5. 新增“正向开单”和“反向开单”两列：
   - 正向开单上方显示合约买一、下方显示现货卖一；价差率为 `(合约买一 - 现货卖一) / 现货卖一 * 100%`。
   - 反向开单上方显示现货买一、下方显示合约卖一；价差率为 `(现货买一 - 合约卖一) / 合约卖一 * 100%`。
   - 两个方向均以正数表示该方向存在正价差，百分比保留两位小数。

用户同时批准了讨论中其余约束：bookTicker 作为 always-on public Group A（始终启用的公共 A 组）来源；bStock 使用解析后的 `row.spot.symbol` 连接；缺失/零价格不计算；跨市场报价成对缓存并携带更新时间；报价连续失败超过两个刷新周期后不作为可用开单价展示；UI 明示这是 60 秒参考报价而非成交保证；价差计算由后端 `Decimal` 统一完成，前端只格式化展示。

2026-07-15 用户进一步明确授权：本 stage 同时集成模型执行回执的
Session ID 展示能力。该 Harness 变更是本 stage 的显式范围修订，原因是
后续 Task A/Task B 及正式 review 都需要立即使用这项行为；它只修改
Harness 规则、适配器说明、工作流与模板，不改变产品运行时。Session ID
只作人工导航，跨模型审阅仍以 stage 内 raw output 路径为准。

原始事实证据已由人工委托 Grok 捕获到：

- `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/evidence-index.md`
- `reports/api-samples/2026-07-bookticker-discovery-v1/20260715T0651Z/capture.md`
- 同目录下 `raw/` 响应、headers 与 `normalized/` 归一化摘要。

这些文件当前是用户工作区中未提交的改动；stage 分支从 `main` 基准创建后原样承接，bookkeeper 不改写其原始内容。

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `false`
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- 用户需求、两个开单方向的价格位置与公式均已明确，没有未决产品语义。
- 改动有界于现有只读快照工作台，不新增下单、借币、转账或其他交易副作用。
- 新增公开 Binance 接口与缓存、Schema 和派生价差，超出纯前端机械改动。
- 后端契约/缓存与前端展示都需要实质性测试，但可在既有 Group A worker 和单页表格结构内完成，无需架构重写。
- 原始公开 API 响应和 headers 已落档，可满足契约修订的事实证据要求。
- 用户明确要求当前 stage 使用新的 Session ID 回执格式，因此满足
  `AGENTS.md` 所述“stage needs new Harness behavior”的混入例外；该变更随
  stage 分支最终 fast-forward 到 `main`，不另行从 `main` 合并 Harness commit。

## Human Gates

- 用户已批准轻量路线并批准上述冻结语义，因此本 stage 跳过 direction panel（方向评审组）。
- `MEDIUM` stage 在实现前必须完成 Claude provider 的 development breakdown（开发细化）；Fable5 配额耗尽时才回退 Opus4.8。
- 实现/评审模型由人工在目标终端执行 bookkeeper 准备的 dispatch，不由 Codex 执行模型命令。
- `review-2 ACCEPT` 后仍须用户明确验收，才能将 stage 分支合并回 `main` 或推送。
- Session ID 规则只要求可验证值或明确的 `unavailable (reason)`，不得因
  provider 未暴露 ID 而猜测，也不得把 ID 当作凭据或跨 provider transcript。

## Routing Decision

- Next node: `stage-design`

## Bookkeeper

- Provider/model/session: `codex / gpt-5 / codex_bookkeeper`
- Independent from implementers: `true`
- If not independent, disclosure: `n/a`

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

理由：后端契约必须先冻结，前端再对已冻结契约集成；采用顺序的 backend → frontend 任务，避免为本次中等规模改动引入并行模式的额外同步面。

## Evaluator

- Provider: `codex`
- Model: `gpt-5`
- Skill: `complexity_evaluator`

当前 Session ID: 019f639a-7890-7573-a04b-7a62debff633
Session ID 来源: runtime_env (`CODEX_THREAD_ID`)
原始输出路径: reports/agent-runs/2026-07-bookticker-open-columns-v1/00-intake.md
本地北京时间: 2026-07-15 17:34:26 CST
下一步模型: claude_glm（由人工执行）
下一步任务: 执行 Task A backend implementation packet；完成后交回 codex_bookkeeper
