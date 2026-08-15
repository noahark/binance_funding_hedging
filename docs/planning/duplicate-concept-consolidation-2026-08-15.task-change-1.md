# 实现任务：发单数量取值收敛为单一函数（改动一）

- 派发人：Opus 5（经 Human 授权）
- 执行模型：claude-glm
- 基线：`main` @ `7d3dbed`
- 性质：**纯重构，零行为变化。** 不改任何判定、不改任何输出。
- 依据：`docs/planning/duplicate-concept-consolidation-2026-08-15.opus5.md` §3
- 评审依据：同目录 `*.review-grok-result.md` 与 `*.review-claude-glm-result.md`
  —— **两份评审均已确认改动一零行为变化、可原样实现**（改动二被判返工，**本任务不含改动二**）

---

## 1. 做什么

当前有**三处**在计算「这一单发多少数量」，逻辑相同、各写各的：

| # | 位置 | 当前代码 | 作用 |
|---|---|---|---|
| 1 | `backend/hedge_open_tasks/service.py:3570` | `send_qty = q_common if q_common is not None else D.Decimal(task["single_amount"])` | 组装两腿 `request_shape` 写入审计记录，**发生在 `prepare_attempt`（`service.py:3614`）之前** |
| 2 | `backend/services/live_hedge_executor.py:828` | `send_qty = ctx.q_common if ctx.q_common is not None else ctx.single_amount` | 真实下单发出的数量 |
| 3 | `backend/tests/fakes.py:152` | 同 #2，字面相同 | dry-run 假执行器，并用它跑合约过滤器 |

**抽出一个函数，三处共用。** 逻辑一字不改。

## 2. 函数落点与签名

放 `backend/hedge_open_tasks/domain.py`——三处均已 `import ... domain as D`，无需新增依赖方向。

```python
def resolve_send_qty(q_common, single_amount) -> Decimal:
    """发单数量：优先用预检取整后的 q_common；为 None 时回退用户原始输入。

    single_amount 可能是 str（任务表 TEXT 列）或 Decimal（AttemptContext）。
    两者统一经 Decimal(...) 转换——对已是 Decimal 的输入是按位精确拷贝。
    """
```

**硬约束：**

- **禁止经 `float`。** 全程 `Decimal`。
- 对已是 `Decimal` 的输入，`Decimal(x)` 是精确拷贝，不得引入 `quantize` / 舍入 / 上下文精度变化。
- 非法输入的异常形态不得改变：现在 `service.py:3570` 会抛 `InvalidOperation`，抽出后在函数内同一处抛，异常类型不变。

## 3. 类型等价性（两份评审已核实，不需重新论证）

| 站点 | 回退值来源 | 类型 |
|---|---|---|
| #1 | `task["single_amount"]` | 任务表 `TEXT` 列（`store.py:45`）；`validate_single_amount`（`domain.py:1619-1628`）校验后仍返回**字符串** |
| #2 #3 | `ctx.single_amount` | `AttemptContext.single_amount: Decimal`（`backend/hedge_open_tasks/executor.py:45`） |

唯一生产构造点 `service.py:3639` 传的就是 `D.Decimal(task["single_amount"])`——**与 #1 同源同值**。
全部测试构造点亦传 `Decimal`（`test_hedge_executor.py:47,159`、`test_hedge_wire_constraints.py:45,243`、
`test_hedge_review2_regressions.py:350`、`test_live_hedge_executor.py:115`）。

## 4. 明确不做（越界即返工）

| 不做 | 说明 |
|---|---|
| **不加 `q_common is None` 的拒发判断** | 那是乘数轮（`leg-unit-size-conversion-2026-08-15.opus5.md` r3 §3.1）的内容 |
| **不做任何倍数 / 乘数相关改动** | 同上 |
| **不动 `service.py:3612` 的 `q_common_str`** | 它是 attempt 的审计字段，不是发单量，不得塞进本函数 |
| **不动 `DisabledHedgeExecutor`（`executor.py:169-178`）** | 它不组单，无此逻辑 |
| **不动 `test_hedge_service.py:780`** | 那是挡板测试的假成交量，不是装配点 |
| **不做改动二**（`open_basis_rate` / 前端价差） | 双评审判 REWORK，方案待重写 |
| **不清理任何死代码** | 含 `hedge_open_fill`，须 Human 单独授权 |
| **不做任何未在 §1 列出的重构** | 顺手「改进」相邻代码即为越界 |

## 5. 验收

1. **现有全量测试原样通过。不得为适配本改动修改任何既有断言或夹具。**
   若有测试变红，说明这不是零行为变化，停下并报告，不要改测试让它变绿。
2. 三处调用点在两种输入下结果与改前一致：
   - `q_common` 有值 → 返回 `q_common` 本身
   - `q_common is None` → 返回 `Decimal(single_amount)`
3. 新增测试仅覆盖该函数本身的两条分支 + 一条类型分支
   （传入 `str` 与传入 `Decimal` 得到相等且精确的结果）。**不新增业务语义断言。**
4. `git diff` 应当只包含：`domain.py` 新增函数、三处调用点替换、新增的小测试。
   出现其它文件即为越界。

## 6. 交付方式

- **在分支上做**：`git checkout -b refactor/resolve-send-qty`（从 `main` @ `7d3dbed`）
- 提交信息说明这是纯重构、零行为变化，并注明依据本任务文件
- **不要合并到 main，不要 push**——完成后交 grok 评审，由 Human 决定合并
- 完成后回报：分支名、提交 hash、测试结果（通过数/失败数）、`git diff --stat`

## 7. 约束

- 只改 §1 列出的文件与新增测试
- 不触碰凭证、不控制服务、不下任何单、不动实盘数据库
- 有疑问先停下报告，不要自行扩大范围
