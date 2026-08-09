# Task Handoff: pm-margin-repay-plan-review

## Source Report (author-only; immutable after task end)

- task_id: `pm-margin-repay-plan-review`
- role: `Reviewer`
- target model: `grok45`（provider `xai`）
- stage_id: `2026-08-09-pm-margin-repay-v1`
- created_at: `2026-08-09 22:39:42 CST`
- base_sha: `8092e94439b6a25a58d044d4c067950687b5d0e2`
- delivery_sha: `none`（计划评审，无实现交付提交）
- status_revision: `1`
- required_skill: `agents/skills/reality-checker.md`

### Scope of this review

只读评审实现计划 `evidence/pm-margin-repay-plan.md`，对照：

1. 币安官方 `POST /papi/v1/margin/repay-debt` 契约（中文文档页 + 官方 Python connector 注释）
2. 现有资产划转资金通路（`server.py` / `asset_transfer/store.py` / `hedge_open_live_client.py`）
3. 前端借款资产卡还款预览与划转 UI 状态机（`frontend/index.html`）
4. 公共契约中的统一账户余额与划转段落（`docs/api/public-market-contract.md`）
5. `PROJECT_STATE.md` 当前阶段边界与未授权项

未改任何实现、计划、status、PROJECT_STATE；未 commit/push；未访问真实币安账户。

### Official contract anchors (verified)

币安中文文档 `杠杆账户还款(TRADE)`：

- HTTP：`POST /papi/v1/margin/repay-debt`
- 请求权重：`3000`
- 参数：`asset` 必填；`amount` 可选；`specifyRepayAssets` 可选（逗号分隔）；`timestamp` 必填
- 单次还款价值 ≤ 50000 USD
- 未发送 `amount` → 偿还资产足够时偿还全部负债
- 发送 `amount` → 仅偿还指定数量
- 无论 `specifyRepayAssets` 是否含负债同币，系统仍优先用同币资产偿还
- 响应字段示例：`amount`、`asset`、`specifyRepayAssets[]`、`updateTime`、`success`

官方 Python connector（`margin_account_repay_debt`）同步：`Weight(IP): 3000`、`Security Type: TRADE`、同一套 amount / specifyRepayAssets / 同币优先语义。

TypeScript 社区类型 `PortfolioMarginRepayDebtResponse` 亦确认 `success: boolean`。

### Acceptance checks (dispatch)

#### 1. 币安契约冻结 — **pass**

计划准确冻结：

| 项 | 计划 | 官方/证据 |
|---|---|---|
| 端点 | `POST /papi/v1/margin/repay-debt` | 文档 + connector 一致 |
| `asset` / 可选 `amount` / `specifyRepayAssets` | 有 | 有 |
| 同币优先 | 明确禁止宣称「只扣 USDT」 | 官方同语义 |
| 50,000 USD | 本地不做错误硬挡，交易所终判 | 官方上限 |
| 权重 3000 | 有（文案写「IP 权重」；中文文档为请求权重 Order，connector 为 Weight(IP)；数值一致，非契约错误） | 3000 |
| 成功语义 | HTTP 200 + JSON 对象 + `success is true` + 响应负债资产与请求一致 | 响应含 `success`；严格判定正确 |
| 费用/滑点 | 明确未知，确认框如实提示 | 官方未披露 |

未把不公开费用/滑点当已知事实。

#### 2. `0` 本地语义 / 正数十进制 / 固定 USDT — **pass**

- 页面 `0` 仅本地「全部」信号；外发必须完全省略 `amount`，绝不发字面 `0`。
- 正数按原始十进制字符串外发；禁止 float。
- 服务端固定 `specifyRepayAssets=USDT`；拒绝客户端覆盖偿还资产字段。
- 与官方「省略 amount = 全还」一致。

备注（不阻塞）：实现时应把 `0.0` / `0.00` 等数值零按 fail-closed 处理（拒绝或等价「全部」二选一，禁止外发 `amount=0*`）。计划已要求「其余必须严格大于零」，足以避免错误外发。

#### 3. 闸门 / 幂等 / one-shot / 四态 — **pass**

相对已上线的资产划转，本计划更严且方向正确：

| 机制 | 计划 | 对照划转现状 |
|---|---|---|
| 独立闸门 | `APP_MARGIN_REPAY_ENABLED` 默认关 | 划转无独立开关（已接受风险） |
| 启用条件 | 显式开闸 + 非离线 + 凭证存在；否则 503 | 仅 offline + key |
| `confirm: true` | 必填 | 同 |
| SQLite 幂等 | `client_request_id` 唯一；`begin` 后 one-shot | 同模式 |
| 四态 | pending / succeeded / failed / unknown | 同 |
| 418/429 | `unknown`（禁止当 failed 诱导换号重试） | 同 |
| 歧义响应 | 网络/超时/5xx/非 JSON/字段矛盾/`success` 不严格 true → `unknown` | 同精神 + 针对 `success` 字段 |
| 自动重试 | 禁止 | 同 |

足以防止：同 UUID 重复外发、结果不明自动重试、默认就开实盘通道。

#### 4. 前后端接缝与刷新恢复 — **pass**

计划接缝与现码可对齐：

- **白名单**：`cross_margin_borrowed > 0` 的统一账户快照资产；前端按钮同样只在 `isPositiveBorrowedAmount` 时出现（`frontend/index.html` 还款控件）。
- **本地 GET** 恢复 SQLite 记录、零上游请求：划转没有 GET，还款计划主动补上，能关掉「浏览器丢响应后换新号重发」路径。
- **localStorage 按负债资产持久化未决请求号**：发送前写入；刷新后先 GET 恢复，不生成新号。这比当前划转「提交时才 `newTransferRequestId()`、无 localStorage」更安全。
- **succeeded → 强制账户快照刷新后再允许新还款**：复用划转已有 `onCacheRefresh` 思路，且比划转（成功后异步刷新、不锁下一笔）更严。
- **failed 可结束；pending/unknown 锁资产；unknown 须「我已到币安核对」解锁**：可直接复用划转 `locked` + 「我已核对」交互。
- **全局一笔提交**：匹配权重 3000 的并发风险。

明确无「刷新后自动用新 UUID 再还一次」的计划路径。

实现提示（不阻塞 ACCEPT，供 T1/T2 阅读）：

- UUID 生成须复用划转已验证的本地拼装 v4（`newTransferRequestId`），勿用环境 `crypto.randomUUID()`（实盘曾产出非法格式被后端 400）。
- T1 须在 `HedgeOpenLiveClient.ALLOWLIST` 增加精确 `("POST", "/papi/v1/margin/repay-debt") → https://papi.binance.com`，方法只接收服务端固定参数。
- GET 须挂到 `do_GET`；POST 挂到 `do_POST`；业务结论一律 HTTP 200 + body.status（与划转一致），仅校验/通道错误用 4xx/503。

#### 5. T1/T2 拆分与最小范围 — **pass**

- T1（后端/审计，`claude_glm`）：config 闸门、client allowlist + 签名 POST、store 幂等、server POST/GET、离线测试清单完整（0 省略 amount、固定 USDT、四态、闸门、GET 零上游、allowlist）。
- T2（前端/契约，`kimi`）：确认文案、防连点、localStorage+GET 恢复、成功强制刷新、docs 同步。
- 顺序：T1 核验后再派 T2；禁止并行共享工作树。
- 明确不抽「通用资金框架」、不顺带改开平借划仓。
- 非目标完整：无 `/repayLoan`、无 BNB 划转、无自动买币/轮询、无多偿还资产选择、无用 60s 缓存预判余额。

#### 6. 禁止实现期真实调用 / 后续授权边界 — **pass**

- 验证仅 fake client + 临时 SQLite + 静态前端检查。
- 部署、开闸门、真实还款、凭证变更均不在本阶段授权。
- review-2 `ACCEPT` 只交 Human 决策，不授权合并/部署/开闸/实盘。

#### 7. Handoff / 结论格式 — **pass**（本文件）

### Overall verdict

**ACCEPT**

计划准确映射官方 `repay-debt` 契约，以最小范围覆盖 Human 已定目标（欠款卡手动还款、`0`→省略 amount、首版固定 USDT 跨资产），并在实现前关闭了重复还款、误导扣款资产、歧义重发、默认开闸与无法验证的主要缺口。相对已接受风险的划转通路，默认关闭独立闸门 + 本地 GET 恢复 + 发送前持久化请求号是正确加严。

未发现满足 `AGENTS.md` §1 准入且必须本轮修订计划才能派发 T1 的 in-range 缺陷。下列为实现期应遵守的提示，不是 REWORK：

1. 数值零金额（`0.0` 等）fail-closed；
2. 复用划转 UUID 拼装，不用 `crypto.randomUUID()`；
3. allowlist 精确路径 + 固定 host；
4. 权重文案「IP/Order」不必改计划，实现注释可写 3000 weight。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
  2. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
  3. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
  4. `PROJECT_STATE.md`
- 执行：Bookkeeper 核验本 handoff 的 `ACCEPT`，封存计划评审通过状态，再准备 T1 后端实现 dispatch（Allowed Files 与计划 §5 T1 一致）；Human 启动该 T1 终端。
- 关卡：仅在 Bookkeeper 核验本 `ACCEPT` 后可派发 T1；T1 完成并核验前不得派 T2；任何部署、开启 `APP_MARGIN_REPAY_ENABLED`、真实还款仍须后续 Human 单独授权。
- 不能假设的事实：
  - 本 `ACCEPT` 不授权写代码、合并、部署、开闸门或真实币安还款；
  - 币安无客户端幂等键、无按本地请求号查询还款结果的公开接口；
  - 跨资产转换价格/手续费/滑点未知；同币资产仍优先于 `specifyRepayAssets=USDT`；
  - 当前服务仍以手动前台进程运行；计划评审通过 ≠ 运行中服务已具备还款能力。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: pm-margin-repay-plan-review
执行结果: completed（完成）
结果摘要: 计划评审 ACCEPT。repay-debt 契约、0→省略 amount、固定 USDT、默认关闸、SQLite 幂等、四态与刷新恢复均充分；可派 T1，仍禁部署/开闸/实盘。
产物: [reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md]
检查结果: [1.币安契约冻结 pass；2.0语义与固定USDT pass；3.闸门幂等四态 pass；4.接缝与刷新恢复 pass；5.T1/T2最小范围 pass；6.禁实盘与授权边界 pass；7.handoff格式 pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-09 22:39:42 CST
下一步模型: codex（Bookkeeper；核验本 handoff）
下一步任务: 读取：reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json；执行：Bookkeeper 核验 ACCEPT 并准备 T1 后端实现 dispatch；关卡：仅 ACCEPT 核验后可派 T1，部署/开闸/真实还款仍须 Human 另授
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `852b3b537dae980bebd41457a719bb9bc501bf8a658430061c5c1fcfe742672f`
- verified_at: `2026-08-09 22:43:23 CST`
- verified_status_revision: `1`
- verifier: `codex`（Bookkeeper）
- result: `ACCEPT verified`
- identity_check: task、Reviewer/xai、stage、status revision、base SHA 与
  `status.json` 一致；`delivery_sha: none` 符合只读计划评审。
- create_only_check: handoff 是唯一未跟踪新文件；原 dispatch 记录的同一路径前置检查为
  absent；核验前无 Bookkeeper append 区块，未覆盖任何既有文件。
- source_check: marker 恰好一个；上述 SHA-256 按 marker 前全部原始字节计算；Human Brief
  的 `[TASK_RESULT v2]`、七项 pass、`评审结论: ACCEPT（接受）`、`问题记录: none`、
  `修复要求: none` 和可执行下一步均完整。
- evidence_check: 端点为 `POST /papi/v1/margin/repay-debt`；计划、官方契约要点、现有
  资产划转/前端接缝和禁止实盘边界均被逐项核验，无阻塞项。
- reproducible_checks: `grep -c '<!-- BOOKKEEPER_APPEND_ONLY:' <handoff>`（追加前为 1）；
  `perl -0ne 'print $1 if /\A(.*?)<!-- BOOKKEEPER_APPEND_ONLY:/s' <handoff> | shasum -a 256`；
  `git cat-file -e 8092e94439b6a25a58d044d4c067950687b5d0e2^{commit}`；
  `git merge-base --is-ancestor 8092e94439b6a25a58d044d4c067950687b5d0e2 HEAD`。
- next: 计划评审封存为通过；准备 T1 后端实现 dispatch。此验证不授权部署、开闸或真实
  币安还款。
