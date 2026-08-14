# Stage Intake — 2026-08-14-smooth-close-orders-v1

本地北京时间：2026-08-14 13:33:23 CST

## Human 决定

- **stage_id**：`2026-08-14-smooth-close-orders-v1`（目录名与之相同）
- **Bookkeeper**：`gemini-3.1-pro`（`agy` 窗口）——Human 在本次 intake 指派，写入 `status.json.bookkeeper` 的必须是这个规范模型 ID，不是窗口标签 `agy`。
- **风险分级**：`HIGH_RISK`（`AGENTS.md` §8）——涉及订单触发时机、平仓资金准备与实盘资金路径。实现前需要一次跨 provider 只读计划评审，交付后 Review-1 + Review-2。
- **产品设计文档（本阶段唯一需求权威）**：`docs/planning/smooth-close-orders-v1.md`
- **分支**：Harness v2 下不强制 `stage/<stage-id>`，由 Human 选定后再开工（本文件落盘时仍在 `main`，工作树除本 stage 文件外干净）。
- **参考 HEAD（本文件落盘时）**：`705bcefbb2dea4b9f33c2c3d9d69123cd9b71fdb`。`base_sha` 由 Bookkeeper 在准备第一个 dispatch packet 前用 `git rev-parse` 自行取值并校验，不得抄本行。

## 目标一句话

给平仓任务加 `mode=smooth`：功能与特点镜像平滑开单，并与立即平仓的资金路径保持一致——每一轮在发单前用 WebSocket 一档盘口等一个更好的平仓率，最多 5 分钟，等不到就按立即平仓成交。

## Bookkeeper 首个动作

1. 读 `AGENTS.md`、本文件、`reports/agent-runs/ACTIVE.json`（当前为 `{"active":null}`）、`PROJECT_STATE.md`、`agents/roles.md` 的 Bookkeeper 段；
2. 创建本 stage 的 `status.json`（`schema_version: "2"`、`revision: 1`、`bookkeeper: "gemini-3.1-pro"`、`phase` 为计划评审阶段、`rework_count: 0`、`blockers: []`），并把 `ACTIVE.json` 指向本 stage；
3. 依 `docs/planning/smooth-close-orders-v1.md` §9 准备**第一个** dispatch packet：一次跨 provider 的**只读计划评审**（不是实现）。评审 provider 必须不同于本设计的作者 provider（`anthropic`）；
4. 准备完 packet 后做最后一次 `status.json` revision 指向它，然后停下，由 Human 启动目标终端。

## 交付边界（本 stage 未授权项）

- 未授权改源码、重启或启动服务、创建任务、下单、`push`、`merge`、部署、实盘验证；
- 未授权变更立即平仓、立即开单、平滑开单、借币、还款、划转的任何行为；
- 未授权修改 `docs/planning/smooth-close-orders-v1.md` §5 第 5 条列出的三项已具名接受的限制（L1/L2/L3）。

## 需要评审重点回答的问题

1. 备料前移（预检 + 合约可平量 + forward 现货余额/划转）后，`docs/planning/smooth-close-orders-v1.md` §5 列出的陈旧风险是否被完整表达，是否还有未列出的发单前事实在平滑路径上失去拦截；
2. 「备料只做一次、暂停恢复不重做」与「单腿刹车阈值 1」的组合，是否足以覆盖暂停期间人工平仓导致的单腿场景；
3. 方向翻转复用 `compute_opening_spread_pct` 是否在四种（forward/reverse × close）组合下都取到正确的价格与数量档位；
4. 备料失败落 `deleted` 是否会与人工软删除的卡混淆到影响操作判断，中文原因是否确实可见；
5. 是否存在当前代码证据支持的资金安全缺口、不可测试点或不必要复杂度。

评审若提出新假设场景，须给出当前代码路径、官方契约或具体并发/单位证据，以及它对本交付的实际影响；对偏好不同、已明确接受的风险或未来扩展不应判为阻塞。
