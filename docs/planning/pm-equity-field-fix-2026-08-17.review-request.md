# Review Request — PM 账户权益字段口径修正（accountEquity → actualEquity）

- 日期：2026-08-17
- 性质：**实施前设计评审（pre-implementation design review）**。代码一行未写，无
  `base_sha..delivery_sha` 区间。**这不是 Review-1，也不是 Review-2**，不产生正式 verdict
  计数；结论用于决定是否授权实施。
- 请求人：Human（经 Claude Opus 5 会话转达）
- 设计来源：`PROJECT_STATE.md` 的 Open Follow-ups 首条（2026-08-16 记录，"已设计未执行"）
- 评审模式：**只读**。不得改代码、不得改文档、不得重启服务、不得下单/借币/还款/划转。

---

## 1. 问题现象

PM 账户面板「总资产估值」与币安 App 对不上：

- 面板显示 `571.13`
- App 显示：现货 `385.7` + 统一账户 `194.2` = `579.9`

## 2. 已实测的根因（三点交叉验证，非推断）

`GET /papi/v1/account` 同时返回 `accountEquity` 与 `actualEquity`。同一时刻实测：

| 字段 | 本地值 | App 值 | 偏差 |
|---|---|---|---|
| `actualEquity` | `194.41521541` | `194.2252` | `0.098%`（价差/取数时刻量级） |
| `accountEquity` | `185.91` | `194.2252` | `4.4%`（抵押率折扣量级，不是价差） |
| `uniMMR` | `11.09568257` | `11.09` | 一致 |

**结论**：App 展示的是 `actualEquity`；本仓的三张卡取了 `accountEquity`。

**推断部分（无项目内证据，请评审判断是否需要更强证据）**：`accountEquity` 是按抵押率折算
后的风控口径，`actualEquity` 是不打折的真实市值。币安文档未在本仓留档。

## 3. 现状代码（已核实行号，2026-08-17）

快照层已经**同时**取了两个字段，无需新增取数：

```
backend/domain/snapshot.py:1157   out["account_equity_usdt"] = _raw_dec_field(pm_account.get("accountEquity"))
backend/domain/snapshot.py:1158   out["actual_equity_usdt"]  = _raw_dec_field(pm_account.get("actualEquity"))
```

消费点：

```
backend/domain/snapshot.py:1381   equity_raw = pm_summary.get("account_equity_usdt")   # ← 决定 total_value_usdt
backend/domain/snapshot.py:1382-1389                                                      # 缺失回退 unified_wallet 毛额
backend/domain/snapshot.py:1390   total = spot_value + unified_net
backend/domain/snapshot.py:1392-1398                                                      # leverage = total / equity
frontend/index.html:4277          const unifiedNetText = maskAmount(pm.account_equity_usdt);
frontend/index.html:4409          <div class="hint">papi accountEquity（接近 App 统一账户净资产）</div>
```

`actual_equity_usdt` 目前**只在契约白名单里透传，前端零消费**
（`frontend/index.html:2239` 仅列在字段白名单中）。

## 4. 提议改法

**4.1 后端（`backend/domain/snapshot.py`）**

把 `unified_net` 的取值改为三级回退链：

```
actualEquity  →  accountEquity  →  unified_wallet（钱包毛额，现有 legacy 回退）
```

改动落在 `:1381`（取哪个字段）与 `:1392`（leverage 分母跟着用同一个 equity）。
保留 `account_equity_usdt` 字段在快照里，**不删**——它仍是风控口径，将来可能有用。

设计理由（请评审判断是否成立）：`cumQuote` 被币安移除有先例，两级回退防字段改名。

**4.2 前端（`frontend/index.html`）**

- `:4277` `pm.account_equity_usdt` → `pm.actual_equity_usdt`（同样需要回退链，否则后端有
  回退而前端没有，两张卡会自相矛盾）
- `:4409` hint 文案 `papi accountEquity` → `papi actualEquity`

**4.3 预期数值变化**

| 卡片 | 改前 | 改后 |
|---|---|---|
| 总资产估值 | `571.13` | ≈ `580.16` |
| 统一账户净资产 | `185.91` | ≈ `194.42` |
| 杠杆率 | `3.07` | ≈ `2.98` |

杠杆率必须一起换：分子 `total_value_usdt` 和分母 equity 都变。如果只换分子不换分母，
界面上「总资产估值 ÷ 统一账户净资产」这句 hint 与两张卡的数会自相矛盾。

**4.4 契约与测试**

- `schemas/api/public-market/snapshot.schema.json:639`（`total_value_usdt` 描述）、
  `:722`（`leverage_ratio` 描述）需同步改口径措辞
- `docs/api/public-market-contract.md` 相关段落同步
- `backend/tests/test_private_account_v1.py:579-623` 的断言随之调整
- `frontend/self-check.js` 相关夹具

## 5. 影响面（已 grep 核实，请复核我是否漏了）

- `_project_pm_account_summary` 在全仓**只有一个调用方**（`snapshot.py:1378`）
- `total_value_usdt` 的生产消费者：后端零个（只有 docstring/schema 描述），前端仅
  `index.html:4273` 一处
- `leverage_ratio` 的生产消费者：前端仅 `index.html:4296` 一处
- **不进入**开单 / 平仓 / 借币 / 还款 / 风控闸门 / preflight 任何决策路径

## 6. 本会话在准备本文档时新发现的一处，请一并判断

`backend/domain/snapshot.py:1172-1179` 内部也有一段 leverage 计算：

```python
equity_raw = out["account_equity_usdt"]
if equity_raw is not None and total_value is not None:
    ...
    out["leverage_ratio"] = _quantize_rate(total_value / equity)
```

但唯一调用方 `:1378-1380` 传的 `total_value` 是 **`None`**，所以 `:1173` 的条件恒为假，
`:1177` 永不执行——真正生效的是 `:1396`。这是**既有死分支**，非本次改动引入。

问题：本轮改口径时要不要一并处理？不处理的话，将来有人新增调用方并传入 total_value，
会拿到 `accountEquity` 口径的杠杆率，与界面口径不一致。

## 7. 请评审回答的问题

1. **根因判断是否成立**——把 App 与本地的差异归因于 `accountEquity` vs `actualEquity`，
   证据够不够？有没有别的解释能同时吻合那三个数？
2. **回退链设计是否正确**——`actualEquity → accountEquity → 钱包毛额`。中间那级回退到
   `accountEquity`（已知偏小 4.4%）是否比直接跌到钱包毛额更好？还是应该 fail-closed 显示
   `—`？（本仓有「展示层诚实性」的既有原则：缺省一侧倒向"已知"是历史上踩过三次的坑，
   见 `PROJECT_STATE.md` 2026-08-07 条目）
3. **影响面是否完整**——第 5 节的 grep 结论有没有漏掉的消费者？特别是有没有任何路径让
   `total_value_usdt` 或 `leverage_ratio` 间接影响资金动作。
4. **前后端回退链一致性**——后端 `total_value_usdt` 有回退，前端「统一账户净资产」卡也需要
   同样的回退链吗？还是应该让前端直接显示后端算好的值（新增一个字段）？
5. **第 6 节的死分支**——本轮处理还是单列 follow-up？
6. **口径断裂的记录义务**——`total_value_usdt` 与 `leverage_ratio` 的历史值会有一个台阶
   （总资产 +9 USDT 量级，杠杆率 -0.09）。需要在契约文档里标注断裂点吗？

## 8. 输出要求

- 结论用 `ACCEPT`（设计成立，可实施）/ `ACCEPT-WITH-CHANGES`（列出必须改的点）/
  `REWORK`（设计有实质缺陷）三选一
- 每条 finding 必须给出**仓库内可验证的证据**（文件:行号 / 命令 + 输出）。本仓有过评审模型
  捏造核实内容的先例，凡引用必被逐条复核。
- 若你认为某条我写的"事实"是错的，直接指出并给出你的验证方式
- 输出写成一段可粘贴的 markdown 回复即可，**不要写文件、不要改代码**

---

## 9. 评审后记（2026-08-17 追加，本文档作者自记）

⚠️ **上文第 4.1 节提出的三级回退链 `actualEquity → accountEquity → 钱包毛额`
未被采纳，实际交付的不是它。** 保留原文供追溯，勿照其实施。

两家评审结论均为 `ACCEPT-WITH-CHANGES`：

- **grok-4.6** 判中间那级不成立：`accountEquity` 与 `actualEquity` 差约 4.3%，不是同一个
  量的近似，在写着「净资产」的标签下静默换用它属于新的假声明；并引 `frontend/index.html`
  划转 UI 的既有硬规则「缺失 → null → 显示 —（绝不把不知道显示成一个数）」。同时指出
  第 4.3 节的 `580.16` 算错（混用 App 现货数与本地 `actualEquity`），本地口径应为 `579.64`。
- **claude-glm** 主张保留一级 `actual ?? account` 兜底，但未反驳上述诚实性原则；另指出
  本请求第 4.4 节漏了源文件 docstring，并提出一个未排除的替代解释（App 显示的可能是钱包
  毛额，当前债务量级下与 `actualEquity` 不可区分）。

**Human 最终决定的规则（实际实施的）**：按数据源计——有几个源就展示几个源的和，缺的不
计入、数字标红并点名缺了谁；单值卡缺则 `—`。据此**钱包毛额回退链被整个删除**（毛额含
借币，回退过去会把总额报大）。这条规则同时改变了 `pm_account` 读不到时的既有行为，并使
契约中 `total_value_usdt = Σ(unified totalWalletBalance) + Σ(spot)` 这条 test-asserted
的 anti-double-count 公式不再成立。

交付实况与口径断裂台阶见 `PROJECT_STATE.md` Current Status 首条；契约见
`docs/api/public-market-contract.md` 的 “Total composition” 与 “PM account equity fields”。
