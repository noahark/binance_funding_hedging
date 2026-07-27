# ADR — Hedge Open Live Hardening v1

本文件只记录本 stage 新增/修订的架构决策。上一 stage 的 ADR-1…ADR-5
（`reports/agent-runs/2026-07-hedge-open-real-api-v1/11-adr.md`）全部继续有效，
不复制。与既有 ADR 的关系在每条内显式声明。

## ADR-H1: clientOrderId 推导改为 `hg{attempt_id}{s|p}`（35 字符）

**Context**：`hgo-{attempt_id}-s` = 38 字符 > 币安 `newClientOrderId` 上限 36，
首笔真实单双腿 `-4015` 被拒（P0，无任何真实订单可成功）。约束：≤36、双腿互异、
全局唯一、且必须继续支撑 ADR-2 的「仅凭 clientOrderId 对账」路径。

**Decision**：`executor._client_order_ids` 改为返回
`f"hg{attempt_id}s"` / `f"hg{attempt_id}p"`（2+32+1=35）。推导点保持唯一
（record 与 live 执行器共享同一函数）。不迁移历史 38 字符记录。

**被否决的备选**：

1. `f"{attempt_id}s"`（33，handoff 草案）——满足全部硬约束，但丢掉可识别前缀；
   在币安订单历史里无法一眼区分本系统订单与其他来源订单，审计成本上升。前缀
   只花 2 字符，仍留 1 字符余量，收益大于成本。
2. 保留 `hgo-` 并截短 uuid（如取前 30 hex）——破坏「attempt_id 即 uuid4 全量」
   的全局唯一性论证，引入截断碰撞分析负担，收益为零。
3. base64/urlsafe 压缩 uuid——字符集边界贴近币安 regex 的允许集边缘（`-`/`_`
   虽允许，但引入大小写混合与额外编解码），复杂度不成比例。
4. 交易所自动生成 id（不传 `newClientOrderId`）——直接摧毁 ADR-2 的
   client-ID-only 对账与崩溃恢复路径，不可接受。

**Consequences**：与 ADR-2 完全兼容——对账/恢复只读持久化 leg 行，从不重新推
导，因此新旧格式在 DB 并存无影响；`client_order_id` UNIQUE 约束无冲突。测试中
约 18 处 `hgo-` 字面量需逐个核对（断言推导格式的必须更新，作为任意实参的不
必）。S5 校验器与新增长度测试从此把该类缺陷钉死在离线。

## ADR-H2: Start 闸门写入契约 —— confirm 字面量 + version CAS + 同事务审计

**Context**：`/api/hedge-open-settings` 只有 GET，`service.set_start_gate()` 无
生产调用方，上次开闸靠直改 SQL。用户已决定形态：对称确认弹窗，开/关同一控件、
各恰好一次确认、无手输确认词。settings 行已有 `version` 列。全新安装必须默认
关闭。

**Decision**：新增 `POST /api/hedge-open-settings/start-gate`，请求体
`{"enabled": <bool>, "confirm": true, "version": <int>}`：

- `confirm` 必须为字面 `true`，否则 400 `confirmation_required`——确认语义在后
  端也有形，裸 POST 无法误开闸；
- 并发语义为 **compare-and-swap**：`UPDATE … WHERE id=1 AND version=?`，未命中
  → 409 `version_conflict` 并返回当前 settings doc；命中 → `version+1`；
- 审计行（`hedge_open_log`，`task_id="start-gate"`，`kind="start_gate_changed"`，
  payload 含 enabled/previous_enabled/version/source）与闸门 UPDATE 落在**同一
  store 事务**，闸门变更与其审计记录原子共存亡；
- `GET /api/hedge-open-settings` additive 增加 `version` 字段（CAS 的前端输入）；
- schema 默认 `start_gate=0` 不动；既有无条件 Python seam `set_start_gate`
  保留给测试，additive 不改签名。

**被否决的备选**：

1. 镜像 borrow 的 `POST /api/borrow-execution/start|stop`（无 body、幂等、无确
   认、无 CAS）——不满足本 stage 的显式确认与并发安全要求；对冲开闸的风险等级
   高于 borrow 执行开关（直接授权真实市价单）。
2. `PUT /api/hedge-open-settings` 整体写——settings 还含 interval 等字段，会把
   闸门写入和无关设置写入耦合进同一面，扩大误写面。
3. 手输确认词——用户显式否决。
4. 闸门事件进冻结 entries 投影——`overall_result`/`next_action` 词表是冻结契约
   （16-breakdown §5），塞入即契约修订；改走 legacy `logs` 数组（全量投影自动
   携带），审计可达且零契约变更。

**Consequences**：直改 SQL 不再是操作程序；双会话竞态由 CAS 收敛为后写者 409
刷新重试；审计保真度上限为 `source:"api"`+时间戳（单操作者应用无身份体系，
已声明）。与 ADR-4 的关系：三道实盘授权彼此独立的结构不变，本决策只是把其中
「durable Start」从 SQL 操作升级为应用内受控操作，不改变任何授权语义。

## ADR-H3: S2 定性 —— 前端按钮条件缺陷，不是后端状态语义问题

**Context**：live 下新建卡 status=`running`，`startDisabled` 只放行
`paused`/`exposure_alert`，而 live 的 `create_task` 不起 worker、`tick()` 是有意
no-op（H-1），只有 `post_start` 能起 worker → 死锁。需要一锤定音：改前端条件，
还是给新建卡引入一个区别于 running 的初始态。

**Decision**：**前端条件缺陷**。`running` 是冻结状态词表中「已武装、允许调度」
的持久语义（dry-run 的 tick 正按它自动派发；live 下它是 worker 的准入条件之
一）。缺失的是「worker 当前是否在跑」这个运行时事实，而后端已以 additive
tri-state 字段 `worker_active` 暴露之。修复为：Start 在
`paused` / `exposure_alert` / （`running` 且 `worker_active === false`）时可
点。后端零改动（`post_start` 对 running 卡已幂等正确：置 running +
`ensure_worker`）。

**被否决的备选**：新增初始状态（如 `created`/`idle`）——(1) 修订冻结的 status
词表（I-4 只额外冻结了 `stopped`），触发契约修订流程；(2) 把运行时事实固化成
持久状态，制造「状态说没跑、线程其实在跑」的第二真相源；(3) 波及
store/筛选器/前端标签/大量测试，收益仅等价于一行按钮条件。

**Consequences**：dry-run 行为逐字不变（dry-run 下 `worker_active===null`，新分
支恒假）；H-1 的 tick no-op 与 create 不起 worker 保持原样；live 下启动 worker
仍然只能由人工点击触发，无自动派单。已知携带限制：`post_start` 无 exhaustion
检查的既有 open P2 略更易触达（display-only，需新授权才能修，本 stage 不动）。

## ADR-H4: S5 约束校验落点 —— 独立纯校验器，live 发送路径不挂

**Context**：fake/record transport 不校验长度、字符集、精度；
`reports/api-samples/` 从未记录 36 上限——S1 因此熬过九轮评审。需要决定约束加
在哪一层：transport 内部还是独立校验器；以及 live 路径是否同样拦截。

**Decision**：新建独立纯模块 `backend/hedge_open_tasks/wire_constraints.py`
（长度/字符集/定点格式/网格/上下界），三个消费点：
(1) `RecordTransportExecutor.execute`——违规即产出两腿 REJECTED 的 outcome
（dry-run 运行时不再「演成功」）；(2) 测试严格假件（`_FakeClient` 对收到的
params 过同一校验器，违规回 `-4015` 风格 400）；(3) 直接单元测试。
**live 发送路径（`live_hedge_executor.py` / `hedge_open_live_client.py`）刻意
不挂**。同时在 `reports/api-samples/<本stage>/client-order-id-cap.md` 落档实测
-4015 证据 + 文档 regex + 未验证边界。

**被否决的备选**：

1. 校验塞进各 transport 内部——record transport、`_FakeClient`、未来的假件各写
   一份规则必然漂移；独立纯模块保证「离线世界只有一份交易所规则」。
2. live 客户端 pre-send 拦截——在真钱路径上引入第二个裁决权威：本地规则一旦与
   币安实际规则出现偏差（regex 版本漂移、新参数），会把**合法**订单拦在本地，
   且拦截结果还需要在错误矩阵里发明新分类（fatal? absent?）。离线门已保证该缺
   陷类在合并前失败；live 侧维持「币安是唯一参数裁决者」的已评审语义。若未来
   想要防御纵深，作为独立 follow-up 需新的用户决策。
3. 只在测试里校验、不动 record transport——dry-run 运行时会继续对违规参数演出
   成交，操作者在 dry-run 演练时得到假信心，违背 S5 的目的。

**Consequences**：格式类缺陷的失败点从「真实发送」前移到「任何一次离线测试/
dry-run 派发」；pre-fix S1 推导的回归测试（monkeypatch 旧推导 → 断言离线
REJECTED）成为可能并被要求；live 行为与已评审版本逐字节一致。附带发现一个
未验证点：`build_*_order_params` 用 `str(quantity)`，理论上极小数会出科学计数
法，校验器会将其判违规——实现时必须以测试证实或证伪（10-design §8）。

## ADR-H5: 建卡双腿存在性 —— 只在「读取成功」时才有权拒绝

**Context**：KORUUSDT 只有合约无现货（`-1121`），preflight 正确 fail-closed，但
建卡无警告，卡片空转。现有 provider 把「读失败」与「symbol 不存在」折叠为同一
个 `None`，无法指明缺哪条腿。

**Decision**：provider 新增三态探针 `check_symbol_legs`（True/False/None，
None=读取失败不可判定）。`create_task` 仅在探针**确定性 False** 时以 400
`missing_leg` 拒绝并用中文指明缺失的腿；None（读取失败）**不拦截**，维持现状
放行。dry-run provider 无探针，行为与网络面零变化。

**被否决的备选**：读取失败也 fail-closed 拒绝建卡——把公共行情接口的瞬时故障升
级为建卡故障；建卡本身不是实盘风险动作（真正的风险闸在 preflight fail-closed，
该机制已被实测证明有效），代价/收益不成立。

**Consequences**：确定性缺腿（KORUUSDT 类）在建卡即被拒，不再产生空转卡；探针
读取失败时空转卡仍可能出现（与今天相同），由 S4a 的 worker 状态展示提供可见
性。仅存在性校验；1000x 前缀归一化仍是已记录的独立 follow-up。

当前 Session ID: 9c443dac-2917-4801-bd93-94db85d27de0
Session ID 来源: runtime_env (harness scratchpad path; navigation only)
原始输出路径: reports/agent-runs/2026-07-hedge-open-live-hardening-v1/11-adr.md
本地北京时间: 2026-07-27 17:59:40 CST
下一步模型: bookkeeper
下一步任务: 归档三份原始设计产物，不要实现代码
