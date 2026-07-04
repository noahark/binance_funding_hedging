# Fix Start Prompt — rework round 2（P2：自动刷新计时器与倒计时显示同步）

（controller 原样转发给 Kimi;所有改动均在 `frontend/**`,Task B owner 不变。
阶段 `2026-07-public-market-ui-cn-v1`,rework_count=2/3,status=fixing。）

## 被复审的 diff 与本轮起点

- 上轮 stage head:`7592b2c`(rework round 1 的 `H_fix`,fingerprint
  `7592b2c:4b8c8de2...`;review-1 round-1 fresh GLM ACCEPT、review-2 round-0 Codex
  ACCEPT 均原样保留在 `review_1_round0` / `review_2_round0` / `30-review-1.md`)。
- 本轮触发:**review-2 round-1(Codex gpt-5.5 xhigh,final gate)= REWORK**,1 个
  P2 阻断发现。controller 已独立复核成立(grep 确认 `frontend/index.html` 全文
  无 `clearInterval`/`clearTimeout`)。

## Finding(P2,阻断,本轮唯一修复目标)

**手动刷新重置了倒计时显示,但没有重置实际的 60s 自动刷新计时器。**

- `startAutoRefresh()`(index.html:635-639)在启动时**仅创建一次**
  `setInterval(() => { if (!refreshState.isRefreshing) loadApi(); }, AUTO_REFRESH_MS)`
  (即 `refreshState.refreshTimer`),以及一个独立的 1s `setInterval(updateCountdown, 1000)`
  (即 `countdownTimer`)。
- 手动刷新入口 `els.btnRefresh.addEventListener('click', loadApi)`(index.html:901)
  只调用 `loadApi()`。
- `loadApi()` 的 `finally`(index.html:876-877)执行
  `refreshState.isRefreshing = false;` 与
  `refreshState.nextRefreshAt = Date.now() + AUTO_REFRESH_MS;`,但**没有**
  `clearInterval` / 重新调度 `refreshTimer`。
- 后果:页面在 T=0 启动,`refreshTimer` 在 T=60 触发;用户在 T=50 点手动刷新,
  `nextRefreshAt` 被重置为 T=110(倒计时显示回到 60s),但原 `refreshTimer` 仍按
  原始周期在 T=60 触发 → 倒计时显示还有约 50s 时,自动刷新已经发生。
  这违反用户决策 C(「手动刷新按钮保留:点击立即 fetch 并将倒计时重置为 60」)
  的**完整**意图:重置必须同时作用于显示与实际下一次自动 fetch。

## 修复要求(最小、外科)

在 `frontend/index.html` 的 `loadApi()` `finally` 块中,**在**
`refreshState.nextRefreshAt = Date.now() + AUTO_REFRESH_MS;` **之后**,加上:

```js
// 手动刷新或自动刷新完成后,把 60s 自动刷新计时器与倒计时显示对齐到同一目标,
// 否则手动刷新只重置显示而不重置实际下一次 fetch(见 review-2 round-1 REWORK)。
if (refreshState.refreshTimer) clearInterval(refreshState.refreshTimer);
refreshState.refreshTimer = setInterval(() => {
  if (!refreshState.isRefreshing) loadApi();
}, AUTO_REFRESH_MS);
```

约束:

- **`refreshState.countdownTimer`(1s)保持独立、不动**——不要 clear/recreate 它,
  也不要把倒计时并入同一个 interval。
- `startAutoRefresh()`(index.html:635-639)的首次创建逻辑**保持不变**(它仍然负责
  在启动时创建第一个 60000ms timer 与 1s countdown timer)。
- 不要引入 `visibilitychange`/`requestIdleCallback`/Promise 重试/退避等任何额外机制
  ——本轮只修这一处对齐,不扩范围。
- 不要改 `AUTO_REFRESH_MS = 60000`、不要改 `nextRefreshAt` 的语义、不要改
  `updateCountdown()`、不要改倒计时「下次刷新: Xs」/「刷新中…」文案。
- 修复后行为应是:**任何 `loadApi()` 完成(无论成功/失败/手动触发/自动触发),
  下一次自动 fetch 时刻 == `nextRefreshAt`(倒计时显示归零的时刻)**。

## 边界(红线,逐字沿用 round 1)

允许写:`frontend/index.html`、`frontend/self-check.js`、
`reports/agent-runs/2026-07-public-market-ui-cn-v1/20-implementation-frontend-rework2.md`。

禁止:`backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、
`agents/**`、`workflows/**`、`scripts/**`;无新依赖;无直接 Binance 调用;
**不得重新引入** `#btn-offline` / `loadFixture()` / `'fixture'` 数据源分支
(round 1 已删除);**同源 `fetch('/api/public-market/snapshot')` 保留不变**;
**`formatFundingRate` / `formatBeijing` / `formatBeijingShort` 不得改动**;
`frontend/fixture/public-market-snapshot.json` 不得改动。

越界即 REWORK。

## self-check 同步(round 2 新增覆盖)

`frontend/self-check.js` 已是「Node 下用 mock DOM 运行 index.html 内联脚本」的
运行时风格(已 mock `global.fetch` 返回 fixture)。**沿用这一风格**新增对
计时器同步的覆盖:

1. 在运行内联脚本**之前**,注入 mock:
   - `global.setInterval`(若尚未 mock):记录每次调用的 `(id, delay, callback)`,
     返回递增整数 id(不要真的定时——测试不应等待 60s)。
   - `global.clearInterval`:记录被 clear 的 id 集合。
2. 运行内联脚本 → `startAutoRefresh()` 会创建一个 60000ms 的 `refreshTimer`
   与一个 1000ms 的 `countdownTimer`。记录它们的 id。
3. 模拟一次手动刷新(通过已 mock 的 DOM 触发 `#btn-refresh` 的 click 处理器,
   或等价地直接调用 `loadApi()` 完成路径——按现有 self-check 触发刷新的方式
   保持一致),让其跑到 `finally`。
4. 断言(round 2 核心):
   - 手动刷新完成后,旧的 **60000ms** `refreshTimer` 的 id 出现在 `clearInterval`
     记录中;
   - 同时新建了一个 **60000ms** 的 interval(新的 `refreshTimer`);
   - **1000ms 的 `countdownTimer` 没有**被 clear(保持独立)。
   - 失败时给出清晰错误信息,指出哪一条不满足。
5. 既有全部断言(round 1 的 19 项)全部保持通过;不要删改它们。

完成后预期:`node frontend/self-check.js` ≥ 20/20 PASS(round 1 的 19 项 +
round 2 的 timer-reschedule 覆盖)。若你的实现需要拆成多个断言,数量可多于 1,
但必须真实运行(运行时 mock),不要退化为纯字符串/正则断言。

## 完成后必跑

```bash
node frontend/self-check.js        # 全 PASS(≥20)
```

报告 `20-implementation-frontend-rework2.md`:改动清单(逐行说明 finally 块的新增
语句 + self-check 新增的 mock/断言)+ self-check 输出原文。

## 收尾(controller,无需 Kimi 执行)

H_fix2 提交 → 重算 task-B(rework round-2 fix)与 stage 级 fingerprint →
review-1(全新只读 Claude-GLM 会话,只审 round-2 fix diff `frontend/**`)→
review-2(Codex gpt-5.5 xhigh,`direction_synthesis` disclosure,重新绑定 round-2
head,recompute stage fingerprint)→ `validate-stage.py --phase pre-accept` →
`stage_accepted_waiting_user`;controller 不声明最终验收。

本地北京时间: 2026-07-04 17:05 CST
下一步模型: Kimi(rework round 2,Task B timer sync)
