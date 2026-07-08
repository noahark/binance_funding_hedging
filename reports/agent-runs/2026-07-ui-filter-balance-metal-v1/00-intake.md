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

1. 费率阈值默认按绝对日费率判断：`abs(Decimal(daily_funding_rate)) <= 0.00030000`，UI 文案明确为 `|日费率| <= 0.03%`。
2. `daily_funding_rate == null` 不由该阈值过滤隐藏，仍只受其它筛选控制。
3. 用户说的「单选选项」按现有 UI 风格实现为 boolean checkbox/toggle，因为该功能只有开/关两态。
4. 余额卡片中数量保留原始精度并加千分位，不四舍五入；折算值 `value_usdt` 保持 2 位 ROUND_HALF_UP，前缀为 `≈ `。
5. 隐私隐藏态继续默认启用：数量与折算值均遮蔽为 `****`。
6. 用户原始口径为「贵金属」，但因 `COPPER` 属于工业金属，本阶段契约命名收口为 `asset_tag=METAL`，前端显示 `METAL(金属)`；`asset_tag_source` 使用 `base_asset_metal_symbol`。
7. `METAL` 只是资产性质标签，不代表禁止借币。金属产品是否可借以私有只读接口返回为准；满足负费率与候选路由时应进入 borrow validation，而不是新增 `DISABLED_METAL`。

## 当前状态

本文件记录需求 intake 与已确认裁定。实现需按 `00-task.md` / `10-design.md` / `12-development-breakdown.md` 的当前口径执行。

本地北京时间: 2026-07-08 09:28:44 CST
下一步模型: codex
下一步任务: 按已确认需求生成实现任务书并进入 serial implementation。
