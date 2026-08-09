# Task Handoff: pm-margin-repay-review-1-rerun

## Source Report (author-only; immutable after task end)

- task_id: `pm-margin-repay-review-1-rerun`
- role: `Reviewer`
- target model: `codex`（provider `openai`）
- stage_id: `2026-08-09-pm-margin-repay-v1`
- created_at: `2026-08-10 00:59:00 CST`
- base_sha: `ee0d5320b319a5bacc708eb8680e8156328db338`
- delivery_sha: `5a81bdc1c40238053a07736faa64b34cab294987`
- status_revision: `5`
- required_skill: `agents/skills/code-reviewer.md`

### Review scope and isolation

以固定提交范围
`ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
只读复核完整 T1+T2 delivery：后端固定资金出口、金额语义、服务端校验、SQLite 幂等与
四态、前端确认/持久化/恢复、公共契约、测试 oracle 及前后端接缝。区间内 stage 控制文件
仅作上下文，不作为产品交付发现。

当前 Reviewer 为 OpenAI/Codex；T1 实现 provider 为 `zhipu_glm`，T2 实现 provider 为
`moonshot`，满足 review-1 跨 provider 隔离。本轮未修改代码、测试、文档、状态或既有证据；
未启动服务、未读取凭证、未访问真实账户、未部署、未开闸、未发起还款、未 commit/push，
也未启动 review-2。唯一写入是 dispatch 指定且创建前不存在的本 handoff。

Human 已在原 review-1 handoff 的 append-only 勘误中明确撤销“必须提交
`_build_margin_repay_client` 组合矩阵测试”的要求，并接受当前源码、已有测试和先前只读
probe；因此本轮没有把原 R1 换名重提。该勘误不改产品交付 SHA，也不消耗 `rework_count`。

### Official contract verification

已于 2026-08-10 复核[币安官方 Portfolio Margin 还款接口](https://developers.binance.com/en/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt)：

- 签名 `POST /papi/v1/margin/repay-debt`，host `https://papi.binance.com`，IP 权重 3000；
- `asset` 必填，`amount` 与 `specifyRepayAssets` 可选；省略 `amount` 时，在指定偿还资产
  足够的前提下偿还该资产全部借款；发送 `amount` 时只偿还该指定数量；
- 系统始终先使用负债同币资产，再使用指定偿还资产；单次偿还资产价值不超过 50,000 USD；
- 响应模型列出 `amount`、`asset`、`specifyRepayAssets[]`、`updateTime`、`success`。

实现与契约一致：固定 host/path，页面精确 `"0"` 映射为省略上游 `amount`，正十进制保持
原字符串，服务端固定 `specifyRepayAssets=USDT`，调用 one-shot 且不重试。响应只在 HTTP
200、JSON 对象、`success is True` 且 `asset` 匹配时归 `succeeded`；`amount` 或
`updateTime` 缺失时分别保留 `repaid_amount=null` / `update_time=null`，不编造字段。

### Read-only live-evidence reconciliation

本轮只核对仓库内已记录证据，不重新访问服务或账户：

- XLM：已记录请求数量 `5`，审计记录 `succeeded` 且 `repaid_amount="5"`，与正数原样透传、
  成功后展示实际数量的代码路径一致。
- INJ：已记录请求数量 `"0"`，上游调用省略 `amount`，仅一笔请求且为 `succeeded`；随后完整
  账户快照的 `cross_margin_borrowed="0.0"`。币安成功响应没有返回 `amount`，所以本地
  `repaid_amount=null`；代码和文档只在该值存在时展示“实际偿还 <数量>”，未把缺失值编成
  精确数量。
- `repay_asset="USDT"` 表示服务端指定的后备偿还资产。确认文案和成功文案都明确“负债同币
  资产仍优先”，没有宣称实际只扣 USDT。

INJ 的本地还款记录自身不能证明精确偿还数量；“全部借款已清”由请求语义、交易所成功结果
和刷新后的完整账户快照共同支持。该限制已在 `PROJECT_STATE.md` 留存，不影响本轮代码正确性
结论，也不授权新增实盘。

### Acceptance-check results

1. **固定出口与金额语义 — pass**：精确 allowlist/host、签名 POST、固定 USDT、`0` 省略
   `amount`、正数字符串透传；无 `/repayLoan`、float、自动重试或 caller 注入 host/path/
   偿还资产。
2. **修订后的配置边界 — pass**：当前源码仍是显式开闸、非 offline、双凭证才注入 client，
   且独立于 hedge executor；Human 已撤销 committed 组合矩阵测试要求，未将原 R1 重提。
3. **服务端校验与幂等 — pass**：请求体恰四字段，confirm/UUID/金额/未知字段/借款资产白名单
   fail closed；SQLite 主键先落 `pending`，同 UUID 顺序或并发重复最多外发一次。
4. **严格四态与不重试 — pass**：严格成功条件成立才 `succeeded`；普通 4xx 为 `failed`；
   408/418/429/5xx/transport/非典型或矛盾 200 为 `unknown`；全部 one-shot 落库。
5. **前端接缝 — pass**：确认后才生成 UUID，POST 前写 localStorage，只认 `body.status`；同号
   GET 恢复一次、不轮询，unknown 留锁，成功仅在完整快照刷新后解锁。
6. **XLM/INJ 证据与诚实展示 — pass**：XLM 精确数量闭环；INJ `repaid_amount=null` 时不展示
   虚构实际数量，完整刷新后的负债为零；界面不把固定 USDT 说成实际只扣 USDT。
7. **回归和范围 — pass**：规定的 diff、前端自检、定向 191 项及全量 1683 项均通过；未发现
   新的 in-range blocker 或需上交的范围外 release-critical 事项。
8. **handoff 与权限边界 — pass**：本文件使用固定直接 SHA 和明确 verdict；未修改交付、状态
   或既有证据，未执行任何新增实盘、合并、推送或下一模型启动。

### Commands and raw results

```text
test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md
=> PASS（创建前路径不存在）

git rev-parse ee0d5320b319a5bacc708eb8680e8156328db338
=> ee0d5320b319a5bacc708eb8680e8156328db338

git rev-parse 5a81bdc1c40238053a07736faa64b34cab294987
=> 5a81bdc1c40238053a07736faa64b34cab294987

git diff --check ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987
=> PASS（无输出，exit 0）

node frontend/self-check.js
=> 全部自检通过，exit 0

python3 -m pytest -q backend/tests/test_config.py backend/tests/test_hedge_open_live_client.py backend/tests/test_margin_repay.py backend/tests/test_asset_transfer.py backend/tests/test_service_health.py backend/tests/test_frontend_field_binding.py
=> 191 passed in 58.22s

python3 -m pytest -q backend/tests
=> 1683 passed in 153.62s (0:02:33)

git diff --exit-code 5a81bdc1c40238053a07736faa64b34cab294987 -- backend/app/server.py backend/config.py backend/margin_repay backend/services/hedge_open_live_client.py backend/tests/test_config.py backend/tests/test_frontend_field_binding.py backend/tests/test_hedge_open_live_client.py backend/tests/test_hedge_purity.py backend/tests/test_margin_repay.py docs/api/public-market-contract.md frontend/index.html frontend/self-check.js
=> PASS（delivery 后产品文件无变化，exit 0）
```

### Overall verdict

**ACCEPT**

修订要求下未发现阻塞问题。固定出口、金额语义、幂等 one-shot、严格四态、前端确认/恢复/
刷新接缝和诚实展示均满足验收；全部规定回归通过。原 review-1 的唯一 R1 是 Human 已撤销的
测试证据要求，不是当前代码流程缺陷。本 `ACCEPT` 只通过 review-1 关卡，允许 Bookkeeper
核验并准备独立 review-2；不等于 review-2、最终 Human 接受、合并、推送、部署、开闸或实盘
授权。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md`
  2. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
  3. `PROJECT_STATE.md`
- 执行：Bookkeeper 核验本 `ACCEPT`、固定 SHA、测试结果和权限边界；核验通过后更新 stage
  状态并准备独立 review-2 dispatch，由 Human 在 fresh 终端启动。
- 关卡：review-1 只有经 Bookkeeper 核验后才可准备独立 review-2；review-2 必须明确
  `ACCEPT` 才能进入最终 Human 决策。当前不授权新增实盘、合并、推送、部署或开闸。
- 不能假设的事实：本轮没有重新访问真实账户；XLM/INJ 是仓库内已记录证据。INJ 本地记录的
  `repaid_amount=null`，不得仅凭该记录宣称精确偿还数量；精确数量缺失不等于还款失败。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: pm-margin-repay-review-1-rerun
执行结果: completed（完成）
结果摘要: Review-1 修订要求后复核通过：固定资金出口、0 省略 amount、固定 USDT、one-shot、幂等四态和前端恢复流程均正确；XLM/INJ 已记录实测与代码一致，INJ 缺少 repaid_amount 时页面不编造数量。规定测试全绿，明确 ACCEPT，可由 Bookkeeper 准备独立 review-2。
产物: [reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md]
检查结果: [1.固定PAPI出口/0省略amount/固定USDT/one-shot pass；2.修订后的配置边界 pass；3.服务端校验与SQLite幂等 pass；4.严格四态与不重试 pass；5.前端确认/持久化/同号恢复/成功刷新 pass；6.XLM/INJ证据与诚实展示 pass；7.diff/前端自检/定向191项/全量1683项 pass；8.handoff与未授权边界 pass]
阻塞项: [none]
评审结论: ACCEPT（接受）
问题记录: none
修复要求: none
本地北京时间: 2026-08-10 00:59:00 CST
下一步模型: codex（Bookkeeper；核验 ACCEPT 并准备独立 review-2 dispatch）
下一步任务: 读取：reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1-rerun.handoff.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json、PROJECT_STATE.md；执行：Bookkeeper 核验 ACCEPT、固定 SHA、测试结果和权限边界，核验通过后更新 stage 状态并准备独立 review-2 dispatch，由 Human 在 fresh 终端启动；关卡：review-2 必须明确 ACCEPT 才能进入最终 Human 决策，当前不授权新增实盘、合并、推送、部署或开闸
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（由 Bookkeeper 核验后追加；Reviewer 不写。）

## Errata (append-only)

（任何更正只可追加；不得改写 Source Report、Human Brief 或 verdict。）

## Bookkeeper Verification (Bookkeeper append-only, actual)

- source_sha256: `8e0330031ab3001db9c46a8dc7278d55126c1d58fbddc954e19bf2bbbfe416e1`
- verified_at: `2026-08-10 01:05:12 CST`
- verified_status_revision: `5`
- verifier: `codex`（Bookkeeper）
- task_base_sha: `ee0d5320b319a5bacc708eb8680e8156328db338`
- delivery_sha: `5a81bdc1c40238053a07736faa64b34cab294987`
- result: `ACCEPT verified; eligible for independent review-2 dispatch`
- identity_and_scope: task、Reviewer/OpenAI、stage、revision、固定 SHA 与 dispatch/status
  一致；handoff 是 dispatch 唯一 create-only 文件，Source Report、Human Brief 与 verdict
  完整且未改写。
- verdict: 明确 `评审结论: ACCEPT（接受）`，`问题记录: none`、`修复要求: none`、八项
  acceptance checks 全部 pass；原 review-1 R1 已按 Human 验收勘误撤销，没有修复提交，
  `rework_count=0`。
- independent_checks:
  - `git diff --check ee0d532..5a81bdc` → pass
  - `git diff --exit-code 5a81bdc -- <全部产品交付文件>` → pass
  - `node frontend/self-check.js` → 全部自检通过
  - 定向六文件 pytest → `191 passed in 57.57s`
- evidence_boundary: XLM/INJ 实盘事实只按仓库已记录证据核验；未访问账户、未读取凭证、未
  请求本地服务、未重启、未开关闸门、未发送还款。
- next_review_isolation: Human 指定 `opus5`（provider `anthropic`）执行 review-2；与 T1
  `zhipu_glm`、T2 `moonshot` 实现 provider 均不同，满足最终评审隔离。
