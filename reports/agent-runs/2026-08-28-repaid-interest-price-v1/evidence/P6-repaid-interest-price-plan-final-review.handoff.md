# Task Handoff: P6-repaid-interest-price-plan-final-review

## Source Report (author-only; immutable after task end)

- task_id: `P6-repaid-interest-price-plan-final-review`
- role: `Reviewer / Plan Review (pre-implementation)`（独立新鲜只读计划复评）
- target model: `gpt-5.6-sol`（provider `openai`）
- stage_id: `2026-08-28-repaid-interest-price-v1`
- created_at: `2026-08-28 21:52:29 CST`
- base_sha: `e93af61630e87a759d8820d33fef61789dac1dcd`
- delivery_sha: `4e3fba75a64326a2b57bfe4727b010e7988fef83`
- status anchor: revision `12`、checkpoint `p5-plan-verified-p6-ready`、current task
  `P6-repaid-interest-price-plan-final-review`
- reviewed range: `e93af61630e87a759d8820d33fef61789dac1dcd..4e3fba75a64326a2b57bfe4727b010e7988fef83`
- reviewed artifact: `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- required_skill: `agents/skills/software-architect.md`（仅此一个）

### Isolation and fixed-range verification

本会话是独立新鲜 Reviewer 会话，不是计划作者、实现者或本 stage 的 Bookkeeper `codex`
会话。P5 计划作者为 `opus5` / `anthropic`，跨 provider 隔离成立。本 stage 至今没有实现代码。

固定区间通过 Git 独立核验：两个 SHA 均为 commit；`git diff --name-status` 只返回
`M reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`；
`git diff --numstat` 为 `260 303`；`git diff --check` 无输出。评审读取的是
`git show 4e3fba75...:<path>`，未以移动 `HEAD` 或工作区版本替代。

### Verdict

`REWORK`。

计划的核心架构已收敛：删除旧归零证明链、Human 约定终态、资金缝隙只保留异常隔离内存读、
单一折算权威、两列 additive schema、STORJ 人工例外边界和两张同根因扫描表均成立。R9 明确
通过：`0 + succeeded` 是规范性产品事件而非外部事实证明，不构成对根因 A 的实质豁免。

但 R4/R6 的控制文本仍有一个 `in-range` 来源契约发现：计划一处把 `fresh` 的源码语义写错，
另一处把 `repay_price_source` 限定为自动来源/NULL，却又要求后续写入
`manual_correction`。这会让实现者和 API 文档面对两个不一致的有效定义。该问题很小，
不需要重做架构或根因扫描，但必须在计划阶段统一；实现后代码评审不应替 Planner 猜控制契约。

### R1-R9 independent findings

#### R1 — pass

最终实现范围只保留两列与内存取价。三个 `repay_after_*` 列、签名余额 GET、缺席即零、
`debt_cleared()`、a/b/c、`coverage_for_window` 回补门、跨库推断、
`--assume-debt-zero`、通用 K 线脚本均只在删除记录/同根因审计/非目标中出现，没有被改名后
留在产品实现清单。最终 bounded 文件表不含脚本。

#### R2 — pass（带一条非阻塞措辞校正）

唯一谓词精确为 `record["amount"] == "0" and record["status"] == "succeeded"`；非零部分
与全部非成功态保持动态。匹配规则以 `settlement_ms >= accrued_at_ms` 明确同毫秒边界，终态间
再以 `client_request_id` 排序；re-borrow 后新行只会匹配下一条终态。现有
`backend/app/server.py:224-271` 还证明正常 POST 会直接拒绝 `"0.0"/"0.00"/"00"`；计划
§3.1 把它们说成“按非零部分还款处理”不够准确，但纯 matcher 对任何异常存量行均不锁价，
不改变本轮终态契约。Planner 在本次文字修订时宜改成“正常 API 拒绝；异常存量行非终态”。

#### R3 — pass

源码 `backend/app/server.py:1028-1032` 确认为 dispatch 返回后立即 `resolve` 再响应；计划
只新增一个条件触发的进程内 `service.get_snapshot()` 读取与本地解析，完整包在
`except Exception` 中。没有网络、重试、sleep、跨库读、第二次业务观测或附加写；所有异常
产生 NULL，`resolve` 在异常边界外恰好一次。`SnapshotService.get_snapshot`
（`backend/services/snapshot_service.py:338-355`）在 live 是零上游纯读，未就绪会抛异常，
与该边界相符。

#### R4 — fail（见 F1）

两列 schema 最小且正常自动来源名 `snapshot_spot_bid_at_capture` 准确；终态缺适用价没有当前价、
计提价或 K 线替代。但计划 §3.2-5 / §9 错称 `fresh` “仅表示四价齐全、无时效含义”。源码完整
语义是：`backend/services/snapshot_service.py:596-619` 先以缓存年龄
`< 2 * cache_ttl_seconds` 计算 `usable`，`backend/domain/snapshot.py:774-782,805-812` 再要求
`usable` 且四价有效才得到 `fresh`。它仍可能滞后，也仍不是交易所还款成交汇率，但不是“无时效
含义”。

#### R5 — pass

计划把索引、匹配与逐行折算放在 `backend/ledger_flow/domain.py` 的一组纯函数中，曲线与持仓
service 都调用该权威。现状代码独立核验为：曲线利息分支在
`backend/ledger_flow/domain.py:569-572`，持仓折 U 在 `backend/app/server.py:1606-1621`；
`close_log` 路径只在 `backend/hedge_open_tasks/service.py:2779-2801` 保存币本位合计，不折 U。
计划的两个消费者收口和 close-log 非目标准确。

#### R6 — fail（见 F1）

§7 已把 STORJ 排除在正常代码/脚本之外，并完整列出单独授权、备份、独立选价、直接更新、不同
人工来源、回读与审计，且明确评审/部署不授权写入。但 §3.4 SQL 注释又写
`repay_price_source` “恒为 snapshot_spot_bid_at_capture 或 NULL”，与 §7 要求的
`manual_correction` 直接冲突；§5 还要求 API 文档写来源语义。必须建立一个无歧义的来源词汇表。

#### R7 — pass

T1-T10 覆盖部分动态、终态一次切换并稳定、re-borrow 重开、取价异常仍落 succeeded+NULL、
终态缺价 fail-closed、排序/tie-break、双消费者一致、迁移幂等与精确谓词；没有为已删除的
`repay_after_*`、a/b/c 或 K 线脚本保留脚手架。它是当前架构的最小充分测试集。

#### R8 — pass

根因 A 表覆盖 P1/P3/P4 的结清误述、双零判定、缺席即零、a/b/c、人工断言、K 线 fallback，
并审计保留的 Human 约定、非成功态、时刻回退与 fail-closed；表外纯查表/迁移/close-log 给出
不适用理由。根因 B 表覆盖旧裸内存取价、签名 GET、保留的异常隔离内存取价，并锁死重试、等待、
二次观测、跨库读、附加 I/O 和 `resolve` 次数；`begin`、幂等回放、响应发送也逐一说明边界。
没有发现应入表而遗漏的旧站点。计划 §2 已明确 `_now_us()` 是 `resolve` 参数求值，不是新增业务
观测，B8 对其所在调用整体已覆盖。

#### R9 — pass

A9 不构成对根因 A 的实质豁免。根因 A 禁止把缺席/推断包装成外部事实；A9 则把两个已存储本地
值解释成 Human 选择的应用终态事件，并明确放弃“交易所债务归零”主张。§1.3、§3.1、要求中的
代码注释、API 文档四个落点都必须使用“Human 约定、非交易所证明”，另有 §4.1 A9 与 §8 的
禁止增强条款交叉保护，足以防止实现或文档偷换回事实主张。

### Formal finding and repair requirement

#### F1 `in-range` — R4/R6 的价格来源契约存在一处源码误述与一处内部冲突

证据锚点：

1. 受审计划 §3.2-5（第 124-126 行）与 §9 P2 F4 对照（第 315 行）称 `fresh` 仅表示四价
   齐全、无时效含义；固定 delivery SHA 的
   `backend/services/snapshot_service.py:596-619` 与
   `backend/domain/snapshot.py:774-782,805-812` 证明 `fresh` 同时要求缓存 age
   `< 2 * cache_ttl_seconds` 和四价有效。
2. 受审计划 §3.4 第 174 行把 `repay_price_source` 详细定义为“恒为
   `snapshot_spot_bid_at_capture` 或 NULL”，而 §7 第 291-293 行要求后续人工修正写
   `manual_correction`。两者是同一字段的两个独立可执行定义，且 §5 要求把来源语义写进 API
   文档。

实际影响：算法方向没有错，捕获值仍是可滞后的内存快照买一价、不是成交汇率；但实现者无法从
当前计划唯一确定 API/代码注释应如何描述 `fresh` 与来源枚举，后续人工审计也可能被文档误判为
非法或无法区分。该问题直接落在本次 money/PnL 控制计划与 R4/R6 验收范围内，不是新假设场景，
Scenario Admission 不适用。

必须在计划阶段完成的最小修复：

1. 把所有“`fresh` 无时效含义”改成源码可证的准确表述：它要求缓存年龄
   `< 2 * cache_ttl_seconds` 且四价有效；仍可能相对真实还款时刻滞后，且绝不是交易所成交汇率。
2. 把 §3.4 的来源定义限定为“正常自动写路径只写
   `snapshot_spot_bid_at_capture` 或 NULL”，并明确同一 TEXT 字段为单独授权的历史人工修正保留
   `manual_correction`；API 文档须同时说明二者，不能把它写成数据库 CHECK 或封闭枚举。
3. 顺手把 §3.1 的 `"0.0"/"0.00"` 说明校正为：正常 API 已拒绝；若数据库存在异常存量值，
   matcher 按非终态处理。此项不改变谓词或测试结论。

为什么不能留给实现后代码评审：这不是待验证的实现细节，而是实现 dispatch 将使用的控制计划
本身存在两个来源定义。代码评审只能检查实现是否符合既定 oracle，不能替 Planner 决定 oracle。
修复仅需收敛文字和来源词汇，不需要新增文件、状态、schema、测试机制或再做架构设计；修订后
复核应只验证这三处和 R1-R9 未回退。

### Commands and raw results

```text
test ! -e reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md
  -> pass（写入前 ABSENT）
git cat-file -e <base>^{commit}; git cat-file -e <delivery>^{commit}
  -> pass
git diff --name-status <base>..<delivery>
  -> M reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md
git diff --numstat <base>..<delivery>
  -> 260 303 reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md
git diff --check <base>..<delivery>
  -> no output
git log --oneline <base>..<delivery>
  -> 4e3fba7 stage: finalize repaid interest price plan
herdr pane list; herdr agent get w1:p6
  -> exactly one label codex; detected agent; project cwd matches
```

未运行测试：本轮是计划评审，固定区间没有实现代码。未访问生产、数据库、凭据或外部服务；未改
计划、状态、源码、测试、schema、PROJECT_STATE 或活文档；未提交、部署、操作实盘或发送其他任务。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md`
  2. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  3. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P6-repaid-interest-price-plan-final-review.dispatch.md`
  4. `backend/services/snapshot_service.py`
  5. `backend/domain/snapshot.py`
  6. `backend/app/server.py`
  7. `docs/api/public-market-contract.md`
- 执行：Bookkeeper `gpt-5.6-sol`（label `codex`）核验本 handoff 与 `status.json` revision 12，
  将 F1 原样带回 Planner；Planner 只修正 `fresh` 事实、来源词汇和零字符串措辞，不重做已通过的
  R1-R3/R5/R7-R9 架构。
- 关卡：修订计划须以新固定 commit 重新通过独立计划复评；`ACCEPT` 前不得准备或启动实现。
- 不能假设的事实：`fresh` 不是只看四价；正常自动来源与人工修正来源必须在同一字段契约中可区分；
  `0 + succeeded` 是 Human 产品约定而非交易所归零证明；本 `REWORK` 不授权实现、数据库修正、
  合并、部署或实盘。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P6-repaid-interest-price-plan-final-review
执行结果: completed（完成）
结果摘要: 固定区间仅改计划。R1-R3、R5、R7-R9通过；A9不是根因A豁免，而是Human明示的规范性终态，四处防误述要求充分。R4/R6返工：计划误称fresh无时效含义，且将repay_price_source写成仅snapshot/NULL却又要求manual_correction，形成来源契约冲突；须在计划阶段统一。
产物: [reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md]
检查结果: [启动与隔离核对、status revision 12、固定SHA区间及仅一文件变更 — pass; R1 删除完整性，无删项改名残留于实现范围 — pass; R2 终态谓词/重复区间/同毫秒边界与 R9 Human约定非证明 — pass; R3 资金缝隙与 R8 两个同根因穷举表 — pass; R4 两列最小schema与缺价fail-closed，但fresh源码语义被误述 — fail; R5 单一折算权威与两消费者/close-log边界 — pass; R6 STORJ人工路径完整，但来源字段定义与manual_correction冲突 — fail; R7 最小资金/PnL测试集且无已删机制脚手架 — pass]
阻塞项: [none（评审已完成；F1须先由Planner统一控制计划，不能留给实现后代码评审猜测）]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md
修复要求: reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md
本地北京时间: 2026-08-28 21:52:29 CST
下一步模型: Bookkeeper gpt-5.6-sol（label codex）——评审者交回，由其核验后返给 Planner
下一步任务: 读取：reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P6-repaid-interest-price-plan-final-review.handoff.md；reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md；reports/agent-runs/2026-08-28-repaid-interest-price-v1/P6-repaid-interest-price-plan-final-review.dispatch.md；backend/services/snapshot_service.py；backend/domain/snapshot.py；backend/app/server.py；docs/api/public-market-contract.md；执行：核验本交接件与status.json revision 12后，把F1原样返回Planner，仅统一fresh事实、repay_price_source正常/人工来源词汇及零字符串措辞，并封存本次REWORK；关卡：修订计划形成新固定commit并重新通过独立计划复评后，才可准备实现dispatch
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `13789ae4feec33034eec3b05bfb13757f7d7b4796be72ceb8de10457930e9d51`
- verified_at: `2026-08-28 21:58:13 CST`
- verified_status_revision: `12`
- result: `accepted_as_REWORK`
- verification: task、role、stage、base SHA、delivery SHA、固定单文件区间、R1-R9 verdict、
  `REWORK` 闭环字段、Required Reading 与 Human Brief 均一致；F1 的 `fresh` 源码语义、
  来源字段冲突及零字符串措辞均由所引源码复现。
- reproducible_checks: `git cat-file -e <sha>^{commit}`；
  `git diff --name-status e93af61630e87a759d8820d33fef61789dac1dcd..4e3fba75a64326a2b57bfe4727b010e7988fef83`；
  `git diff --check e93af61630e87a759d8820d33fef61789dac1dcd..4e3fba75a64326a2b57bfe4727b010e7988fef83`；
  `sed -n '580,625p' backend/services/snapshot_service.py`；
  `sed -n '760,815p' backend/domain/snapshot.py`；
  `sed -n '210,280p' backend/app/server.py`。
- next_state: P6 封存为 `REWORK`；计划评审返工不计入 `rework_count`。准备 P7 仅修订
  控制计划文字契约，修订计划须形成新固定 commit 并再次通过独立计划复评后才能派实现。

## Errata (append-only)
