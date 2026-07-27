# 用户授权 —— 第 7 次有界后端变更（Review-2 的 3 条 P1 + validator 覆盖）

> **起草者**：Claude Opus 5（Anthropic），本 stage 当前 bookkeeper（2026-07-25 从 Codex 接任，
> 双重身份披露见 `27-user-authorized-r4-repair.md` §6 与 `status.json.bookkeeper.dual_hat_disclosure`）。
> 本文件是 stage state（授权记录），**不构成验收**。

## 1. 授权

- **时间**：2026-07-26（北京时间），在读完 `69-review-2.md`（verdict `REWORK`，6 条 P1，
  `next_action = human_escalation_required`）与 bookkeeper 的逐条讲解之后。
- **决定**：授权**第 7 次**有界代码变更。`rework_count` 上限由 **6 → 7**。
- **用户明确的产品方向（逐字记录）**：

  > 我们的目标是尽快上线验证，在实盘中再发现问题做优化。不要在设计阶段太关注低概率场景发生的事情

  本授权的范围裁剪完全依据这条方向：**只修实盘必然发生的问题，低概率与观测性问题一律后置。**
- **实现者路由**：Claude-GLM（`glm-5.2[1m]`，`zhipu_glm`），与前六轮后端 owner 一致。
  该路由同时保证下一轮 Review-1 的 provider 隔离（Anthropic 仍可用）。
- **投递**：人类操作员把 packet 贴进 GLM 终端。任何模型不得自行派发。

## 2. 授权范围：4 项必做

### 2.1 【R2-F1】非限频 single_leg 未计入连续失败；计划组数用尽未转 done

Review-2 finding 1。非限频、非致命的 `single_leg` 结果当前完全不动 `fail_count` /
`consecutive_submission_failures`，导致"连续失败 3 次自动暂停"这道刹车在单腿场景下永不触发；
且最后一笔计划 attempt 结算后任务未按批准语义转 `done`。

### 2.2 【R2-F2】client-ID 查询误判与查询阶段 429 被丢弃

Review-2 finding 2。`classify_query_response`：
- 任何 2xx 但缺少有效 `orderId` 的响应被判成 `LEG_REJECTED`（"订单不存在"），
  而批准的合同只允许**显式** 404 / `-2013` 确认未受理；
- 查询阶段的 429 / `-1003` / 418 返回 `None`，服务层无法观察到限频事实。

**这条是本次范围内风险最高的一项**：实盘限频时必然触发，后果是把**可能已经成交**的订单
判成未成交，进而继续开下一组 —— 直接导致重复开仓与账本失真。

### 2.3 【R2-F4】两腿都终态但 `pair_outcome` 为 NULL 的崩溃缝隙

Review-2 finding 4。腿终态化与 attempt 结算是两个事务。若在两者之间崩溃，恢复时看不到非终态腿
（无腿可 drain），而 `prepare_attempt` 又因未结算的 attempt 拒绝开新组 —— 该组真实成交永久留在
计数器/阈值/审计之外，且 running 任务可能无 pacing 空转。

### 2.4 【R2-F6 剩余项】validator 覆盖

Review-2 finding 6 的**簿记部分已由 bookkeeper 于 2026-07-26 修复并提交**
（`faa33b9`：66/67/68 回执封存 + Review-2 回执封存 + 根状态 `review_1 → review_2`；
所有时间戳均标注真实来源，无法取得的字段按 `unavailable` + 原因记录，**未发明任何时间或 Session ID**）。

**本次授权的增量**是让 `scripts/validate-stage.py` 能**自动检出**这两类漏洞：
1. 当前阶段引用的 dispatch 回执必须是 `completed`（不得停在 `pending` 却已有产出）；
2. 根 `status` 必须与所处工作流阶段一致（例如派发 Review-2 时根状态不得仍是 `review_1`）。

用户原话：「finding6加入一起修」。

## 3. 明确**不做**（用户逐条裁定）

| 项 | 用户决定 | 记录 |
| --- | --- | --- |
| Review-2 F5 账户健康（`accountStatus` / `uniMMR`） | **不做** | 需新增 `GET /papi/v1/account` 并解冻七端点 allowlist；用户选择不引入 |
| Review-2 F5 现货 `MIN_NOTIONAL` 解析 | **不做** | 用户原话：「finding5金额我会输入的时候做校验的，会输入一个大于最小金额的数量」。bookkeeper 已提示"输入的是数量、交易所卡的是名义金额（数量×价格），需留余量"，用户接受该操作约定 |
| Review-2 F3 人工 delete/pause 被迟到 worker 写入覆盖 | **暂时不修** | 用户原话：「删除和暂停会出现点击后状态被运行中任务再改回来的问题也可以暂时不修」。bookkeeper 已一次性说明风险（紧急删除时卡片可能显示为 paused、删除决定丢失、需人工再点 Start 才会继续开组、不会自动下单）。**连带效果：`frontend/**` 无需改动，前端 Review-1 的 ACCEPT 继续有效** |
| 排队期间取消删除命令 | **不做** | 用户原话：「排队期间能否取消删除没必要做」 |
| `aggregate_positions` 过滤 `deleted` 导致敞口不可见 | **不做** | 用户原话：「敞口任务卡删除，敞口状态我会从持仓面板核对，下单只记录成交信息」 |
| 命令队列（方案 B）/ 条件 UPDATE（方案 A）/ 删除 UI 文案 | **全部作废** | 随 F3 不修一并取消；本轮不引入 `requested_action` 状态机，不改 API 语义 |
| r4/r5 既有 P3（settle 错误列、Start 竞态、post_start 时序）、跨进程预留守卫、`X-MBX-ORDER-COUNT-*` 节流、前端展示 `worker_active` | **后置 follow-up** | 均为低概率或纯观测性，符合用户"不要在设计阶段太关注低概率场景"的方向 |

## 4. 文件边界

**允许修改**：

```text
backend/hedge_open_tasks/domain.py
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/store.py
backend/services/live_hedge_executor.py
scripts/validate-stage.py                      # 仅 §2.4 的两项检查
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_review2_regressions.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_domain.py
backend/tests/test_live_hedge_executor.py
scripts/tests/test_validate_stage_dispatch_protocol.py   # 仅 §2.4 的新检查
reports/agent-runs/2026-07-hedge-open-real-api-v1/60-test-output.txt   # 仅追加
reports/agent-runs/2026-07-hedge-open-real-api-v1/71-fix-review-2-backend-r7.md  # 新建
```

**禁止修改**：`frontend/**`、`docs/**`、PRD、`10-design.md`/`11-adr.md`、
`backend/services/hedge_open_live_client.py`（**七端点 allowlist 冻结不变**）、
`backend/services/hedge_preflight_provider.py`（账户健康与 MIN_NOTIONAL 本轮不做）、
`backend/hedge_open_tasks/scheduler.py`、`backend/app/server.py`、
`reports/api-samples/**`、`status.json`、`70-handoff.md`、任何契约文档（15/16/17/19/21/23/24/25/26/27/28）
与任何评审报告（30/42/45/50/58/59/64/66/68/69）、环境/凭据/网络配置。

**硬安全约束**：绝不读取凭据、绝不连接 Binance、绝不发送真实 POST、绝不启用 live、
绝不触发 Start、绝不 commit、绝不派发评审、绝不自行判定验收。
**不得新增全局守护 / 周期扫描器 / timer / 自动补腿 / 撤单 / 平仓 / 借还 / 转账 / WebSocket / 平滑开仓。**

## 5. 精确自测

```bash
.venv/bin/python -m pytest \
  backend/tests/test_hedge_task_local.py \
  backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_service.py \
  backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_domain.py \
  backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_purity.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check
```

基线参照（bookkeeper 本机实测，head `b9e1978`）：十组聚焦 = **230 passed**；
`backend/tests` = **906 passed**；前端自检全通过；Harness = **55 passed**；`git diff --check` exit 0。

## 6. 验收条件（用于新一轮 Review-1）

1. §2 四项各自有确定性回归，且**先证明缺陷代码会失败、再验证修复转绿**（实现报告须给出自己的原始输出）。
2. `backend/tests` 全量、前端自检、Harness 协议套件全绿；`git diff --check` 干净。
3. H-1 三防线（`test_6a/6b/6c`）、packet 62/63/65/67 的既有性质（`test_1`–`test_5`、`test_4b`、R1–R9）仍全绿。
4. `frontend/**` 零改动；七端点 allowlist 未变；`_ENTRY_EVENT_KINDS` 未新增 kind；
   未新增全局守护/定时器/周期扫描器。
5. 全程零真实 POST、零私有网络、零凭据访问、零 live 启用、零 Start。

## 7. bookkeeper 待办

1. ✅ 落盘本授权 + `status.json` 的 `max_rework` 6 → 7。
2. ✅ 生成 packet `72-fix-review-2-backend-r7.dispatch.md`，PROMPT BODY 以 Review-2 的原始
   `fix_start_prompt` 为基底，仅按本授权做**透明标注的定点裁剪**（排除项 + 新增 validator 项 + 允许文件清单）。
3. GLM 完成后：R4 差异核对、独立复跑测试、**自己做反向验证**（不采信声称）、创建证据提交、
   重算指纹、准备新一轮 Review-1（provider 需与 `zhipu_glm` 隔离）。
4. **实盘门**：本授权**不**解除任何实盘门。live 启用、Start、第一笔真实订单仍是独立的人类授权。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/28-user-authorized-r7-repair.md
本地北京时间: 2026-07-26 CST
下一步模型: claude_glm / glm-5.2[1m]
下一步任务: execute packet 72 in a fresh write-capable Claude-GLM session (human operator delivers it)
