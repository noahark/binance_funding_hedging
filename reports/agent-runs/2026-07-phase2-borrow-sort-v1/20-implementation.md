# Implementation Report (aggregated) — 2026-07-phase2-borrow-sort-v1

本 stage 在并行开发模式（`docs/parallel-development-mode.md`，ADOPTED-TRIAL
首次试运行）下交付，实现拆为两个并行任务。本文件按 stage-delivery 的
required-file 约定作聚合入口；任务级权威报告：

- 后端：`20-implementation-backend.md`（Task A，implementer claude_glm，
  dual-hat with bookkeeper，按 status.json evidence_policy 披露）
- 前端：`20-implementation-frontend.md`（Task B，implementer kimi-2.7）

## 摘要

- **后端 (A)**：单一 HMAC 出口 `private_client.py`（deny-by-default
  `(method, exact-path)` 白名单 = status.json `endpoint_whitelist` 四项，
  GET-only，门控先于签名，凭据清理审计日志，1h TTL 缓存，限流退避，env
  缺失降级）+ fundingInfo 接入（`funding_interval_hours` +
  `daily_funding_rate`，decimal.Decimal 禁 float）+ rows 后端排序
  （abs daily 降序 / null 末尾 / symbol 升序）+ `borrow_validation` 三态块
  （classic_margin 全候选 / portfolio_account bounded top-N）+ schema v0.2
  + contract amendment。
- **前端 (B)**：拆列（合并列→独立两列）+ 新「日费率」列（复用
  formatFundingRate string-shift，null→`—`）+ 结算间隔 `8h/4h/1h` 徽标 +
  **零排序逻辑**（payload 顺序渲染）+ 优雅降级 + 不消费 `borrow_validation`。
- **耦合面**（funding_interval_hours / daily_funding_rate / rows 有序性）
  设计期冻结，双端严格遵守，无 R3 升级。

## 测试

- `python3 -m pytest backend/tests/ -q` → **95 passed**（既有 54 + A1 16 +
  A4 25），零回归。原始输出：`60-test-output.txt`。
- `node frontend/self-check.js` → **20 PASS**（exit 0）。

## 嵌入预审（checkpoint，R5；非评审门）

- A ← fresh Kimi 只读会话：**PASS**，无 blocker（95/95 测试，硬边界零触碰）。
- B ← fresh Claude-GLM 只读会话（plan-mode fresh）：**PASS**，无 blocker。
- **R4 落盘前对账**：A/B 两 scope 当前工作树 diff 与各自 round1.diff.patch
  完全一致（零未受审改动）。

## 待决设计问题（已上报，非实现 bug）

- bounded portfolio `portfolio_filled=0`（live）：§3.4 bounded 选样 + 市场现实
  （高费率小币在 PM 不可借；可借大币费率低不入 bounded）。详见
  `20-implementation-backend.md` §3.1 与 `11-adr.md` ADR-5。属耦合面之外的
  design 决策，按红线停手上报 review/用户（R3）。

## 提交链

- H_A `d8a1164`（backend）→ H_B `cc25148`（frontend）→ H_bind `59e0eab`
  （fingerprint 绑定 + status=review_1）。
- `diff_fingerprint` = `cc25148:9dc905d5...`（base = H_intake `4d47ad2`）。

---

本地北京时间: 2026-07-04 23:24 CST
作者: bookkeeper (claude_glm，聚合；任务级报告署名见各文件)
