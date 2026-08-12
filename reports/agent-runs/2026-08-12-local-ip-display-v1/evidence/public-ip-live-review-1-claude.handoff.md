# Task Handoff: public-ip-live-review-1-claude

## Source Report (author-only; immutable after task end)

- task_id: `public-ip-live-review-1-claude`
- role: `Reviewer / Review-1`（只读；创建本交接件为唯一写入）
- target model: `claude / Anthropic`（Opus 5，fresh independent read-only session）
- stage_id: `2026-08-12-local-ip-display-v1`
- created_at: `2026-08-12 21:27:03 CST`
- base_sha: `54b23cc904b9785e77f7f984f7bbdd4972de2f44`
- delivery_sha: `f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc`
- status.json revision checked: `12`（`current_task.id = public-ip-live-review-1-claude`，`state = dispatched`）
- 评审结论：**ACCEPT（接受）**

### Provider 隔离披露

本 reviewer 的 provider 是 `anthropic`；受审实现作者为 `claude_glm`（provider `zhipu_glm`，后端）
与 `kimi`（provider `moonshot`，前端 + 状态范围修复）。三者互不同源，`AGENTS.md` §3.5 与
`agents/roles.md` Reviewer/Isolation 的跨 provider 要求成立。**参与披露**：本 reviewer 与本阶段
计划复审 R1/R2 为同一 provider 会话身份，但计划复审不是实现或修复作者，未参与任何被审代码的
编写；本轮结论全部重新从固定 diff 与原始代码得出，计划复审 handoff 仅用作约束来源。

### 只读范围与执行边界

- 固定区间：`git diff 54b23cc904b9785e77f7f984f7bbdd4972de2f44..f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc`。
  两个 SHA 均经 `git rev-parse` 回显自身；每条命令都显式带该固定区间，**未使用移动 `HEAD`、
  未使用未提交工作区**（`git status --porcelain` 在评审开始与全部命令执行后两次均为空）。
- 本轮未发起任何网络请求、未访问币安、未读取凭据或扩展密钥环境、未启动/重启/部署服务、
  未触碰 live DB、未修改代码/文档/既有证据/`status.json`/`PROJECT_STATE.md`、未 commit/push/merge。
- **不能证明的事实（明示保留）**：仓库提交不代表当前 Human 手动前台进程已加载本交付；本轮
  未做任何真实公网 IP 查询，也不把该端点展示值当作币安实际观察到的出口 IP，不建议也不执行
  任何 API 白名单变更。

### 范围分层（产品交付 vs 阶段控制）

区间含 6 个提交、16 个文件。经 `git show --name-only` 逐个核对：

| 提交 | 分类 | 文件 |
|---|---|---|
| `13acc93` | 阶段控制（仅上下文） | R2 计划复审 handoff、后端 dispatch、`status.json` |
| `73f525d` | **产品交付（后端）** | `backend/app/server.py`、`backend/services/public_ip_service.py`、`backend/tests/test_public_ip_api.py`、`docs/api/public-market-contract.md`（+ 本任务原始输出/handoff/status） |
| `b373e98` | 阶段控制（仅上下文） | 后端 handoff 验证追加、前端 dispatch、`status.json` |
| `6d6678d` | **产品交付（前端）** | `frontend/index.html`、`frontend/self-check.js`（+ 原始 self-check 输出/handoff/status） |
| `c010fa6` | 阶段控制（仅上下文） | 前端 handoff 拒收追加、修复 dispatch、`status.json` |
| `f2ad1bf` | 阶段控制（仅上下文） | 状态范围修复 handoff、`status.json` |

产品代码只出现在 `73f525d` 与 `6d6678d`，无产品改动藏在控制提交里。受审产品面为
后端 `+22` 行、新服务 123 行、新测试 468 行、API 契约 `+67` 行、前端 36 行、自检 124 行。

### 后端核查（逐项对照 dispatch 验收 2）

- **构造期零 I/O、仅标准库**：`public_ip_service.py:25-30` 只 import `ipaddress`/`json`/
  `threading`/`time`/`urllib.request`/`datetime`（`json`、`datetime` 是解析主源与生成时间戳所
  必需，均属标准库，与 dispatch「只用标准库」不冲突）；`__init__`（`:46-51`）只做赋值，
  无请求、无线程、无环境变量、无持久化。
- **主备顺序与单次尝试**：`_try_sources`（`:76-83`）先主后备，各一次；`_read_primary`
  （`:85-98`）在异常 / 非 JSON / 非 dict / 缺或非字符串 `ip` / 校验不过时返回 `None` 才落到
  `_read_backup`（`:100-104`，去空白纯文本）。测试 `test_primary_exception_falls_back_to_backup_once`、
  `test_primary_invalid_json_falls_back_to_backup`、`test_primary_non_string_ip_falls_back_to_backup`
  均以 `fake.calls == [PRIMARY, BACKUP]` 钉死「恰好一次备用」。
- **2 秒 / 64 字节**：`_FETCH_TIMEOUT_SECONDS = 2`、`_MAX_READ_BYTES = 64`（`:34-36`），
  `_fetch`（`:106-111`）单次 `resp.read(64)`；`test_reads_at_most_64_bytes` 断言 `read_sizes == [64]`，
  `test_truncates_long_body_and_falls_back` 证明截断后走 fail-closed 回退而不是猜值。
- **5 分钟成功与失败缓存**：`get()`（`:53-60`）在同一把锁内判 TTL 并缓存 `_fetch_cycle` 的
  **任何**结果（含 `stale`/`unavailable`），因此失败同样被缓存；
  `test_success_cache_no_repeat_within_ttl`、`test_failure_cached_no_repeat_within_ttl`、
  `test_success_cache_refetches_after_ttl` 覆盖三侧。并发正确性：锁串行 miss，第二个线程醒来
  时缓存已新，最坏只多等一次外呼时长；`now` 在取锁前采样只会让差值更小，不会造成超 TTL 误服。
- **四字段三态契约**：`_fetch_cycle`（`:62-74`）三条返回路径字段集恒为
  `{status, public_ip, source, checked_at}`；`stale` 复用 `_last_success`，`checked_at` 不前进
  （`test_stale_after_success_then_failure_preserves_last_success` 直接断言等于首次成功值）；
  `unavailable` 三字段全 `null`，不猜测、不合成。
- **私网拒绝**：`_validate`（`:113-123`）先 `ipaddress.ip_address`（IPv4/IPv6 皆可），再拒
  `is_private`（含 loopback/link-local/reserved）。这是本交付里最值得肯定的一处：门户劫持
  返回的本地地址若被当成「公网出口 IP」，恰好会误导 Human 去改白名单。
  `test_private_ip_rejected_falls_back_then_unavailable` 与
  `test_private_primary_public_backup_succeeds` 双向覆盖。
- **无异常泄漏**：`_fetch` 的 `except Exception -> None`（`:110-111`）吞掉 URL/异常文本/请求头；
  路由只回三态字典。逐条走查所有可抛点（`decode` 用 `"replace"`、`json.loads` 与
  `ip_address` 均在 try 内）后确认 `get()` 对真实 `urlopen` 不会向 handler 抛出。
- **未注入 503 且不外呼**：`server.py:642-651` `_handle_public_ip` 先判 `None` 再决定是否调用
  `get()`；`test_http_503_when_not_injected` 断言 `503 {"error":"public_ip_unavailable"}`。
- **`no-store`**：`_send_ledger` 仅对 200 加 `Cache-Control: no-store`，503 不带（与计划一致；
  503 按 HTTP 语义默认不可缓存，无实际暴露）。`test_http_200_three_states_exact_fields_and_no_store`
  对三态各断言 `set(keys) == 四字段` 且头部为 `no-store`。
- **build_server 返回后注入的 seam（R1 约束）**：`server.py:1499` 每次构建复位为 `None`；
  `server.py:1733` 保持两参数 `build_server(config, service)`；`server.py:1740` 在其**返回后**
  创建并注入，与 `ledger_flow_service`（`:1736`）同一装配顺序，未新增参数或关键字。
  `test_build_server_resets_public_ip_service_each_call` 与
  `test_run_injects_public_ip_after_build_server`（包真实 `build_server` 以让复位真的执行，
  再断言 build 期间为 `None`、run 返回后是真 `PublicIpService`）把 R1 坏读法 A/B 都变成红灯。
  另核实全仓 `build_server` 生产调用点唯一（`server.py:1733`），其余均在 `backend/tests/`。

### 前端核查（逐项对照 dispatch 验收 3）

- **仅同源 GET**：`index.html:6886` `fetch('/api/system/public-ip', { cache: 'no-store' })`，
  无外域、无第二个请求；`self-check.js:8270` 把该路径加入同源白名单，`:8324-8325` 限定只允许
  `GET`，`:8341-8342` 的兜底分支保证任何非 GET 只读路由都会红。
- **三态与降级**：`:6890-6911` — `ok`/`stale` 仅在 `public_ip`/`source`/`checked_at` 均为非空
  字符串时成立，`unavailable`、HTTP 非 200、JSON 异常、字段类型错误、未知 `status` 全部落到
  中性「公网出口 IP 暂不可用」，不写页面错误区、不显示 URL/异常文本/假 IP。self-check `18b`
  段六个分支逐一断言可见文案与 `title`。
- **不泄露外部服务细节**：`title` 里只出现契约字段 `source`（`api.ipify.org` /
  `checkip.amazonaws.com`，本身就是 v0.19 公开契约的枚举值），无 URL、无异常、无请求头。
- **不阻塞快照/持仓/刷新**：`:6920` 在 `loadApi()` 内 fire-and-forget 调用，未 `await`，自身
  `.catch` 兜底（`:6907-6910`）；`loadApi` 的 `isRefreshing`/60 秒重排逻辑（`:6933-6945`）与它
  无耦合，因此最坏 4 秒外呼不进主链。
- **无新 timer / localStorage / 外域 fetch**：`loadPublicIp` 不注册任何 interval、不写
  localStorage；既有全局护栏 `self-check.js:8345-8362`（interval delay 白名单 60000/1000/2000 +
  localStorage 键白名单）在本次未放宽，仍对新代码生效——这一点我按「护栏是否被悄悄放宽」
  单独核对过，两处白名单均逐字未改。
- **页面明示边界**：`ok`/`stale` 的 `title` 都带「不能证明币安实际看到的出口 IP」
  （`:6897`、`:6900`），与前端 dispatch 验收 1 规定的载体一致；`unavailable` 态不展示任何 IP，
  故无须重复该边界。相关可读性观察见 O-2/O-3（不阻塞）。

### 证据与只读复跑

| 命令 | 结果 |
|---|---|
| `git rev-parse 54b23cc…` / `f2ad1bf…` | 回显自身；`git status --porcelain` 空（复跑前后各一次） |
| `git diff --check 54b23cc..f2ad1bf` | 退出码 `0` |
| `python3 -m pytest -q`（dispatch 指定六文件） | `168 passed in 71.30s`，与原始证据 `168 passed in 70.42s (0:01:10)` 一致 |
| `python3 -m pytest -q`（另四个触碰 `backend/app/server` 的既有文件：`test_account_cache_refresh_v1`、`test_borrow_api`、`test_frontend_field_binding`、`test_hedge_api`） | `132 passed in 52.77s`（本轮自加，验证共享 `server.py` 的复位行无回归） |
| `node frontend/self-check.js` | 「全部自检通过」，含 `[PASS] 公网出口 IP 初始加载请求与失败降级`、`[PASS] 公网出口 IP 三态展示与失败降级` |

原始证据核对：`evidence/public-ip-backend-claude-glm-pytest.txt` 为六文件命令的原始尾部输出；
`evidence/public-ip-frontend-kimi-self-check.txt` 为 self-check 原始输出，两条新 `[PASS]` 行在
第 5、29 行。所有测试全程 fake transport，未产生真实网络请求，复跑后工作树仍干净。

### 发现与范围三分类

**本轮无 `REWORK` 发现**，故无 `in-range` / `pre-existing-independent` /
`pre-existing-release-critical` 条目。以下四项为带重开条件的观察，按 `AGENTS.md` §1 不改变交付
范围、不进入 Human 摘要、不构成 `REWORK` 依据。

- **O-1（配置语义，非缺陷）** `run()` 无条件创建并注入 `PublicIpService`（`server.py:1740`），
  因此 `APP_OFFLINE=true` 启动的进程在页面命中该端点时**仍会外呼** ipify/checkip（每 5 分钟
  最多一次）。这不是回归：本仓 `offline` 的既有语义是「币安数据通道改读冻结原始数据」
  （`backend/services/snapshot_service.py:5-9`、`backend/config.py:40`），不是「进程零出网」，
  且已接受的计划明确不引入配置项与环境变量读取。契约文档那句
  「When the public-ip service is not injected (isolated/offline wiring), the route answers a
  fixed 503」在本仓「offline 测试」的语境下读得通（`build_server` 直连即未注入），但脱离语境
  可能被读成「offline 模式不外呼」。重开条件：Human 明确要求 `APP_OFFLINE=true` 时零第三方
  出网，或有人引用该句断言 offline 模式不做 IP 查询。
- **O-2（展示一致性）** `stale` 的 `title` 直接回显后端 UTC 串（如 `2026-08-12T09:00:00Z`），
  而页面其余时间统一走 `formatBeijing()`（`index.html:2064-2075`）显示北京时间。`Z` 后缀本身
  不构成假声明，且这正是前端 dispatch 验收 1 的字面要求，故不阻塞。重开条件：Human 实际把它
  误读成本地时间，或要求时间显示口径一致；最小改法是 `formatBeijing(Date.parse(checked_at))`。
- **O-3（边界可见度）** 「不能证明币安实际看到的出口 IP」只存在于 `title`（需悬停），徽标
  可见文本只有「公网出口 IP <IP>」。这与 dispatch 指定的载体一致，且 review-2 的发布就绪视角
  更适合判定是否够用。重开条件：Human 对外截图分享该页面，或未悬停即据徽标改白名单。
- **O-4（测试覆盖 nit）** 改写后的 self-check `3b` 段去掉了「badge 位于 `title-row` 内、紧邻
  `h1`」的容器断言，只保留「不得放入右侧刷新/排序控件区」。位置回归的覆盖面因此变窄一点。
  重开条件：标题区布局再次调整时把该断言补回。

### 未以新假设阻塞的声明（`AGENTS.md` §1 Scenario Admission）

本轮未用任何自行提出的假设场景阻塞交付。O-1..O-4 均附当前证据锚点与重开条件，且都不涉及
资金、订单、live gate、凭据或账务含义；无「必需证据缺失」情形——dispatch 要求的原始证据齐备
且可复跑。唯一无法在只读会话取得的外部事实（币安安全说明是否以 ipify 为示例、当前手动前台
进程是否加载本代码）不属于受保护关切，且交付本身已在代码注释、契约文档与三份 handoff 中
明示该边界。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md`
  2. `reports/agent-runs/2026-08-12-local-ip-display-v1/status.json`
  3. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-backend-claude-glm.handoff.md`
  4. `reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-frontend-kimi.handoff.md`
- 执行：Bookkeeper 核验本轮 Review-1 结论并追加同文件验证区
- 关卡：`ACCEPT` 后准备独立 Review-2（provider 须不同于 `zhipu_glm`、`moonshot`，且按
  `agents/roles.md` Review-2 默认路由选型）；`REWORK` 后准备最小修复
- 不能假设的事实：
  - 不得假设本 stage 代码已被当前手动前台进程加载——本轮未重启、未部署、未做任何运行时验证。
  - 不得把该端点展示的公网 IP 当作币安实际观察到的出口 IP，或据此改动 API 白名单。
  - 不得假设本轮 `ACCEPT` 授权合并、部署、重启、交易所访问或白名单变更；它只接受代码、契约、
    测试与接线层面的正确性。
  - 不得假设 O-1..O-4 已由 Review-2 覆盖或已作废；它们是带重开条件的观察项，不是待修发现。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: public-ip-live-review-1-claude
执行结果: completed（完成）
结果摘要: 以固定 SHA 完成独立只读 Review-1。后端服务、端点契约、注入 seam、前端三态接线与文档逐项核对通过；私网拒绝、失败缓存、fail-closed 回退与 R1 装配约束均有测试钉死。六文件 pytest 168 passed、另四个触碰 server.py 的既有文件 132 passed、self-check 全过、git diff --check 干净。无阻塞发现，结论 ACCEPT；四条带重开条件的观察项留档不阻塞。
产物: [reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md]
检查结果: [1 固定区间 54b23cc..f2ad1bf 与 status revision 12 一致、工作树干净、未用移动 HEAD、产品交付(73f525d/6d6678d)与四个阶段控制提交已分离: pass, 2 后端构造零 I/O 仅标准库、主备各一次、2s/64B、5 分钟成功+失败缓存、四字段三态、私网拒绝、异常不外泄: pass, 3 端点 200 带 no-store、未注入固定 503 不外呼、不并入快照；build_server 每次复位且 run() 仅返回后两参数注入(生产调用点唯一): pass, 4 前端仅同源 GET no-store、三态与 HTTP/schema/未知态降级、不泄外部细节、fire-and-forget 不阻塞快照持仓刷新: pass, 5 无新增 timer/localStorage/外域，既有全局护栏白名单逐字未放宽: pass, 6 只读复跑 168 passed + 132 passed + self-check 全过 + git diff --check 退出 0，与原始证据一致且工作树仍干净: pass, 7 API 契约 v0.19 与实现逐项相符，含四字段三态/主备源/2s/5min/no-store/仅供核对边界: pass, 8 无 REWORK 发现故无范围三分类条目；O-1..O-4 为带重开条件的观察，不阻塞不进摘要: pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md
修复要求: none
本地北京时间: 2026-08-12 21:27:03 CST
下一步模型: codex / GPT-5（Bookkeeper）
下一步任务: 读取：reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md；执行：Bookkeeper 核验 Review-1 结论；关卡：ACCEPT 后准备独立 Review-2，REWORK 后准备最小修复
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `4e2622d6be00c844d5a899acb267331373c698a1ca0882b6072d46869bd8685f`（`perl -0777 -ne '$marker = "<!-- BOOKKEEPER_APPEND_ONLY:"; $i = index($_, $marker); die "missing marker\\n" if $i < 0; print substr($_, 0, $i)' reports/agent-runs/2026-08-12-local-ip-display-v1/evidence/public-ip-live-review-1-claude.handoff.md | shasum -a 256`）
- verified_at: `2026-08-12 21:32:01 CST`
- status revision checked: `12`（`public-ip-live-review-1-claude` 为 `dispatched`）
- 结构、身份与范围通过：handoff 是该 reviewer 唯一新建的未跟踪文件；task/role/stage、Anthropic provider 隔离披露、`base_sha=54b23cc904b9785e77f7f984f7bbdd4972de2f44`、`delivery_sha=f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc` 均与 dispatch、status 和 `git rev-parse` 一致。`TASK_RESULT v2`、八项 `pass`、三条中文交接行及明确 `ACCEPT`／问题记录／`修复要求: none` 均合规。
- 证据与结论通过：报告引用固定 diff、原始测试、只读复跑及产品／控制提交分层；Bookkeeper 另执行 `git diff --check 54b23cc904b9785e77f7f984f7bbdd4972de2f44..f2ad1bfba56ec3f9822a4308c61e4ae1e27dc4dc`，通过。O-1..O-4 都有当前证据与重开条件，报告明确不构成 `REWORK` 或修复要求；其内容不改变现有交付范围或 Human 结论。
- 结论：Review-1 `ACCEPT` 已核验。准备独立 Review-2；其 provider `anthropic` 与两位实现／修复作者的 `zhipu_glm`、`moonshot` 均隔离。此结论不授权合并、部署、重启、真实公网查询或 API 白名单变更。

## Errata (append-only)
