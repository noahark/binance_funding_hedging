# Review 请求：文档同步性整顿（2026-08-08）

> 请求 opus5 对今日「文档追平 + Harness 两条规则 + PROJECT_STATE 清理」做独立评审。
> 评审范围锚定**已提交区间 `cdf7e69..493d748`**（两个提交），勿用工作树 HEAD——
> 工作树当前含有另一会话的在途改动（见「明确不在范围内」）。

## 背景与动机

当日审计发现 docs/ 下多份活文档严重落后于代码事实：`ARCHITECTURE.md`（定格
2026-07-16）声称「系统无任何交易功能」，而下单/借币/划转/平仓均已实盘在线；
`PRD.md`、`DEVELOPMENT_GUIDE.md` 同类失真；`ROADMAP.md` 把四项已完成工作列为
待办、把已作废的 smoke 门禁写成「实盘硬性前置」；行为权威契约
`docs/api/public-market-contract.md` 自 v0.12（2026-08-04）停滞，其描述的现货腿
解析规则已被纯表方案取代（直接矛盾）。根因：文档同步义务原只挂在 stage 收尾
（AGENTS.md §9），而 2026-08-06~08 的高强度改动全是 Human 直接驱动、无 stage。

## 评审对象（两个提交）

### 提交 1 `0406f8c` — docs: 追平活文档到 2026-08-08 + 收口必同步文档契约（15 文件）

- `AGENTS.md` §7 新增一句：任何交付收口（含 Human 直接驱动、无 stage）必须检查
  并同步 docs/ 活文档；有 stage 归 Bookkeeper（§9 不变），无 stage 归在
  PROJECT_STATE 记录收口的模型。**Human 授权直改、豁免 §8 评审拓扑。**
- `docs/architecture/ARCHITECTURE.md`、`docs/product/PRD.md`、
  `docs/development/DEVELOPMENT_GUIDE.md`、`docs/planning/ROADMAP.md`：事实追平
  （已交付能力、白名单含 POST 写路径、环境变量补 APP_HEDGE_EXECUTOR 等、
  Current Focus 重写），抬头统一 as of 2026-08-08，易漂移细节改指针。
- `docs/api/public-market-contract.md`：头部 v0.8→v0.16；追加四个 amendment——
  v0.13 资产划转端点、v0.14 纯表符号解析（标注 supersede 旧猜测规则）、
  v0.15 `unavailable_sources`（F4）、v0.16 max-withdraw + fixture 作废声明；
  白名单节改指针式写法。旧章节正文未动，由新 amendment 标注取代。
- `docs/planning/DECISIONS.md`：补 9 行 2026-08-03 之后的 Human 裁定
  （DEC-2026-08-04-001 ~ DEC-2026-08-07-008）。
- 四份误导文档加状态头：`symbol-mismatch-analysis.md`（方案已废弃勿重做）、
  `deferred-hedge-task-lifecycle.md`（四项输入已解决）、
  `issue-triage-2026-08-07.opus5.md`（Q4 残留状态）、
  `spot-order-routing-v1.md`（stage 已交付）。
- `agents/roles.md`：review-2 默认模型 Opus 5 → sonnet5。**这是判断性改动**：
  DEC-2026-08-04-001 原文为「由默认 Opus 5 改为 sonnet5」且无时限，按默认变更
  同步；若 Human 本意是 stage 级临时决定，此处需回退。
- `backend/__init__.py` docstring 追平（初版触发 websocket 守卫测试，改用
  user-data-stream 措辞）；删除孤儿且不过 schema 校验的
  `frontend/fixture/public-market-snapshot.json` + 同步移除
  `backend/tests/smoke_server.py` 中的 fetch 检查；契约 v0.16 措辞同步为「已删除」。

### 提交 2 `493d748` — docs(state): PROJECT_STATE 按定义清理 61KB→24KB + 完结留痕进 git（2 文件）

- `PROJECT_STATE.md`：61,465 → 24,279 字节。删除与 Last Completed 重复的已归档
  stage 总结、Merged Position Table 全节（A/B/F4 均 RESOLVED）、5 条已关闭
  follow-up 等；RESOLVED 长叙事压成骨架 + git/archive 指针；**全部 OPEN 项
  原样保留**（1000x 八处清单与行号校验脚本逐字未动，13 项关键内容 grep 核对
  无丢失）；Next Priority 按当前真实优先项重写。
- Update Rule 补正面一半：完结留痕在 git 提交与 archive 引用，本文件只记
  活风险、待办与指针；提交信息必须写清一句话结果。
- `docs/planning/DECISIONS.md`：DEC-2026-08-08-001 记录当日两条 Harness 决定
  （收口同步文档义务；completed 索引文件不建、也不逢开发必开 stage）。

## 明确不在范围内

工作树现有 6 个**非本次评审作者改动**的文件（另一会话在途的 net_pnl 利息口径
修复：`backend/app/server.py`、`backend/tests/test_hedge_api.py`、
`frontend/index.html`、`frontend/self-check.js`、
`docs/planning/hedge-open-cycle-stage3-stats-dev.md`、
`docs/planning/hedge-open-position-cycle-v1.md`）。请勿纳入评审、勿计入交付。

## 已做验证

- 全量 `pytest backend/tests`：**1601 passed**；`node frontend/self-check.js`：
  **EXIT=0**。（注：该运行在另一会话的 net_pnl 改动出现于工作树**之前**，
  只覆盖本次评审区间。）
- PROJECT_STATE 清理后 13 项 OPEN 关键内容 grep 逐一核对无丢失；
  `wc -c` = 24,279 / 65,536（37%）。
- 两个提交本身已含「一句话结果」，是 Update Rule 新规则的首次实践。

## 请重点评审的问题

1. **事实准确性**：追平后的各处「当前状态」声明与代码是否一致（抽查即可，
   重点：契约 v0.13-v0.16 四个 amendment 的端点/字段/语义描述 vs
   `backend/app/server.py`、`backend/domain/normalize.py`、
   `schemas/api/public-market/snapshot.schema.json`）。
2. **信息丢失**：PROJECT_STATE 压缩是否丢了仍活着的事实（重点对照 git
   `cdf7e69:PROJECT_STATE.md` 中 Live Risks / Open Follow-ups 的 OPEN 项）。
3. **规则一致性**：AGENTS.md §7 新句、PROJECT_STATE Update Rule、
   DEC-2026-08-08-001 三处表述是否互相一致、有无与 §9 冲突或制造第二权威。
4. **roles.md 的 sonnet5 改动**：对 DEC-2026-08-04-001 的解读是否成立。
5. **新引入的误导**：本轮改动是否把任何「曾经的真话」改成了「现在的假话」
   （本轮修的就是这个病，最怕自己也染上）。
6. DECISIONS.md 补记的 10 行（9+1）与 PROJECT_STATE/git 历史的事实核对。

## 评审结论格式

按 AGENTS.md §7：`评审结论: ACCEPT | REWORK` + `问题记录` + `修复要求`。
