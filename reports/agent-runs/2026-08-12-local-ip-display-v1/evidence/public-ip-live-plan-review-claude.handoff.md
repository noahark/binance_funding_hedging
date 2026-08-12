# Task Handoff: public-ip-live-plan-review-claude

## Source Report (author-only; immutable after task end)

- task_id: `public-ip-live-plan-review-claude`
- role: `Reviewer / Plan Review`（只读，创建本交接件为唯一写入）
- target model: `claude / Anthropic`（Opus 5）；被审计划作者 `codex / OpenAI`，provider 隔离成立
- stage_id: `2026-08-12-local-ip-display-v1`
- created_at: `2026-08-12 19:58:39 CST`
- base_sha: `983e900fc4af257c834774d0eb1bdc5dc2e111b7`
- delivery_sha: `2625cf3a532f25d92a5f660aa2b845a6eaaaf009`
- 复审对象：`reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
- 评审结论：**REWORK（返工）**

### 只读范围与验证方式

固定命令 `git diff 983e900fc4af257c834774d0eb1bdc5dc2e111b7..2625cf3a532f25d92a5f660aa2b845a6eaaaf009`
输出 1 个文件、85 行新增，仅 `evidence/public-ip-live-plan.md`，与 `status.json` revision 5 的
`base_sha`/`delivery_sha` 完全一致；工作树 `git status --porcelain` 为空，未移动 `HEAD`
（当前 `HEAD=a3fc3eb`，为 dispatch 控制提交，未作为接受依据）。本次评审未发起任何外部网络请求、
未读取凭据、未访问币安、未运行服务、未修改除本交接件外的任何文件。

### 计划的可取之处（先说好的）

- 范围克制：一个只读端点 + 一个进程内缓存服务 + 一段前端文案，零新依赖、零新配置项、零后台线程、
  零重试循环、零 localStorage、零浏览器外域请求；`urlopen` 可注入的形状与既有
  `backend/services/hedge_open_live_client.py:228-235`、`backend/services/portfolio_margin_borrow_client.py:101-108`
  完全同构，实现者有现成范式可抄。
- 诚实性到位：三态（`ok`/`stale`/`unavailable`）能区分「知道」「知道但过期」「不知道」，
  从不伪造地址，不向浏览器泄漏异常文本/URL/请求头；失败结果同样缓存，避免 60 秒刷新反复外呼。
  这与 2026-08-07「展示层诚实性整族修复」确立的口径一致（缺省一侧倒向「已知」的反面教训）。
- 边界声明正确：明确写出「该展示不能证明币安实际观察到相同出口 IP」，且不驱动下单、资金动作、
  live gate 或白名单变更。这条必须在实现后的 UI 与文档里原样保留。
- 文档落点选得对：`docs/api/public-market-contract.md` 已按修订号收纳非行情端点
  （v0.13 划转、v0.17 还款），新增一节 v0.19 与既有惯例一致；`docs/architecture/ARCHITECTURE.md`
  与 `docs/development/DEVELOPMENT_GUIDE.md` 只登记有资金闸门的端点，本次确实无需改动，
  计划给出的理由成立。

### 阻塞发现（`in-range`，须由 Planner 修订计划）

#### R1 🔴 后端注入 seam 欠定义：三种合理读法里两种是坏的，且都躲得过本计划自己的验收

计划第 2 节写：「服务只在 `run()` 中创建并注入 `_Handler`；`build_server()` 增加一个可选、
默认 `None` 的关键字注入参数并在每次建 server 时复位该 handler 属性」。这两句合在一起没有把
**注入与 `build_server` 的先后**钉死，而现有代码里这条 seam 有一个已知陷阱：

- 证据锚点 A：`backend/app/server.py:1473-1483` —— `build_server()` 每次调用都会把
  `_Handler.service`/`borrow_service`/`hedge_open_service` 复位，然后才构造 server。
- 证据锚点 B：`backend/app/server.py:1712-1729` —— `run()` 先在 1715 行调用
  `build_server(config, service)`（注释明写「keeps its original 2-arg call shape here so
  process-level stubs of build_server keep working」），**之后**才在 1716-1729 行逐个赋值
  `ledger_flow_service` / `asset_transfer_*` / `margin_repay_*`。
- 证据锚点 C：`backend/tests/test_service_health.py:307`、`:339`、`:369`、`:422` ——
  四处以 `lambda c, s: srv` 猴补 `build_server`，只接受两个位置参数。

由此三种实现读法：

| 读法 | 结果 |
|---|---|
| A. `run()` 把新 service 作为关键字参数传给 `build_server` | `test_service_health.py` 四处 `lambda c, s` 立即 `TypeError`，四个既有测试红 |
| B. `run()` 在 1715 行**之前**赋值 `_Handler.public_ip_service` | 被 `build_server` 内的复位清成 `None` → **生产环境该路由永久 503**，页面永远显示「暂不可用」 |
| C. `run()` 在 `build_server` 返回**之后**赋值（同 1716-1729 行既有写法） | 正确 |

读法 B 尤其危险：它只在真实 `run()` 路径上坏，而计划的全部离线测试都是直接注入 handler 属性，
一条也不会红；再叠加验收标准第 6 条明写「无需……服务重启或部署」，本轮根本不会有人跑到那条路径，
缺陷要等到下一次手动重启才暴露。

**最小修法（推荐，同时结构性消灭读法 A/B）**：删掉 `build_server` 的新增关键字参数，只在
`build_server` 里加一行 `_Handler.public_ip_service = None` 复位（测试隔离目标不变），
`run()` 在 `build_server(config, service)` **返回之后**赋值，与 `ledger_flow_service` 同写法；
测试按 `backend/tests/test_ledger_flow_api.py:69-84` 的既有范式直接存取 `_Handler` 属性并在
`finally` 里还原。该参数目前不会有任何非测试调用方使用，属于多余入口。计划须把这句顺序写成
明文，不能留给实现者推断。

#### R2 🔴 验收的测试范围盖不住被改动的共享文件（正好也盖不住 R1）

验收标准第 6 条只跑 `python3 -m pytest -q backend/tests/test_public_ip_api.py`、
`node frontend/self-check.js`、`git diff --check`。但本次改动落在共享的
`backend/app/server.py` 与 `_Handler` 类属性上，而该 seam 的既有覆盖分散在
`backend/tests/test_service_health.py`（`run()` 装配与 `build_server` 猴补）、
`backend/tests/test_max_withdraw_api.py:48`、`backend/tests/test_ledger_flow_api.py:72-75`、
`backend/tests/test_asset_transfer.py:104`、`backend/tests/test_margin_repay.py:112`
（后三者以 3/4 位置参数调用 `build_server`）。只跑新测试文件时，R1 的读法 A（四个既有测试变红）
与读法 B（生产 503）都不会被任何一条断言抓到。项目既有实践也不是单文件验收
（`PROJECT_STATE.md` Last Completed 记「定向后端 131 项通过」）。

**修法**：验收标准第 6 条补上这五个既有测试文件（或整个 `backend/tests` 定向套件）并要求
记录原始输出；这不新增测试结构、不新增依赖，只是把已存在的护栏纳入验收口径。

### 非阻塞建议（Planner 可采纳，也可留给实现 dispatch）

- R3 🟡 **前端触发方式建议写成非阻塞**。`frontend/index.html:6881-6912` 的 `loadApi()` 全程
  `refreshState.isRefreshing = true`，并在 `finally` 里重排 60 秒定时器与倒计时；后端在缓存未命中
  且两源都超时时最坏约 4 秒（2s × 2）。若 `loadPublicIp()` 被 `await` 进这条主链路，每 5 分钟
  一次的刷新会被自己拖慢约 4 秒。计划已写「失败不进入失败态」，但没写「不拖慢节奏」。建议明文：
  `loadPublicIp()` 以不 `await` 的方式触发并自带 `catch`，与快照/持仓链路完全解耦。
- R4 🟡 **失败缓存 TTL 缺一条测试**。验收标准第 3 条要求「成功与失败缓存均为 5 分钟；缓存期内
  没有重复外呼」，但第 4 节的测试清单只列了主源成功的 5 分钟缓存。建议在同一测试文件里补一条
  「两源失败后，5 分钟内再次请求不产生新的 `urlopen` 调用」——这正是防止 60 秒刷新变成持续外呼的
  那道闸，不加新结构。
- R5 💭 **两点小事**：(a) 外部响应体建议限长读取（如 `resp.read(64)`），两个新外部主机不在既有
  币安契约覆盖范围内，代价一个参数；(b) 页面隐私开关（`frontend/index.html:1698,1726` 默认
  `privacyHidden: true`）只遮金额，不遮该 badge，真实住宅出口 IP 会常驻标题栏——是否需要跟随隐私
  开关遮蔽是 Human 的产品选择，非缺陷，不阻塞。重开条件：Human 需要对外分享页面截图时再定。
- R6 💭 计划引用「币安 API key 安全说明把 ipify 作为示例」；本次评审为只读、禁外呼，无法核实该外部
  引用，也不影响计划成立，仅记录为未验证事实。

### 未以新假设阻塞的声明（`AGENTS.md` §1 Scenario Admission）

R1/R2 均非模型自造的假设场景：R1 的锚点是三处可追溯代码路径（`server.py:1473-1483`、
`server.py:1712-1729`、`test_service_health.py:307/339/369/422`），R2 的锚点是计划自身的验收
条款与五个既有测试文件的调用形状。二者对本轮交付的具体影响与「为何必须本轮修」已在上文写明：
计划一旦定稿即被前后端两个实现者共用，且本计划的验收口径正好盖不住这两条。R5(b)、R6 为不进入
Human 摘要的观察项，不改变交付范围。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md`
  2. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan.md`
  3. `backend/app/server.py`（1473-1483、1712-1729 行）
  4. `backend/tests/test_service_health.py`（307、339、369、422 行）
  5. `backend/tests/test_ledger_flow_api.py`（69-84 行）
- 执行：Bookkeeper 核验本次计划复审结论并向 Human 报告；REWORK 成立时由 Planner（codex / OpenAI）
  按 R1、R2 修订 `evidence/public-ip-live-plan.md`，R3~R6 由 Planner 自行取舍。
- 关卡：修订后的计划须再走一次跨 provider 只读计划复审；通过后才准备 Kimi（前端）与
  Claude-GLM（后端）实现 dispatch。任何接受都不授权重启、部署、交易所访问或白名单变更。
- 不能假设的事实：
  - 不得假设实现者会自行推断 `run()` 与 `build_server()` 的注入先后；读法 B 在全部离线测试下静默。
  - 不得假设「新测试文件全绿」等于「共享 `server.py` 无回归」。
  - 不得假设当前运行中的手动前台进程会加载本 stage 的代码——本轮不重启、不部署。
  - 不得把本计划展示的公网 IP 当作币安实际观察到的出口 IP，或据此改动白名单。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: public-ip-live-plan-review-claude
执行结果: completed（完成）
结果摘要: 独立只读复审「真实公网出口 IP 展示」计划。范围、诚实性三态、安全边界、文档落点都对，但后端注入 seam 欠定义：三种合理读法里，一种会让四个既有测试变红，一种会让生产端点永久 503 且全部离线测试静默；而验收只跑新测试文件，正好两种都盖不住。结论 REWORK，两条必修均为计划文字级修订。
产物: [reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md]
检查结果: [1 固定 SHA 与 status 一致、diff 仅计划文件、未移动 HEAD: pass, 2 同源只读端点/固定主备源/标准库/2s 超时/5 分钟缓存/零新配置依赖线程重试: pass, 3 三态四字段可区分可用与过期与未知、不伪造、不泄漏异常: pass, 4 仅供 Human 核对、不证明币安所见、不驱动资金与白名单: pass, 5 前端复用刷新节奏、同源、失败不影响交易控件、无新 timer/localStorage: pass（R3 建议非阻塞）, 6 离线测试与活文档范围: fail（R2 验收只跑新测试文件盖不住共享 server.py 回归；R4 失败缓存 TTL 无测试）, 7 未以新假设阻塞、全部发现有代码锚点: pass, 8 后端注入 seam 定义充分性: fail（R1 build_server 复位与 run() 赋值先后未钉死）]
阻塞项: [R1 计划未钉死 run() 与 build_server 的注入先后（server.py:1473-1483 与 1712-1729；test_service_health.py:307/339/369/422 只接受两参 stub）, R2 验收标准第 6 条未纳入五个既有 server 装配测试文件]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md
修复要求: reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md
本地北京时间: 2026-08-12 19:58:39 CST
下一步模型: codex / GPT-5（Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-plan-review-claude.handoff.md；执行：Bookkeeper 核验计划复审并向 Human 报告；关卡：ACCEPT 后准备实现 dispatch，REWORK 后由 Planner 修订计划
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `ee0b0ac7fd3192ca223ccef744f41de60b554b5de6afd6324d82a45f0f439239`（`BOOKKEEPER_APPEND_ONLY` 前的精确字节）
- verified_at: `2026-08-12 20:02:52 CST`
- status revision checked: `5` → verified status revision `6`
- fixed review range: `git rev-parse` confirms base `983e900fc4af257c834774d0eb1bdc5dc2e111b7` and delivery `2625cf3a532f25d92a5f660aa2b845a6eaaaf009`; `git diff --name-status base..delivery` contains exactly `evidence/public-ip-live-plan.md`; `git diff --check base delivery` exits 0.
- result verification: review is well-formed `REWORK`, provider-isolated (OpenAI author / Anthropic reviewer), and its two blocking findings are supported by current code: `build_server()` resets handler dependencies before construction, `run()` invokes it with two positional arguments and only then wires sibling handler services, while existing startup tests monkeypatch that two-argument shape. The plan's named test command omits those affected server-wiring suites.
- status: non-accepting plan review recorded. This is pre-implementation plan correction, so `rework_count` remains `0`; no implementation dispatch may be prepared until the plan is revised and re-reviewed.

## Errata (append-only)
