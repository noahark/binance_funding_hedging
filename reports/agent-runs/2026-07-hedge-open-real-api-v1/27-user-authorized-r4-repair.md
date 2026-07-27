# 用户授权 —— 第 6 次有界后端变更（Review-1 r4 的两项 P2）

> **本文件的身份**
>
> 起草者：**Claude Opus 5（Anthropic）**，本 stage 当前的 **bookkeeper**。
> 同一模型也是本轮 Review-1（`66-review-1-backend-r4.md`）的审查者 —— **双重身份已如实登记**，
> 见 §6 与 `status.json.bookkeeper.dual_hat_disclosure`。
>
> 本文件是 stage state 的一部分（授权记录），由 bookkeeper 落盘。它**不构成验收**：
> 验收仍需新一轮 provider 隔离的 Review-1 + Review-2。

## 1. 背景：bookkeeper 交接

- **触发**：2026-07-25，用户报告 **Codex（GPT-5 Codex）无额度**，原 bookkeeper 无法继续。
- **用户原话**：

  > codex 无额度了，你立即接管 bookkeeper 角色位置。同步信息，然后给 sonnet5 一份修复指南，我派他来修复

- **交接结果**：bookkeeper 由 `codex / GPT-5 Codex` 变更为 `claude / Claude Opus 5`，
  `status.json.bookkeeper` 已同步更新并附双重身份披露。

## 2. 实现者路由：从 Sonnet 5 改为 Claude-GLM（用户决定）

用户最初指定 **Claude Sonnet 5** 作为修复实现者。bookkeeper 在出 packet 前提示了一个**硬性路由后果**：

按 `AGENTS.md`「审查者不得是被审代码的实现者或修复作者 —— 硬禁、无披露豁免」+
`review_1_identity_granularity: provider`，若 Sonnet 5（provider `anthropic`）成为本次修复作者，
下一轮后端 Review-1 的可用池将**清零**：

| 候选 | 状态 |
| --- | --- |
| Anthropic（Opus 5 / Fable 5） | 与修复作者同 provider → **被禁** |
| Claude-GLM（`zhipu_glm`） | 被审后端代码本体的实现者 → **硬禁** |
| Kimi | 无额度（`15-kimi-review-1-unavailable.md`） |
| Codex | 无额度（本次交接的起因） |

→ 会停在 `decision_models_exhausted`，除非用户另出书面豁免。

**用户在获知该后果后选择：改派 Claude-GLM 修复（推荐项）。** 这保持后端 owner 不变
（GLM 已连续承担 5 轮后端），并使 Claude Opus 5 在下一轮继续具备 Review-1 资格，管线不中断。

## 3. 用户在授权前提出的两个技术问题（如实记录 + 回答要点）

这两问直接影响用户对本次授权范围的判断，故一并入档。

### 3.1「可视化卡片里的执行中/已暂停/已删除/已完成，怎么没跟后端同步？」

**回答：状态本身是同步的，P2-2 漏的不是这张表。**

- 前端筛选：`frontend/index.html:3300-3303` 的 `running / paused / deleted / done`；
- 后端：`domain.filter_status_for_list`（`domain.py:1101-1120`）四个全支持，另有仅在「全部」
  可见的 `stopped`（已终止）与 `exposure_alert`（敞口告警）。
- **二者一致，无缺口。**

P2-2 指的是后端**启动时一次性恢复交接**内部的一个状态元组
（`service.py:1219`：`for status in (PAUSED, STOPPED, DELETED)`），它决定"重启时去哪几种状态里
把还欠对账的卡捡回来继续查"，**漏了 `DONE`**。这不是给用户看的筛选，而是清点逻辑。

### 3.2「线程怎么接收界面点的暂停？为什么不放在下单校验之后再检查命令（FMZ 的 `GetCommand()` 模式）？」

**回答：用户描述的顺序正是当前实现，而且正是本轮 P1-2 修复的内容。**

- **命令通道**：无消息队列。前端点暂停 = `POST /api/hedge-open-tasks/<id>/pause`
  （`index.html:3396`/`3603`），后端只把该卡数据库 `status` 改成 `paused`；
  worker 线程每轮开头 `get_task`（`service.py:990`）读一次数据库即得知。
  等价于 `GetCommand()` 的轮询模型，载体是状态字段而非命令队列 —— 天然幂等，
  重复点击不重复消费，重启不丢命令。
- **顺序**：`_worker_round`（`service.py:975-1032`）= ①先 `_reconcile_own_legs` 对账 →
  ②还有非终态腿就继续查 → ③腿全终态且该组结算完，**才**检查 `status != RUNNING` 退出 →
  ④仍 running 才开下一组。即"下单 + 下单后处理"是不可被暂停打断的收尾单元。
- **修复前**是第一步就检查暂停信号直接 `return True` 退出（在对账之前）—— 这正是上一轮的 P1-2 缺陷。
- **诚实补充**：`stop_event` 仍在轮首检查，但现在**只有 `service.stop()`（进程关停）**会置位，
  界面暂停已不再触碰它。进程关停跳过 drain 是可接受的，**前提是重启那次交接能捡回来** ——
  而这正是 **P2-2 的缺口所在**。两个问题在此连接：P2-2 不是孤立的洞，是 stop 路径兜底机制的缺口。

## 4. 授权内容（如实记录）

- **时间**：2026-07-25（北京时间），在读完 `66-review-1-backend-r4.md`（verdict = `REWORK`）
  及上述两问的回答之后。
- **用户决定**：**「两个都修」** —— 即第 6 次有界变更同时覆盖 P2-1 与 P2-2。
- **授权含义**：
  1. `rework_count` 由 **5** 抬高上限至允许**第 6 次**代码变更，范围严格限定为本文件 §5。
  2. **P2-1 本就在既有 §4/§5 授权内**（把 R3/R4 修成合格回归）；
     **P2-2 是本次新授权的增量**（`service.py:1219` 补 `STATUS_DONE` + 一条同构回归）。
  3. 实现者路由：**Claude-GLM（`glm-5.2[1m]`，provider `zhipu_glm`）**（§2）。
  4. 投递方式：由**人类操作员**把 packet 贴进 GLM 终端执行。任何模型不得自行派发。
- **本授权明确**不**包含**：新产品功能、更大范围重构、smooth/WebSocket、凭据访问、
  真实 Binance 流量、启用 live、Start 动作、任何真实订单、前端源码改动、契约文档改动、
  自动补腿/撤单/平仓/还币/转账/完整会计。**实盘门未被本授权解除。**

## 5. 授权的修复范围（2 项必做）

固定锚点：base `28c550d87c1ca90983d5bde9c7102d42cffecd4e`，
head `9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c`，
指纹 `9d1bac071e30a57fe9c0619fb0c3cd59ccc4ce3c:fbf52f40fbebe7018bdf6e460d7f2e4855519c52e3a6403151db420aa13d99db`
（bookkeeper 会在 GLM 完成后重算）。

### 5.1 【P2-1，既有授权内】把 R3 / R4 从空回归修成真回归

- **根因**：`_pump_worker`（`service.py:942-964`）在**每次调用开头无条件 `ev.clear()`**；
  测试辅助 `_step()`（`test_hedge_task_local.py:57-63`）就是一次 `_pump_worker` 调用，
  而 R3/R4 的写法是 `_step(1) → post_pause()/post_delete() → _step(3)`，第二次 `_step`
  把 pause 可能置位的 stop event 又清掉了。
- **Review-1 双向实测**（猴补丁，未改仓库任何文件）：
  - 把删掉的 `_wake_worker` 语义放回 `post_pause` → 事件确实置位，R3 四条断言**全部照样通过**；
  - 重建修复前 seam 语义 → `stop_events registered at all : {}`，R3 **同样全绿**。
- **后果**：用户授权书 §10.1「八条回归在修复前可复现所述缺口」对 R3/R4 客观未达成；
  `44-fix-review-1-backend-r3.md` §3 的「已复现」为不成立陈述；905 个测试里**没有任何一条**
  在保护"人工暂停/删除不得丢弃在飞真实订单"这条最危险路径。
  且 §4.5 P3 建议原意是"让中断语义**可被同步测试观察**"，无条件 clear 使其**更不可观察**，方向做反。
- **修法**：(a) `_pump_worker` 不再吞 stop event —— 只在**首次注册**时创建并 clear，已存在则保持原状；
  或加仅测试用形参（如 `reset_stop_event: bool = False`）由用例显式传入。
  (b) R3 / R4 各加断言：`post_pause` / `post_delete` 后该卡 stop event **未被置位**。
  (c) 可选：R3 增加真实线程版本。**不得改动 `post_pause` / `post_delete` / `_worker_round`
  的生产语义 —— 已被 Review-1 用真实线程验证为正确。**

### 5.2 【P2-2，本次新授权】`_recover_workers` 兜底补 `STATUS_DONE`

- **根因**：`service.py:1219` 的只对账兜底集合本轮从 `(PAUSED, STOPPED)` 扩到
  `(PAUSED, STOPPED, DELETED)`，仍不含 `DONE`。而 `resolve_attempt(leg_terminal=...)`
  （`store.py:892-924`）在"两腿都拿到 orderId、但其中一腿仍 `NEW`/`PARTIALLY_FILLED`"时，
  会先把该组判 accepted 并把任务推到 `done`，同时按设计把该腿留在 `terminal=0`
  （`service._leg_terminal`，`service.py:1530-1538`）。
- **Review-1 离线实测**（`target_n=1`，perp FILLED，spot 受理但 NEW，零网络）：

  ```text
  after dispatch:
    task status = done / accepted_pair_count = 1
    leg spot order_id=s1 status=NEW terminal=0 cum_base=0
    non-terminal legs = 1
  -- process restart (new service instance, same sqlite file) --
    ensure_worker calls during recovery = []
    query_calls made                    = 0
    leg spot terminal=0 status=NEW cum_base=0
    non-terminal legs still = 1
  ```

- **后果**：该现货腿在币安其实已成交，本系统永久记 0。`aggregate_positions`
  （`store.py:1567-1576`）只累加 `exchange_status == FILLED` 的腿，于是一组**已经对冲好的**仓位
  在持仓面板上被**永久**显示成裸空头（`position_qty=-0.5`、`spot_avg=0`），且不会自愈。
- **性质**：base 提交就存在的既存缺口，**非本轮引入的回归**；但它落在本轮修改的同一行上，
  且是 stop 路径兜底机制的缺口（见 §3.2 末段）。
- **修法**：把 `D.STATUS_DONE` 加进 `service.py:1219` 的兜底元组（该 worker drain 完即因
  `status != RUNNING` 退出，绝不开新组，与刚加的 `DELETED` 完全同构），并加一条与 R5 同构的回归。

### 5.3 明确**不在**本次授权范围（记为 follow-up）

- **P3-1**：`settle_attempt_no_counters` 不落 attempt 级 `error_category`/`error_code`/
  `error_reason_zh`。仅可观测性，**无安全后果**（`classify_query_response` 只产出 `absent`，
  永不产出 `fatal`，故 429 组不会吞掉致命停机义务）。
- **P3-2**：人工 Start 撞上 worker 退出窗口可能静默空转（既存、极窄，已被新增的 `worker_active` 可见化）。
- **P3-3**：`post_start` 响应混用派发前任务行与派发后 `worker_active`（纯展示层）。
- **前端**：展示 `worker_active` / `last_worker_exit_reason` 并提示需人工恢复 —— 沿用 packet 65 已记的 follow-up。
- 跨进程预留守卫、`X-MBX-ORDER-COUNT-*` 主动节流：维持既有"已记录剩余风险"状态，不改。

## 6. 双重身份披露（bookkeeper = 本轮 Review-1 审查者）

- Claude Opus 5 同时是 `66-review-1-backend-r4.md` 的审查者与本 stage 当前 bookkeeper。
- **允许的理由**：`AGENTS.md` 对 bookkeeper 的约束是"只有 bookkeeper 可创建 packet、更新
  `status.json`/`70-handoff.md`、创建证据提交"，属机械簿记与路由；对"自审"的硬禁针对的是
  **审查者不得是被审代码的实现/修复作者**。Opus 5 未写任何被审业务代码。
- **本 bookkeeper 明确不做**：不把自己的 verdict 当作已验收、不代替新一轮 Review-1、
  不修改 `66-review-1-backend-r4.md` 的任何评审证据、不自行判定 stage 验收。
- **下一轮 Review-1 的资格**：由于修复作者是 `zhipu_glm`，Claude Opus 5 继续具备 provider 隔离资格
  （与 r3/r4 同一路由理由）。若届时用户改派 Anthropic 模型做修复，须先解决 §2 的池清零问题。

## 7. 精确自测命令（提交前全部跑绿，原始输出追加到 `60-test-output.txt`）

```bash
.venv/bin/python -m pytest \
  backend/tests/test_hedge_task_local.py \
  backend/tests/test_hedge_service.py \
  backend/tests/test_hedge_review2_regressions.py \
  backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_domain.py \
  backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_purity.py \
  backend/tests/test_hedge_open_live_client.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_executor.py -q
.venv/bin/python -m pytest backend/tests -q
node frontend/self-check.js
.venv/bin/python -m pytest scripts/tests/test_validate_stage_dispatch_protocol.py -q
git diff --check
```

基线参照（Review-1 r4 本机实测）：十组聚焦 = **229 passed**；`backend/tests` = **905 passed**；
前端自检全通过；Harness = **55 passed**；`git diff --check` exit 0。新增回归后总数应上升。

## 8. 验收条件（用于新一轮 Review-1）

1. R3 / R4 在 `_wake_worker` 中断语义被放回时**会失败**、在当前代码下全绿（实现报告须给出实测输出）。
2. done 卡带受理但非终态腿 → 重启一次 recovery → 该腿被查到终态、`dispatch_calls` 不增（零重发）、
   `status` 仍为 `done`。
3. `backend/tests` 全量、前端自检、Harness 协议套件全绿；`git diff --check` 干净。
4. `test_6a/6b/6c`（H-1 三防线）与 `test_1`–`test_5`、`test_4b`、R1–R8 仍全绿；
   **未新增任何全局守护/定时器/周期扫描器**。
5. `frontend/**` 零改动；`_ENTRY_EVENT_KINDS` 未新增 kind；`store.py`/`domain.py`/
   `backend/services/**` 本次**不得改动**。
6. 全程零真实 POST、零私有网络、零凭据访问、零 live 启用、零 Start。

## 9. bookkeeper 待办（自持清单）

1. ✅ 落盘本授权（本文件）+ `status.json` 授权记录与 `max_rework` 6。
2. ✅ 更新 `status.json.bookkeeper`（Codex → Opus 5）+ `dual_hat_disclosure`。
3. ✅ 登记 `66-review-1-backend-r4.md` 的 REWORK verdict 与 findings。
4. ✅ 生成 packet `67-fix-review-1-backend-r4.dispatch.md`，
   `target_model: claude_glm / glm-5.2[1m]`，`executor: human_operator`，
   PROMPT BODY 直接采用 Review-1 verdict 的 `fix_start_prompt`（不得摘要替换）。
5. ✅ 更新 `70-handoff.md` Recovery Header。
6. ✅ 创建证据提交；派发前跑 `--phase dispatch-ready`，GLM 完成后跑 `--phase pre-review`。
7. GLM 完成后：R4 差异核对、创建证据提交、**重算指纹**、准备**新一轮后端 Review-1**
   （provider 需与 `zhipu_glm` 隔离）。
8. 前端 Review-1 的 ACCEPT 保留：本轮区间 `frontend/**` 零改动。
9. **实盘门**：本授权**不**解除任何实盘门。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native Session ID)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-open-real-api-v1/27-user-authorized-r4-repair.md
本地北京时间: 2026-07-25 CST
下一步模型: claude_glm / glm-5.2[1m]
下一步任务: execute packet 67 in a fresh write-capable Claude-GLM session (human operator delivers it)
