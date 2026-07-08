# 15-requirements-review：2026-07-ui-filter-balance-metal-v1

## 审查模型

- **Reviewer**: Kimi Code CLI
- **Provider/Model 标识**: kimi / kimi-code/kimi-for-coding
- **Session Role**: 预实现需求/设计审查（非正式 review-1 代码审查）
- **审查对象**:
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-intake.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/00-task.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/10-design.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/11-adr.md`
  - `reports/agent-runs/2026-07-ui-filter-balance-metal-v1/12-development-breakdown.md`

## 审查结论

**状态：REWORK（需求澄清后可通过）**

需求范围、文件边界、验收标准整体清晰，具备 MEDIUM 阶段的可实现性。但实现前建议先澄清 4 处语义细节，否则容易产生边界分歧或用户验收争议。

## 发现的问题与澄清建议

### Q1. 低日费率文案与绝对值语义不一致

- **当前文案草稿**：`隐藏 ≤0.03% 日费率`
- **当前实现规则**：`abs(daily_funding_rate) <= 0.00030000`

**问题**："≤0.03%" 在字面上包含 -0.04%、-0.05% 等更负的费率，但实际规则只按绝对值过滤。用户看到文案后可能对负费率行的显示行为产生错误预期。

**建议**：文案改为明确表达绝对值，例如：
- `隐藏 |日费率| ≤ 0.03%`
- `隐藏 ±0.03% 及以下日费率`
- `隐藏绝对值 ≤ 0.03% 的日费率`

### Q2. "贵金属"中文命名与 COPPER 的分类冲突

用户列出的集合包含 `COPPER`（铜），但铜严格来说不属于贵金属。

**问题**：当前设计使用 `METAL(贵金属)`，如果包含 COPPER，存在产品语义错误。

**建议**：确认以下选项之一：
1. 仅保留 `XAU/XAG/XPT/XPD`，中文用 `METAL(贵金属)`；
2. 保留 COPPER，中文改为 `METAL(金属)` 或 `METAL(贵金属/工业金属)`；
3. 拆分为 `PRECIOUS_METAL` 与 `BASE_METAL`，但会扩大本阶段范围。

### Q3. 余额数量千分位规则未细化

设计说"保留原始精度，加千分位"，但未明确：
- 千分位是否只作用于整数部分？
- 小数部分是否保留原始字符串（含末尾零）？
- 是否处理科学计数法或异常长小数？

**建议**：在 `00-task.md` 或 `10-design.md` 中明确为：
> 仅对整数部分加千分位，小数部分保持原始字符串不变；不四舍五入、不截断末尾零。

例如：`1234.56789000` → `1,234.56789000`。

### Q4. 默认过滤开启的 fixture/self-check 覆盖不足

新增选项默认选中，会改变首屏可见行数。

**问题**：若现有 fixture 中没有 `daily_funding_rate` 为 `0.00030000` 及以下的行，验收标准第 1 条"默认隐藏"无法被 self-check 验证。

**建议**：
1. 在 `frontend/fixture/public-market-snapshot.json` 中显式增加边界行：
   - `daily_funding_rate="0.00030000"` → 默认隐藏
   - `daily_funding_rate="-0.00030000"` → 默认隐藏
   - `daily_funding_rate="0.00030001"` → 默认显示
2. 在 `frontend/self-check.js` 中断言"默认可见行数"与"取消勾选后可见行数"的差值，而不是仅断言某一行存在。

## 肯定的方面

1. **范围边界清晰**：允许/禁止修改的文件列表明确，未侵入私有签名、下单、借还、划转逻辑。
2. **技术决策合理**：
   - 使用字符串 Decimal helper 避免 float 阈值漂移（ADR-2、breakdown）。
   - 余额展示拆成三行，数量与折算值分离（ADR-3）。
   - METAL 初版不新增禁用态，降低范围蔓延风险（ADR-4）。
3. **验收标准可验证**：9 条验收标准覆盖 UI 行为、隐私态、schema、契约文档、前后端测试。
4. **风险披露充分**：COPPER baseAsset 命名风险、负费率禁用态范围外、fixture 行数变化风险均已记录。

## 建议修改清单

- [ ] `00-task.md` R1：更新低日费率隐藏选项文案，明确绝对值语义。
- [ ] `00-task.md` R3 / `10-design.md` 第 3 节：确认 METAL 中文命名，处理 COPPER 分类。
- [ ] `10-design.md` 第 2 节：细化余额数量千分位规则。
- [ ] `10-design.md` 第 1 节 / `frontend/fixture/public-market-snapshot.json`：增加低日费率边界样本行。
- [ ] `frontend/self-check.js`：增加默认过滤开启后的行数差值断言。
- [ ] 澄清后更新 `00-task.md`、`10-design.md`、`11-adr.md`（如文案/命名变更）。

## 审查者声明

- 本审查未修改任何交付代码，仅审查需求与设计草稿。
- 本审查者与当前阶段实现者无身份重叠（当前尚未指定实现者）。
- 本审查者与该阶段的设计者/breakdown author（codex_current_session）分属不同 provider（kimi vs openai），符合跨 provider 审查隔离。

本地北京时间: 2026-07-08 08:56:51 CST
下一步模型: gpt / codex（由用户指定复阅）
下一步任务: 根据 GPT/用户反馈澄清 Q1-Q4，然后更新需求/设计草稿并进入 serial implementation。
