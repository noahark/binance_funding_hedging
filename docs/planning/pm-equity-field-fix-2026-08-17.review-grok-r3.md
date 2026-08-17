# Review — PM 权益口径终审（grok-4.6, round 3）

- 日期：2026-08-17 22:52:06 CST
- 性质：交付后终审。把 `a3f2b8a` 以来整包未提交改动当作一份交付，不只看增量。
- 作者会话：Claude Opus 5。本文件作者：grok-4.6（只读复评，唯一写入即本文件）。
- 范围：`git diff` 相对 `a3f2b8a`，7 文件 `+428 / −102`；外加未跟踪
  `docs/planning/pm-equity-field-fix-2026-08-17.review-request.md`、
  `docs/planning/pm-equity-field-fix-2026-08-17.review-packet.md`。
- 模式：只读。未改其它文件、未重启/停服务、未 POST、未写 `data/*.sqlite3`。
- 服务：PID `45346`，`127.0.0.1:8787`，`live` + `start_gate=true`（本轮独立核对）。
- packet 第 6 节是作者自记，下文每条均重新核过，不把它当已验证事实。

---

## 结论

**`ACCEPT`**

必改：**0 条**。可以提交（仍须 Human 明确授权 commit / push；本结论不授权合并、部署或实盘操作）。

整体行为已经收束到同一套规则：总额 = 现货估值 + `actualEquity`；缺源不回退；总额不完整则不出杠杆。上一轮指出的契约/schema 打架已经改掉。剩下的是注释级残留和已点名的验证空白，不挡提交。

---

## 1. 整包在做什么（以代码为准）

三件事叠在同一份 diff 里：

1. 展示口径：`accountEquity` → `actualEquity`。`account_equity_usdt` 留在快照里，不给任何标着「净资产」的卡用。
2. 缺源：能加的源就加，缺的不计入，总资产卡标红点名；净资产 / 杠杆是单值卡，缺则 `—`。钱包毛额回退删掉。
3. 死分支：`_project_pm_account_summary` 不再算杠杆，也不再收 `total_value`。

生效计算在：

```1397:1399:backend/domain/snapshot.py
    total_complete = spot is not None and unified_net is not None
    if total_complete and unified_net > 0 and total.is_finite():
        pm_summary["leverage_ratio"] = _quantize_rate(total / unified_net)
```

`unified_net` 只来自 `actual_equity_usdt`（`snapshot.py:1387-1390`）。`accountEquity` 与钱包毛额都不进总额、都不当分母。

---

## 2. 五处对同一行为是否一致

对照五份活文档/实现：`snapshot.py`、`snapshot.schema.json`、`public-market-contract.md`、`test_private_account_v1.py` + `self-check.js`、`PROJECT_STATE.md`。

### 2.1 总额公式

| 处 | 说法 | 是否与代码一致 |
|---|---|---|
| 代码 `snapshot.py:1390` | `spot_value + (actual or 0)` | 基准 |
| schema `:639` | `spot_value_usdt + actual_equity_usdt`，缺源贡献 0，不回退 | 一致 |
| 契约 `:833-834`、`:840-841` | 同上，禁止换口径 | 一致 |
| 测试 `anti_double_count`、`account_equity_alone` | `88000+7550=95550`；只有 account=80 时总额=100 | 一致 |
| `PROJECT_STATE.md:18-22` | 旧 Σ(wallet)+Σ(spot) 已废，毛额单独报 | 一致 |
| 前端 `:4285-4296` | 不重算总额，只按缺源标红 | 一致 |

活文档里已搜不到「`total = Σ(wallet)+Σ(spot)` 仍成立」的现行句子。`PROJECT_STATE.md:18` 与契约 `:869-874` 把它标成**已废**的历史台阶，不是现行规则。

### 2.2 不回退到 `accountEquity` / 钱包毛额

代码不再有那条链。前端净资产卡只读 `pm.actual_equity_usdt`（`index.html:4284`），注释已改成「方向不固定……少报约 90 U」（`:4280-4283`），不再写「毛额会报大」。

契约 `:882-886`、schema `:677` 写明 `accountEquity` 不是净资产替身。测试 `test_assemble_private_account_account_equity_alone_is_not_net_worth`（`:679-693`）钉住：只有 `accountEquity=80` 时总额仍是现货 100、杠杆 `None`。本轮跑过：`passed`。

### 2.3 杠杆：总额不完整则 null

这是 round 2 的必改项。**现文已经对齐。**

- 代码：`total_complete = spot is not None and unified_net is not None`（`:1397`）。
- 契约 `:887-896`：只有总额完整才相除；现货源没读到或 `actual_equity` 为空则为 null；**即使两个操作数都为正**也不出；真空 `[]` 不是缺源，那种 `1.00` 是真值；并写了「不要改回 both-positive」。
- schema `:724`：同一套话。
- 测试：`no_leverage_when_total_is_partial`（`spot=None` → `leverage is None`）；`leverage_survives_unrelated_source_loss`（`unified=None` 或 `um=None` 仍给出 `2.11111111`）。本轮 3 条新测试均 `passed`。
- `PROJECT_STATE.md:36-39`、`:43-45`：与上相同，并写明 self-check **守不住**后端再算出 `1.0`。

前端杠杆卡只把后端 null 画成 `—`（`index.html:4314-4316`）。这是刻意的单点计算，不是第二套公式。self-check `:9181-9184` 自己写了分层边界，与 `PROJECT_STATE.md:43-45` 一致。

### 2.4 缺源不对称

- 现货：求和，`0` 与真空仓分不清 → `unavailable_sources` 含 `spot_balances`（`snapshot.py:1264-1271`；前端 `:4275-4278`）。
- 统一净资产：单值，`actual_equity_usdt === null`（前端 `:4293-4294`；契约 `:856-860`）。

两端同一套形状理由。`unified_balances` / `um_positions` 不进总额完整性——代码如此，新测试如此，契约写 um 名义仓永不计入（`:837-838`）。

### 2.5 口径台阶

契约 `:869-874` 与 `PROJECT_STATE.md:15-17` 用的是同一组触发测量：`571.13 → 579.64`、杠杆 `3.07207789 → 2.98142928`。schema `:639`、`:724` 标明改前不可比。没有时序库会把旧总额和新总额接在一起（`snapshot_service.py` 仍是进程内发布）。

---

## 3. 实盘只读核对（本轮独立取数）

```text
PID 45346  STARTED 2026-08-17 22:23:47  听 127.0.0.1:8787
READYZ {"status":"ready"}
GET /api/hedge-open-settings
  executor_mode=live  start_gate=true  close_gate=true
GET /api/public-market/snapshot  （unavailable=[]）
  spot    387.39790478
  actual  191.9292248
  account 183.47509191
  wallet  100.78144698
  total   579.32712958  = spot + actual
  lev     3.01844146    = total / actual
  total ≠ spot + account
```

与 `PROJECT_STATE.md:46-51` 写的「当前 `45346`、源齐全路径已验、缺源无实盘证据」相符。数字和 packet 第 2 节 / 更早的 `579.45913371` 不同，是快照随时间漂，不是公式分叉。

`PROJECT_STATE.md:46` 写启动 `22:23:47`，与 `ps -p 45346` 的 `lstart` 一致。

---

## 4. 上一轮必改 / 应改是否还在

| 项 | 本轮核对 |
|---|---|
| 现货缺源不得出 `1.00×` | 代码 + `no_leverage_when_total_is_partial` 绿 |
| 契约/schema 不得再写「两正数就相除」 | 契约 `:887-896`、schema `:724` 已改，并加禁令 |
| `unified`/`um` 丢失不应抹掉杠杆 | `leverage_survives_unrelated_source_loss` 绿 |
| 前端「毛额会报大」 | `index.html:4280-4283` 已改 |
| `PROJECT_STATE` PID | 现写 `45346`，与进程一致 |
| 只有 `accountEquity` 不得进总额 | `account_equity_alone_is_not_net_worth` 绿 |
| `snapshot.py` 两处「wallet 已覆盖」旧理由 | `:1293-1294`、`:1301-1303` 已改成 actualEquity |
| `maps_cross_margin_free` docstring | `:511-515` 已改到毛额字段 |

没有改一半、没有改错函数。

---

## 5. 残留不一致（不挡提交）

这些不是现行总额/杠杆规则的分叉，提交后不必再开一轮修；需要时再收拾。

### R1. 钱包「含 um/cm」在同一份交付里两种口气

- `snapshot.py:1197` 仍写 wallet gross「um/cm never re-added」，像已结算事实。
- `test_private_account_v1.py:698` 同口径。
- 契约 `:863-867` 与 `PROJECT_STATE.md:382-387` 明确说**尚未结算**，本轮毛额已不进总额所以没追。

权威在契约增补。代码注释落后于同一次交付写下的存疑项。不影响任何展示数字。

### R2. `private_client.py:626` 仍写该端点「Used for accountEquity」

不在本 diff 的 7 个文件里。取数函数两种字段都原样返回，装配层才选 `actualEquity`。容易误导下一轮读者，但不是行为错误。

### R3. packet 文首过期

`review-packet.md:6-11` 仍写 `+297/−97`、PID `24679`。第 6 节后半已改口。这是作业单的头，不是活契约。`review-request.md` 仍是实施前方案（含后来否决的三级回退），应保持原样当史料。

### R4. 真空现货 `spot=[] → leverage=1.00` 无测试

契约和 schema 都把「真空数组是真 1.00」写进规则。现有测试只覆盖 `spot=None`（应 null）和现货有余额。round 2 本评审用装配函数跑过 `spot=[] → 1.00000000`，与文档一致，但仓库里没有钉住它的断言。

### R5. throw 点数怎么数

`self-check.js` 该块源码 `throw new Error` **14** 处；`for` 展开后运行时 **16** 个检查；若不算 locator、把 4 条杠杆算进去，是 **15**。`PROJECT_STATE.md:41` 写「15 个 throw 点」取的是最后这种。不是行为矛盾。

### R6. 已点名、未做的验证

- 缺源路径无实盘，只有单测（`PROJECT_STATE.md:50-52`）。
- 面板 vs App 人工复对仍 `[OPEN][VERIFY]`（`:375-380`）。follow-up 里的 `579.45913371` 来自 `24679`（口径已换、杠杆缺源修复之前），只用来说明「跟 App 对一眼」，不要拿它当当前进程的数。

---

## 6. 能不能提交

**能。** 五处对现行规则（总额构成、不回退、杠杆完整性、缺源不对称、台阶）已经一致。round 2 那条「契约会把 1.00× 订回规范」的必改已经落地。

提交前不需要再改代码。Human 授权后提交即可。下列不是提交门槛：App 复对、缺源实盘、R1–R5。

本结论不授权 push、合并、部署、改闸门或实盘下单。

---

## 7. 本轮核对过的命令

```text
git rev-parse HEAD
# a3f2b8a18774b3600aa2d4f0af83ec0f1a126bb0
git diff --stat
# 7 files, +428 −102

.venv/bin/python -m pytest -q \
  backend/tests/test_private_account_v1.py::test_assemble_private_account_no_leverage_when_total_is_partial \
  backend/tests/test_private_account_v1.py::test_assemble_private_account_leverage_survives_unrelated_source_loss \
  backend/tests/test_private_account_v1.py::test_assemble_private_account_account_equity_alone_is_not_net_worth
# 3 passed

ps -p 45346 ; GET /readyz ; GET /api/hedge-open-settings ; GET /api/public-market/snapshot
# 见 §3
```

未跑全量后端、未跑 `self-check.js`（不改文件、不做变异）。分层边界以源码注释和断言指向为准。
