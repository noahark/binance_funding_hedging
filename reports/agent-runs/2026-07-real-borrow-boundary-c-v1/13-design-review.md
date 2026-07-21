# Independent Design Review — Real Borrow Boundary C

Stage: `2026-07-real-borrow-boundary-c-v1`
Prompt: `reports/agent-runs/2026-07-real-borrow-boundary-c-v1/design-review.prompt.md`
Mode: **read-only design review**. 无实现、无 dispatch、无凭据读取、无任何 Binance 请求。
这不是正式 review-1 或 review-2（此时尚无实现）。

## Reviewer

- Provider / model: **Anthropic / Claude Opus 4.8**（`claude-opus-4-8`）
- Role: independent design reviewer（human-operator 指定）
- Independent from designer/bookkeeper（Codex/GPT）: `true`
- Independent from proposed implementer（`claude_glm` / zhipu_glm）: `true`
- Prior involvement in this stage: `none`

## Read Set Actually Consulted

本会话内真实读取：

- `AGENTS.md`（reviewers / dispatch 章节）
- `workflows/templates/stage-delivery.yaml`（review 与 breakdown 相关段）
- `docs/parallel-development-mode.md`（v0.5 R11-R12 / 适用条件 / 角色表）
- 本 stage：`00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.draft.md`
- `reports/agent-runs/2026-07-real-borrow-execution-v1/03-grok-borrow-api-capacity-recon.md`
- 现行源码：`backend/borrow_tasks/{domain,executor,scheduler,service,store}.py`、
  `backend/services/private_client.py`、`backend/config.py`、
  `backend/app/server.py`（borrow 路由段）、
  `backend/tests/test_private_client.py`、`backend/tests/test_borrow_executor.py`、
  `frontend/index.html`（借币文案段）

`06-direction-synthesis.md` 的结论经由 `00-intake.md` 与 recon 的引用进入本评审；
未递归读取其他 stage 或任何 `history/` 目录。

---

## 1. Verdict: REWORK

## 2. Blocking findings

### P0-1 — 无单实例保障，多进程可对同一任务并发发出真实借币 POST

`10-design.md` D4 / ADR-005 的不变量写的是「**每进程**至多一个 POST 在飞行」，而串行性
完全由 `backend/borrow_tasks/service.py:117` 的进程内 `threading.Lock` 提供。但 DB 路径是
固定默认值（`backend/config.py:23`），`scripts/run-server.sh` 被跑两次（本地操作者极常见：
换终端、忘了旧进程、launchd + 手动各一份）即产生两个各自持有调度线程的进程，共享同一
SQLite。

后果不是「节奏变快」，而是**同一任务在同一时刻被两个进程各插入一条 pending 并各发一次
POST**——真实双倍债务，且两条 pending 互相看不见（见 P2-9）。设计文档、ADR、acceptance
criteria、Required Test Scenarios 里都没有任何一条覆盖这个场景。

这是本设计唯一的 P0：它绕过了「绝不重复 POST」这条硬性正确性要求，而且不需要任何异常
网络条件。

### P0-2 — `deleted` 会被成功结果覆写为 `completed`（现行代码已存在，C 阶段变为真实缺陷）

`backend/borrow_tasks/store.py:431-437`：

```python
new_status = task["status"]
if category == D.RESULT_SUCCESS:
    new_count = task["success_count"] + 1
    if new_count >= task["success_target"]:
        new_status = D.STATUS_COMPLETED
```

飞行中操作者点删除 → 事务里读到 `status='deleted'` → 若这次成功刚好达标，`new_status`
被改写为 `completed`，任务从「已删除」复活成「已完成」。这直接违反 `11-adr.md`
Edge Cases 第 2 条与 `00-task.md` 验收标准 10（"a deleted task stays deleted"）。A+B 下
它是潜伏的（disabled 执行器永不返回 success），C 一旦接通就是可触发的。

设计只声明了要求，没有指出**这段现存代码必须改**。必须在 breakdown 里点名该行，并冻结
规则：`deleted` 为终态，任何 resolve 路径不得改写它（success_count 仍可累加，作为审计
事实）。

### P1-3 — `tick()` 的追赶累加会在冷却/阻塞结束后**突发连打**真实 POST

`backend/borrow_tasks/service.py:266-275`：

```python
if now < self._last_tick_mono + interval:
    return False
self._last_tick_mono = self._last_tick_mono + interval   # 只推进一个 interval
return self._dispatch_one(...)
```

`_last_tick_mono` 每次只前进一个 interval，而 `scheduler.py:70` 的轮询片最快 5ms、最慢
250ms。于是任何「应发未发」的时间（429 全局冷却、任务被 unknown 阻塞、慢请求、无
eligible 任务）都会累积成 backlog，恢复后以**轮询片频率**而非 interval 频率补发。

具体：interval=5s、一次 60s 冷却结束后，`_last_tick_mono` 落后 60s，此后每 0.25s 补一次
→ **3 秒内连发 12 笔真实借币**。`10-design.md` D4 声称「慢请求只会让实际节奏比配置更慢」，
与代码事实相反。这同时打穿 recon 给出的配额包络（POST weight 100 × 12 笔 ≈ 1200 IP
weight / 3s）并直接放大债务。

修法只需一行语义变更：跳过或慢于 interval 时把 `_last_tick_mono` 重置为 `now`（不补偿），
并冻结「永不补发历史 tick」为不变量 + 回归测试。

### P1-4 — 全局 interval 无下限，是**契约阻断**而非风险偏好

`backend/borrow_tasks/domain.py:125-147` 明确写着 "There is no upper bound or product
minimum"，`PUT /api/borrow-scheduler-settings` 可设 `"0.1"`。C 接通后 0.1s =
600 POST/min × weight 100 = 60000 weight/min，是 recon Class A 文档化的 PM IP 预算
6000/min 的 **10 倍**——结构性不可服务，必然 429/418 封禁。

按 prompt 的要求区分：这**不是**用户已否决的那类「应用层 USDT 上限 / 资产白名单 /
maxBorrowable 预检」。用户冻结的风控维度是 `principal / amount_per_attempt /
success_target`，**请求速率不在其中**，而速率上限由交易所文档化的配额直接决定。因此
建议加一条最小间隔硬下限（建议 `1` 秒，默认仍保持 `5`），理由是配额算术，不是风险口味。

若用户仍要拒绝下限，则必须在 ADR 里显式记录「操作者可自行触发 IP 封禁」，并让 UI 在
interval < 1s 时给出明确警示——本评审不推荐这条路。

### P1-5 — `known_rejection` 缺少**已验证的业务码白名单**，默认方向反了

`00-task.md` 验收 5 与 `10-design.md` D5 写的是 "explicit exchange/business rejection
proving no loan → `known_rejection`（任务留在轮转中，可再次 POST）"。但仓库里**不存在**
任何一份「哪些 code 证明未产生贷款」的已验证清单，recon §7.6 明确把「retryable vs
terminal 业务码集合」列为未解未知。

按现在的写法，实现者最自然的做法是「HTTP 4xx + 有 `code` 字段 → known_rejection」，而这会
把语义不明的 4xx（例如风控/账户状态类，或未来新增码）判成「确定没借到」，于是任务继续
POST——这正是重复债务路径。

必须反转为 deny-by-default：**只有落在冻结的、有官方证据支撑的码集合内**才判
`known_rejection`（起步集合建议仅 `51061` 一类池空/额度不足，且需本阶段证据归档确认其
PM 借币语义）；集合外的一切 4xx 一律 `unknown` → 阻塞 → 对账。

### P1-6 — 三个既有安全 grep 测试会硬失败，设计未规定「必须收紧而非放宽」

签名提取与新写客户端会直接撞上：

- `backend/tests/test_private_client.py:77-87`：`hmac`/`hashlib`/`signature =` 只允许出现在
  `private_client.py` → 新增 `binance_signing.py` **必失败**。
- `backend/tests/test_private_client.py:90-102`：`urlopen` 只允许出现在
  `private_client.py` 与 `binance_public.py` → 新 PM 写客户端 **必失败**。
- `backend/tests/test_borrow_executor.py:86-102`：`backend/borrow_tasks/**` 禁止 import
  `urllib/http/socket/hmac/hashlib/ssl` → 决定了 `LiveBorrowExecutor` 可以放在
  `borrow_tasks/`，但传输层**必须**在 `backend/services/`。

`10-design.md` 只说 "existing regression tests still enforcing GET-only exact
allowlisting"，没有点名这三处。这恰恰是实现者会用「把断言放宽 / 加通配」来图省事的位置，
也正是评审要点里「signer extraction 是否削弱 GET-only」的实际落点。必须在 breakdown
冻结：三个测试只允许**逐文件精确扩白名单**（新增恰好 1 个签名模块名 + 恰好 1 个写客户端
模块名），不得改为前缀 / 通配 / 目录级豁免，且扩白名单后必须补一条「该模块不得出现在
`WHITELIST` 之外的 path」的对偶断言。

### P1-7 — File Boundaries 缺少新写客户端及其测试的路径

`00-task.md` 的 Allowed 列表只有 `backend/services/binance_signing.py` 与
`backend/services/private_client.py`，但 D3 要求的 `PortfolioMarginBorrowClient`
**没有任何被允许的落点**；同样 `backend/tests/test_binance_signing.py` 与假传输 fixture
（对应现有 `backend/tests/borrow_paper_executor.py` 的角色）也不在允许集内（只允许
`test_borrow_*.py` / `test_private_client.py` / `test_config.py`）。实现者要么越界，要么把
写客户端硬塞进 `private_client.py`——后者正好破坏 ADR-003 的隔离目标。

### P2-8 — Global Stop 与 pending 插入非原子

`service.py:278-295` 先读 settings、再 `insert_pending_attempt`，两次独立事务；HTTP 侧的
stop 处理器不持有 `service._lock`。存在「操作者已收到 stop 200、随后仍发出一笔 POST」的
窗口。验收 9 的措辞（"immediately after the current in-flight call returns"）需要这个
原子性才成立。建议把开关判定下推进 `insert_pending_attempt` 的同一事务（条件插入，未通过
返回 `None`），而不是在服务层先读后写。

### P2-9 — 飞行期间任务仍是 eligible（纵深防御缺口）

`store.py:326-375` 插入 pending 时**不**设置 `unresolved_attempt_id`，而
`store.py:225-234` 的 eligibility 依赖该字段为 NULL。即飞行窗口内任务在 DB 层面仍可被
选中，唯一阻挡是进程内锁——这正是 P0-1 能得逞的原因。建议插入 pending 时即置
`unresolved_attempt_id = attempt_id`，resolve 时按结果清除（`unknown` 保留）。这与
`store.py:165-171` 的重启孤儿恢复语义天然一致，改动很小，但把「绝不并发 POST」从
「靠一把内存锁」降级为「DB 层不变量」。

### P2-10 — `tranId` 的类型规范化未定义

DB 列是 TEXT，而 Binance 的 `tranId` 通常是 JSON 整数（大整数）。设计只说 "valid
non-empty tranId"。若成功路径存 `str(int)`、对账路径从 `txId` 回来的值格式不同（或经过
float 中转），匹配会静默失效并把已成功的尝试判成无法对账。必须冻结：单一规范化函数、
拒绝 float 路径、成功写入与对账查询使用同一表示，并有针对大整数的用例。

### P2-11 — 对账匹配规则强度不足

两处必须收紧：

- **金额比较必须用 `Decimal`**，不得字符串相等（`"1.25"` vs 交易所回显 `"1.25000000"`）。
- **跨任务碰撞必须判 blocked**：D6 的「响应缺失时按 asset+amount+时间窗唯一匹配」在两个
  任务同资产同金额时会互相窃取对方的贷款记录。规则应为：窗口内候选记录唯一 **且** 该
  窗口内本进程不存在第二个可能产生该记录的未解尝试，否则一律保持 blocked。

### P2-12 — 签名字节与实际发送字节必须同源

POST 的参数放 query 还是 body 尚未由证据确定（见 §7）。经典缺陷是「签名了排序后的串、
发送了另一个串」。必须冻结：一个序列化函数产出**一个** payload 字符串，签名与发送共用它；
并为新客户端补一条与 `test_private_client.py:164` 对等的 **gate-fires-before-signing**
测试——现有那条只覆盖 `PrivateClient`，新客户端不继承它。

## 3. Non-blocking findings

- **P3-a**：`disabled` 模式下调度器仍会为每个 eligible 任务每 tick 写一条
  `execution_disabled` 尝试行（`executor.py:48-52`）。interval=5s 时约 17k 行/天，会把
  操作者用来监督真实借币的日志淹掉。C 阶段建议：`can_execute=false` 时不插入尝试行，
  只在 execution-status 里反映原因。
- **P3-b**：`scheduler.py:32-35`，当游标任务变为不可选时 `cursor_seq` 为 `None`，轮转回到
  列表首位，多任务下分配略不公平。不影响正确性。
- **P3-c**：启动恢复应把「本次启动恢复了 N 个 live-authorized borrowing 任务、M 个被孤儿
  pending 阻塞」打进生命周期日志并进入 execution-status，这是恢复决策（开放项 5）能被人
  监督的最低成本前提。
- **P3-d**：前端 `frontend/index.html:942 / 953 / 2482` 三处「本阶段不发起真实借币（执行
  未启用）」文案必须全部替换为按后端状态派生的动态文案——尤其 2482 是逐任务渲染的，最
  容易漏。

## 4. Open-item decisions

**开放项 1 — 执行控制路由与 schema：确认路由名，但冻结幂等语义。**
保留 `GET /api/borrow-execution-status`、`POST /api/borrow-execution/start`、
`POST /api/borrow-execution/stop`。不要改成带 `version` 的 PUT（与
`/api/borrow-scheduler-settings` 对齐的诱惑）：**stop 绝不能因为乐观并发冲突而失败**，
安全动作必须无条件幂等。start/stop 均不接受 body，重复调用返回 200 + 当前状态。status
body 采用 D2 提案原样，补一个字段：`live_authorized_task_count`（int），供 P3-c 的监督
使用。schema 落 `schemas/api/borrow-tasks/execution-status.schema.json`，
`schema_version = "borrow-execution/v1"`，`additionalProperties: false`。

**开放项 2 — 凭据命名与缺凭据时的启动行为：命名照用；启动时「报告 blocked」，不 hard-fail。**
`BINANCE_BORROW_API_KEY` / `BINANCE_BORROW_API_SECRET` / `APP_BORROW_EXECUTOR=disabled|live`
保持。分两种失败：

- **模式值非法**（既非 `disabled` 也非 `live`）→ 启动即 `ValueError`，沿用
  `backend/config.py:182-186` 的既有行为。
- **`live` 但缺凭据** → **正常启动**，`mode="live"`、`can_execute=false`、
  `block_reason="borrow_credentials_missing"`，绝不发请求。

理由：hard-fail 会让一个借币凭据拼写错误击垮整个快照服务（公开行情面板一起挂掉），而仓库
既有约定就是「缺凭据 → `enabled=False` + `last_error` 降级」（`private_client.py:113`）。
降级同样 fail-closed，但不制造停机。

**开放项 3 — Retry-After 缺失/非法的兜底冷却：冻结 60 秒，并对合法值做区间钳制。**

- 429：冷却 = `clamp(Retry-After, 60s, 300s)`；缺失/非法 → 60s。
- 60s 的依据是配额算术而非口味：PM 的 IP 预算是**每分钟**窗口，等满一整分钟保证计数窗口
  翻篇。
- 上限 300s 防止畸形超大值把任务静默冻死数小时。
- 418 的语义（Binance 侧通常是时长可变的 IP 封禁）在本仓无已验证证据 → 归入 §7；在证据
  落地前，418 一律按 300s 冷却 **且** 在 execution-status 暴露为显式 blocked 原因，要求
  人工确认，不自动恢复。

**开放项 4 — 对账读取时序：冻结 4 次有界退避 `+5s / +30s / +120s / +600s`，耗尽即永久 blocked。**

- 成本可忽略：loan-record weight 10 × 4 = 40，相对 6000/min 无关紧要。
- 不设更快的首读：recon §7.1 明确「成功后到 `tranId` 可查询的传播延迟」完全未知，早读只会
  把传播延迟误判为「无记录」。
- 全程任务保持 ineligible，无论对账成败。
- 耗尽后**不**新增任何「强行重试」动作（与 D6 一致）；操作者唯一可用出口是删除任务。

**开放项 5 — 普通重启：维持 draft 的「恢复」，不做全体 re-arm。**
理由：两道门（进程模式 + 持久开关）加孤儿 pending 阻塞已经 fail-closed；每次重启强制
re-arm 会让操作者对「重新武装」这个动作产生条件反射式点击，反而稀释了它本该承载的授权
含义（这正是 pre-C quarantine 想保护的东西）。代价用 P3-c 的恢复日志 + status 计数抵消：
重启后必须能一眼看到「有几个任务正在活着」。

注意这与 ADR-006 的 pre-C quarantine 并不冲突——那是**一次性迁移**授权，这是**常态重启**
语义，两者应在 ADR 里明确写成两条不同的规则。

## 5. Required amendments

| 文件 / 章节 | 修改意图 |
| --- | --- |
| `11-adr.md` 新增 **ADR-008 单实例执行权** | 冻结：调度线程启动前必须取得基于 DB 路径的排他进程锁（`fcntl.flock` 咨询锁或 DB 内带 boot-token 的 owner 行）；取不到锁的进程正常提供只读 API 但**不启动调度器**，并在 execution-status 报 `block_reason="not_execution_owner"`。（P0-1） |
| `10-design.md` D8 + `00-task.md` 验收 10 | 点名 `backend/borrow_tasks/store.py:431-437`，冻结「`deleted` 为终态，任何 resolve 分支不得改写」，并要求一条针对性回归用例。（P0-2） |
| `10-design.md` D4 | 删除「慢请求只让节奏变慢」的表述，改为冻结不变量「**永不补发历史 tick**」：`service.py:272-275` 落后时把 `_last_tick_mono` 重置为 `now`。补测试：60s 冷却后 3 秒内派发次数 ≤ 1。（P1-3） |
| `10-design.md` D1 / `11-adr.md` ADR-002 | 增加最小 interval 硬下限（建议 1s，默认仍 5s），落在 `backend/borrow_tasks/domain.py:parse_interval_seconds`；ADR-002 明确写这是配额契约约束，不是被否决的那类应用层风控上限。（P1-4） |
| `10-design.md` D5 表格 + `00-task.md` 验收 5 | 把 `known_rejection` 改为**证据白名单**判定：仅冻结集合内的业务码归此类，其余 4xx 一律 `unknown`。白名单初始内容由本阶段证据归档确定。（P1-5） |
| `12-development-breakdown.md`（正式版）新增「安全测试收紧规则」 | 点名三处 grep 测试（`test_private_client.py:77/90`、`test_borrow_executor.py:86`），冻结「仅允许逐文件精确扩白名单，禁止通配/目录豁免」，并要求扩白名单同时补对偶断言。（P1-6） |
| `00-task.md` File Boundaries | 补入 `backend/services/pm_borrow_client.py`（或等价确定文件名）、`backend/tests/test_binance_signing.py`、`backend/tests/test_pm_borrow_client.py`、假传输 fixture 文件路径。（P1-7） |
| `10-design.md` D2 | 全局开关判定下推进 `insert_pending_attempt` 的同一事务（条件插入 → `None` 即中止本轮）。（P2-8） |
| `10-design.md` D6 / D4 | 插入 pending 时即置 `unresolved_attempt_id`，resolve 时按类别清除或保留。（P2-9） |
| `10-design.md` D5 / D6 | 冻结 `tranId` 单一规范化表示（大整数安全、无 float 路径）；对账金额比较用 `Decimal`；跨任务同 asset+amount 候选碰撞判 blocked。（P2-10 / P2-11） |
| `10-design.md` D3 | 冻结「签名 payload 与发送 payload 由同一序列化函数产出」，并要求新客户端自带 gate-before-signing 负例测试。（P2-12） |
| `11-adr.md` ADR-006 | 拆成两条独立规则：一次性 pre-C quarantine（需显式 Start）vs 常态重启恢复（保持运行 + 恢复计数上报）。（开放项 5） |

## 6. Lean implementation assessment

**单任务、串行、embedded review 关闭的路线是恰当的**，不建议改成并行。理由三条：
`docs/parallel-development-mode.md` §1 的启用条件要求 ≥2 个互不相交的实现任务，而本阶段
前端改动是薄集成（三处文案 + 一个徽章 + 一个开关），拆出去会制造接口冻结成本却省不下
墙钟时间；本阶段的风险集中在后端单一路径上，跨端协调只会稀释注意力；
review-1(Kimi) / review-2(Codex 带设计披露) 的拓扑与 `AGENTS.md:213-229` 一致，无需变更。

**但建议把「契约证据归档」从实现任务的第 1 步提升为独立前置门。** 它不是实现步骤，而是
D5 的业务码白名单、D6 的对账参数、开放项 3/4 冻结值的**输入**；混在同一个任务里意味着
实现者会一边写代码一边定义自己代码的验收标准。归档完成后应触发一次轻量的设计增量确认
（不是完整 review），再放实现。

**没有发现为达成用户后端直连目标而言属于多余的组件。** 逐个检查过：共享签名原语
（ADR-003）是必需的，否则加密出口从 1 个变 2 个并直接打穿现有 grep 证明；持久全局开关是
必需的，因为 `APP_BORROW_EXECUTOR` 改一次要重启进程，而急停不能依赖重启；
execution-status 的 `in_flight_attempt_id` 可从 pending 行直接查得，成本近零。唯一本评审
新增的组件是单实例锁（P0-1），它是正确性必需，不是风控偏好。

## 7. Evidence gaps

以下事实必须在写代码前落到 `reports/api-samples/2026-07-real-borrow-boundary-c-v1/`
（公开文档归档，不含任何认证样本）：

1. `POST /papi/v1/marginLoan` 的**确切参数集、security type、请求权重**。recon 给出
   weight 100 / `asset` + `amount`，但那是另一模型的阅读结论，本仓无归档页面。
2. **参数放 query 还是 body**，以及签名覆盖的确切字节范围。直接决定 P2-12 的实现形状。
3. `tranId` 的**类型与量级**（JSON integer 还是 string），决定 P2-10 的规范化。
4. `GET /papi/v1/margin/marginLoan` 的**必填/可选参数**（`asset` 是否必填、`txId` 参数名、
   `startTime/endTime`、分页字段）、**可查询历史深度**、响应记录字段（尤其金额字段名与
   小数格式、状态字段）。D6 的窗口匹配完全建立在这些之上。
5. **成功后到记录可查询的传播延迟**（recon §7.1 明列为未知）。若官方无说明，则须在归档里
   显式记为「无官方 SLA」，开放项 4 的退避序列按此保守值成立。
6. **能证明「未产生贷款」的业务码集合**（P1-5 白名单的唯一合法来源）。若官方文档不足以
   支撑任何一个码，则白名单初始为**空**，一切 4xx 归 `unknown`。
7. **418 的语义与时长**（是否为 IP ban、是否携带 Retry-After），决定开放项 3 的 418 分支。
8. `marginLoan` 是否计入 **order 1200/min** 限额（recon §7.2 未解）。
9. `X-MBX-USED-WEIGHT-*` 响应头在 PM 写路径上的**确切命名**，D10 要求持久化该数值计数器。

以上任何一项与 `10-design.md` 的现有假设冲突时，按 `12-development-breakdown.draft.md`
Dependencies 第 4 条，必须先修订设计并重新确认，再进入实现。

---

## Execution Record

本次为只读设计评审。本会话内：未编辑任何产品代码或 stage 文件（本报告除外，由 human
operator 明确指示落档）、未调用或转派任何其他模型会话 / adapter 命令、未读取 `.env` 或
任何凭据文件、未发出任何认证请求或 Binance POST。所有 file:line 引用均对应本会话内真实
读取的文件内容。

当前 Session ID: unavailable (runtime does not expose provider-native Session ID)
Session ID 来源: unavailable
评审模型: Anthropic / Claude Opus 4.8 (`claude-opus-4-8`)
原始输出路径: reports/agent-runs/2026-07-real-borrow-boundary-c-v1/13-design-review.md
本地北京时间: 2026-07-20 21:16:41 CST
下一步模型: bookkeeper (Codex/GPT) → 注册 breakdown 作者
下一步任务: 按 §5 修订 `00-task.md` / `10-design.md` / `11-adr.md`，先行完成 §7 契约证据
归档，再产出正式 `12-development-breakdown.md`
