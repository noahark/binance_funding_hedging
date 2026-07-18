# Stage Intake And Complexity

## User Discussion Summary

在行情表的“借贷状态 / 资产”右侧增加“操作”列。每行提供两个输入框：单次借币数量、累计成功次数上限，以及“确认”按钮。确认后只在前端内存创建借币任务；任务页展示任务的币种、单次数量、成功进度/目标、累计目标数量、固定重试间隔和模拟状态。

`HOME` 是本轮必须支持的借币资产：当行情行的 `base_asset` 为 `HOME` 时，操作列必须创建 `HOME` 任务。当前样例快照没有 `HOME` 行，因此不得伪造或写入市场数据；自检通过把内存样例行的 `base_asset` 改为 `HOME` 覆盖该流程。

本轮仅做前端 fake 供用户查看效果。不得新增借币 API、后端任务、定时器、私有签名请求、凭据、持久化或交易动作。后端自动重试与真实借币将在用户确认 UI 后另立阶段。

同时删除额度子行中的独立“已借完”徽标；保留借贷状态徽标“可借 0(已借完)”。

用户追加了最小借币量契约：已有 `GET /sapi/v1/margin/allAssets` 的 `userMinBorrow` 按 `assetName` 保存并装配到 `rows[].borrow_validation.classic_margin.user_min_borrow`，匹配规则与 `asset_borrowable` 相同；同一最小量的 USDT 价值按现有价格规则计算为 `user_min_borrow_value_usdt`，保留两位小数。行情表操作列的单次借币数量输入保持空值，只将固定“如 1000”替换成最小借币量及其 USDT 价值占位提示。

## Classification

- Complexity: `MEDIUM`
- Direction panel required: `false`
- Existing synthesis covers this work: `false`
- User approved lightweight route: `true`
- Lightweight skip allowed: `true`

## Rationale

- 原始 fake 任务改动限定在现有单文件前端和已有 Node 自检；本次补充的最小借币量为窄幅后端、API 契约和数据语义扩展。
- 借币任务在浏览器内存中 fake，明确不产生外部副作用。
- 用户明确要求先完成前端 fake 并在视觉确认后再增加后端逻辑，等同于批准轻量路线。
- 现有表格行已经提供 `base_asset`，可作为任务资产，不需要新增资产选择器或伪造行情行。
- 用户追加了任务状态机、软删除、列表内参数编辑和状态筛选；这已超出 LOW 的一次性 UI 原型，但仍是用户明确批准的前端 fake 范围。
- 最小借币量是现有 classic-reference 链路的窄幅后端/契约扩展；它需要原始公共样例、schema 和后端测试，但不增加新 endpoint、写操作或外部副作用。

## Human Gates

- 用户查看并确认 fake UI 后，才能启动包含真实借币请求、后台调度、重试、存储或 Binance 私有 API 的后端阶段。
- 本阶段不得把“确认”连接到任何外部请求。

## Routing Decision

- Next node: `development-breakdown`

## Bookkeeper

- Provider/model/session: Codex/GPT（Session ID unavailable: 当前运行时未暴露 provider-native ID）
- Independent from implementers: `true`
- If not independent, disclosure: N/A

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

## Evaluator

- Provider: Codex/GPT
- Model: unavailable (runtime does not expose a provider-native model label)
- Skill: complexity_evaluator

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-borrow-task-ui-fake-v1/00-intake.md
本地北京时间: 2026-07-18 18:26:49 CST
下一步模型: Kimi
下一步任务: 执行前端 fake 借币任务 UI 的实现派发包
