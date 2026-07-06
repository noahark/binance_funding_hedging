# Implementation Report (aggregated) — 2026-07-private-account-v1

本 stage 在并行开发模式（`docs/parallel-development-mode.md`）下交付，是
**并行试运行 #2 + stage 分支制首跑**（DEC-2026-07-05-001 生效）。实现拆为
两个并行任务。本文件按 stage-delivery required-file 约定作聚合入口；
任务级权威报告：

- 后端：`20-implementation-backend.md`（Task A，implementer claude_glm
  独立会话，与 bookkeeper 同模型但不同会话，按 status.json
  `dual_hat_disclosure` 披露）
- 前端：`20-implementation-frontend.md`（Task B，implementer Kimi）

## 摘要

- **后端 (A)**：`private_client.py` 白名单 4→12（deny-by-default GET，
  单一 HMAC 出口不变，dual-TTL 缓存 §1.6）+ 成本腿四级链快照级单 tier
  命中（§1.3，实测 tier 1 next_hourly）+ `net_daily_yield`（§1.1 六向量，
  Decimal 禁 float）+ `sort_basis` 双基准（§1.2/§3.5，net 优先 / abs 回归）+
  借币探测扩围 + coverage/warnings（§1.5，上限 50 可配）+ `private_account`
  三态块 + 防重复计算（§1.4）+ ticker 价格 map 折算 + schema v0.3 additive
  + contract amendment。
- **前端 (B)**：净收益列（string-shift 复用、null→`—`、负值红、
  borrow_rate_source 徽标、vip0_reference 显著标注）+ sort_basis 只读标注
  （零客户端排序）+ 私有面板三态（总览/分账户/UM 持仓）+ 隐私开关（默认隐藏、
  localStorage 布尔）+ 行联动方向标（不带数量）+ 旧后端优雅降级 + self-check
  §4.7 全断言集。
- **耦合面**（net_daily_yield / borrow_rate_source / sort_basis /
  private_account / 顶层 borrow_validation）设计期冻结，双端严格遵守，
  无 R3 升级。

## 测试

- `python3 -m pytest backend/tests/ -q` → **147 passed**（基线 96 → round1
  145 → round2 147，零回归 + §3.3 负向单测 + round2 +2 回归）。原始输出：
  `20-implementation-backend.md` §3。
- `node frontend/self-check.js` → **29/29 PASS**（§4.7 全断言集）。原始输出：
  `60-test-output.txt`。
- bookkeeper 续任会话独立复跑两侧均绿（2026-07-06T03:18Z）。

## 嵌入预审（checkpoint，R5；非评审门）

- A ← fresh Kimi 只读：round1 **BLOCKER**（scope 内两项：§1.5 截断 warning +
  §1.4 private_account disabled 三态）→ 实现端修复 + 2 回归测试 + 147 passed
  → round2 fresh Kimi **PASS**（10/10）。四件套落档
  `embedded-review-a-round{1,2}.*` + `round2.dispatch.md`。
- B ← fresh Claude-GLM 只读：round1 调用 command_error/timeout（300s，
  connectors disabled）→ 用户在独立 claude-glm 窗口复用同提示词完成 **PASS**，
  raw output 回填 `embedded-review-b-round1.raw-output.md`；dispatch 记录
  `embedded-review-b-round1.dispatch.md`。
- **R4 落盘前对账**：A/B 两 scope 当前工作树 diff 与各自最后一轮 diff.patch
  sha256 完全相等（零未受审改动）。

## 待决设计问题（已上报，非实现 bug）

- **tier② E2b 全候选覆盖**（`11-adr.md` ADR-9，OPEN）：A1 假设，需 bookkeeper
  实测 E2b 是否接受逗号 `asset`。属耦合面之外 design 决策（R3）。
- **设计期 fixture 行序**（ADR-8）：AUSDT/BUSDT/CUSDT 与 §1.2 net 严格降序
  偏差——合成数据问题，运行时排序由后端保证。交 review-1 核查。
- **ADR-11 补录**：Kimi 非阻塞观察，`docs/architecture/ADR/11-adr.md` 不在
  Task A §3.1 允许文件内、本轮未改动，建议 bookkeeper 按 00-task 硬约束补录
  v0.3 决策的架构记录（scope 外 follow-up）。

## 提交链（stage/2026-07-private-account-v1 分支）

- H_intake `fce1452`（G1-G5 PASS）→ 回填 `91fd4e8` → 派工 RECEIPT `0bb9df6`
  → H_A `6ca6ee1`（backend）→ H_B `6c1e992`（frontend）→ status→review_1
  `3c1d7c9`（指纹绑定 + embedded_reviews）。
- `diff_fingerprint`（stage top）= `6c1e992c…49:a2140bfd…`（base = H_intake `fce1452`）。
- Task A fp = `6ca6ee1…:fdfba1…`（base fce1452）；Task B fp = `6c1e992…:50998c…`
  （base H_A 串行链，每任务指纹对应其 scope，匹配 review-prompts T1/T2 范围）。

---

本地北京时间: 2026-07-06 11:21 CST
作者: bookkeeper (claude_glm，续任会话；聚合；任务级报告署名见各文件)
