# Review Packet — PM 权益字段口径修正 + 缺源「部分和标红」（2026-08-17）

- 性质：**交付后代码评审**。作者 = Claude Opus 5（本仓主会话）。
- 评审范围：**工作区未提交改动**，基线 `a3f2b8a`。
  ```bash
  git diff                 # 7 个文件，+297 / −97
  git status --short       # 另有 2 个未跟踪文件（docs/planning/pm-equity-field-fix-*）
  ```
- 评审模式：**严格只读**。不得改代码/文档、不得重启或停止服务、不得下单/借币/还款/划转、
  不得写任何 `data/*.sqlite3`。
- ⚠️ **服务正在运行且是 live 模式**（PID `24679`，`127.0.0.1:8787`，`start_gate=true`）。
  只读 GET 可以调；任何 POST 一律禁止。

---

## 1. 这次改了什么

**改动一：权益字段口径。** 「总资产估值 / 统一账户净资产 / 杠杆率」三张卡由
`accountEquity`（按抵押率折算的风控口径）改取 `actualEquity`（与币安 App 同口径）。
`accountEquity` 字段保留在快照里不删。

**改动二：缺源展示规则（Human 提出并拍板）。** 按数据源计——有几个源就展示几个源的和，
缺的不计入、数字标红并点名缺了谁；单值卡缺则 `—`。

由改动二导出的两个连带后果：

1. **钱包毛额回退链被整个删除。** 此前统一账户读不到时，`total_value_usdt` 退到
   `unified_wallet_value_usdt`（钱包毛额）。现在缺了就不计入。
2. **一条 test-asserted 的契约硬规则被废。** 契约原文：
   `total_value_usdt = Σ(unified totalWalletBalance priced) + Σ(spot free+locked priced)`
   （anti-double-count）。unified 侧改取净值后此式不再成立。原有 6 个测试守着它。

**改动三：删死分支。** `_project_pm_account_summary` 内那段 leverage 计算，唯一调用方传
`total_value=None`，条件恒假，永不执行；连同 `total_value` 形参一起删除。

## 2. 实测数据（重启后从运行中的服务取）

```
spot_value    : 388.04157919
wallet_gross  : 100.68845086      <- unified_wallet_value_usdt
actual_equity : 191.41755452
account_equity: 182.95449282
total_value   : 579.45913371      = spot + actual  ✅
leverage      : 3.02719954
（旧口径下 total 会是 570.99607201）
```

## 3. 请重点看的地方

1. **改动二的连带影响面是否找全。** 我只改了「总资产 / 现货 / 统一账户净资产 / 杠杆率」
   四张卡。有没有别的展示位、导出、日志、对账路径仍隐含「总额含统一账户毛额」的旧假设？
2. **被废的 anti-double-count 规则，其原意有没有丢。** 我把那 6 个测试里守「um/cm 不重复
   计入」「`crossMarginFree` / 负债不移动总额」的断言挪到了 `unified_wallet_value_usdt`
   字段上。请判断：挪过去之后，原规则真正想防的错误是否仍被守住？有没有哪条本意是只能
   在 `total_value_usdt` 上表达的？
3. **缺源判据的不对称是否正确。** 统一账户侧用 `actual_equity_usdt === null` 判缺（单值，
   null 可区分）；现货侧用 `unavailable_sources` 含 `spot_balances` 判缺（求和，0 与真空仓
   不可区分）。这个不对称我认为是数据形状决定的，请证伪或确认。
4. **`total_value_usdt` 是否真的不进任何决策路径。** 我的 grep 结论：后端零消费者，前端仅
   `index.html` 一处渲染。请独立复核，特别是有没有间接路径影响下单/平仓/借币/还款/风控。
5. **口径断裂的记录是否充分。** 契约与 `PROJECT_STATE.md` 都标了台阶。历史数据是否有落库
   的时间序列会因此对不上？（我查到的是快照为进程内当前值，未落时序库——请复核。）
6. **测试有效性。** 新增 4 条前端断言 + 1 条后端断言，我做过变异验证（5 次全部改坏变红）。
   请判断断言是否覆盖了真正的失败模式，有没有「测了个寂寞」的。

## 4. 一处我自己发现并已修正的错误（供参考，不必再报）

初版注释/文档写的是「毛额含借币，回退过去会把总额**报大**」。重启后实测显示毛额
`100.69` 只有净值 `191.42` 的一半多——方向相反，旧回退是**少报约 90 USDT**。已在
`snapshot.py`、契约、`PROJECT_STATE.md`、测试注释四处改成「两者是不同口径的量，差距既不小
方向也不固定」。

这同时带出一条 pre-existing 存疑项（已记为 follow-up，本轮未追）：契约长期声称
`totalWalletBalance` 已含 um/cm 子钱包，但实测差距与该说法不符。

## 5. 输出要求

- 结论：`ACCEPT` / `ACCEPT-WITH-CHANGES`（列出必须改的点）/ `REWORK`（有实质缺陷）
- 每条 finding 必须给**仓库内可验证的证据**（`文件:行号` 或 `命令 + 输出`）。
  本仓有过评审模型捏造核实内容的先例，你的每条引用都会被逐条复核。
- 区分「本轮引入」与「pre-existing」，后者不阻塞但请标出。
- 若认为我第 1–4 节陈述的某条「事实」是错的，直接指出并给出你的验证方式。
- 输出打在终端里，**不要写文件、不要改代码**。

---

## 6. 评审结论与处置（2026-08-17 追加，packet 作者自记）

两家结论均为 `ACCEPT-WITH-CHANGES`。所有引用经本会话逐条复核，属实。

### grok-4.6 独有的实质发现（已修）

**现货源缺失时杠杆率恒为 `1.00×`。** `spot is None` → `spot_value=0` → 总额退化成净值
本身 → `total / unified_net == 1`。页面上是：总资产卡标红说「缺现货账户」，紧挨着的杠杆率
却是个看着完整的 `1.00×`，读起来像「没加杠杆」。本会话已独立复现：

```
spot=None, actualEquity=90 → unavailable=['spot_balances'],
total=90.00000000, leverage=1.00000000
```

严格说这个算术在本轮之前就存在，但本轮才立了「缺源要诚实」的规则却没套到杠杆卡上，
按本轮规则判定为本轮缺陷。**修法**：总额只要是部分和就不给比值（`total_complete = spot
is not None and unified_net is not None`）。只改后端一处——前端本就把 null 渲染成 `—`，
再判一次是重复逻辑。补了后端 1 条 + 前端 4 条断言，均变异验证过。

### 两家共同指出的文档失准（已改）

1. `frontend/index.html` 注释仍写钱包毛额「含借币，会把总额报大」——被本 packet 第 2 节的
   实测自证为反（毛额 `100.69` < 净值 `191.42`，旧回退是**少报**约 90 U）。这是第五处，
   packet 第 4 节称「已改四处」时漏了它。
2. `PROJECT_STATE.md` 仍写「未重启服务、PID 36213 跑旧代码」，与实际（`24679` 跑新代码）
   矛盾。

### grok 的「应改」项（已全部处置）

- `snapshot.py` 两处仍用「`totalWalletBalance` 已覆盖该资产」解释 `crossMarginInterest` /
  `crossMarginFree` 不进总额——旧理由，总额已不走钱包。已改成「unified 侧取
  `actualEquity`，per-asset 行根本到不了总额」。
- `test_assemble_private_account_maps_cross_margin_free` 的 docstring 仍写
  `never moves total_value_usdt`，而断言已挪到毛额字段上。已同步措辞。
- 补了「有 `accountEquity`、无 `actualEquity` → 那个数不进总额、不出比值」的后端回归测试。

### 未处置（供 Human 决定，均非阻塞）

- **`[pre-existing]` unified 读到真空列表（非缺源）时负债卡显示 `—` 而非 `0`。**
  claude-glm 报，方向安全（不会假报 0），与本轮改动无关。
- **`[OPEN][VERIFY]` 面板 vs 币安 App 的人工复对仍待 Human 做**（见 `PROJECT_STATE.md`）。

### 复评 round 2（2026-08-17，服务已重启至 PID 45346 后）

两家结论仍为 `ACCEPT-WITH-CHANGES`，且**必须改的是同一条**：

**契约与 schema 的 `leverage_ratio` 描述跟实现打架（已改）。** 原文写「`total` 与
`actual_equity` 都为正则相除，否则 null」，可现货缺源时两者恰恰都是正数（总额退化成净值
本身），代码却故意不出比值。grok 的原话：「以后若有人按契约『修』代码，会把 `1.00×`
请回来。」已在 `docs/api/public-market-contract.md` 与 `snapshot.schema.json` 两处改写为
「总额不完整时即使两者为正也为 null」，并加了一条显式禁令；同时写明「现货读到的是真空
数组」不算缺源、那种情况下 `1.00` 是真值。

**grok 建议补的回归测试（已补）**：`unified_balances` 或 `um_positions` 丢失时杠杆率
**仍应给出**——它们不进总额，把它们写进完整性判据会白白抹掉一个本来良好定义的比值。
新测试 `test_assemble_private_account_leverage_survives_unrelated_source_loss`，变异验证
（把 `unified is not None` 加进判据）确认变红。

**grok 指出的一处文档自相矛盾（已改）**：断言条数在 packet 写「前端 4 条」、
`PROJECT_STATE` 写「6 项」，两处都不准。实际是 1 个测试块、4 个场景、15 个 throw 点。

**grok 的一条使用警告（已写进代码注释与 `PROJECT_STATE`）**：self-check 的杠杆率断言其
夹具写死 `leverage_ratio: null`，所以**后端若改回在缺源时算出 `1.0`，self-check 照样全
绿**——守住那一侧的只有 pytest 那条。不要把 self-check 通过当成「`1.00×` 不会回来」的证据。

**两家均独立验证了进程含修复**（PID 45346 启动时间晚于源文件 mtime），并各自跑了只读 GET，
两组数与本会话第三组各自自洽。grok 另外把边界穷举跑了一遍（`spot=[]` 真空仓 → 真 `1.00`、
`actualEquity` 为 `""`/`abc`/`NaN`/`Infinity`/`0`/`-1` → null），结论与实现一致。

### 评审质量备注

两家各自独立跑了只读 GET，取数时刻不同（`579.39451865` / `579.41256849` / packet 的
`579.45913371`），三组数各自自洽且公式一致——可确认两家都真的跑了，不是复述 packet。
claude-glm 摸到了杠杆率卡的边（提「pmMissing 未断言杠杆率」）但未深入到缺源恒 1 的缺陷。
