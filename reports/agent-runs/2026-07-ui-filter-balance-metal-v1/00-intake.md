# 00-intake：2026-07-ui-filter-balance-metal-v1

## 用户原始需求

用户要求创建需求草稿和 stage，包含三项：

1. UI 在「显示 PERP_ONLY_EXCLUDED」后面增加一个默认选中的单选/选项，用于隐藏 `0.03%` 及以下日费率的展示。
2. 账户余额资产展示格式由当前类似：
   ```text
   PEPE
   0.02【: 0.00 USDT】
   ```
   改为：
   ```text
   USDT
   100.0861659
   ≈ 100.09 USDT
   ```
3. 资产标签新增「贵金属」，标记 `XAU`、`XAG`、`COPPER`、`XPT`、`XPD` 等现实金属产品性质的资产。

## 初步归类

- complexity: `MEDIUM`
- mode: `serial`
- reason: 同时触及前端筛选/账户显示、后端资产标签、schema enum、契约文档、fixture/self-check/backend tests。改动不大，但有跨层契约面，不能只改 UI。

## 待用户确认的草稿假设

1. 费率阈值默认按绝对日费率判断：`abs(Decimal(daily_funding_rate)) <= 0.00030000`，即 UI 显示 `0.03%` 及以下。
2. `daily_funding_rate == null` 不由该阈值过滤隐藏，仍只受其它筛选控制。
3. 用户说的「单选选项」按现有 UI 风格实现为 boolean checkbox/toggle，因为该功能只有开/关两态。
4. 余额卡片中数量保留原始精度并加千分位，不四舍五入；折算值 `value_usdt` 保持 2 位 ROUND_HALF_UP，前缀为 `≈ `。
5. 隐私隐藏态继续默认启用：数量与折算值均遮蔽为 `****`。
6. 贵金属标签命名初稿为 `METAL`，前端中文显示为 `METAL(贵金属)`；`asset_tag_source` 使用 `base_asset_precious_metal_symbol`。

## 当前状态

本文件是需求 intake + 草稿阶段，不授权实现。开发需等用户确认或修改 `00-task.md` / `10-design.md` 后再开始。

本地北京时间: 2026-07-08 02:23:15 CST
下一步模型: human
下一步任务: 审阅并确认需求草稿，尤其是阈值语义、null 行处理、贵金属标签命名。
