# 20-implementation-frontend-rework2.md

阶段: `2026-07-public-market-ui-cn-v1`  
任务: Task B frontend rework round 2 (2/3)  
修复目标: P2 — 手动刷新后 60s 自动刷新计时器与倒计时显示同步  
执行模型: Kimi  

## 改动清单

### 1. `frontend/index.html` — `loadApi()` finally 块新增计时器重调度

位置: `frontend/index.html:875-884`（`loadApi` 的 `finally` 块）。

在原有:

```js
refreshState.isRefreshing = false;
refreshState.nextRefreshAt = Date.now() + AUTO_REFRESH_MS;
updateCountdown();
```

之后新增:

```js
// 手动刷新或自动刷新完成后，把 60s 自动刷新计时器与倒计时显示对齐到同一目标，
// 否则手动刷新只重置显示而不重置实际下一次 fetch（见 review-2 round-1 REWORK）。
if (refreshState.refreshTimer) clearInterval(refreshState.refreshTimer);
refreshState.refreshTimer = setInterval(() => {
  if (!refreshState.isRefreshing) loadApi();
}, AUTO_REFRESH_MS);
```

逐行说明:

- `if (refreshState.refreshTimer) clearInterval(refreshState.refreshTimer);`
  - 清除旧的 60000ms 自动刷新 interval。无论本次 `loadApi()` 是手动点击触发还是 `refreshTimer` 自动触发，旧周期都必须失效。
- `refreshState.refreshTimer = setInterval(() => { if (!refreshState.isRefreshing) loadApi(); }, AUTO_REFRESH_MS);`
  - 以当前时刻为起点重新创建 60000ms interval，保证下一次自动 fetch 发生在 `nextRefreshAt`（倒计时归零时刻）。

约束遵守情况:

- `refreshState.countdownTimer`（1000ms）保持独立，未 clear、未 recreate，倒计时逻辑未并入同一个 interval。
- `startAutoRefresh()` 首次创建逻辑未改动，仍负责启动第一个 60000ms timer 与 1000ms countdown timer。
- 未引入 `visibilitychange`、`requestIdleCallback`、Promise 重试、退避等额外机制。
- `AUTO_REFRESH_MS = 60000`、`nextRefreshAt` 语义、`updateCountdown()`、倒计时文案均保持不变。

### 2. `frontend/self-check.js` — 新增 timer-reschedule 运行时断言

位置:

- mock 注入: `frontend/self-check.js:24-39`（`eval(script)` 之前）。
- timer 断言: `frontend/self-check.js:286-303`（原有 19 项断言之后）。

新增内容:

```js
// mock setInterval / clearInterval，记录调用以便验证自动刷新计时器重调度
let intervalIdSeq = 0;
const intervalCalls = [];     // { id, delay, callback }
const clearedIntervalIds = new Set();
global.setInterval = (callback, delay) => {
  const id = ++intervalIdSeq;
  intervalCalls.push({ id, delay, callback });
  return id;
};
global.clearInterval = (id) => {
  clearedIntervalIds.add(id);
};
```

以及断言:

```js
// 19. 手动刷新后 60s 自动刷新计时器被重调度，1s 倒计时计时器保持独立
const initialRefreshTimer = intervalCalls.slice().reverse().find(c => c.delay === 60000);
const initialCountdownTimer = intervalCalls.slice().reverse().find(c => c.delay === 1000);
if (!initialRefreshTimer) throw new Error('未找到初始 60000ms 自动刷新计时器');
if (!initialCountdownTimer) throw new Error('未找到初始 1000ms 倒计时计时器');
await Promise.all((elements['btn-refresh'].listeners.click || []).map(h => h()));
if (!clearedIntervalIds.has(initialRefreshTimer.id)) {
  throw new Error('手动刷新完成后，旧的 60000ms 自动刷新计时器未被 clearInterval');
}
if (clearedIntervalIds.has(initialCountdownTimer.id)) {
  throw new Error('手动刷新完成后，1000ms 倒计时计时器不应被 clearInterval');
}
const newRefreshTimer = intervalCalls.slice().reverse().find(c => c.delay === 60000);
if (!newRefreshTimer || newRefreshTimer.id === initialRefreshTimer.id) {
  throw new Error('手动刷新完成后，未重新创建 60000ms 自动刷新计时器');
}
console.log('[PASS] 手动刷新后 60s 自动刷新计时器重调度，倒计时计时器保持独立');
```

说明:

- mock 在运行内联脚本前注入，返回递增整数 id，不实际等待 60s。
- 记录每次 `setInterval` 的 `(id, delay, callback)` 与每次 `clearInterval` 的 id。
- 通过触发 `#btn-refresh` 的 click 处理器模拟手动刷新，并 `await` 其完成。
- 断言:
  1. 旧的 60000ms `refreshTimer` id 出现在 `clearInterval` 记录中；
  2. 1000ms `countdownTimer` id 未被 `clearInterval`；
  3. 重新创建了一个新的 60000ms interval。

## self-check 输出原文

```text
[PASS] 内联脚本语法检查
[PASS] 默认请求 /api/public-market/snapshot
[PASS] 数据源标签显示后端 API
[PASS] 数据说明区可见且内容已渲染
[PASS] 默认隐藏 PERP_ONLY_EXCLUDED，渲染 4 行
[PASS] 显示 PERP_ONLY_EXCLUDED 后渲染全部 6 行
[PASS] BSTOCK 行标识正确
[PASS] alias 行显示实际现货腿与 B 后缀别名标识
[PASS] 时间转换正确
[PASS] 列名/文案符合契约
[PASS] 无交易按钮/开仓票据
[PASS] 资金费率格式化 7 个样例
[PASS] 数据说明条目数与 API warnings 一致
[PASS] 提示标记映射正确
[PASS] 离线 fixture 按钮及文案已删除
[PASS] 自动刷新 60s 与倒计时元素存在
[PASS] 路由/资产/负费率状态列显示「英文枚举(中文解释)」格式
[PASS] 筛选下拉 option 使用「英文枚举(中文解释)」格式
[PASS] 侧栏品牌已中文化
[PASS] 手动刷新后 60s 自动刷新计时器重调度，倒计时计时器保持独立

全部自检通过
```

结果: `20/20 PASS`（round 1 的 19 项 + round 2 的 timer-reschedule 覆盖）。

## 未执行事项

- 未执行 `git commit`（controller 将提交 `H_fix2`）。
- 未改动 `backend/**`、`schemas/**`、`docs/**`、`reports/api-samples/**`、`agents/**`、`workflows/**`、`scripts/**`。
- 未重新引入 `#btn-offline` / `loadFixture()` / `'fixture'` 数据源分支。
- `frontend/fixture/public-market-snapshot.json` 未改动。

---

本地北京时间: 2026-07-04 17:10:01 CST  
下一步模型: controller（提交 `H_fix2` 并触发 review-1 / review-2）  
下一步任务: 等待 controller 完成 stage fingerprint 重算与 review 调度
