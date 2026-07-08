# 70-handoff

## 当前状态

status=`implementing`。已创建 stage 分支与需求/设计草稿；Kimi/GLM 预实现 review 已落档并吸收；用户已裁定 METAL 借币语义；已生成 serial implementation prompt 并选择 `claude_glm` 作为实现者。

## 分支

- branch: `stage/2026-07-ui-filter-balance-metal-v1`
- base main sha: `3d3c66e64446d1285a96b4a0e0843e912e4c540e`
- current scope: implementation dispatch + public sample evidence + reports
- review absorption started from HEAD: `ad0ce29`
- implementation dispatch base HEAD: `95ed0da`

## 已完成

- 读取现有前端筛选、余额卡片、资产标签、schema enum 和契约位置。
- 创建 `00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`。
- 明确草稿假设：绝对日费率阈值、null 行不隐藏、METAL 标签、隐私遮蔽。
- Kimi Code CLI 完成需求审查，输出 `15-requirements-review.md`。
- 落档 `16-design-review.md`（design review，reviewer=glm-5.2/zhipu_glm via claude_glm，verdict=not_ready_for_implementation）：增量发现 S1（self-check 连锁失败策略，深化 Kimi Q4）、S2（纠正 Kimi Q4 文件路径）、M1（METAL 借币探测语义矛盾，Kimi 未覆盖）、M3（旧行内格式断言）；与 15 互补。
- 用户裁定：金属/贵金属产品不一定禁止借币，有些可以借币，具体以接口返回为准。
- 已更新 `00-intake.md`、`00-task.md`、`10-design.md`、`11-adr.md`、`12-development-breakdown.md`、`status.json`，吸收 Kimi Q1-Q4 与 GLM S1/S2/M1/M2/M3/L1-L3。
- 已只读采集 public sample evidence：`reports/api-samples/2026-07-ui-filter-balance-metal-v1/20260708T0928Z/`。当前 Binance futures public `exchangeInfo` 命中 `XAUUSDT/XAGUSDT/XPTUSDT/XPDUSDT/COPPERUSDT`，均为 `TRADIFI_PERPETUAL`；spot exact/B-suffix alias 查询均为 invalid symbol。
- 已生成实现任务书：`task-serial-claude-glm.prompt.md`。实现者 `claude_glm`；review-1 预选 fresh Kimi。

## 已确认决策

1. 低日费率过滤按绝对值判断，`daily_funding_rate == null` 不被该过滤器隐藏；文案为 `隐藏 |日费率| ≤ 0.03%`。
2. 新选项按 checkbox/toggle 实现，默认选中，位置在 `显示 PERP_ONLY_EXCLUDED` 后。
3. METAL 前端显示 `METAL(金属)`，覆盖 `XAU/XAG/COPPER/XPT/XPD`，避免把 `COPPER` 强称为贵金属。
4. METAL 不是禁止借币约束；满足负费率和 `MARGIN_SPOT_CANDIDATE` 时进入只读 borrow validation，最终以接口返回为准，不新增 `DISABLED_METAL`。
5. 余额数量仅整数部分加千分位，小数部分保持原始字符串；现货主数量行展示 `free`，`locked` 单独显示 `冻结:`。
6. 低费率边界样本使用独立/deep-copy self-check 场景，不破坏默认 6 行基线。

## 阻塞 / 待确认

无产品阻塞。正在进入交付代码实现。

## 下一步

执行 `task-serial-claude-glm.prompt.md`。实现完成后 bookkeeper 检查 diff、复跑 `python3 -m pytest backend/tests -q` 与 `node frontend/self-check.js`、提交实现、计算标准 fingerprint、运行 `scripts/validate-stage.py 2026-07-ui-filter-balance-metal-v1 --phase pre-review`，然后派发 Kimi review-1。

本地北京时间: 2026-07-08 09:38:08 CST
下一步模型: claude_glm
下一步任务: 执行 serial implementation prompt，完成代码与 `20-implementation.md`。
