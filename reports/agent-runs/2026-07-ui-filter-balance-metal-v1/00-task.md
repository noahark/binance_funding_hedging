# 00-task：需求草稿 — 2026-07-ui-filter-balance-metal-v1

## 目标

在现有公开行情 + 私有账户只读 UI 上做三项小型产品增强：

1. 市场表默认隐藏低日费率行，减少低价值机会噪音。
2. 私有账户余额卡片改成更清晰的三行展示：资产、数量、折算 USDT。
3. 后端与前端新增金属资产标签，使 `XAU`、`XAG`、`COPPER`、`XPT`、`XPD` 等现实金属产品不再混入 `CRYPTO`。

## 用户可见需求

### R1 低日费率默认隐藏

- 在市场表筛选区「显示 PERP_ONLY_EXCLUDED」之后新增选项：
  - 文案：`隐藏 |日费率| ≤ 0.03%`
  - 默认选中。
- 选中时隐藏满足以下条件的行：
  - `daily_funding_rate` 可解析为 Decimal；
  - `abs(daily_funding_rate) <= 0.00030000`。
- 取消选中后恢复显示这些低日费率行。
- 与现有筛选组合生效：搜索、资产标签、路由分类、显示 PERP_ONLY_EXCLUDED、低日费率隐藏共同取交集。
- 草稿默认：`daily_funding_rate == null` 不因该选项隐藏。

### R2 账户余额卡片格式

将统一账户余额和现货账户余额的每个资产卡片从行内折算：

```text
PEPE
0.02【: 0.00 USDT】
```

改为三行式：

```text
USDT
100.0861659
≈ 100.09 USDT
```

细则草稿：

- 数量行：展示原始数量字符串的可读格式；仅整数部分加千分位，小数部分保持原始字符串，不四舍五入、不裁剪尾零、不压缩为 2 位。
- 折算行：`≈ ${formatUsdt2(value_usdt)} USDT`。
- `value_usdt == null`：显示 `≈ — USDT`。
- `value_usdt == "0.00000000"`：显示 `≈ 0.00 USDT`。
- 隐私隐藏态：
  ```text
  USDT
  ****
  ≈ **** USDT
  ```
- 现货余额如有 locked/free 区分，保留 `冻结: ...` 信息，但折算行单独显示，不再塞进数量行。

### R3 金属资产标签

新增 `asset_tag = "METAL"`：

- 初始识别集合：`XAU`、`XAG`、`COPPER`、`XPT`、`XPD`。
- 匹配对象：`base_asset`。
- 前端中文显示：`METAL(金属)`。用户原始口径可称贵金属，但本集合包含 `COPPER`，所以契约显示不使用纯「贵金属」。
- `asset_tag_source`：`base_asset_metal_symbol`。
- 合约仍可保留原有 `route_class` 计算；资产标签改变 `asset_tag`、summary、筛选、徽章和契约 enum。
- `negative_funding_status` 优先级草稿：
  1. `PERP_ONLY_EXCLUDED` → `DISABLED_PERP_ONLY`
  2. `asset_tag == BSTOCK` → `DISABLED_BSTOCK`
  3. `SPOT_ONLY_CANDIDATE` → `DISABLED_SPOT_ONLY`
  4. 其它 → `PRIVATE_BORROW_VALIDATION_REQUIRED`
- 用户确认：`METAL` 不新增专门禁用态，也不等同于 bStock 禁用。金属是否可借、可借数量和借币成本以私有只读接口返回为准。
- 实现要求：若金属行是 `MARGIN_SPOT_CANDIDATE` 且 `daily_funding_rate < 0`，应与 `CRYPTO` 一样进入 borrow validation 候选集；不得因 `asset_tag=METAL` 跳过探测。
- 若接口返回不可借、未配置私有 API、预算外未探测或请求失败，沿用既有 `borrow_validation` / `borrowability_not_probed` / 错误展示契约，不新增 `DISABLED_METAL`。

## 非目标

- 不改变后端排序基准。
- 不改变借币利率链、私有 API、下单/借还/划转能力。
- 不引入用户自定义阈值输入；本阶段阈值固定为 `0.03%`。
- 不保存低日费率过滤偏好到 localStorage；默认每次加载选中。
- 不做新的实盘交易行为；如需验证金属样本，只读读取公开行情即可。

## 文件边界草稿

允许修改：

- `backend/domain/normalize.py`
- `backend/domain/snapshot.py`（传入 `baseAsset` 给 `asset_tag_for`；将 METAL 纳入只读 borrow validation 候选；不改资金费率计算）
- `backend/tests/test_normalize.py`
- `backend/tests/test_snapshot.py`
- `backend/tests/test_private_account_v1.py`（若 fixture/schema 回归需要）
- `backend/tests/fixtures/private-account-v1-design.json`（self-check 专用 fixture；不得破坏默认 6 行基线）
- `schemas/api/public-market/snapshot.schema.json`
- `docs/api/public-market-contract.md`
- `frontend/index.html`
- `frontend/self-check.js`
- `frontend/fixture/public-market-snapshot.json`
- `reports/api-samples/2026-07-ui-filter-balance-metal-v1/`（若实现期能只读采集到金属公开样本）

禁止修改：

- 私有签名通道、白名单、下单/借还/划转逻辑。
- `backend/services/private_client.py`，除非实现中发现测试 fixture 需要但应先升级。
- unrelated stage reports / historical evidence。

## 验收标准草稿

1. 默认 UI 打开时，低日费率过滤选项已选中，`abs(daily_funding_rate)<=0.0003` 行被隐藏。
2. 取消该选项后，被隐藏行恢复。
3. `PERP_ONLY_EXCLUDED` 显示选项仍保持原行为，新增选项位于其后。
4. 余额卡片显示为资产、数量、`≈ value USDT` 三行；隐私隐藏态遮蔽数量和折算值。
5. `value_usdt=null` 和 `value_usdt=0` 的显示分别为 `≈ — USDT`、`≈ 0.00 USDT`。
6. `XAU/XAG/COPPER/XPT/XPD` 被标记为 `METAL`，schema、contract、summary、UI 筛选与徽章同步，前端显示 `METAL(金属)`。
7. `METAL` 负费率候选不被禁用；满足 `MARGIN_SPOT_CANDIDATE` 时进入只读 borrow validation，最终是否可借以接口返回为准。
8. 现有 `BSTOCK`、`CRYPTO`、`UNKNOWN` 行不回归；bStock 仍禁用，不进入借币套利。
9. self-check 覆盖低日费率边界 `0.00030000`、`-0.00030000`、`0.00030001`，且不破坏默认 6 行基线。
10. `python3 -m pytest backend/tests -q` 通过。
11. `node frontend/self-check.js` 通过。

本地北京时间: 2026-07-08 09:28:44 CST
下一步模型: codex
下一步任务: 生成实现任务书并进入 serial implementation。
