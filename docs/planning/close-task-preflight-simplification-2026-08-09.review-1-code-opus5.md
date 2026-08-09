# 平仓两段式交付：Opus 5 Review-1 代码评审文稿

> 这是 Review-1 的审查目标 companion，不是可单独启动的正式 dispatch。必须等 Claude-GLM Bookkeeper 封存提交后，由 Human 同时交付 stage 内正式 dispatch；若正式 dispatch 没有确定 `base_sha`、`delivery_sha`、`status_revision` 和唯一 create-only handoff 路径，立即返回非接受，不得审移动中的 `HEAD` 或未提交工作树。

## 任务身份与隔离

- 目标角色：`Reviewer / Review-1`
- 目标模型：Opus 5
- provider：`anthropic`
- 实现作者：Codex / OpenAI
- 风险：`HIGH_RISK`（订单、持仓、划转前置门）
- 默认 skill：`agents/skills/code-reviewer.md`

Opus 5 曾完成本需求 v1/v2 的独立计划评审，v2 结论为 `ACCEPT`，但没有编写本次实现。正式结果必须披露这段设计评审参与；实现作者与代码 Reviewer provider 不同，隔离成立。计划被接受不代表代码实现正确，本轮要重新从固定 diff 和源码调用链验证。

## 评审目标

判断固定 `base_sha..delivery_sha` 是否以最小、安全、可恢复的方式实现：

1. 创建 close 卡只做本地轻量校验并原子落 `paused / awaiting_manual_start`，立即回显；
2. 只有 Human 点击 Start 才把任务交给异步 worker；Start handler 本身不等待交易所预检；
3. live dispatch 在任何 attempt 和订单 POST 前完成必要安全门，失败就以准确原因暂停；
4. 保留有判断价值的 cache-first/live-fallback，只删除 close 无消费者或可固化的读取；
5. open、dry-run、最终平仓核实及既有补腿/reconcile 行为不被误改；
6. 交付完整落实计划复评强制约束 C1—C3，并同步活文档。

## 必读顺序

正式 dispatch 提供的路径和 SHA 优先；至少依次读取：

1. `AGENTS.md`
2. 正式 Review-1 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. 当前 stage `status.json`
6. `agents/roles.md` 的 `Shared Rules`、`Task Handoff Evidence Contract`、`Reviewer` 小节
7. `agents/skills/code-reviewer.md`
8. stage intake evidence 与 Bookkeeper 原始测试输出
9. `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-request-opus5.md`
10. `docs/planning/close-task-preflight-simplification-2026-08-09.v2.review-opus5-result.md`
11. `docs/planning/DECISIONS.md`、`docs/product/PRD.md` 和相关架构/历史计划更新
12. 固定 `base_sha..delivery_sha` 的完整 diff、调用方、消费者和测试

## 先验门

在看实现好坏前先确认：

- `git rev-parse` 与 `status.json` 的 base/delivery 完全一致；
- `git diff --name-status <base> <delivery>` 是固定已提交范围；
- 实现作者为 OpenAI，Reviewer 为 Anthropic；
- 唯一允许写入的 handoff 在开始前不存在；
- ledger/control commit 不得冒充 delivery 或进入受审范围；
- 未获得任何 merge、push、部署、重启、服务、数据库、交易所、凭据、gate、订单或划转授权。

任一前提不成立即非接受，写清缺失证据，不要用当前 `HEAD` 猜一个范围。

## 必查调用链与验收

### 1. 轻量建卡与原子状态

- `create_task` 的 close 分支只允许参数校验、active cycle/首个 open task 的 SQLite 读取、纯本地 symbol identity 双判和单条 INSERT。
- 证明没有 `check_symbol_legs`、`get_snapshot`、`compute_preflight`、exchangeInfo/ticker/balance/position/rate-limit GET、资产划转、attempt、worker 或订单 POST。
- `store.create_task` 必须在同一条 INSERT 原子写入 `status=paused`、`pause_reason=awaiting_manual_start`、`pause_reason_zh`；不得先 running 再 pause。
- close 卡 `q_common=NULL`、no-preflight snapshot、继承 origin 现货身份和 `position_side_mode`；origin mode 为 NULL 时固化 `BOTH`。
- 新卡进程重启后不能被 `_recover_workers` 当成 running 自动发单；仅允许已有未终结腿的 drain 语义保持。

### 2. Start 与绕过防护

- `/start` 只改 running、清原因、提交既有 worker 并立即返回，不得同步进入 preflight 或交易所 I/O。
- 首次待启动 close 的 fill-once/fill-all：前端禁用只是体验层，后端 `_require_fillable` 必须同样以 409 拒绝直接 API 绕过。
- 启动后因其它原因再次 paused 的任务不得被永久锁死；既有恢复/fill 语义应保持。

### 3. Dispatch 固定顺序与 fail-closed

live close 每轮必须在 `prepare_attempt` 前按顺序完成：

1. 存量固化值 OR 当前纯映射的 1000x 双判；
2. fresh preflight 的 filters、price、quantity/notional 等必要计算；
3. signed UM position 门；
4. forward ordinary-spot base 门；
5. 全部通过后才 `prepare_attempt` 和两腿提交。

每个失败分支都要验证：attempt 不增、两腿 POST 为 0、精准 `pause_reason_zh` 不被 worker 的通用暂停覆盖。确认新 signal 没有造成忙循环、误重试或吞掉其它既有 signal。

### 4. C1：UM position 新鲜度、方向和数量

- `um_positions` 必须走现有 `_cached("um_positions", _CACHE_MAX_AGE_BALANCE)`，上限 300 秒；不能无上限信任旧缓存。
- fresh cache 有目标 symbol 才返回其数量；fresh cache 无行应解释为 flat/0 并阻塞，不能当 miss 后用旧事实放行。
- cache miss、超龄、坏形状才调用 hedge executor 的 `query_symbol_um_qty` 实时兜底。
- `None`、异常、不可解析、`NaN`、无限值、0、无行、反号、数量不足全部 fail-closed。
- forward 必须是负持仓且 `abs(positionAmt) >= q_common × remaining_attempts`；reverse 必须是正持仓且数量满足。
- 检查 symbol 匹配、Decimal 转换和缓存时间单位，防止测试与实现共用同一个错误假设。

### 5. C2/F2：每轮 base 门

- forward close 的普通现货 base 校验必须在 fresh `q_common` 产生后、每个 live attempt 前运行，不能只跑首笔。
- required 必须精确为 `q_common × (target_n - scheduled_attempt_count)`，第 1/2/3 笔对应 `×3/×2/×1`；失败 attempt 消耗计数的现有语义不得造成少备或负数。
- cache 足够零网络；cache miss/不足才实时确认；实时仍不足才查统一账户并只划 deficit。
- 查询能力缺失、实时确认失败、可转不足、划转失败都必须在 attempt/POST 前暂停。
- reverse close 不误走普通现货 base 门；普通现货资产名必须使用固化的 spot base，不能从 `1000BONKUSDT` 等合约字符串错误剥取。

### 6. 保留与删除的读取

- close 只跳过/替换：实时 position mode、PAPI order rate-limit、Spot order rate-limit、普通现货 USDT。
- position mode 来自任务固化值；其它仍有消费者的数据继续 cache-first/live-fallback。
- exchangeInfo、price、方向性余额及外置的 forward base/UM 门在缓存缺失时仍可恢复；`private_channel_enabled=false` 不得造成“能开不能平”的永久暂停。
- open 的 provider 调用、实时兜底、rate-limit/余额判断和 `_degrade_note` 不能被 close 专用参数或默认值改变。
- 全仓查消费者，确认被跳过的三个无消费者快照字段没有隐蔽决策用途；position mode 是替换而非裸删除。

### 7. C3：dry-run、最终核实和既有执行语义

- dry-run close 在 Start 后允许使用原始 `single_amount` 记录，绕过新增 UM/base live 门，且 record transport 永远 0 POST；不得把“无需 live 查询”误实现成“可走真实订单”。
- live path 必须使用 fresh `q_common`，不能沿用建卡时 NULL 或原始 amount。
- `_verify_close_flat` 继续实时查询并保持 flat/open/failed 和周期关闭语义，不得改成缓存。
- 两腿并发、client order ID、自动补腿、reconcile、rate-limit 后处理和 gate 语义不在本轮重构范围。

### 8. 前端与文档

- 页面立即插入后端返回的 paused close 卡；中文原因准确；Start 可用；首次 fill 两按钮禁用。
- 不新增前端交易所请求，不把约 60 秒 UI 缓存当成后端安全事实。
- `PRD.md`、`ARCHITECTURE.md`、`DECISIONS.md`、旧计划 supersession 指针和 `PROJECT_STATE.md` 必须诚实区分“本地待评审”与“运行中行为”。
- API 路径/响应字段/schema 未改时无需硬造 API 文档改动；如实际 diff 改了公共契约则必须指出。

## 必跑检查

在只读 review 环境运行并引用原始结果：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider backend/tests
node frontend/self-check.js
git diff --check <base_sha> <delivery_sha>
```

还要按固定 diff 定向运行/检查两段式 create/start、1000x 历史 NULL、UM 正反号/无行/超龄/实时失败、3 次 forward remaining、第二笔失败零 attempt/POST、dry-run 零 POST、open cache miss 回归、startup recovery 和 fill API 绕过。不要使用毫秒阈值；用 fake client 调用次数证明 create/Start 同步外部调用为 0。

## 发现与 verdict 规则

- 一次给全反馈，不分轮滴漏；重点是错误订单、单腿敞口、人工启动绕过、不可恢复卡死、契约回归和必要测试缺口，不报纯风格偏好。
- 每条 `REWORK` 发现必须按 `AGENTS.md` §8 标成 `in-range`、`pre-existing-independent` 或 `pre-existing-release-critical`，附源码/测试/提交证据；`pre-existing-*` 必须给早于 base 的 `git blame` 或 `git log -L`。
- Reviewer 新提出的假设场景只有满足 Scenario Admission 才能阻塞；写清当前证据、实际影响及为何必须本轮修。缓存与交易所之间天然竞态、两腿并发非原子、多 close 卡竞争等已在计划写成剩余风险，除非固定 diff 新增可证明的未闭合危险，不要把既知非目标重新包装成无证据 blocker。
- 只要存在一个有证据的 `in-range` 阻塞项就返回明确 `REWORK（返工）`；如果实现、测试和契约全部通过，返回明确 `ACCEPT（接受）`。发现全为范围外时按规则仍返回 `ACCEPT`，但问题记录必须保留。
- 计划评审的 `ACCEPT` 不能替代本次代码 verdict；后端全绿也不能替代资金路径的静态量纲、顺序和 fail-closed 检查。

## 唯一写入与 Stop

Reviewer 除正式 dispatch 指定且已预检不存在的确定性 handoff 外完全只读。不得修改本文、交付代码、测试、既有文档、`status.json`、`PROJECT_STATE.md`，不得 commit、merge、push、部署、重启、控制服务、读取凭据、访问 live DB 或发起交易所请求。

handoff 必须遵守 `agents/roles.md` 的 Task Handoff Evidence Contract，引用固定 base/delivery SHA、原始命令结果、逐项结论、问题路径和修复要求。控制台严格按 `AGENTS.md` §7 输出 review 版 `[TASK_RESULT v2]`；只有格式完整且明确 `评审结论: ACCEPT（接受）` 才算通过。完成后停止，由 Claude-GLM Bookkeeper 核验；不得自行启动修复或 Review-2。
