# 03-intake-decisions —— bookkeeper（opus5）intake 定稿记录

日期：2026-07-31。承接 `01-intake-to-opus5.md`（claude_glm 交接）。

## 决策 4：ACTIVE.json 切到本 stage

`ACTIVE.json` 由 `2026-07-hedge-fast-fix-v1` 切到 `2026-07-31-hedge-task-inline-log-v1`。

理由：fast-fix 的 `status.json` 处于 `awaiting_findings`、`current_task: null`，没有在跑的
任务；本 stage 有真实待启动的 dispatch。`ACTIVE.json` 是单一 active 指针，应指向真正在
跑的 stage。fast-fix 目录与状态原样保留（未关闭、未归档），后续可切回收口。

## 决策 5：packet 定稿要点

### F10 取方向 B，明确否决方向 A

- **A（否决）**：worker 退出线改用 `accepted >= target_n`。否决理由两条：
  1. **资金语义变更**。`scheduled_attempt_count` 是 A-1「计划调度硬上限」：用户设定
     计划 N 组，系统最多发出 N 组订单，失败也消耗配额。改成 accepted 口径后，失败会
     持续重发新订单直到成功 N 组，突破用户设定的下单次数上限——属 HIGH_RISK 资金
     语义变更，不在本 stage 授权范围。
  2. **只改 `service.py:1116` 不会生效**。该上限在 `store.py:736` 的预留事务里原子
     生效，`store.py:686` 的调度过滤也带同一判据；只改 worker 退出线，任务仍拿不到
     预留。
- **B（采纳）**：保持 A-1 语义不变，让「计划用尽但未达成」的任务进入明确终态，并让
  「启动」给出明确反馈，而不是静默置 running 后卡死。

### 根因家族一次穷举（预防性适用 AGENTS §8 同根因刹车）

`scheduled >= target_n` 判据现存至少四处：`service.py:1116`（worker 退出）、
`store.py:686`（调度过滤）、`store.py:736`（预留原子上限）、`store.py:971`（R2-F1 结算
收口为 `done`）。packet 要求交付逐一列出处理或不适用理由。此项来自 `hedge-order-truth-v1`
的教训：不变量型标准必须配路径穷举清单，否则修一处、漏三处，反复返工。

### 其余定稿调整

- Acceptance Check 第 1 条改为「先写复现测试并提交失败输出，再修复转绿」——原草稿的
  F10 验收「手动启动后能真正恢复」缺可执行判据。
- 日志数据口径写死：必须覆盖该任务**全部**尝试，不得是全局分页的切片。核实结果：
  `GET /api/hedge-open-logs`（`server.py:588`）当前**没有**按任务过滤的参数，草稿
  Inputs 里「按 task 过滤」的前提不成立，已在 packet 中改为待定实现选择（既有路由上
  的可选参数，或前端过滤但须保证不漏历史尝试），并交计划评审判定。
- 「进展」列口径显式绑定 `scheduled_attempt_count / target_n`，与方向 B 一致。
- packet 结构收敛为 `agents/roles.md` 规定的六段（Identity / Goal / Allowed Files /
  Inputs / Acceptance Checks / Stop），草稿里的「路由」「待 Human 决策」两段已移除
  （路由信息进 status/本文件）。

## 计划评审 provider 建议

首选 `kimi`（moonshot）。四个 provider 完全不重叠：计划评审 moonshot / implementer
zhipu_glm / review-1 xai / review-2 openai，且 kimi 未参与 packet 定稿。

备选 `grok`（xai）：若 kimi 额度或服务不可用。代价是计划评审与 review-1 同 provider，
须在结论中披露设计参与事实（`agents/roles.md` Reviewer「Prefer a final reviewer that did
not plan or design the stage… disclose it」）。不建议让 `codex` 兼任计划评审——它是
review-2 终审，让终审带上设计参与是最不该污染的一条。

本终端（opus5）定稿了 packet，因此不担任本 stage 的计划评审。
