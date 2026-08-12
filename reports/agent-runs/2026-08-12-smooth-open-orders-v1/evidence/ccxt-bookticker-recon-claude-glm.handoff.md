# Task Handoff: ccxt-bookticker-recon-claude-glm

## Source Report (author-only; immutable after task end)

- task_id: ccxt-bookticker-recon-claude-glm
- role: Implementer
- target model: claude-glm (provider zhipu_glm)
- stage_id: 2026-08-12-smooth-open-orders-v1
- created_at: 2026-08-13
- base_sha: 9cab1ec4304bb1ce1df99123290daa559772a5fc
- delivery_sha: pending

### 任务背景

smooth-open V1 的 P0 只读公共行情 proof（设计 `docs/planning/smooth-open-orders-v1.md`
§11、§13-4、§12「Human 2026-08-13」第 2 项）：判定 CCXT `watchBidsAsks` 能否作为 V1
`BestBidAskProvider`，产出可回填设计的精确证据。本任务不集成 CCXT、不触订单/账户/资产
接口、不连私有流、不装进生产 venv。

### 实际范围

只读摸排 + 仓库外隔离 venv 实测 + 中文报告 + 原始证据 + handoff + reported status + 一个
本地 delivery commit。未改产品代码、依赖清单、服务、凭证、schema、API 契约；未实现
provider/watcher/gate/executor。

### 结论

`continue-with-ccxt`（条件性）。CCXT 4.5.64 主包内置 `ccxt.pro`（MIT，无需独立付费包），
`binance` 与 `binanceusdm` 的 `watchBidsAsks` 经运行时实测可用，两个独立 client watcher
并发收 `BTC/USDT` 成功，取消其一不影响另一个；普通 USDⓈ-M 合约 `contractSize=1.0`，
raw qty 与设计 `q_common` 同量纲。

### 关键实测事实

- ccxt 4.5.64，MIT；`ccxt.pro` 随主包内置，`import ccxt.pro as cpro` 可用；依赖 aiohttp 3.13.5。
- `binance`/`binanceusdm` 的 `has['watchBidsAsks']=True` 且实测连上；USDⓈ-M raw `info` 含
  `e=bookTicker` → 底层为 Binance `<symbol>@bookTicker`。
- 两独立 watcher 各收 5 条 `BTC/USDT`；cancel spot 后 perp 41→96 持续更新（隔离成立）。
- 普通 `BTC/USDT:USDT`：type=swap、linear、settle=USDT、`contractSize=1.0`、precision.amount=0.001。
  raw `B/A`（张数=base 币量）与 normalized 数值相等 → 与 `q_common` 同量纲。
- **CCXT normalized `bid/ask/bidVolume/askVolume` 是 float**，丢尾零（`7.48647000`→`7.48647`；
  perp `7.370`→`7.37`）→ adapter 必须取 raw `info` 的 `b/B/a/A` 原始字符串，禁 float。
- **spot 无交易所时间戳**：raw_keys 不含 `E/T`，CCXT `timestamp=None`（不为 spot 注入本地
  时间）；perp raw 含 `E/T`，CCXT `timestamp`=raw `E`。两侧时间口径不同。
- **1000x**：CCXT 对 `1000PEPE/USDT:USDT` 也报 `contractSize=1.0`，与普通合约不可区分 →
  现有 `SPOT_SYMBOL_MAP` 1000x 封禁必须保留，绝不能被“CCXT contractSize==1”绕开。
- secondary OKX：`has['watchBidsAsks']=True`，但 `BTC/USDT:USDT` `contractSize=0.01`（≠Binance
  1.0）→ 跨交易所必须各自 proof，不可外推。
- `close()` 正常返回；“close 后零内部 watcher task 残留”与“断线自动重连”未由本轮 executable
  证明（进程内自检无法干净隔离调用链 task）→ 留 P1 fake-source 压测。

### 未完成 / 未做

未压测断线自动重连；未验证多 symbol 共享 watcher 引用计数（D14）；未连 OKX WS；未写任何
provider/manager/gate/executor；未改依赖清单；未启动服务或下单；未读凭证/私有流/订单/账户/资产。

### 命令与结果

- `python -m py_compile <proof.py>` → OK
- `python <proof.py> > <output.txt> 2>&1` → exit 0；A–F 段全部产出证据
- 隔离 venv：`mktemp -d /tmp/ccxt-recon-XXXXXX` + `pip install ccxt`（=4.5.64），仓库外，未碰生产 `.venv`

### 仓库内证据路径

- `docs/planning/ccxt-bookticker-recon-2026-08-13.md`（中文报告）
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py`
- `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt`

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md`
  2. `docs/planning/ccxt-bookticker-recon-2026-08-13.md`
  3. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt`
  4. `docs/planning/smooth-open-orders-v1.md`（§11/§13-4 待回填）
  5. `reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/01-advisory-design-reviews.md`（已冻结不变量）
- 执行：Bookkeeper 核验 delivery_sha、源 SHA-256 边界、5 个 Allowed Files；Planner 据此把 CCXT 证据回填 smooth 设计 §11/§13-4
- 关卡：Bookkeeper verify 通过 → Human 决定是否授权 P1、唯一运行时依赖清单、进入正式跨 provider 计划评审
- 不能假设的事实：
  - CCXT normalized bid/ask/volume 是 float，不可直接用，必须取 raw `info` 的 `b/B/a/A`
  - 1000x 封禁不可由 CCXT `contractSize` 绕开（1000PEPE 也报 1.0）
  - spot 无交易所时间戳，必须用本地 `received_at_us`
  - close 后零内部 task 残留、断线重连策略未由本轮 executable 证明，须 P1 fake-source 压测

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: ccxt-bookticker-recon-claude-glm
执行结果: completed
结果摘要: 隔离venv实测ccxt4.5.64(内置Pro,MIT)watchBidsAsks:spot+USDⓈ-M双独立watcher可用且cancel隔离;普通合约contractSize=1同q_common量纲;CCXT volume经float化须取raw字符串;spot无交易所时间戳;1000x的contractSize亦=1故SPOT_SYMBOL_MAP封禁须保留;OKX=0.01跨所不可外推。结论continue-with-ccxt(条件)。未触凭证/私有流/订单/生产venv。
产物: [docs/planning/ccxt-bookticker-recon-2026-08-13.md, reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py, reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt, reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md, reports/agent-runs/2026-08-12-smooth-open-orders-v1/status.json]
检查结果: [py_compile pass; proof exit 0 九段证据齐 pass; watchBidsAsks 两 client 实测可用 pass; 双独立 watcher cancel 隔离 pass; 普通合约 contractSize=1 且 1000x 须保封禁 pass; CCXT float 须取 raw pass; 无凭证/私有/订单/生产 venv pass; git diff --check pass; handoff+status reported+1 本地 commit 未 push pass]
阻塞项: [none]
本地北京时间: 2026-08-13 00:45:07 CST
下一步模型: codex（status.json.bookkeeper，Bookkeeper 核验本 handoff）
下一步任务: 读取：reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm.handoff.md、docs/planning/ccxt-bookticker-recon-2026-08-13.md、reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-output.txt；执行：Bookkeeper 核验 delivery_sha、源 SHA-256 边界与 5 个 Allowed Files，Planner 据此回填 smooth 设计 §11/§13-4；关卡：Bookkeeper verify 通过后 Human 决定是否授权 P1、唯一运行时依赖清单与正式跨 provider 计划评审
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `5f0923db9854775db6bb43473bdaa5a706b02bec16d352e11066c54ad99dd993`
- verified_at: `2026-08-13 00:57:49 CST`
- status_revision: `4`
- base_sha: `9cab1ec4304bb1ce1df99123290daa559772a5fc`
- delivery_sha: `5b744350a04b9f5555dff22cd9d7ba87160cac52`
- verdict: `VERIFIED / pass（条件性 continue-with-ccxt）`
- scope: delivery commit 仅含 dispatch 允许的 5 个文件；未修改产品代码、依赖清单、服务或资金路径。
- reproduced: `python3 -m py_compile reports/agent-runs/2026-08-12-smooth-open-orders-v1/evidence/ccxt-bookticker-recon-claude-glm-proof.py`、`git diff --check 5b744350a04b9f5555dff22cd9d7ba87160cac52^..5b744350a04b9f5555dff22cd9d7ba87160cac52` 均通过；原始输出 A-F 完整，无 section failure、timeout 或 traceback。
- evidence limit: executable 证明了双 client 订阅、有限样本、取消隔离和 `close()` 正常返回；没有证明断线自动重连、重连 generation、引用归零、关闭后零 CCXT 内部 task、多 symbol 共享。上述项目必须作为 P1 的 fail-closed 验收，不能据此启用生产集成。

## Errata (append-only)

- 2026-08-13 Bookkeeper editorial correction: Human Brief 的 `执行结果: completed` 按规范读取为 `执行结果: completed（完成）`；不改变任务完成状态或技术结论。
- 2026-08-13 Bookkeeper editorial correction: Human Brief 的 9 个检查项按上限合并读取为 8 项：`[py_compile+proof exit: pass; watchBidsAsks 两 client 实测: pass; 双 watcher cancel 隔离: pass; 普通 contractSize/1000x 边界: pass; raw float 风险: pass; 无凭证/私有/订单/生产 venv: pass; git diff --check: pass; handoff+reported status+单 commit 未 push: pass]`。原始命令、证据和逐项 pass 状态不变；“九段证据”仅指九项 acceptance，对应原始输出 A-F。
