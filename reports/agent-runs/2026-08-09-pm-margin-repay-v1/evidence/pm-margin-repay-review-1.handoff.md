# Task Handoff: pm-margin-repay-review-1

## Source Report (author-only; immutable after task end)

- task_id: `pm-margin-repay-review-1`
- role: `Reviewer`
- target model: `codex`（provider `openai`）
- stage_id: `2026-08-09-pm-margin-repay-v1`
- created_at: `2026-08-10 00:30:19 CST`
- base_sha: `ee0d5320b319a5bacc708eb8680e8156328db338`
- delivery_sha: `5a81bdc1c40238053a07736faa64b34cab294987`
- status_revision: `4`
- required_skill: `agents/skills/code-reviewer.md`

### Review scope and isolation

以固定提交范围
`ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
只读检查完整 T1+T2 delivery：后端资金出口、配置闸门、SQLite 幂等与四态、前端确认/
持久化/恢复、公共契约、测试 oracle 和前后端接缝。区间内 stage dispatch、status、
`PROJECT_STATE.md` 与 Bookkeeper 控制提交仅作上下文，不作为产品交付发现。

当前 Reviewer 为 OpenAI/Codex；T1 实现 provider 为 `zhipu_glm`，T2 实现 provider 为
`moonshot`，满足 review-1 跨 provider 隔离。未修改代码、测试、文档、状态或既有证据；
未启动服务、未读凭证、未访问真实账户、未部署、未开还款闸门、未 commit/push，也未启动
review-2。

### Official contract verification

已于 2026-08-10 复核[币安官方 Portfolio Margin 交易接口文档](https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt)：

- 签名 `POST /papi/v1/margin/repay-debt`，host `https://papi.binance.com`，IP 权重 3000；
- `asset` 必填，`amount` 与 `specifyRepayAssets` 可选；省略 `amount` 才是全额偿还；
- 同币资产始终优先使用，单次价值不超过 50,000 USD；响应含 `amount`、`asset`、
  `specifyRepayAssets[]`、`updateTime`、`success`。

实现的固定 host/path、`"0"` → 省略上游 `amount`、正十进制原字符串、服务端固定
`specifyRepayAssets=USDT` 与诚实用户文案均与该契约一致。

### Finding R1 — in-range blocker

🔴 **资金出口组合根闸门缺少 dispatch 明确要求的可执行回归 oracle**

- 范围分类：`in-range`。
- 根因名称：`资金出口组合根闸门缺少可执行回归 oracle`。
- 要守住的 invariant：`_build_margin_repay_client(config)` 当且仅当
  `margin_repay_enabled=True`、`offline=False`、hedge key 与 secret 均非空时返回 client；
  该结果必须独立于 `hedge_executor`。
- 当前代码证据：`backend/app/server.py:1618-1638` 实现了上述判断。本 review 的一次性只读
  probe 覆盖 `gate_off`、`offline`、`missing_key`、`missing_secret`、
  `enabled_executor_disabled` 五个组合，当前结果分别为不注入、不注入、不注入、不注入、
  注入且 `credentials_present=True`；所以这里没有主张当前产品代码已误开闸。
- 缺口证据：`reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md:106-115`
  把“配置默认值和启动注入有回归测试”列为 T1 最低离线证据；T1 Human Brief 又明确声称
  `offline/key/secret/独立闸门不受HEDGE_EXECUTOR控制` 为 pass。但
  `backend/tests/test_config.py:246-266` 只断言默认值和环境解析，
  `backend/tests/test_margin_repay.py:461-472` 只断言 handler 在 client 缺失时返回 503；
  全仓 `rg -n '_build_margin_repay_client' backend/tests` 无命中。当前全绿测试没有执行组合根
  构造函数，因而不能证明所声称的启动注入回归保护。
- 实际影响：这是还款资金出口的唯一客户端注入闸门。以后若误删 secret 条件、把开关与
  `APP_HEDGE_EXECUTOR` 耦合、或在 gate/offline 条件上写反，现有测试仍可能全绿；HIGH_RISK
  交付缺少 dispatch 要求的必需证据，按 fail-closed 不能进入 review-2。
- 最小修复：仅在现有 `backend/tests/test_margin_repay.py` 增加直接针对
  `_build_margin_repay_client` 的参数化/分支测试，至少覆盖：关闸但其余条件齐全 → `None`；
  开闸但 offline → `None`；分别缺 key/secret → `None`；开闸 + 非离线 + 双凭证且
  `hedge_executor="disabled"` → client 存在且凭证完整。不要改产品代码，除非新测试发现真实
  不一致；不要新增抽象、状态、依赖或网络调用。
- false-positive effect：若未来有意改变上述资金闸门契约，该测试会先阻断交付并要求重新授权，
  这正是 fail-closed 预期；测试只构造 client、不发网络，不会产生运行侧误报或外部副作用。

### Acceptance-check results

1. **币安出口和金额语义 — pass**：精确 allowlist/host、签名 one-shot、固定 USDT、`0`
   省略 amount、正数字符串透传；无 `/repayLoan`、float、重试或可注入 host/path。
2. **默认关闭与服务端校验 — pass（当前行为）**：配置默认 false；只在显式开闸、非 offline、
   双凭证时构造 client，独立于 hedge executor；confirm/UUID/金额/未知字段/借款白名单均
   fail closed。组合根的回归证据缺口单列 R1，并计入检查 6 的 fail。
3. **幂等和结果不明安全 — pass**：SQLite 主键先 pending、锁外 one-shot、同 UUID 并发只
   外发一次；200 严格成功、普通 4xx failed、408/418/429/5xx/transport/非 JSON/矛盾 200
   unknown，全部落库且不重试。
4. **前后端契约与刷新恢复 — pass**：body 恰四字段且只认 `body.status`；确认后生成 UUID、
   POST 前 localStorage、提交期全局防连点；同号 GET 一次、不轮询；failed 结束，
   pending/unknown 锁+人工核对，succeeded 仅 complete 刷新后解锁对应资产。
5. **用户文案和公共契约 — pass**：确认框明确同币优先、USDT 后备、转换成本未披露与约
   60 秒缓存滞后；v0.17 与代码一致并明确不授权部署/开闸/实盘。
6. **测试 oracle 与回归 — fail**：所有规定命令通过，且发送前持久化、固定 body、四态、
   并发幂等、allowlist、恢复和成功刷新均有真实断言；但启动组合根闸门没有提交级回归
   oracle，未满足计划最低证据与 T1 回执声称的覆盖，见 R1。
7. **范围和结论 — pass**：delivery 只加入批准的手动还款 v1 与控制上下文；未夹带部署、
   开闸、自动还款、多偿还资产或其他资金路径。未发现范围外需上交事项。
8. **handoff — pass**：本文件使用固定直接 SHA、记录原始命令结果、明确 `REWORK` 和最小
   修复要求。

### Commands and raw results

```text
test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md
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
=> 191 passed in 57.64s

python3 -m pytest -q backend/tests
=> 1683 passed in 152.81s (0:02:32)

rg -n "_build_margin_repay_client" backend/tests
=> 无输出（exit 1；没有 committed test 引用该组合根函数）
```

一次性组合 probe 的完整结果（只构造 client，零网络）：

```text
gate_off False None
offline False None
missing_key False None
missing_secret False None
enabled_executor_disabled True True
```

每行第二列为 `client is not None`，第三列为 client 存在时的
`credentials_present`。该 probe 证明当前代码行为正确，但不是可持续的提交级回归 oracle，
不能替代 R1 要求的测试。

### Overall verdict

**REWORK**

只发现一条 `in-range` blocker：必需的资金出口组合根闸门回归证据缺失。其余代码、契约、
接缝与规定测试通过；没有发现当前实现会误发、重复外发、把歧义结果误判为失败/成功，或
夹带部署/开闸/实盘。补最小测试并提交后必须回到独立 review-1；review-1 明确 `ACCEPT`
前不得准备 review-2。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md`
  2. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
  3. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
  4. `backend/app/server.py`
  5. `backend/tests/test_margin_repay.py`
- 执行：Bookkeeper 核验本 `REWORK`，记录根因“资金出口组合根闸门缺少可执行回归 oracle”，
  按规则递增本交付的 `rework_count`，准备仅补上述最小回归测试的修复 dispatch；由 Human
  启动修复终端。
- 关卡：修复提交与全套规定测试经 Bookkeeper 核验后，返回独立 review-1；review-1 明确
  `ACCEPT` 前不得准备 review-2，仍不授权合并、部署、开闸或真实还款。
- 不能假设的事实：当前产品代码 probe 行为正确不等于回归 oracle 已存在；本轮只要求补测试，
  不授权顺手改产品逻辑或扩大文件范围。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

```text
[TASK_RESULT v2]
任务 ID: pm-margin-repay-review-1
执行结果: completed（完成）
结果摘要: Review-1 结论 REWORK：当前代码与全部规定测试通过，未发现误发或重发缺陷；但资金出口组合根没有提交级闸门回归测试，未证明“仅显式开闸+非离线+双凭证注入，且独立于 APP_HEDGE_EXECUTOR”。按 HIGH_RISK fail-closed，补最小参数化测试后重审。
产物: [reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md]
检查结果: [1.币安固定出口/0省略amount/固定USDT/one-shot pass；2.当前默认关闸与服务端fail-closed行为 pass；3.SQLite幂等与严格四态 pass；4.前后端确认/先持久化/恢复/成功刷新接缝 pass；5.诚实文案与v0.17契约 pass；6.测试oracle fail（缺_build_margin_repay_client组合根闸门回归）；7.交付范围与未授权边界 pass；8.handoff格式与固定SHA pass]
阻塞项: [R1 in-range：资金出口组合根闸门缺少可执行回归 oracle；仅补 backend/tests/test_margin_repay.py 的最小参数化测试后返回 review-1]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md
修复要求: reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md
本地北京时间: 2026-08-10 00:30:19 CST
下一步模型: codex（Bookkeeper；核验 REWORK 并准备最小修复 dispatch）
下一步任务: 读取：reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md、reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json、reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md、backend/app/server.py、backend/tests/test_margin_repay.py；执行：Bookkeeper 核验 REWORK、记录根因、递增本交付 rework_count，并准备仅补组合根闸门参数化测试的修复 dispatch，由 Human 启动；关卡：修复核验后返回独立 review-1，明确 ACCEPT 前不得准备 review-2，仍不授权合并/部署/开闸/实盘
[/TASK_RESULT]
```

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

（由 Bookkeeper 核验后追加；Reviewer 不写。）

## Errata (append-only)

（任何更正只可追加；不得改写 Source Report、Human Brief 或 verdict。）

### 2026-08-10 Human acceptance correction

- Human 明确撤销“必须为 `_build_margin_repay_client` 提交组合根闸门参数化回归测试”这一
  验收要求，并接受当前代码、已有测试以及 Reviewer 一次性只读组合 probe 作为该设计的
  足够证据；不补该测试，不修改产品代码。
- 本勘误只更正验收要求，不把上方 Reviewer 原始 `REWORK` 改写成 `ACCEPT`。按
  `AGENTS.md` §3，仍须由新的独立 review-1 在修订后的要求下给出明确 verdict。
- 这是 Human requirement refinement，不是交付缺陷修复；没有 repair delivery，
  `rework_count` 保持 `0`。

## Bookkeeper Verification (Bookkeeper append-only, actual)

- source_sha256: `c30113fa54baca8a50fa18abfb819044b9796444d6b0ecc492a4058dd8d06879`
- verified_at: `2026-08-10 00:46:23 CST`
- verified_status_revision: `4`
- verifier: `codex`（Bookkeeper）
- task_base_sha: `ee0d5320b319a5bacc708eb8680e8156328db338`
- delivery_sha: `5a81bdc1c40238053a07736faa64b34cab294987`
- result: `verified REWORK; sole blocker removed by later Human acceptance correction`
- identity_and_scope: task、Reviewer/OpenAI、stage、revision、固定 SHA 与 dispatch/status
  一致；handoff 是 dispatch 允许的唯一 create-only 文件，Source Report、Human Brief 与原始
  verdict 未改写。
- finding_verification: `_build_margin_repay_client` 当前组合行为正确，原始 R1 只主张缺少
  committed 组合测试，不主张误开闸、误发或重发；该事实与 handoff 的一次性 probe、源码及
  `rg -n "_build_margin_repay_client" backend/tests` 无命中一致。
- independent_checks:
  - `git diff --check ee0d532..5a81bdc` → pass
  - `node frontend/self-check.js` → 全部自检通过
  - 定向六文件 pytest → `191 passed in 57.78s`
- human_correction_effect: Human 已删除 R1 所依赖的计划最低证据要求，因此不派修复、不改
  测试、不递增 `rework_count`；原 `REWORK` 仍不是 `ACCEPT`，下一步只准备一份修订要求后的
  fresh review-1 dispatch。
