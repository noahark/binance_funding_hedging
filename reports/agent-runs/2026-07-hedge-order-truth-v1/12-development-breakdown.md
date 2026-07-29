# Development Breakdown — Hedge Order Truth And Error Fidelity v1

## 1. 串行 / 并行结论：**串行，单 owner**

维持 intake 判断（`status.json.parallel_mode`）：单 owner 串行，owner =
`claude_glm`（`glm-5.2[1m]`），单任务 `backend`。

理由：T1/T2/T3/T5 四项全部落在 `live_hedge_executor.py` / `store.py` /
`domain.py` / `service.py` 这同一组文件上，且相互咬合——T1 改 `LegDispatch`
seam 与 `_leg_final_fields`，T3 也改 `LegDispatch` 与 store 写入面，T2 改
executor 的分类调用点，T5 改 service 的 outcome 构造。不存在不相交的文件边界；
强行切出第二个任务需要先冻结 `LegDispatch`/store 写入面两条共享契约，冻结成本
高于并行收益（四项总量约一个中等 diff）。UI 是显式非目标，没有第二域。
不推翻。`parallel_mode.enabled` 保持 false，无 dispatch-ready 门。

## 2. 前置证据步骤 W0（human operator，非实现工时）

- **内容**：对现存真实订单执行一次只读签名
  `GET /papi/v1/um/order?symbol=NOMUSDT&origClientOrderId=hgd1a45d5b7df0423a8840d72556767f82p`
  （或 `orderId=888412130`），原始响应全文（脱敏：去 header/签名）落
  `reports/api-samples/2026-07-hedge-order-truth-v1/um-order-detail-post-removal-sample.md`。
- **为什么**：ADR-T1 的契约修订样本；验证「订单详情 GET 仍带
  cumQuote/avgPrice」这一目前**未验证**的推断（10-design §1(a)）。只读、免费、
  不产生订单；执行者为 human operator（代理不得发私有请求）。
- **门槛语义**：W0 是**强烈建议的前置**而非硬阻塞——若推迟，T1 照 GET 文档
  形状实现（NULL 表示法兜底错误假设），W0 补上后若形状不符再走 fix 轮。
  但 review-1 前应尽量已有该样本，否则 T1 的核心假设进评审时仍是推断。
  **若样本证明 GET 也没有这些字段**：停止 T1 的实现，回到设计层走
  userTrades 契约修订（ADR-T1 Rejected 段的预声明路径），不得由实现者顺手扩
  allowlist。
- **附带收益**：样本里的 cumQuote 就是 leg id=6 的真实名义金额，作为证据留档
  （生产库仍按 ADR-T6 置 NULL，不回填）。

## 3. 任务卡：`backend`（唯一实现任务）

- **Owner**：`claude_glm`（`glm-5.2[1m]`），provider `zhipu_glm`。
- **Reviewer**：review-1 = codex，review-2 = codex（两个全新只读会话，见
  `status.json.model_routing`）。
- **实现报告**：`reports/agent-runs/2026-07-hedge-order-truth-v1/20-implementation.md`
- **测试证据**：`reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt`
- **diff**：stage 分支 `stage/2026-07-hedge-order-truth-v1` 上的
  `<base_sha>..<head_sha>`，base = `ecc3841`（status 记录为准）。

### 3.1 允许 / 禁止文件

**允许**（与 10-design §10 完全一致）：

```text
backend/hedge_open_tasks/domain.py
backend/hedge_open_tasks/store.py
backend/hedge_open_tasks/service.py
backend/hedge_open_tasks/executor.py
backend/services/live_hedge_executor.py
backend/tests/test_hedge_domain.py
backend/tests/test_hedge_store.py
backend/tests/test_hedge_service.py
backend/tests/test_hedge_executor.py
backend/tests/test_hedge_task_local.py
backend/tests/test_hedge_api.py
backend/tests/test_live_hedge_executor.py
```

**禁止**：`backend/services/hedge_open_live_client.py`（传输面锁死；确需改动
= 契约修订，停下报 bookkeeper）、`backend/services/binance_signing.py`、
`backend/hedge_open_tasks/wire_constraints.py`、`backend/hedge_open_tasks/scheduler.py`、
`frontend/**`、`backend/borrow_tasks/**`、公共快照/借款全部面、`schemas/**`、
`scripts/**`、`docs/**`、`reports/**`（除本 stage 目录）、`data/**`。
其余未列文件默认禁止；需要时先问 bookkeeper。

### 3.2 数据契约（实现必须遵守的 seam 冻结点）

1. `LegDispatch.cumulative_quote: Optional[str]`（None=未携带）、新增
   `raw_response: dict | None`；`executed_qty` 保留 `"0"` 默认。
2. `hedge_open_leg.cumulative_quote_amt`：NULL=未知、`"0"`=真零；表重建迁移
   保留全部既有行数据与三个索引。
3. 新表 `hedge_open_raw_response`（列清单见 10-design §3(a)；additive）。
4. `domain.classify_exchange_code(product, code, msg)`：纯函数，两层查询，
   返回类别含显式 `unclassified`；`MARGIN_BUSINESS_CODES` 初始只含 `"51169"`。
5. `service._dispatch_to_outcome(.., ts_us)` 必传；
   `domain.build_leg_exposure` 对 `ts_us <= 0` raise。
6. wire additive：leg doc `cumulative_quote_amt: string|null`；position doc
   `avg_price_incomplete`（bool，可缺省）。
7. 纯度不变式：`hedge_open_tasks/**` 不 import 网络/签名（`test_hedge_purity`
   继续全绿）。

### 3.3 实现顺序（避免互踩，含依赖说明）

依赖关系：T1 与 T5 在 `leg_exposure`（price 恢复 + ts 传参）上相交；T2 与 T3
在错误路径（分类调用点 + raw 捕获点都在 `classify_leg_response`/`_send_one_leg`
附近）相交。顺序安排让每一步落在前一步已稳定的面上：

| 步 | 内容 | 为什么在这个位置 |
| --- | --- | --- |
| W1 | **T2** 分类重构（domain 两层表 + executor 调用点 + attempt 上卷 + pause 映射） | 纯 domain 为主，不碰 LegDispatch 形状；后续 W3/W4 的错误路径直接建立在新分类上，避免先写旧分类再返工 |
| W2 | **T5** ts 统一（service 签名 + domain guard + 实盘路径回归测试） | 极小、独立；先落锁避免 W4 改 outcome 构造时再碰同一函数产生连环 diff |
| W3 | **T3** raw 持久化（新表 + LegDispatch.raw_response + 捕获点 + 容错） | 先建 raw 基础设施，W4 的 inline confirm GET 天然复用它取证 |
| W4 | **T1** 成交数据来源（FILL_FIGURES_SOURCE + inline confirm + 终态收紧 + `_leg_final_fields` 重写 + 表重建迁移 + aggregate_positions） | 最大的一步，压在 W1–W3 已稳定的分类/raw/ts 面上 |
| W5 | **ADR-T6** 历史数据迁移 M1/M2 + 审计事件 + fixture 测试 | 必须在 W4 定稿 schema（可空列）之后 |
| W6 | fold-in：preflight snapshot 键名契约测试（见 §5） | 纯测试，最后做，不影响任何前序 diff |

每步完成即跑该步涉及套件；W6 后跑全量并生成 `60-test-output.txt`。

### 3.4 确定性测试命令

```bash
cd "/Users/ark/Desktop/ai code/funding_hedging"
python3 -m pytest \
  backend/tests/test_hedge_domain.py backend/tests/test_hedge_store.py \
  backend/tests/test_hedge_service.py backend/tests/test_hedge_api.py \
  backend/tests/test_hedge_executor.py backend/tests/test_hedge_task_local.py \
  backend/tests/test_live_hedge_executor.py \
  backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py \
  -q 2>&1 | tee reports/agent-runs/2026-07-hedge-order-truth-v1/60-test-output.txt
```

（`test_hedge_open_live_client.py` 与 `test_hedge_purity.py` 在必跑清单内但不在
允许修改清单内——它们必须**原样**通过。）此外全仓回归：
`python3 -m pytest backend/tests -q` 结果一并附入 60 文件。

### 3.5 新增测试义务（验收逐条锁，详见 10-design §8）

- T1：post-2026-07-14 UM 响应形状（2026-07-27 实测形状为参照）不产生零名义;
  confirm 失败 → NULL + 非终态；margin POST 路径不变；`_leg_final_fields`
  规则表；aggregate NULL 跳过。
- T2：正数 fatal（注入表测机制）/ 正数 insufficient-funds（margin 表内暂无
  实证码，注入表测机制）/ `51169 → collateral_cap`（task-local pause +
  `pause_reason=collateral_cap_full` + 10-design §2(d) 冻结文案逐字断言，
  不落 `insufficient_margin`）/ 正数未列出（`unclassified`）/ 负数码全量
  回归矩阵 / attempt 上卷（含 `collateral_cap` 位次）。
- T3：拒单 msg 可从库中查出；成功单也有 raw 行；截断；raw 写失败不改业务结果;
  脱敏断言。
- T5：**服务级实盘路径**测试（`_dispatch_live` 全链路断言真实 ts；只测
  executor.py 不算数）+ `build_leg_exposure(0)` raise。
- 迁移：旧 schema fixture → 重建后数据完整、M1/M2 生效、审计事件存在、二次
  运行 no-op。

### 3.6 风险点（实现时对照 10-design §11）

W0 未落地时 T1 按文档形状实现并显式标注；表重建迁移只在测试临时库验证；
51169 变严的行为变化写进实现报告的「判定变化清单」；`test_hedge_purity` 若因
新 import 变红即为设计违约，停下。

### 3.7 评审关注点（建议 review packet 引用）

1. 「任何取不到的金额是否都不可能落成 `"0"`」——沿 `_decimal_str` 默认值、
   `_leg_final_fields` 每个分支、迁移 M1 逐条核。
2. 负数码判定零变化的回归矩阵是否完备（T2(c) 表只允许 51169 一行变化）。
3. raw 落库路径的容错是否真的不改控制流（注入 store 抛错验证）+ 脱敏不变式。
4. T5 测试是否真的走 `service._dispatch_to_outcome`（不是 executor 路径的
   又一个假覆盖）。
5. 表重建迁移的幂等与旧数据保真；生产库零接触（diff 中不得出现任何对
   `data/` 的路径引用变化）。
6. `hedge_open_live_client.py` 与 `wire_constraints.py` 的 diff 必须为空。

## 4. T4 的位置

T4 **不是实现工作**（`status.json.tasks[].note` 已记）。付费判别实验已于
2026-07-28 取消（根因已立：`02-collateral-cap-finding.md`；结果已知，下单是
花真钱确认已知答案）——**不下单不需要请求任何用户授权**。剩余工作 = 只读
recon，规程钉死在 10-design §5：公开文档核读可由 bookkeeper 完成；签名 GET
由 human operator 执行；证据落
`reports/api-samples/2026-07-hedge-order-truth-v1/collateral-cap-recon.md`。
preflight（`domain.py:806-825`）在 recon 回答落盘前一行不动；「preflight
有意不动，理由如下」是完整可验收的 T4 结局。recon 与 backend 任务卡互不
阻塞。

## 5. 上一 stage 遗留 p3 的折入判断

**折入 `p3-preflight-snapshot-key-contract-untested`（W6）**：一个纯测试文件
改动（断言 `compute_preflight` 的 snapshot_record 输出
`spot_min_qty/spot_max_qty/perp_min_qty/perp_max_qty` 与
`executor._leg_qty_filters` 读取的键名一致），零产品代码 diff，与本 stage
「静默降级」主题同形，真的便宜。其余四个 p3（backslash-prose /
confirm-negative-matrix / 409-dialog-title / selfcheck-dialog-body）继续
deferred——全是 UI/文案面，会把数据真实性 diff 搅宽。

## 6. 硬性测试约束（对实现者的绝对禁令）

- 不得发任何真实 POST；不得访问、读取、打印凭据；不得发任何 Binance 私有请求
  （W0 由 human operator 执行，不是实现者）。
- 不得启动/停止/重启服务（PID 96409 正以 live 模式运行，Start 闸门开着）。
- 不得写 `data/hedge-open-tasks.sqlite3` 的任何表（含 settings）；迁移只在
  测试临时库上运行；取证性只读查询允许。
- 不得建卡、不得触发 Start、不得下单。
- 测试全部离线确定性（fake urlopen / fake executor / 临时 SQLite）。
- 收尾三件事后停下等 bookkeeper：跑 §3.4 测试命令、写 20-implementation.md
  （含 T2(c) 判定变化清单与 T5(c) price 恢复实测陈述）、生成 60-test-output.txt。
  不得自行 dispatch 任何评审。

---

当前 Session ID: unavailable (Claude Code 未向本会话暴露 provider-native session id)
Session ID 来源: unavailable
原始输出路径: reports/agent-runs/2026-07-hedge-order-truth-v1/10-design.md, 11-adr.md, 12-development-breakdown.md
本地北京时间: 2026-07-28 17:29 CST（§3.5 T2 测试行与 §4 于此时刻按 16-design-revision.dispatch.md 修订；其余为 14:45:33 原稿）
下一步模型: bookkeeper
下一步任务: 归档修订后的三份产物并核对 diff 是否只落在指定章节
