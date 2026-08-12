# CCXT 公共行情摸排报告：`watchBidsAsks` / bookTicker（smooth-open V1 前置）

- 日期：2026-08-13（执行 UTC 2026-08-12T16:35–16:38）
- 任务：`ccxt-bookticker-recon-claude-glm`
- 性质：只读、无凭证、无订单、无服务控制的公共行情 proof。**不接入产品、不改依赖清单、不授权实盘。**
- 证据：
  - 脚本：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py`
  - 原始输出：`reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt`
- 对照设计：`docs/planning/smooth-open-orders-v1.md`（D1/D2、§4–§6、§11、§12「Human 2026-08-13」、§13-4）
- 对照原生 recon：`reports/api-samples/2026-07-hedge-open-live-v1/websocket-bookticker-recon.md`

## 0. 结论

**`continue-with-ccxt`（条件性）。** CCXT 4.5.64 主包已内置 `ccxt.pro`（无需独立付费包），`binance`（spot）与 `binanceusdm`（USDⓈ-M）的 `watchBidsAsks` 经运行时实测可用，两个独立 client watcher 并发收 `BTC/USDT` 成功，取消其中一个不影响另一个。可作为 V1 `BestBidAskProvider` 的实现基础。

**必须满足的条件**（否则切原生 fallback）：

1. adapter **只从 `info` 取原始字符串 `b/B/a/A`**，绝不使用 CCXT 的 normalized `bid/ask/bidVolume/askVolume`（后者是 float，丢尾零精度）。
2. 普通可达合约须断言 `market.contractSize == 1`；**1000x 仍由本仓库 `SPOT_SYMBOL_MAP` 显式封禁**，CCXT 的 `contractSize` 字段不足以识别 1000x（实测 1000PEPE 也报 `1.0`）。
3. spot 侧无交易所时间戳，adapter 须用本地 `received_at_us`；perp 侧可记 raw `E`。
4. P1 用 fake source 压测 CCXT 重连/`close()` 残留 task；若不可控则切原生 Binance public bookTicker fallback。

重开条件见 §10。

---

## 1. 测试环境与版本（acceptance 1）

| 项 | 值 |
|---|---|
| Python | 3.9.6（系统 python3，隔离 venv） |
| 包 | `ccxt` **4.5.64** |
| License | **MIT**（PyPI `License` 字段确认；`ccxt.__license__` 属性未暴露返回 `?`） |
| Home-page / Author | https://ccxt.com / Igor Kroitor |
| 关键依赖 | `aiohttp` 3.13.5、`requests` 2.32.5（CCXT 自带，无额外显式依赖） |
| CCXT Pro 是否独立/付费包 | **否**：`ccxt.pro` 随主包 4.5.64 内置，`import ccxt.pro` 直接可用，MIT，无 `ccxtpro` 第二包 |

安装命令（仓库**外**隔离临时 venv，未触碰生产 `.venv`）：

```bash
VENV=$(mktemp -d /tmp/ccxt-recon-XXXXXX)
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install ccxt          # 装入 ccxt==4.5.64，含 ccxt.pro
```

导入形态：`import ccxt.pro as cpro`，`cpro.binance()` / `cpro.binanceusdm()`。

权威链接：CCXT Pro manual https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual ；Binance Pro 源 https://github.com/ccxt/ccxt/blob/master/python/ccxt/pro/binance.py 。

> 输出首行 `urllib3 NotOpenSSLWarning`（LibreSSL 2.8.3）是隔离 venv 用系统 SSL 的噪音，与 proof 逻辑无关，不影响结论。

---

## 2. 观测运行事实（executable）

### 2.1 `watchBidsAsks` 可用性与底层通道（acceptance 2）

- `binance.has['watchBidsAsks']` 与 `binanceusdm.has['watchBidsAsks']` 均为 `True`，且方法属性存在（非仅声明）。运行时实测两侧均成功连接并收到数据。
- USDⓈ-M 一侧 raw `info` 含 `"e": "bookTicker"`，与 `u/s/ps/b/B/a/A/T/E/st` 同列 → CCXT 把 Binance `<symbol>@bookTicker`（公共 WS）解析为 `watchBidsAsks`，**底层通道经实测确认**（非仅文档）。
- symbol 规范化：`binanceusdm` 把入参 `BTC/USDT` 规范化为 unified key `BTC/USDT:USDT`；`binance` spot 保持 `BTC/USDT`。adapter 须按规范 key 取值，不能假设 key 等于入参字面。

### 2.2 两个独立 watcher、四价四量、时间戳（acceptance 3）

两个**独立** `cpro.binance()` / `cpro.binanceusdm()` client 各跑一个 asyncio watcher，对同一普通对 `BTC/USDT` 并发各收 5 条（output B 段）。代表性样本：

```
spot key=BTC/USDT   bid=63549.38(float) ask=63549.39   bidVol=7.48647(float) askVol=0.63923(float)
      raw B=7.48647000(str) A=0.63923000(str) | numeric_eq=True str_eq=False
      ts_ms=None datetime=None raw_E=None raw_T=None local_wall_ms=1786552697392
      raw_keys=['A','B','a','b','s','u']
perp key=BTC/USDT:USDT bid=63528.8(float) ask=63528.9   bidVol=7.37(float) askVol=10.158(float)
      raw B=7.370(str) A=10.158(str) | numeric_eq=True str_eq=False
      ts_ms=1786552697610 raw_E=1786552697610 raw_T=1786552697609 local_wall_ms=1786552697484
      raw_keys=['A','B','E','T','a','b','e','ps','s','st','u']
```

事实：

- **数值一致、字符串不一致**：CCXT 把 raw 字符串解析成 **float** 再输出，丢尾零（`7.48647000`→`7.48647`；perp `7.370`→`7.37`）。`numeric_eq=True` 但 `str_eq=False`。→ **adapter 必须取 raw `b/B/a/A` 原始字符串**（见 §5/§6）。
- **时间戳不对称**：spot raw_keys 不含 `E/T`，CCXT `timestamp=None`（CCXT **不**为 spot 注入本地接收时间，直接为 None）；perp raw 含 `E/T`，CCXT `timestamp` = raw `E`（事件时间）。→ spot 侧必须由 adapter 记本地 `received_at_us`。

### 2.3 取消一个 watcher 不影响另一个（acceptance 4，executable）

两个独立 watcher 各自 `_drain`，6 秒预采集后 `cancel` spot 任务，再采 6 秒（output D 段）：

```
before cancel: spot updates 4   perp updates 41
spot watcher cancelled: yes
after  cancel: spot updates 4   perp updates 96     perp kept updating after spot cancel: True
```

executable 已建立：**一个独立 owner 被取消/失败，不阻止另一个 owner 继续收更新**。这支撑设计 D3/D14 的“两侧独立 watcher + 故障隔离”。

> 说明：本 proof 用“独立 client + 独立 asyncio task”模拟设计中的“两个独立 owner”。CCXT 内部对断线/重连的自动恢复未在此处压测（见 §4、§7）。

### 2.4 `close()` 与残留 task（acceptance 6，executable 部分）

```
watch succeeded before close: yes
binanceusdm.close() returned: yes
asyncio tasks still alive after close: 2   caller/current task: ['Task-2']   other tasks: ['Task-1']
note: in-process self-check cannot cleanly isolate CCXT-internal watcher tasks from the caller chain ...
```

executable 事实：`client.close()` 调用正常返回、无异常。残留的 `Task-1/Task-2` 是调用链自身（`asyncio.run` 的 driver + 当前 section coroutine），**非**被证明为 CCXT 内部 watcher loop 残留。进程内自检无法把“调用链 task”与“CCXT 内部 task”干净分离，因此“close 后零 CCXT 内部残留”**未由本轮 executable 证明**（留 P1，见 §10）。

---

## 3. 单位、`contractSize` 与 1000x（acceptance 5）

`load_markets()` 后（output C 段）：

| market | type | linear | settle | contractSize | precision.amount |
|---|---|---|---|---|---|
| `BTC/USDT:USDT`（perp） | swap | True | USDT | **1.0** | 0.001 |
| `BTC/USDT`（spot） | spot | — | — | None（spot 无） | — |
| `1000PEPE/USDT:USDT`（perp，1000x） | swap | True | — | **1.0** | — |

单位规则（有实测证据）：

- **普通 USDⓈ-M 线性合约**：`contractSize == 1.0` → 1 张 == 1 base 单位；raw `B/A`（张数）在数值上即 base 资产量，与设计 `q_common`（base 币量）**同量纲**。本 proof 已证：普通 `BTC/USDT:USDT` 的 raw qty 与 normalized 数值相等，且 contractSize=1。
- **spot**：无 `contractSize`，qty 即 base 资产量，与 `q_common` 同量纲。
- **1000x（1000PEPE）**：CCXT 报 `contractSize=1.0`，**与普通合约不可区分**。币安原生语义下 1 张 1000PEPEUSDT = 1000 PEPE，而本仓库 `q_common` 对 1000x 是未换算的张数量纲（这是 1000x 被封禁的根因）。→ **CCXT 的 `contractSize` 字段不足以识别 1000x；现有基于 `SPOT_SYMBOL_MAP` 的 1000x fail-closed 必须保留，绝不能被“CCXT contractSize==1”绕开。** 这与设计 §13-4「1000x 仍无法建卡」一致。

---

## 4. 权威源事实（CCXT Pro 架构；source/manual，非 executable）

下列来自 CCXT Pro 官方架构（manual + 仓库源），本轮**未逐项压测**，标注为 inferred，供 P1 用 fake source 定向验证：

- **自动重连/心跳**：CCXT Pro 的 watch 方法内部维护订阅循环与心跳，断线后由库自身重连，应用层**不**应再叠加第二重固定退避（与设计 §9「不自造第二重固定退避」一致）。本轮未做人为断网压测。
- **`close()`**：CCXT Pro client 覆盖了 `close()`，旨在停止其 spawn 的内部 watcher future 并等待退出（manual）。本轮 executable 仅证“`close()` 正常返回、无异常”；“close 后内部 watcher future 全部退出、无悬挂”需 P1 在隔离环境下用 `asyncio` 工具或进程级检查验证（见 §10 重开条件）。
- **关闭后再 watch**：CCXT Pro 设计上再次调用 watch 方法会重建连接；本轮未单独验证此行为。

> 区分（acceptance 4/6）：executable 已证 = watchBidsAsks 可用、双 watcher 独立、cancel 隔离、`close()` 正常返回、contractSize/单位。source-inferred = 重连策略、内部 future 清理细节。

---

## 5. CCXT normalization 风险（acceptance 8/9 须 flag）

| 维度 | 风险 | 对策 |
|---|---|---|
| precision | `bid/ask/bidVolume/askVolume` 均被 CCXT 转 **float**，丢尾零（实测 `7.48647000`→`7.48647`） | adapter **只取 raw `info` 的 `b/B/a/A` 原始字符串**，按 Decimal 解析；禁用 normalized float 进 gate/展示 |
| units | 普通合约 qty=base，同量纲；1000x CCXT 不可信；跨所 contractSize 不同 | 普通 symbol 断言 `contractSize==1`；1000x 走 `SPOT_SYMBOL_MAP` 封禁；跨所独立 proof |
| timestamps | spot 无交易所 ts（CCXT `None`，不注入本地时间）；perp `timestamp`=raw `E` | spot 用本地 `received_at_us`；perp 记 raw `E`（有则记，无则降级本地）；**两侧时间口径不同**，gate 不得要求同刻（设计 §5.2 latest/latest） |
| freshness | bookTicker 实时推送；CCXT 不提供 stale TTL | 与设计 §5.2 一致：不造人为 stale 秒数；有效性由 generation/连接状态驱动 |

---

## 6. adapter 必须保留的最小字段

后续 `BestBidAskProvider` 实现须从一个 `watchBidsAsks` 返回项中至少保留：

- 原始字符串 `b`（买一价）、`B`（买一量）、`a`（卖一价）、`A`（卖一量）—— 来自 `item['info']`，**禁 float**；
- perp：raw `E`（事件时间，ms，有则记，作 `exchange_ts`）；
- spot：无 `E`，`exchange_ts = null`，必记 `received_at_us`（本地墙钟，µs）；
- `generation`、`status(connecting|live|disconnected)`、安全中文错误摘要：由 provider 自管（CCXT 不提供）；
- `contractSize`：仅用于断言普通合约 `==1`；**不**用于判定 1000x（用 `SPOT_SYMBOL_MAP`）；
- 价格/数量必须可解析为 **Decimal 且 > 0**，否则该侧 invalid（设计 §5.1）。

---

## 7. 与原生 Binance bookTicker recon 的对比（acceptance 8）

对照 `reports/api-samples/2026-07-hedge-open-live-v1/websocket-bookticker-recon.md`：

- **match（实测印证）**：① spot 与 perp 都用 `<symbol>@bookTicker`、实时、免鉴权；② **spot bookTicker 无 `E/T`**（实测 raw_keys=`[A,B,a,b,s,u]`，与原生结论一致）；③ **perp bookTicker 带 `e/E/T`**（实测印证，原生为推导/待实测项，本轮落实）；④ 价格字段为 STRING、payload `s` 大写。
- **补充/新事实**：实测 perp raw 还含 `ps`（pair symbol）与 `st` 字段（原生 recon 未列，应为 2026 年后新增字段，不影响 bid/ask 解析）。
- **contradiction**：无（原生 recon 的核心字段结论均被实测印证）。
- **unresolved（本轮未覆盖）**：① 原生 recon 推测的“现货 `@depth5@100ms` 带 `E`”未在本轮验证（本轮只覆盖 bookTicker，平滑设计已用 latest/latest + 5 分钟超时替代 ≤200ms 同刻门控，depth5 不再是必需）；② 原生 recon 的 24h 强制断开/重连运维点（ping 20s/3min、1024 stream 上限）属生产 manager 范畴，本轮不建 manager。
- **CCXT 相对原生**：CCXT 统一了订阅/字段/重连/heartbeat，代价是 normalized float 须绕开 + 一个外部库依赖；原生 public WS 零依赖、raw 字段直取，但需手写订阅/重连/心跳（仓库已有 REST `bookTicker` 适配器 `backend/adapters/binance_public.py` 可复用口径）。

---

## 8. 集成最小后果（acceptance 6 后半；不写生产代码）

针对设计「进程级专用 event-loop 线程 + 两个独立 watcher owner」：

- **可行**：两个独立 `cpro.binance()`/`cpro.binanceusdm()` client 在同一 event-loop 实测隔离，cancel/失败不互相阻塞（§2.3）。两 owner 各自 `watch_bids_asks([symbol])` 循环、各自更新不可变快照、各自 close，符合 D3/D14。
- **fail-closed**：raw `b/B/a/A` 任一缺失/非正/不可解析 → 该侧 snapshot invalid；普通合约 `contractSize != 1` 或不明 → invalid；1000x → 不建卡（`SPOT_SYMBOL_MAP`）。5 分钟超时或人工放行可绕过行情有效性，但仍经现有立即开单全部安全门（设计 §9）。
- **生命周期**：服务关闭时在 event-loop 线程内 `await spot.close(); await perp.close()`；引用计数归零才取消共享 watcher（D14）。本轮不实现 manager。
- **桥接**：同步 worker 线程 ↔ event-loop 线程，只读不可变 Decimal 快照 + 锁（设计 advisory 不变量 4）。本轮不写桥。

---

## 9. acceptance 对照

| # | acceptance | 状态 | 证据 |
|---|---|---|---|
| 1 | 版本/包/Pro/license/依赖/链接、是否需付费独立包 | pass | §1；output A 段 |
| 2 | 运行时证明 client/symbol/has/通道 | pass | §2.1；output A/B（perp raw `e=bookTicker`） |
| 3 | 双独立 watcher 收四价四量+时间戳+raw 摘要 | pass | §2.2；output B 段 |
| 4 | 一 watcher 延迟/取消不影响另一；区分 executable vs inferred | pass | §2.3/§2.4/§4 |
| 5 | 数量对比 raw B/A、contractSize、普通/非1/1000x 规则 | pass | §3；output B/C |
| 6 | 取消/`close()` 行为、异常/重连契约、最小集成后果、fail-closed | pass | §2.4/§4/§8 |
| 7 | 一个 secondary exchange 浅探，不泛化 | pass | §（见下）|
| 8 | 与原生 recon 对比 + 结论（continue/use-native/blocked） | pass | §7/§0 |
| 9 | 中文报告分观测/源/建议、最小字段、normalization flag | pass | §2/§4/§5/§6 |

secondary（acceptance 7）：浅探 OKX（output F 段）。`okx.has['watchBidsAsks']=True`、`has['watchOrderBook']=True`；`BTC/USDT:USDT` 为 swap、linear，但 **`contractSize=0.01`**（≠ Binance 的 `1.0`），`precision.amount=0.01`。→ 跨交易所 unified 能力检查、symbol 集合、contract metadata、channel/重连均**需各自 proof**，Binance 实测不得外推；本轮未连 OKX WS、未建通用框架。

---

## 10. 结论、重开条件与边界

**结论：`continue-with-ccxt`（条件性）**，理由见 §0。

切到 `use-native-binance-fallback` 的重开条件（任一成立）：

- P1 用 fake async source 压测发现 CCXT 重连/`close()` 残留 task 不可控，或断线后 generation/freshness 语义无法与设计 §5 对齐；
- raw 字段绕开 float 的 adapter 成本或外部依赖审计超预期，Human 决定回到零依赖的原生 public bookTicker（复用 `backend/adapters/binance_public.py` 口径）。

`blocked-pending-evidence` 不适用：本轮公共网络/包/运行时事实均已取得。

边界（本轮未做）：未压测断线自动重连；未验证多 symbol 共享 watcher 的引用计数（D14）；未连 OKX WS；未写任何 provider/manager/gate/executor 代码；未改依赖清单；未启动服务或下单；未读凭证/私有流/订单/账户/资产接口。原始输出首行的 urllib3 警告为隔离 venv 的 SSL 噪音，不影响结论。

---

## 附录：精确命令

```bash
# 隔离 venv（仓库外）
VENV=$(mktemp -d /tmp/ccxt-recon-XXXXXX)
python3 -m venv "$VENV" && "$VENV/bin/pip" install --upgrade pip && "$VENV/bin/pip" install ccxt

# 运行 proof（含 py_compile 自检）
"$VENV/bin/python" -m py_compile reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py
"$VENV/bin/python" reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py \
  > reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt 2>&1
```
