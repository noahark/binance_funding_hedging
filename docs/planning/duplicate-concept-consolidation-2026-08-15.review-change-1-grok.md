# 交付评审：发单数量取值收敛（改动一）

**结论：ACCEPT。**

对象：`refactor/resolve-send-qty` @ `654dc95`
base：`ce53f68`（相对 `7d3dbed` 仅多任务包文档，代码零差异）
diff：5 files, +25 / −3。改动二不在范围内。

只读复核。未改交付代码，未合并，未 push。本文件是评审请求授权的唯一写入。
说明：我评过方案稿（改动一零行为、可实现；改动二 REWORK）。本稿实现作者是 claude-glm，提供方不同；我不是实现者。

---

## 给 Human

**发生了什么：** 三处「这一单发多少」各写各的，现已收成 `domain.py` 里一个函数。声称纯搬家、下单数量不变。

**实际影响：** 核对成立。有预检取整量时仍用原来那个数；没有时仍把用户原始输入转成十进制小数。真实下单、审计记录、假执行器三条路结果与改前一致。没有改判定、没有加拒发、没有动倍数。

**建议：** 可以按该提交合并。合并、push、部署、实盘仍须你单独点头。

**备选：** 若要先清掉仓库里两条与本改动无关的基线测试红（见问题 5），那是另一件事，不要塞进这次合并。

---

## 五问

### 问题 1：是否真的零行为变化？

**是。** 三处在 `q_common` 有值 / 为 `None` 两种输入下，与改前逐一等价。

函数（`domain.py:1631-1639`）：

```python
if q_common is not None:
    return q_common
return Decimal(single_amount)
```

| 站点 | 改前 | 改后 | 有值 | 为 None |
|---|---|---|---|---|
| `service.py:3570` | `q_common if … else D.Decimal(task["single_amount"])` | `D.resolve_send_qty(q_common, task["single_amount"])` | 返回同一对象 | `Decimal(str)`，与 `D.Decimal(str)` 同类同构造 |
| `live_hedge_executor.py:828` | `ctx.q_common if … else ctx.single_amount` | `D.resolve_send_qty(ctx.q_common, ctx.single_amount)` | 返回同一对象 | `Decimal(已是 Decimal)` |
| `fakes.py:152` | 同执行器 | 同执行器 | 同上 | 同上 |

`service.py:3570` 专门核对：

- `task["single_amount"]` 仍是任务表 TEXT（`store.py:45`），`validate_single_amount`（`domain.py:1619-1628`）校验后仍返回字符串。改前改后都走 `Decimal(字符串)`，不经 `float`，无 `quantize`。
- `D.Decimal` 就是标准库 `Decimal`（`domain.py` 模块级 import）。非法字符串仍抛 `decimal.InvalidOperation`，类型不变。调用栈只多一帧 `resolve_send_qty`，调用方按类型捕获则无差别。
- 该站点的 `q_common` 来自 `fresh.q_common` 或 `D.Decimal(task["q_common"])`（`service.py:3515/3519`），有值时本就是 `Decimal`，函数原样返回，不改精度。

`#2/#3` 回退：本仓库 `.venv` 的 CPython 3.11.15 上，`Decimal(已有 Decimal)` **就是原对象**（`id` 相同，`as_tuple` 相同）。即便其他解释器做成拷贝，也是按位精确、不看上下文精度。随后 `fmt_decimal`（`domain.py:1739-1752`）再包一层 `Decimal(value)` 做成订单 `quantity` 字符串，`str(send_qty)` 写审计，两种实现输出相同。

未改任何判定：`q_common is None` 仍回退，不拒发。

### 问题 2：是否越界？

**没有。** 任务包 §4 七条都不在 diff 里，也没有顺手改相邻代码。

| 不做 | 核对 |
|---|---|
| 不加 `q_common is None` 拒发 | 函数仍回退；无新 `raise` / pause |
| 不做倍数 / 乘数 | 五文件无乘数、无 `1000`、无 `symbol_match_type` 改动 |
| 不动 `service.py:3612` `q_common_str` | 仍是 `D.fmt_decimal(q_common) if q_common is not None else task["single_amount"]` |
| 不动 `DisabledHedgeExecutor` | `executor.py` 不在 diff；`169-178` 仍不组单 |
| 不动 `test_hedge_service.py:780` | 该文件不在 diff；仍是挡板假成交量 |
| 不做改动二 | 无 `store.py` / `index.html` / `open_basis_rate` |
| 不清理死代码 | 无 `hedge_open_fill`、无 schema |

`git diff --name-only ce53f68 654dc95` 恰为任务包 §5.4 的五个文件。三处调用各改一行，无注释、无相邻整理。

`service.py:3301` 的 `D.Decimal(task["single_amount"])` 是预检输入，不是发单装配，正确未收。

### 问题 3：新增测试是否恰当？

**恰当。** `test_resolve_send_qty_branches_and_type_equivalence`（`test_hedge_domain.py:637-645`）覆盖该函数的全部分支，没有多余业务语义。

函数只有两个分支：

1. `q_common is not None` → `assert … is q`（同一性）
2. `q_common is None` → `== Decimal("1.5")`

外加任务包要求的类型分支：`"1.500"` 与 `Decimal("1.500")` 得到 `==` 且 `str(...) == "1.500"`（无舍入、保留系数零）。

`is q` 是正确的等价性表达：任务包写明「有值 → 返回 `q_common` 本身」；若改成 `return Decimal(q_common)`，这条会红。它锁的是「不包一层」，不是业务含义。

未测 `InvalidOperation`：任务包 §5.3 只要两分支 + 类型分支，不多写是对的。既有断言与夹具零改动。main 收集 153 条 domain 测试，分支 154 条，多的就是这一条。

### 问题 4：函数落点是否合适？

**合适。** 放在 `backend/hedge_open_tasks/domain.py` 没有新依赖方向。

三处调用方本来就 `import … domain as D`，本次无新 import。函数只用已有的 `Decimal`，无 SQLite、无网络、无执行器，符合该模块「纯数量规则」的边界。`live_hedge_executor` → `hedge_open_tasks.domain` 是既有方向，没有反过来。

`service.py:3570` 发生在构造 `AttemptContext`（`3634`）之前，放进 `executor.py` 会让装配点去依赖执行器缝。domain 与 `validate_single_amount` 相邻是合理的。

### 问题 5：是否引入了新问题？

**没有引入新的行为问题。** 派发方对两条基线失败的判断成立。

**类型注解：** 签名写 `-> Decimal`，有值分支直接返回入参。当前三处入参是 `Decimal | None`（`AttemptContext.q_common` 注解；service 侧来自 `fresh.q_common` 或 `D.Decimal(task["q_common"])`），有值时注解成立。若有人传入非 `Decimal` 且非 `None`（例如未转换的字符串），函数会原样返回——与改前三处字面逻辑相同，不是新行为。这不是转换构造器。未来误用路径是「以为它会把 `q_common` 也转成 `Decimal`」；现网没有这样的调用。按 §1，这不是本轮阻塞项。

**基线失败（独立复现，main 与 `654dc95` 同名同因）：**

1. `test_urlopen_only_in_designated_http_clients` → `backend/services/public_ip_service.py` 含 `urlopen`，不在允许名单。checklist `smooth-open-orders-v1-development-checklist.md:612` 已记。本 diff 未改该文件或该测试。
2. `test_no_websocket_listenkey_scaffolding` → `backend/app/server.py:105` 注释「there is no browser WebSocket」。扫描命中 `websocket`。引入提交 `f95577f`（2026-08-14，平滑平仓前端串联），早于本 base，本 diff 未改。属基线漂移，不是本次引入。

本评审在 `654dc95` 树独立跑全量：`2 failed, 1938 passed`。main 收集 1939 条，分支 1940 条，差额即新测试。调用点相关 242 条（executor / live executor / wire / purity / review2 / service / api）全绿。

---

## 发现清单

无 in-range 阻塞项。无 `REWORK`。

观察（不阻塞，勿当修复任务）：

- 注解不保证运行时把非 `Decimal` 的 `q_common` 转成 `Decimal`；这是有意保持旧语义。
- `server.py:105` 注释触发的纯度扫描失败可另开文档/测试豁免，不要夹带进本次合并。

---

## 独立核对命令

```text
git diff --stat ce53f68 654dc95
# 5 files, +25 -3

.venv/bin/python -m pytest backend/tests/test_hedge_domain.py::test_resolve_send_qty_branches_and_type_equivalence -q
# 在 654dc95 树：pass

.venv/bin/python -m pytest backend/tests -q --tb=no
# 在 654dc95 树：2 failed, 1938 passed
# 失败即上述两条基线，与 main 工作树复现一致
```

```text
[TASK_RESULT v2]
任务 ID: review-duplicate-concept-consolidation-change-1
执行结果: completed（完成）
结果摘要: 改动一交付评审 ACCEPT。三处发单量收敛为零行为变化；七条不做未触碰；新测试覆盖两分支与类型等价；全量 1938 passed / 2 failed，两条红与本改动无关。
产物: [docs/planning/duplicate-concept-consolidation-2026-08-15.review-change-1-grok.md]
检查结果: [Q1三处等价pass；Q2七条不做未触碰pass；Q3测试覆盖与is-q pass；Q4落点domain无新依赖pass；Q5注解观察不阻塞pass；全量1938/2与基线同因pass；文件集恰五份pass；既有断言零改动pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-15 18:58:09 CST
下一步模型: Human（决策者）
下一步任务: 读取：docs/planning/duplicate-concept-consolidation-2026-08-15.review-change-1-grok.md；执行：决定是否合并 refactor/resolve-send-qty @ 654dc95；关卡：合并/push/部署/实盘须你单独授权
[/TASK_RESULT]
```
