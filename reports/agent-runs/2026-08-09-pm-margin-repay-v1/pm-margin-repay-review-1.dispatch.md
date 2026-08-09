# Dispatch: pm-margin-repay-review-1

## Identity

- task_id: `pm-margin-repay-review-1`
- target_role: `Reviewer`
- target_model: `codex`
- provider: `openai`
- status_revision: `4`
- required_skill: `agents/skills/code-reviewer.md`

## Goal

对统一账户全仓杠杆还款 v1 的完整 T1+T2 delivery 做独立、跨实现 provider 的
HIGH_RISK review-1。以固定提交范围
`ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
检查后端资金出口、默认闸门、本地幂等/四态、前端确认/持久化/恢复、公共契约、测试覆盖
和前后端接缝，给出明确 `ACCEPT` 或 `REWORK`。

本评审不修改产品代码，不部署、不启动服务、不读取凭证、不开启还款闸门、不访问真实
币安账户，也不授权合并或资金操作。

## Allowed Files

- 全仓库只读检查；以固定 `base_sha..delivery_sha` 为唯一正式差异，不使用移动 `HEAD`
  代替交付范围。
- 唯一写权限（create-only）：
  `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md`
- Bookkeeper 已执行前置检查：
  `test ! -e reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-review-1.handoff.md`
  返回 `PASS`。若执行时该路径已存在，立即 `blocked`，不得覆盖。
- 禁止修改代码、测试、文档、计划、既有 handoff、`status.json`、`PROJECT_STATE.md`；禁止
  commit、push、merge、部署、重启服务或启动下一模型。

## Inputs

按顺序读取，不扫描历史 stage：

1. `AGENTS.md`（重点 §1、§3、§7、§8）
2. 本 dispatch
3. `reports/agent-runs/ACTIVE.json`
4. `PROJECT_STATE.md`
5. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/status.json`
6. `agents/roles.md` 的 Shared Rules、Task Handoff Evidence Contract、Reviewer 章节
7. `agents/skills/code-reviewer.md`
8. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan.md`
9. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-plan-review.handoff.md`
10. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-backend-implement.handoff.md`
11. `reports/agent-runs/2026-08-09-pm-margin-repay-v1/evidence/pm-margin-repay-frontend-implement.handoff.md`
12. 固定差异：
    `git diff --no-ext-diff ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987`
13. 交付代码与测试：`backend/config.py`、`backend/margin_repay/`、
    `backend/services/hedge_open_live_client.py`、`backend/app/server.py`、
    `backend/tests/test_config.py`、`backend/tests/test_hedge_open_live_client.py`、
    `backend/tests/test_hedge_purity.py`、`backend/tests/test_margin_repay.py`、
    `frontend/index.html`、`frontend/self-check.js`、
    `backend/tests/test_frontend_field_binding.py`、`docs/api/public-market-contract.md`
14. 既有对照：`backend/asset_transfer/store.py`、`backend/tests/test_asset_transfer.py`
15. 币安官方契约：
    <https://developers.binance.com/zh-CN/docs/catalog/advanced-trading-derivatives-trading-portfolio-margin/api/rest-api/trade#margin-account-repay-debt>

区间内 stage dispatch、status、PROJECT_STATE 与 Bookkeeper commit 是评审上下文，不是产品
交付；发现须按 `AGENTS.md` §8 做范围三分类。T1 的 `backend/tests/test_hedge_purity.py`
是 Human 2026-08-09 明确扩入的最小白名单守卫更新，授权和 Bookkeeper 核验见 T1 handoff。

创建 handoff 前必须遵守 Task Handoff Evidence Contract；Reviewer 只可创建上面指定文件。

## Acceptance Checks

1. **币安出口和金额语义**：只允许签名 one-shot
   `POST /papi/v1/margin/repay-debt`，固定 host 与 `specifyRepayAssets=USDT`；页面精确
   `"0"` 经过本地 API 后必须省略上游 `amount`，正数保持原始十进制字符串；不得出现
   `/repayLoan`、客户端偿还资产覆盖、float、自动重试或可注入 host/path。
2. **默认关闭与服务端校验**：`APP_MARGIN_REPAY_ENABLED` 默认 false，只有显式开启、非
   offline 且 key/secret 齐全才注入 client，不受 `APP_HEDGE_EXECUTOR` 控制；confirm、UUID、
   金额、未知字段和 `cross_margin_borrowed > 0` 白名单 fail closed，错误路径零上游。
3. **幂等和结果不明安全**：SQLite 唯一请求号必须先 pending、锁外 one-shot、终态落库；
   同 UUID 并发只外发一次；仅严格 200/`success is True`/asset 一致成功，明确普通 4xx
   failed，408/418/429/5xx/transport/非 JSON/矛盾 200 unknown；任何歧义不得诱导换号重发。
4. **前后端契约与刷新恢复**：POST body 恰四字段，前端只认 body.status；Human 确认后才
   生成 UUID，且 localStorage 成功先于 POST；全局防连点；刷新/丢响应后同号 GET 一次、
   不轮询；failed 结束，pending/unknown 锁+人工核对；succeeded 仅 complete 快照刷新后
   解锁。检查取消确认、GET 404、传输错误、localStorage 失败与页面 60 秒重渲染接缝。
5. **用户文案和公共契约**：确认框不得声称只扣 USDT 或保证余额足够；必须说明同币优先、
   USDT 后备、转换价格/手续费/滑点未披露、约 60 秒缓存滞后。v0.17 的本地 POST/GET、
   四态、默认关闸和“不授权部署/开闸/实盘”必须与代码一致。
6. **测试 oracle 与回归**：检查测试是否真正断言发送前持久化、固定请求体、严格四态、
   并发幂等、默认关闸、allowlist、恢复与成功刷新，而非只搜文案；确认资产划转和既有前端
   行为未回归。至少运行并记录：

```text
git diff --check ee0d5320b319a5bacc708eb8680e8156328db338..5a81bdc1c40238053a07736faa64b34cab294987
python3 -m pytest -q backend/tests/test_config.py backend/tests/test_hedge_open_live_client.py backend/tests/test_margin_repay.py backend/tests/test_asset_transfer.py backend/tests/test_service_health.py backend/tests/test_frontend_field_binding.py
node frontend/self-check.js
python3 -m pytest -q backend/tests
```

7. **范围和结论**：验证完整 delivery 只实现批准的手动还款 v1，不夹带部署、开闸、自动还款、
   多偿还资产或其他资金路径。任何 `REWORK` 发现必须给出当前证据锚点、实际影响、范围分类
   和可执行最小修复；范围外观察按 §8 处理，不得用未经准入的假设阻塞。
8. 创建合规 handoff：Reviewer handoff 的 `base_sha` 与 `delivery_sha` 必须写上述直接 SHA，
   Source Report 记录逐项证据与完整测试结果；Human Brief 输出合规 `[TASK_RESULT v2]`，并
   附明确 `评审结论: ACCEPT|REWORK`、`问题记录`、`修复要求`。

## Stop

只完成固定范围 review-1 并创建指定 handoff 后停止。不得修代码、commit、push、启动
review-2、部署、开闸或实盘。`ACCEPT` 仅允许 Bookkeeper 核验并准备独立 review-2；
`REWORK` 仅返回具名发现和最小修复要求，不授权 Reviewer 自修。
