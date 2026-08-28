# Task Handoff: P8-repaid-interest-price-plan-contract-rereview

## Source Report (author-only; immutable after task end)

- task_id: `P8-repaid-interest-price-plan-contract-rereview`
- role: `Reviewer / Plan Review (pre-implementation)`（独立只读计划复评）
- target model: `gpt-5.6-sol`（provider `openai`）
- stage_id: `2026-08-28-repaid-interest-price-v1`
- created_at: `2026-08-28 22:30:22 CST`
- base_sha: `db680957151e17ad9703e1889bcf6571d4ecd812`
- delivery_sha: `34ad78db1929716d5860067821b6b349500ac6e7`
- status anchor: revision `14`、checkpoint `p7-plan-verified-p8-ready`、current task
  `P8-repaid-interest-price-plan-contract-rereview`
- reviewed range: `db680957151e17ad9703e1889bcf6571d4ecd812..34ad78db1929716d5860067821b6b349500ac6e7`
- reviewed artifact: `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
- required_skill: `agents/skills/software-architect.md`（仅此一个）

### Isolation and fixed-range verification

本会话是独立 `codex-review` Reviewer 会话，不是 P7 计划作者 `opus5` / `anthropic`，也不是
本 stage 的 Bookkeeper `codex` 会话；跨 provider 计划评审隔离成立。本 stage 尚未实现。

固定区间通过 Git 独立核验：两个 SHA 均为 commit；`git diff --name-status` 只返回
`M reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`；
`git diff --numstat` 为 `63 14`；`git diff --check` 无输出。计划与源码证据均从固定
delivery SHA 读取，没有用移动 `HEAD` 或未提交工作区替代。

### Verdict

`REWORK`。

P7 已实质修好 P6 F1 的三个主体问题：`fresh` 同时要求缓存年龄
`< 2 * configured cache_ttl_seconds` 和四价有效；自动与人工来源统一为同一自由、可空
TEXT 契约；正常 API 的零字符串拒绝与异常存量 matcher 行为也已分开。旧错误句仅作为明确标注
“P5 曾误述”的历史说明。R1-R3/R5/R7-R9 没有回退，允许将来使用其他可审计、且与自动值可区分
的人工来源名，也不削弱当前 `snapshot_spot_bid_at_capture` 与 `manual_correction` 的含义。

但 active contract 仍把 `cache_ttl_seconds` 写成“当前 = 60，故上界约 120 秒”。固定提交源码只
证明 `60` 是代码默认值；运行时可由环境变量覆盖。该措辞会把默认阈值误读为运行时保证，属于
实现前必须消除的控制计划歧义。

### Acceptance checks

#### 1. P6 F1 三项主体修复 — pass

- `fresh`：计划 §3.2-5 已同时写明 age `< 2 * cache_ttl_seconds`、四个归一价格非 None、
  可能滞后且不是交易所还款成交价。固定源码
  `backend/services/snapshot_service.py:596-606` 与
  `backend/domain/snapshot.py:748-808` 支持该参数化语义。
- 来源字段：计划 §3.4 建立单一契约——自由 nullable TEXT、无 CHECK/封闭枚举；自动路径只写
  `snapshot_spot_bid_at_capture` 或 NULL；人工历史修正每次另获 Human 授权，写
  `manual_correction` 或其他可审计、与自动值可区分的人工来源名。
- 零字符串：计划 §3.1 与 T9 准确区分正常 API 拒绝
  `"0.0"/"0.00"/"00"` 和异常存量 matcher 的非终态行为；固定源码
  `backend/app/server.py:224-270` 支持该结论，精确终态谓词未变。

#### 2. 历史错误句 — pass

两处旧“`fresh` 无时效含义”均分别标为“P5 的一处自陈错误”和“P5 曾误述”，紧邻活动契约的
更正及原因，不会被合理读成现行规则。

#### 3. 未来人工来源名 — pass

该扩展口只存在于正常程序之外、每次单独授权的人工修正路径；计划同时要求来源可审计、必须与
自动值可区分，并明确 API 文档说明当前两个来源值。它没有允许自动 writer 写第三种值，也没有
改变当前两个值的来源含义。自由 TEXT 是审计出处字段，不是业务分支枚举；读取侧不按来源名决定
金额，因此无需在本轮封闭未来人工标签。

#### 4. P6 已通过设计无回退 — pass

固定 diff 除 P7 三项控制文字及其直接重复处外没有改动 schema、算法、bounded 文件、测试机制、
STORJ 人工例外、fail-closed、资金缝隙唯一动作、共享 domain 权威、A9 Human 约定或根因 A/B
扫描拓扑。`0 + succeeded` 仍明确是 Human 产品终态，不是交易所债务归零证明。

### Formal finding and repair requirement

#### F1 `in-range` — 60/120 秒把代码默认值写成未经核实的运行时常量

证据锚点：

1. 受审计划 §3.2-5 第 151-158 行先正确使用参数化表达式，但第 154 行写“当前
   `cache_ttl_seconds = 60`，故上界约 120 秒”。“当前”没有限定为代码默认值。
2. 固定 delivery SHA 的 `backend/config.py:38` 只定义
   `cache_ttl_seconds: int = 60` 默认值；同文件 `:264-269` 明确允许
   `APP_CACHE_TTL_SECONDS` 或兼容环境变量覆盖它。
3. 固定源码 `backend/services/snapshot_service.py:596-606` 使用运行时
   `self.config.cache_ttl_seconds` 计算 `< 2 * ttl`，没有把 `60` 或 `120` 写死。

实际影响：实现者可能把“120 秒”写成无条件 API/注释保证，而实际部署若配置不同就不成立；对
还款时价格的新鲜度说明会失真。该问题来自本次新增的活动控制文字，分类为 `in-range`。它是明确
验收项不合规，不是 Reviewer 新设假设，Scenario Admission 不适用。

必须在计划阶段完成的最小修复：把该句限定为“`Config` 的代码默认值为 60 秒；未被配置覆盖时，
`fresh` 要求 age `< 120` 秒（最大滞后接近 120 秒）；实际运行阈值始终是
`2 * configured cache_ttl_seconds`，本计划没有核实具体部署值”。同步确保后续 API 文档任务
不得把默认 120 秒写成固定运行时常量。无需修改架构、schema、算法、测试机制或其他文件。

为什么必须在计划阶段解决：计划是后续实现与 API 文档的控制 oracle；若它同时给出参数化规则与
未经限定的“当前 60”，代码评审无法判断实现应承诺默认值还是部署常量。先改清一句即可，不能把
这个产品契约选择留给实现者或实现后 Reviewer 猜。

范围外发现：无。没有 `pre-existing-independent` 或 `pre-existing-release-critical` 发现。

### Commands and raw results

```text
test ! -e reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md
  -> pass（写入前 ABSENT）
git cat-file -e <base>^{commit}; git cat-file -e <delivery>^{commit}
  -> pass
git diff --name-status <base>..<delivery>
  -> M reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md
git diff --numstat <base>..<delivery>
  -> 63 14 reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md
git diff --check <base>..<delivery>
  -> no output
herdr pane list
  -> exactly one label codex at w1:p6; codex-review is a distinct pane; project cwd matches
```

未运行测试：本轮只复评计划控制契约，固定区间没有实现代码。未访问生产、数据库、凭据或外部
服务；未改计划、状态、源码、测试、schema、PROJECT_STATE 或活文档；未提交、部署、操作实盘
或发送其他任务。

### Required Reading for the Next Task

- 读取路径及顺序：
  1. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md`
  2. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md`
  3. `backend/config.py`
  4. `reports/agent-runs/2026-08-28-repaid-interest-price-v1/P8-repaid-interest-price-plan-contract-rereview.dispatch.md`
- 执行：Bookkeeper `gpt-5.6-sol`（label `codex`）核验本 handoff 与 `status.json` revision 14，
  将 F1 原样交回 Planner；Planner 只把 60/120 改成“代码默认/默认阈值”，并保留参数化运行时契约。
- 关卡：修订计划形成新的固定 commit 并再次通过独立计划复评后，才可准备实现 dispatch。
- 不能假设的事实：本计划未核实生产或任何部署环境实际 TTL；本 `REWORK` 不授权实现、数据库
  修正、合并、部署或实盘。

## Human Brief / Console Receipt Source (author-only; immutable after task end)

[TASK_RESULT v2]
任务 ID: P8-repaid-interest-price-plan-contract-rereview
执行结果: completed（完成）
结果摘要: 固定区间仅改计划（+63/-14）。P6三项主体修复及R1-R3/R5/R7-R9均未回退；未来人工来源名不削弱当前两值含义。唯一in-range问题：计划把可配置TTL的代码默认60秒写成“当前60”，易把默认约120秒误当运行时保证，须在实现前改清。
产物: [reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md]
检查结果: [启动身份、隔离、status revision 14及固定SHA单文件+63/-14 — pass; fresh参数化时效、四价、可滞后且非成交价主体契约 — pass; 60/120未明确为代码默认而易被误读为运行时常量 — fail; 自动/人工统一自由TEXT契约及未来人工标签可审计边界 — pass; 正常API零字符串拒绝与异常存量matcher边界 — pass; 两处旧错误句均明确标为已废弃自陈 — pass; R1-R3/R5/R7-R9无回退 — pass; 范围三分类与证据门：唯一F1为in-range验收不合规、非新假设 — pass]
阻塞项: [none（评审已完成；F1须先由Planner把60/120限定为代码默认，不能留给实现后代码评审）]
评审结论: REWORK（返工）
问题记录: reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md
修复要求: reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md
本地北京时间: 2026-08-28 22:30:22 CST
下一步模型: Bookkeeper gpt-5.6-sol（label codex）——评审者交回，由其核验后返给 Planner
下一步任务: 读取：reports/agent-runs/2026-08-28-repaid-interest-price-v1/evidence/P8-repaid-interest-price-plan-contract-rereview.handoff.md；reports/agent-runs/2026-08-28-repaid-interest-price-v1/repaid-interest-price.plan.md；backend/config.py；reports/agent-runs/2026-08-28-repaid-interest-price-v1/P8-repaid-interest-price-plan-contract-rereview.dispatch.md；执行：核验本交接件与status.json revision 14后，把F1原样返回Planner，仅将60/120改成代码默认/默认阈值并保留按configured TTL计算的运行时契约；关卡：修订计划形成新固定commit并重新通过独立计划复评后，才可准备实现dispatch
[/TASK_RESULT]

<!-- BOOKKEEPER_APPEND_ONLY: all bytes before this marker are the source payload -->

## Bookkeeper Verification (Bookkeeper append-only)

- source_sha256: `d48aec70868d4f9697f496cb7ce08a3f5fa2383d670074602a8dee918f608b03`
- verified_at: `2026-08-28 22:33:10 CST`
- verified_status_revision: `14`
- result: `accepted_as_REWORK`
- verification: task、role、stage、base SHA、delivery SHA、固定单文件 `+63/-14`
  区间、review closure、Required Reading 与 Human Brief 均一致；F1 可由
  `backend/config.py:38,264-269` 与
  `backend/services/snapshot_service.py:596-606` 复现。
- reproducible_checks: `git cat-file -e <sha>^{commit}`；
  `git diff --name-status db680957151e17ad9703e1889bcf6571d4ecd812..34ad78db1929716d5860067821b6b349500ac6e7`；
  `git diff --numstat db680957151e17ad9703e1889bcf6571d4ecd812..34ad78db1929716d5860067821b6b349500ac6e7`；
  `git diff --check db680957151e17ad9703e1889bcf6571d4ecd812..34ad78db1929716d5860067821b6b349500ac6e7`。
- next_state: P8 封存为 `REWORK`；计划评审返工不计入 `rework_count`。P6 与 P8
  连续暴露同一配置事实家族，下一 Planner 任务按同根因刹车执行一次有界穷举扫描，
  不只点改 `60/120` 一处；扫描与修正后须重新通过固定提交计划复评。

## Errata (append-only)
