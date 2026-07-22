[HARNESS-EXECUTOR-CONTRACT v1]
你是本任务的唯一执行者。
1. 禁止调用、启动或转派任何其他模型会话或 adapter 命令（包括但不限于
   claude-glm -p、kimi -p、codex exec、grok）。需要其他模型时，输出
   ESCALATED 及原因并停止。
2. 禁止编造未实际执行的命令结果或未实际读取的文件内容；你写下的每一条
   执行记录都必须对应你本会话内真实发生的动作。
3. 你的评审依据只能是本 prompt 列出的 raw artifact 路径与你自己实际读取的
   文件。

# Review-1 — Hedge Open Fake UI v1（fresh-context Claude-GLM）

你是本 stage 的 review-1，fresh-context Claude-GLM 会话，模型
`glm-5.2[1m]`，provider identity `zhipu_glm`。实现者为 Kimi
（`moonshot_kimi`），与你 provider 不同，交叉评审成立。你未参与本 stage 的
设计/breakdown/实现，`reviewer_prior_involvement` 如实填 `none`。

人类操作员须在新的 Claude-GLM terminal 执行本 prompt（复用则先 `/clear`）。
不要继承任何其他会话的结论或工具状态。

## 严格只读与安全边界
- 只读评审：禁止编辑/创建/删除/暂存/提交/推送/合并/部署任何文件。
- 禁止读取 `.env`、key/cookie/credential，禁止输出完整环境变量。
- 禁止向 Binance 或任何外部服务发请求。本 stage 是纯前端 fake，不应存在任何
  真实网络/下单/websocket 路径——若发现，即为高优先级发现。
- 不得调用或转派其他模型。当前 `HEAD` 可能晚于被审 head；只审固定
  `base_sha..head_sha`，不得以移动 `HEAD` 替代。

## 固定审查身份与范围
- Stage: `2026-07-hedge-open-fake-ui-v1`
- Role: `first_reviewer`
- Base SHA: `46ea46f6caacf78dca4ef5345f60518c77d6e378`
- Head SHA: `f2afabe5ece95169e6eb38b6835d50dbc11fb1e6`
- Diff fingerprint:
  `f2afabe5ece95169e6eb38b6835d50dbc11fb1e6:05ea25bb543c798ec2b35573e127d5828ed01ba576aa8ca0fe75e798c5d99f1b`
- 查看被审改动：
  `git diff 46ea46f6caacf78dca4ef5345f60518c77d6e378..f2afabe5ece95169e6eb38b6835d50dbc11fb1e6`

## 必读原始 artifact
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/00-task.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/10-design.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/11-adr.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/12-development-breakdown.md`（含 review 关注点）
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/20-implementation.md`
- `reports/agent-runs/2026-07-hedge-open-fake-ui-v1/60-test-output.txt`
- 源文件：`frontend/index.html`、`frontend/self-check.js`

## 审查重点（对照 12-development-breakdown「Risk points」）
1. 文件边界：改动是否仅落在 `frontend/index.html` + `frontend/self-check.js`。
2. self-check 耦合：新逻辑是否全在**第一个** `<script>` 块内；既有断言是否
   全部保留；是否引入未清理定时器或跨域 fetch。
3. 列改造：`正向开单率/反向开单率` 仅改名（估算列语义不变）；两操作列是否**在
   `借币` 列之后**按序；两列恒可点、按费率符号高亮推荐方向。
4. 基差口径（ADR-2，不得改符号/腿映射）：正向=(perp_bid1−spot_ask1)/mid、
   反向=(spot_bid1−perp_ask1)/mid、≥0.05% 才开。
5. 单腿敞口→exposure_alert+leg_exposure+暂停；累计 >3 失败→终止+暂停+不补发；
   失败注入可 seed（自检确定性）。
6. 持仓聚合数学：均价=Σnotional/Σqty per leg；量权基差；净盈亏=价格PnL+资金费−利息。
7. 冻结契约字段名（Task/Fill/localStorage 键）逐字符合 design §4。
8. scope 蔓延：无真实 websocket、无后端桩、无下单路径、无新文件/依赖；反向开单
   不自动借币（只查 fake 额度）。
9. 用户追加需求（状态筛选+软删除，见 10-design §2.1b/§4.2、11-adr ADR-5）：状态
   筛选栏 全部/执行中/已暂停/已删除/已完成 带实时计数、默认执行中；删除为软删除
   （status='deleted' 保留持久化、卡片全按钮禁用、拒绝 启动/成交1次/立即成交所有/
   重复删除、被引擎与持仓聚合跳过、不计入导航「执行中」徽标）。核查新增 'deleted'
   态在各处状态标识符的一致性，以及 exposure_alert 仅在「全部」可见。

## 自行验证
- 运行 `node frontend/self-check.js`，确认 exit 0 且既有+新增断言全绿；把你实际
  观察到的结果写进评审正文（不得编造）。

## 输出要求
- 评审正文写你实际读取/运行的证据与发现。
- 结尾输出**唯一一个** schema-valid JSON，匹配
  `schemas/review-verdict.schema.json`：字段含 `schema_version:1`、
  `stage_id`、`role:"first_reviewer"`、`model`、`verdict`（ACCEPT/REWORK/BLOCKED）、
  `diff_fingerprint`（上面那串）、`reviewer_prior_involvement:"none"`、
  `reviewed_artifacts`、`findings`、`required_fixes`、`next_action`。
- 若 `REWORK`，必须含 `fix_start_prompt`（可直接派给 Kimi 的修复 prompt，保留
  raw artifact 路径、发现、需修项、文件边界、精确测试命令、验收标准）。
- 追加 AGENTS.md「Output Footer」六行；为保证 JSON 可解析，footer 置于最终
  JSON 块之前。
- 只读评审：写完即停，不改任何文件、不 commit、不转派。
