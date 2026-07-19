# Stage Intake And Complexity

## User Discussion Summary

在已验收并合并的 `2026-07-borrow-task-ui-fake-v1` 基础上，用户要求进入真实借币业务开发阶段。上一阶段已提供前端 fake 借币任务：从费率行情创建任务、任务列表筛选、启动/暂停/删除、参数编辑，以及最小借币量和估值回显；它没有借币 API、后台任务、定时器、持久化或私有写请求。

本阶段的产品目标是把已确认的任务 UI 接入真实后端借币能力：任务可被可靠保存和恢复；处于“借币中”的任务按受控间隔尝试借入指定资产和数量；失败按策略重试；达到累计成功次数后停止；状态和进度回显到页面。此前被 Review-2 标为 P3 的“同页其他卡片未提交编辑值会在重渲染时丢失”与表格行内可访问性设计问题，用户明确决定本阶段忽略，不作为范围或阻塞项。

真实借币会创建账户负债并调用交易所私有写接口。方向冻结前不得实现、调用、模拟调用或以任何方式触发 Binance 借币端点；不得在仓库、报告、日志或模型提示中写入凭据。

## Classification

- Complexity: `MILESTONE`
- Direction panel required: `true`
- Existing synthesis covers this work: `false`
- User approved lightweight route: `false`
- Lightweight skip allowed: `false`

## Rationale

- 这是从浏览器内存 fake 迁移到真实账户负债、持久后台调度、私有写 API、失败重试和前后端一致性的跨域变更。
- 自动重试会在无人点击时产生新的借款请求，必须先明确授权模型、幂等性、状态机、上限、暂停/删除竞态、故障恢复与审计证据。
- 凭据、交易所 API 语义和实际资金风险均属于 Harness 人工门禁事项；MILESTONE 路径不可由轻量路线替代。

## Human Gates

- 用户审批方向综合稿后，才可创建 stage branch、设计实现任务和开发代码。
- 任何真实 Binance 借币请求之前，必须在批准的设计中冻结：账户/保证金模式、资产/数量规则、任务重试间隔、成功定义、授权与二次确认边界、单任务及全局风险上限、停止开关、幂等/重复请求防护、凭据注入方式、审计和恢复策略。
- 不得在阶段产物、终端输出或模型提示中记录 API key、secret、cookie、签名或完整私有账户数据。

## Routing Decision

- Next node: `direction-drafts`

## Direction Panel

- Active panel key: `direction_panels.default`
- Derived stage key: `2026_07_real_borrow_execution_v1`（未在 registry 中覆盖，使用 default）
- Members: `codex`, `claude`, `glm52`, `kimi27`, `grok-build`
- Synthesizer: `codex` / GPT

## Bookkeeper

- Provider/model/session: Codex/GPT（Session ID unavailable：当前运行时未暴露 provider-native session ID）
- Independent from implementers: `true`
- If not independent, disclosure: N/A；当前未开始实现，且 Codex 不担任本 Harness 的实现/修复作者。

## Parallel Mode

- Uses `docs/parallel-development-mode.md`: `false`
- R10 dispatch tail required: `false`
- R4 diff reconciliation required: `false`

## Evaluator

- Provider: Codex/GPT
- Model: unavailable（runtime 未暴露 provider-native model label）
- Skill: complexity_evaluator

当前 Session ID: unavailable (current runtime does not expose provider-native session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-real-borrow-execution-v1/00-intake.md
本地北京时间: 2026-07-19 02:16:55 CST
下一步模型: direction panel（Claude、GLM、Kimi、Grok；Codex draft 已由本会话写入）
下一步任务: 形成独立的真实借币执行与风险控制方向草案
