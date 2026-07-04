# 20-implementation-frontend.md

## 阶段

`2026-07-public-market-ui-cn-v1` Task B：前端展示层中文化与列合并

## 改动清单

仅修改 `frontend/**` 与当前报告文件：

1. **`frontend/index.html`**
   - `<title>`、页头改为 `资金费率对冲工作台`；副标题改为 `公开数据 · 只读`。
   - 顶部约束 badge：`Public Only` → `公开数据`、`Read-only` → `只读`、`Manual Refresh` → `手动刷新`。
   - 侧边栏品牌副标题改为 `公开数据 · 只读`。
   - 路由筛选与 badge：`PM 现货候选` → `杠杆现货候选`。
   - 合并原第 4、5 列为 `资金费率/结算时间`（title="本周期实时预估 / 北京时间"）。
   - 新增 `formatBeijingShort` 输出北京时间 `HH:mm`；`formatBeijing` 保持完整 `YYYY-MM-DD HH:mm:ss` 用于 tooltip。
   - 重写 `formatFundingRate`：仅使用字符串移位，禁止 `*100` 浮点运算。
   - `提示标记` 列：
     - `MARGIN_PUBLIC_UNVERIFIED` 不再渲染为行内 badge；改为页面级说明。
     - `PERP_ONLY_NO_SPOT_LEG` → `无现货腿`（muted）。
     - `TRADIFI_BSTOCK` → `bStock`（accent）。
     - 未知值原样渲染（muted），枚举原值放入 `title`。
   - 数据说明区：
     - 标题改为 `数据说明`，样式改为中性信息样式。
     - 固定展示三条中文说明，与 API `warnings` 数组顺序一一对应。
     - API 英文原文放入 `<details>` 折叠。
     - 页面级说明：`杠杆可借性未经私有验证（当前为公开数据阶段）`。
   - 空状态、无匹配状态的 `colspan` 由 8 改为 7。
   - 暴露 `globalThis.__appHelpers` 供 `self-check.js` 调用格式化函数。

2. **`frontend/fixture/public-market-snapshot.json`**
   - `warnings[1]` 更新为 `backend/domain/snapshot.py` 中 `CONTRACT_WARNINGS[1]` 的新文案。

3. **`frontend/self-check.js`**
   - mock 新增元素：`warnings-raw`、`warnings-raw-content`、`margin-public-note`。
   - 更新数据说明区断言（中文内容、页面级说明、英文原文折叠）。
   - 时间断言改为校验 `HH:mm` 格式。
   - 列名断言改为校验新列名，并拒绝旧列名残留。
   - 新增资金费率格式化 7 个必测样例断言。
   - 新增中文说明条目数 === `fixture.warnings.length` 断言。
   - 新增 `MARGIN_PUBLIC_UNVERIFIED` 无行内 badge、枚举原值进 `title` 断言。

## 格式化函数实现说明

资金费率格式化仅做字符串操作，禁止浮点 `*100`：

```javascript
function formatFundingRate(str) {
  if (str === undefined || str === null || str === '') return '—';
  const m = String(str).match(/^(-?)(\d+)\.?(\d*)$/);
  if (!m) return '—';
  const [, sign, intPart, fracPart] = m;
  // 小数点右移 2 位：小数部分前 2 位并入整数，不足补 0
  const firstTwo = (fracPart + '00').slice(0, 2);
  const newIntRaw = intPart + firstTwo;
  const newInt = newIntRaw.replace(/^0+/, '') || '0';
  // 剩余小数部分裁尾零
  const remainingFrac = fracPart.slice(2).replace(/0+$/, '');
  const isZero = newInt === '0' && remainingFrac === '';
  if (isZero) return '0%';
  const value = remainingFrac ? `${newInt}.${remainingFrac}` : newInt;
  const finalSign = sign ? '-' : '+';
  return `${finalSign}${value}%`;
}
```

验证样例：

| 输入 | 输出 |
|---|---|
| `"0.00010000"` | `+0.01%` |
| `"-0.00005000"` | `-0.005%` |
| `"0.00000000"` | `0%` |
| `"-0.00000000"` | `0%` |
| `"0"` | `0%` |
| `"0.00008556"` | `+0.008556%` |
| `""` | `—` |

时间格式化：

- `next_funding_time === 0` → `—`
- 非零毫秒 → 北京时间 `HH:mm`（`formatBeijingShort`）
- tooltip 使用完整 `YYYY-MM-DD HH:mm:ss`，格式为：`北京时间 YYYY-MM-DD HH:mm:ss 结算 · 原始费率 {原始字符串} · 预估值，结算时最终确定`

## self-check 结果原文

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

全部自检通过
```

---

本地北京时间: 2026-07-04 13:22:47 CST
下一步模型: review-1（Kimi/Claude-GLM 交叉复核）
下一步任务: 按验收口径复核列合并、提示标记、数据说明区、中文化、diff 范围与 self-check
